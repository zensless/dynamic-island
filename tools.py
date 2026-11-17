"""Mencari dan menjalankan alat pendamping: LibreHardwareMonitor (suhu CPU) dan PresentMon (FPS)."""
import os
import subprocess
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent


def _roots():
    home = Path.home()
    return [
        (HERE / "tools", 2), (HERE, 2), (Path("C:/Tools"), 2), (Path("C:/tools"), 2),
        (home / "Downloads", 1), (home / "Documents", 1), (home / "Desktop", 1),
    ]


def _find(patterns, skip=()):
    seen, hits = set(), []
    for root, depth in _roots():
        try:
            if not root.is_dir():
                continue
            for pat in patterns:
                for level in range(depth + 1):
                    for hit in root.glob("*/" * level + pat):
                        key = str(hit).lower()
                        if key in seen or not hit.is_file():
                            continue
                        if any(w in hit.name.lower() for w in skip):
                            continue
                        seen.add(key)
                        hits.append(hit)
        except Exception:
            continue
    # nama terbesar (versi terbaru) lebih dulu
    hits.sort(key=lambda p: p.name.lower(), reverse=True)
    return str(hits[0]) if hits else ""


def find_lhm() -> str:
    return _find(["LibreHardwareMonitor.exe"])


def find_presentmon() -> str:
    # versi konsol saja; "capture"/"app" adalah aplikasi bergambar yang tidak cocok
    return _find(["PresentMon*.exe"], skip=("capture", "app", "service"))


def lhm_running() -> bool:
    try:
        for p in psutil.process_iter(["name"]):
            if (p.info.get("name") or "").lower() == "librehardwaremonitor.exe":
                return True
    except Exception:
        pass
    return False


def pawnio_installed() -> bool:
    """Driver PawnIO (dibutuhkan LibreHardwareMonitor untuk membaca suhu CPU) sudah terpasang?"""
    if os.name != "nt":
        return False
    try:
        import winreg
        sub = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\PawnIO"
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub, 0, winreg.KEY_READ | view):
                    return True
            except OSError:
                continue
    except Exception:
        pass
    return (Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "PawnIO").is_dir()


def ensure_lhm_config(exe: str, quiet: bool = True) -> None:
    """Pastikan Remote Web Server LibreHardwareMonitor menyala; quiet = mulai diminimalkan ke tray."""
    import xml.etree.ElementTree as ET
    cfg = Path(exe).with_suffix(".config")
    want = {"runWebServerMenuItem": "true", "listenerPort": "8085",
            "startMinMenuItem": "true" if quiet else "false",
            "minTrayMenuItem": "true" if quiet else "false",
            "minCloseMenuItem": "true" if quiet else "false"}
    try:
        if cfg.exists():
            tree = ET.parse(cfg)
            root = tree.getroot()
        else:
            root = ET.Element("configuration")
            tree = ET.ElementTree(root)
        app = root.find("appSettings")
        if app is None:
            app = ET.SubElement(root, "appSettings")
        have = {e.get("key"): e for e in app.findall("add")}
        for k, v in want.items():
            if k in have:
                have[k].set("value", v)
            else:
                ET.SubElement(app, "add", {"key": k, "value": v})
        ET.indent(tree)
        tree.write(cfg, encoding="utf-8", xml_declaration=True)
    except Exception:
        pass


def start_lhm(path: str, hidden: bool = True):
    """Jalankan LibreHardwareMonitor (diminimalkan bila hidden). Butuh hak Administrator."""
    if os.name != "nt" or not path or not os.path.exists(path):
        return None
    try:
        ensure_lhm_config(path, quiet=hidden)
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 6 if hidden else 1  # SW_MINIMIZE / SW_SHOWNORMAL
        return subprocess.Popen([path], cwd=os.path.dirname(path), startupinfo=si)
    except Exception:
        return None


def stop(proc) -> None:
    try:
        if proc and proc.poll() is None:
            proc.terminate()
    except Exception:
        pass
