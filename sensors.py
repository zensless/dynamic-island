"""Pembaca sensor: CPU/RAM (psutil), GPU/VRAM/suhu GPU (NVML), suhu CPU (LibreHardwareMonitor), FPS (PresentMon)."""
from __future__ import annotations

import csv
import json
import re
import subprocess
import threading
import time
import urllib.request
from collections import defaultdict, deque
from pathlib import Path

import psutil
from PySide6.QtCore import QObject, Signal

try:
    import pynvml  # paket: nvidia-ml-py
except Exception:  # pragma: no cover
    pynvml = None

_NUM = re.compile(r"-?\d+(?:[.,]\d+)?")


def _num(s):
    m = _NUM.search(s or "")
    return float(m.group().replace(",", ".")) if m else None


class GpuReader:
    """GPU NVIDIA lewat NVML. GPU AMD/Intel tidak didukung (nilai None)."""

    def __init__(self):
        self.h = None
        if pynvml:
            try:
                pynvml.nvmlInit()
                self.h = pynvml.nvmlDeviceGetHandleByIndex(0)
            except Exception:
                self.h = None

    def read(self):
        if not self.h:
            return None, None, None
        try:
            util = float(pynvml.nvmlDeviceGetUtilizationRates(self.h).gpu)
            mem = pynvml.nvmlDeviceGetMemoryInfo(self.h)
            vram = mem.used * 100.0 / mem.total
            temp = float(pynvml.nvmlDeviceGetTemperature(self.h, pynvml.NVML_TEMPERATURE_GPU))
            return util, vram, temp
        except Exception:
            return None, None, None


class LhmReader:
    """Suhu CPU dari Remote Web Server LibreHardwareMonitor."""

    def __init__(self, url: str):
        self.url = url
        self._last = 0.0
        self.cpu_temp = None

    def poll(self):
        now = time.time()
        if now - self._last < 2.0:
            return self.cpu_temp
        self._last = now
        try:
            with urllib.request.urlopen(self.url, timeout=0.4) as r:
                tree = json.loads(r.read().decode("utf-8"))
        except Exception:
            self.cpu_temp = None
            return None

        temps = []

        def walk(node, in_cpu, in_temp):
            text = node.get("Text", "") or ""
            icon = (node.get("ImageURL") or "").lower()
            is_cpu = in_cpu or "cpu" in icon
            is_temp = in_temp or "temperature" in text.lower()
            val = node.get("Value", "") or ""
            if is_cpu and is_temp and "°C" in val:
                n = _num(val)
                if n is not None:
                    temps.append((text.lower(), n))
            for ch in node.get("Children", []) or []:
                walk(ch, is_cpu, is_temp)

        walk(tree, False, False)
        value = None
        for key in ("package", "tdie", "tctl", "cpu"):
            for name, n in temps:
                if key in name:
                    value = n
                    break
            if value is not None:
                break
        if value is None and temps:
            value = max(n for _, n in temps)
        self.cpu_temp = value
        return value


_IGNORE = {
    "dwm.exe", "explorer.exe", "searchhost.exe", "shellexperiencehost.exe",
    "textinputhost.exe", "startmenuexperiencehost.exe", "python.exe", "pythonw.exe",
}


