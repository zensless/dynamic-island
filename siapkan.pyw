"""Klik dua kali untuk menyiapkan Dynamic Island, lalu menjalankannya. Tanpa PowerShell.

Langkah: membuat folder .venv, memasang paket dari requirements.txt, lalu membuka aplikasi.
Butuh Python 3.10+ (dari python.org) dan koneksi internet. Aman dijalankan ulang.
"""
import os
import queue
import subprocess
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def venv_python(here, windowed=False):
    if os.name == "nt":
        return os.path.join(here, ".venv", "Scripts", "pythonw.exe" if windowed else "python.exe")
    return os.path.join(here, ".venv", "bin", "python")


def base_python():
    """python.exe (bukan pythonw.exe) dari instalasi yang sedang dipakai."""
    cand = os.path.join(os.path.dirname(sys.executable), "python.exe")
    return cand if os.path.exists(cand) else sys.executable


def run(cmd, log, cwd):
    log("> " + " ".join(cmd))
    p = subprocess.Popen(
        cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW,
    )
    for line in p.stdout:
        log(line.rstrip())
    return p.wait()


def setup(here, log, launch=True):
    if sys.version_info < (3, 10):
        log("Python terlalu lama; butuh 3.10 atau lebih baru.")
        return False
    vpy = venv_python(here)
    if not os.path.exists(vpy):
        log("Membuat lingkungan Python (.venv)...")
        rc = run([base_python(), "-m", "venv", os.path.join(here, ".venv")], log, here)
        if rc != 0 or not os.path.exists(vpy):
            log("Gagal membuat .venv.")
            return False
    log("Memasang paket (butuh internet, beberapa menit)...")
    run([vpy, "-m", "pip", "install", "--upgrade", "pip"], log, here)
    if run([vpy, "-m", "pip", "install", "-r", os.path.join(here, "requirements.txt")], log, here) != 0:
        log("Gagal memasang paket. Periksa koneksi internet lalu jalankan ulang berkas ini.")
        return False
    log("Selesai. Membuka Dynamic Island...")
    if launch:
        subprocess.Popen([venv_python(here, True), os.path.join(here, "main.py")], cwd=here)
    return True


def main():
    try:
        import tkinter as tk
        from tkinter import ttk
    except Exception:  # tanpa tkinter: jalankan diam-diam, tulis log, tampilkan hasil dengan kotak pesan
        lines = []
        ok = setup(HERE, lines.append)
        with open(os.path.join(HERE, "siapkan.log"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0, "Selesai." if ok else "Gagal. Lihat siapkan.log di folder aplikasi.", "Dynamic Island", 0x40 if ok else 0x10)
        except Exception:
            pass
        return

    root = tk.Tk()
    root.title("Menyiapkan Dynamic Island")
    root.geometry("660x400")
    label = tk.Label(root, text="Menyiapkan Dynamic Island... jangan tutup jendela ini.", anchor="w")
    label.pack(fill="x", padx=12, pady=(12, 6))
    bar = ttk.Progressbar(root, mode="indeterminate")
    bar.pack(fill="x", padx=12)
    bar.start(12)
    frame = tk.Frame(root)
    frame.pack(fill="both", expand=True, padx=12, pady=12)
    text = tk.Text(frame, state="disabled", font=("Consolas", 9), wrap="none")
    scroll = tk.Scrollbar(frame, command=text.yview)
    text.configure(yscrollcommand=scroll.set)
    scroll.pack(side="right", fill="y")
    text.pack(side="left", fill="both", expand=True)

    q = queue.Queue()

    def worker():
        try:
            ok = setup(HERE, q.put)
        except Exception as e:  # jangan biarkan jendela menggantung
            q.put(f"Galat tak terduga: {e!r}")
            ok = False
        q.put(("done", ok))

    def poll():
        try:
            while True:
                item = q.get_nowait()
                if isinstance(item, tuple):
                    bar.stop()
                    if item[1]:
                        label.config(text="Selesai. Dynamic Island sudah berjalan di tengah atas layar.")
                        root.after(3000, root.destroy)
                    else:
                        label.config(text="Gagal. Baca pesan di bawah, lalu jalankan ulang berkas ini.")
                else:
                    text.config(state="normal")
                    text.insert("end", item + "\n")
                    text.see("end")
                    text.config(state="disabled")
        except queue.Empty:
            pass
        root.after(100, poll)

    threading.Thread(target=worker, daemon=True).start()
    root.after(100, poll)
    root.mainloop()


if __name__ == "__main__":
    main()
