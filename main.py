"""Dynamic Island untuk Windows — titik masuk aplikasi."""
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from PySide6.QtCore import QLockFile, Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

import config
import tools
from island import Island
from media import MediaHub
from server import NotifyHub
from sensors import SensorHub
from store import Notes
from winnotif import WinNotifHub

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


HERE = Path(__file__).resolve().parent
ICON_FILE = HERE / "icon.ico"
TASK_NAME = "DynamicIsland"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def make_icon() -> QIcon:
    if ICON_FILE.exists():
        return QIcon(str(ICON_FILE))
    pix = QPixmap(64, 64)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#050506"))
    p.drawRoundedRect(2, 14, 60, 36, 18, 18)
    p.setBrush(QColor("#FFFFFF"))
    p.drawEllipse(17, 25, 13, 14)
    p.drawEllipse(34, 25, 13, 14)
    p.end()
    return QIcon(pix)


def _pythonw() -> str:
    exe = sys.executable
    pyw = exe.replace("python.exe", "pythonw.exe")
    return pyw if os.path.exists(pyw) else exe


def _q(s: str) -> str:  # escape tanda petik tunggal untuk PowerShell
    return s.replace("'", "''")


def _ps(cmd: str, timeout: int = 40):
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-Command", cmd],
        creationflags=NO_WINDOW, timeout=timeout, capture_output=True,
    )


# ---------- hak Administrator ----------

def is_admin() -> bool:
    if os.name != "nt":
        return False
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def want_admin(cfg: dict) -> bool:
    mode = cfg.get("run_as_admin", "auto")
    if mode is True or str(mode).lower() == "true":
        return True
    if mode is False or str(mode).lower() == "false":
        return False
    # auto: perlu bila FPS (PresentMon) atau suhu CPU (LibreHardwareMonitor) bisa dipakai
    return bool(cfg.get("presentmon_path")) or bool(cfg.get("lhm_autostart", True) and (cfg.get("lhm_path") or tools.find_lhm()))


def relaunch_as_admin() -> bool:
    """Buka ulang dirinya dengan hak Administrator (muncul satu kali jendela izin Windows)."""
    try:
        import ctypes
        r = ctypes.windll.shell32.ShellExecuteW(None, "runas", _pythonw(), f'"{HERE / "main.py"}" --no-elevate', str(HERE), 1)
        return r > 32
    except Exception:
        return False


# ---------- mulai bersama Windows ----------

def _run_key(on: bool):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, config.APP_NAME, 0, winreg.REG_SZ, f'"{_pythonw()}" "{HERE / "main.py"}"')
        else:
            winreg.DeleteValue(k, config.APP_NAME)


def autostart_enabled() -> bool:
    if os.name != "nt":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, config.APP_NAME)
            return True
    except Exception:
        pass
    try:
        r = subprocess.run(["schtasks", "/Query", "/TN", TASK_NAME], creationflags=NO_WINDOW,
                           capture_output=True, timeout=15)
        return r.returncode == 0
    except Exception:
        return False


def task_script() -> str:
    """Tugas terjadwal saat masuk Windows, level tertinggi (tanpa jendela izin), jalan juga saat memakai baterai."""
    return (
        f"$a=New-ScheduledTaskAction -Execute '{_q(_pythonw())}' "
        f"-Argument '\"{_q(str(HERE / 'main.py'))}\" --no-elevate' -WorkingDirectory '{_q(str(HERE))}';"
        "$t=New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME;$t.Delay='PT10S';"
        "$p=New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest;"
        "$s=New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries "
        "-ExecutionTimeLimit ([TimeSpan]::Zero);"
        f"Register-ScheduledTask -TaskName '{TASK_NAME}' -Action $a -Trigger $t -Principal $p -Settings $s -Force | Out-Null"
    )


def set_autostart(on: bool) -> bool:
    if os.name != "nt":
        return False
    ok = True
    try:
        try:
            _run_key(False)  # bersihkan cara lama; cukup satu cara aktif
        except Exception:
            pass
        if on:
            if is_admin():
                r = _ps(task_script())
                ok = r.returncode == 0
            else:
                ok = False
            if not ok:  # tanpa hak admin: pakai cara biasa (FPS tidak aktif saat dimulai begini)
                _run_key(True)
                ok = True
        else:
            if is_admin():
                _ps(f"Unregister-ScheduledTask -TaskName '{TASK_NAME}' -Confirm:$false -ErrorAction SilentlyContinue")
    except Exception:
        ok = False
    return ok


# ---------- pintasan (Desktop + menu Start) dengan ikon sendiri ----------

def shortcut_script() -> str:
    icon = str(ICON_FILE) if ICON_FILE.exists() else _pythonw()
    return (
        "$w=New-Object -ComObject WScript.Shell;"
        "foreach($d in @([Environment]::GetFolderPath('Desktop'),[Environment]::GetFolderPath('Programs'))){"
        "$s=$w.CreateShortcut((Join-Path $d 'Dynamic Island.lnk'));"
        f"$s.TargetPath='{_q(_pythonw())}';$s.Arguments='\"{_q(str(HERE / 'main.py'))}\"';"
        f"$s.WorkingDirectory='{_q(str(HERE))}';$s.IconLocation='{_q(icon)},0';"
        "$s.Description='Dynamic Island';$s.Save()}"
    )


