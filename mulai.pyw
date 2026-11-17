"""Klik dua kali berkas ini untuk menjalankan Dynamic Island tanpa jendela terminal."""
import os
import subprocess
import sys

here = os.path.dirname(os.path.abspath(__file__))
pyw = os.path.join(here, ".venv", "Scripts", "pythonw.exe")

if not os.path.exists(pyw):
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            0,
            "Folder .venv belum ada. Siapkan dulu lingkungannya (lihat README), lalu coba lagi.",
            "Dynamic Island",
            0x10,
        )
    except Exception:
        pass
    sys.exit(1)

subprocess.Popen([pyw, os.path.join(here, "main.py")], cwd=here)
