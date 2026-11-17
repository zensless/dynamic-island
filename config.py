"""Konfigurasi dan lokasi data aplikasi."""
import json
import os
from pathlib import Path

APP_NAME = "DynamicIsland"

DEFAULTS = {
    # tema warna: "air" (biru malam + aksen biru es) atau "amber" (hitam + aksen amber)
    "theme": "air",
    # timpa warna tema, mis. {"accent": "#6EC1F5", "bg": "#060D17", "ripple": true}
    "colors": {},
    # jarak island dari tepi atas layar (px)
    "top_margin": 8,
    # layar mana yang dipakai (0 = utama)
    "screen_index": 0,
    # island mengembang saat kursor diam di atasnya
    "hover_expand": True,
    "hover_delay_ms": 250,
    # jeda sebelum island mengecil setelah kursor pergi
    "collapse_delay_ms": 900,
    # lama notifikasi tampil otomatis (detik)
    "notif_seconds": 6,
    # ekspresi mata (mengikuti kursor, senyum, kaget, menegang, mengantuk); false = mata polos
    "eye_expressions": True,
    # jalankan sebagai Administrator (perlu untuk FPS/PresentMon): "auto" = hanya jika PresentMon ada,
    # true = selalu, false = tidak pernah
    "run_as_admin": "auto",
    # jalankan LibreHardwareMonitor otomatis (untuk suhu CPU); lhm_path kosong = cari sendiri
    "lhm_autostart": True,
    "lhm_path": "",
    # pintasan Desktop/Start sudah dibuat (diatur otomatis)
    "shortcut_done": False,
    # port server lokal untuk menerima notifikasi
    "notify_port": 8765,
    # tampilkan notifikasi Windows dari aplikasi tertentu (mis. WhatsApp) di island.
    # win_notif_apps = potongan ID aplikasi (huruf kecil); [] = semua aplikasi
    "win_notif": True,
    "win_notif_apps": ["whatsapp"],
    # false = tampilkan nama pengirim saja, isi pesan disembunyikan
    "win_notif_show_body": True,
    # LibreHardwareMonitor -> Options -> Remote Web Server (untuk suhu CPU)
    "lhm_url": "http://localhost:8085/data.json",
    # path PresentMon.exe (untuk FPS); kosong = FPS nonaktif
    "presentmon_path": "",
    "presentmon_args": ["--output_stdout", "--no_console_stats", "--stop_existing_session"],
}


def data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    d = Path(base) / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def load() -> dict:
    path = data_dir() / "config.json"
    cfg = dict(DEFAULTS)
    if path.exists():
        try:
            cfg.update(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            pass
    else:
        path.write_text(json.dumps(DEFAULTS, indent=2), encoding="utf-8")
    return cfg


def update(key: str, value) -> None:
    """Ubah satu kunci di config.json tanpa menyentuh yang lain."""
    path = data_dir() / "config.json"
    try:
        cur = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        cur = {}
    cur[key] = value
    path.write_text(json.dumps(cur, indent=2), encoding="utf-8")