def create_desktop_shortcut() -> bool:
    if os.name != "nt":
        return False
    try:
        return _ps(shortcut_script(), 30).returncode == 0
    except Exception:
        return False


def main():
    cfg = config.load()
    # cari PresentMon sendiri bila path belum diisi, jadi tidak perlu mengatur ulang
    if os.name == "nt" and not cfg.get("presentmon_path"):
        cfg["presentmon_path"] = tools.find_presentmon()

    # FPS (PresentMon) butuh Administrator: minta izin sekali saat dibuka, lalu lanjut di proses baru
    if os.name == "nt" and "--no-elevate" not in sys.argv and want_admin(cfg) and not is_admin():
        if relaunch_as_admin():
            sys.exit(0)

    app = QApplication(sys.argv)
    # hanya satu island yang boleh berjalan; klik ganda tidak membuat salinan baru
    lock = QLockFile(os.path.join(tempfile.gettempdir(), "dynamic_island.lock"))
    if not lock.tryLock(100):
        sys.exit(0)
    app.setApplicationName(config.APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    app.setWindowIcon(make_icon())

    # suhu CPU: jalankan LibreHardwareMonitor otomatis (hanya mungkin jika island berjalan sebagai Administrator)
    lhm_proc = None
    need_driver = False
    if os.name == "nt" and cfg.get("lhm_autostart", True) and is_admin() and not tools.lhm_running():
        lhm_path = cfg.get("lhm_path") or tools.find_lhm()
        if lhm_path:
            # perangkat baru: driver PawnIO belum ada, jadi tampilkan jendelanya agar pertanyaan pemasangan terlihat
            need_driver = not tools.pawnio_installed()
            lhm_proc = tools.start_lhm(lhm_path, hidden=not need_driver)
    app.aboutToQuit.connect(lambda: tools.stop(lhm_proc))

    island = Island(cfg, Notes())

    sensors = SensorHub(cfg)
    sensors.updated.connect(island.on_stats)
    sensors.start()
    app.aboutToQuit.connect(sensors.fps.stop)

    media = MediaHub()
    media.changed.connect(island.on_media)
    island.set_media_hub(media)
    media.start()

    notify = NotifyHub(int(cfg["notify_port"]))
    notify.received.connect(island.on_notify)
    notify.start()

    winnotif = None
    if os.name == "nt" and cfg.get("win_notif", True):
        winnotif = WinNotifHub(cfg.get("win_notif_apps", ["whatsapp"]), cfg.get("win_notif_show_body", True))
        winnotif.received.connect(island.on_notify)
        winnotif.start()

    tray = QSystemTrayIcon(make_icon(), app)
    tray.setToolTip("Dynamic Island")
    menu = QMenu()
    act_toggle = QAction("Tampilkan / sembunyikan", menu)
    act_toggle.triggered.connect(lambda: island.setVisible(not island.isVisible()))
    act_auto = QAction("Mulai bersama Windows", menu, checkable=True)
    act_auto.setChecked(autostart_enabled())

    def _toggle_auto(on):
        ok = set_autostart(on)
        if on and ok and not is_admin():
            note = "Aktif. Catatan: tanpa Administrator, FPS tidak ikut menyala saat dimulai."
        else:
            note = ("Aktif." if on else "Dimatikan.") if ok else "Gagal mengubah pengaturan."
        tray.showMessage("Dynamic Island", note, QSystemTrayIcon.MessageIcon.Information, 3500)

    act_auto.toggled.connect(_toggle_auto)
    act_shortcut = QAction("Buat pintasan (Desktop dan menu Start)", menu)

    def _make_shortcut():
        ok = create_desktop_shortcut()
        tray.showMessage("Dynamic Island",
                         "Pintasan dibuat di Desktop dan menu Start." if ok else "Gagal membuat pintasan.",
                         QSystemTrayIcon.MessageIcon.Information, 3000)

    act_shortcut.triggered.connect(_make_shortcut)
    act_folder = QAction("Buka folder pengaturan", menu)
    act_folder.triggered.connect(lambda: subprocess.Popen(["explorer", str(config.data_dir())]) if os.name == "nt" else None)
    act_quit = QAction("Keluar", menu)
    act_quit.triggered.connect(app.quit)
    for a in (act_toggle, act_auto, act_shortcut, act_folder):
        menu.addAction(a)
    menu.addSeparator()
    menu.addAction(act_quit)
    tray.setContextMenu(menu)
    tray.show()

    # pertama kali (atau setelah folder diunduh ulang): buat pintasan dengan ikon sendiri secara otomatis
    if os.name == "nt" and not cfg.get("shortcut_done"):
        def _first_shortcut():
            if create_desktop_shortcut():
                config.update("shortcut_done", True)
        threading.Thread(target=_first_shortcut, daemon=True).start()

    island.show()
    if need_driver and lhm_proc is not None:
        tray.showMessage("Dynamic Island",
                         "Suhu CPU: setujui pemasangan driver PawnIO di jendela yang muncul (cukup sekali).",
                         QSystemTrayIcon.MessageIcon.Information, 8000)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