class FpsMonitor:
    """FPS dari keluaran CSV PresentMon (opsional)."""

    def __init__(self, path: str, args: list):
        self.path = path or ""
        self.args = args
        self.fps = None
        self.ms = None
        self._frames = defaultdict(deque)
        self._seen = {}
        self._last_frame = 0.0
        self._last_calc = 0.0
        self.proc = None
        self.status = "unset"  # unset | missing | starting | running | exited | error
        self.error = ""
        if self.path:
            if Path(self.path).exists():
                self.status = "starting"
                threading.Thread(target=self._run, daemon=True).start()
            else:
                self.status = "missing"

    def stop(self):
        """Hentikan PresentMon saat island keluar supaya tidak tersisa di latar belakang."""
        try:
            if self.proc and self.proc.poll() is None:
                self.proc.terminate()
        except Exception:
            pass

    @property
    def enabled(self) -> bool:
        return bool(self.path)

    def _log(self, text):
        """Catatan diagnosis di %APPDATA%\\DynamicIsland\\fps_debug.log (hanya awal sesi)."""
        try:
            from config import data_dir
            with open(data_dir() / "fps_debug.log", "a", encoding="utf-8") as f:
                f.write(text + "\n")
        except Exception:
            pass

    def _run(self):
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            from config import data_dir
            (data_dir() / "fps_debug.log").write_text("", encoding="utf-8")
        except Exception:
            pass
        self._log("perintah: " + " ".join([self.path, *self.args]))
        try:
            proc = subprocess.Popen(
                [self.path, *self.args],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, bufsize=1, creationflags=flags,
            )
        except Exception as e:
            self.status, self.error = "error", repr(e)[:80]
            self._log("gagal start: " + repr(e))
            return
        self.proc = proc
        self.status = "running"

        def drain_err():
            n = 0
            for ln in proc.stderr:
                n += 1
                if n <= 20:
                    self._log("stderr: " + ln.rstrip())
        threading.Thread(target=drain_err, daemon=True).start()

        app_i = ms_i = t_i = None
        n_lines = 0
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            n_lines += 1
            if n_lines <= 6:
                self._log("stdout: " + line[:300])
            try:
                parts = next(csv.reader([line]))
            except Exception:
                continue
            if app_i is None:
                low = [x.strip().lower() for x in parts]
                col = next((c for c in ("frametime", "msbetweenpresents", "msbetweendisplaychange") if c in low), None)
                if "application" in low and col:
                    app_i, ms_i = low.index("application"), low.index(col)
                    t_i = low.index("timeinms") if "timeinms" in low else None
                    self._log(f"kolom ditemukan: Application={app_i}, {col}={ms_i}")
                continue
            try:
                app = parts[app_i].lower()
                ms = float(parts[ms_i])
            except Exception:
                continue
            if app_i is not None and n_lines == 7:
                self._log("contoh aplikasi terdeteksi: " + app)
            if app in _IGNORE or ms <= 0:
                continue
            now = time.time()
            t = now * 1000.0
            if t_i is not None:
                try:
                    t = float(parts[t_i])
                except Exception:
                    continue
            self._frames[app].append((t, ms))
            self._seen[app] = now
            self._last_frame = now
            if now - self._last_calc >= 0.25:
                self._last_calc = now
                self._recalc(now)
        # PresentMon berhenti sendiri (biasanya karena bukan Administrator atau argumen tidak cocok)
        self.status = "exited"
        self._log(f"PresentMon berhenti; kode keluar {proc.poll()}; baris stdout total {n_lines}")
        try:
            self.error = ""
        except Exception:
            pass

    def _recalc(self, now):
        """FPS dari stempel waktu frame di CSV (bukan waktu tiba), jadi tidak goyah saat data datang berkelompok."""
        best, best_n = None, 0
        for app, dq in list(self._frames.items()):
            if now - self._seen.get(app, 0) > 2.0:
                dq.clear()  # aplikasi ini sudah berhenti mengirim frame
                continue
            while dq and dq[-1][0] - dq[0][0] > 1000.0:
                dq.popleft()
            if len(dq) > best_n:
                best, best_n = app, len(dq)
        if not best or best_n < 2:
            return  # pertahankan nilai terakhir; current() yang memutuskan kapan dianggap hilang
        dq = self._frames[best]
        span = dq[-1][0] - dq[0][0]
        if span <= 0:
            return
        fps = (len(dq) - 1) * 1000.0 / span
        ms = sum(m for _, m in dq) / len(dq)
        # haluskan sedikit supaya angka tidak meloncat
        self.fps = fps if self.fps is None else self.fps * 0.5 + fps * 0.5
        self.ms = ms

    def current(self):
        if time.time() - self._last_frame > 3.0:
            self.fps = self.ms = None
            return None, None
        return self.fps, self.ms


class SensorHub(QObject):
    updated = Signal(dict)

    def __init__(self, cfg: dict):
        super().__init__()
        self.gpu = GpuReader()
        self.lhm = LhmReader(cfg["lhm_url"])
        self.fps = FpsMonitor(cfg["presentmon_path"], cfg["presentmon_args"])

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        psutil.cpu_percent(None)
        while True:
            time.sleep(1.0)
            g, v, gt = self.gpu.read()
            fps, ms = self.fps.current()
            self.updated.emit({
                "cpu": psutil.cpu_percent(None),
                "ram": psutil.virtual_memory().percent,
                "gpu": g,
                "vram": v,
                "cpu_temp": self.lhm.poll(),
                "gpu_temp": gt,
                "fps": fps,
                "frame_ms": ms,
                "fps_enabled": self.fps.enabled,
                "fps_status": self.fps.status,
                "fps_error": self.fps.error,
            })
