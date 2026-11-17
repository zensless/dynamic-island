"""Diagnosis: tampilkan 15 notifikasi Windows terakhir yang tercatat (hanya di komputer ini).

Jalankan:  .venv\\Scripts\\python.exe cek_notif.py
Gunanya untuk melihat 'ID aplikasi' WhatsApp di komputer Anda. Isi pesan dipotong.
"""
import tempfile

from winnotif import WinNotifHub, parse_payload

hub = WinNotifHub([])
print("Database:", hub.db, "-> ada" if hub.db.exists() else "-> TIDAK ADA")
if not hub.db.exists():
    raise SystemExit("Berkas database notifikasi tidak ditemukan (apakah ini Windows 10/11?).")

try:
    with tempfile.TemporaryDirectory() as tmp:
        con = hub._open_copy(tmp)
        rows = con.execute(
            "SELECT n.Id, h.PrimaryId, n.Type, n.Payload FROM Notification n "
            "LEFT JOIN NotificationHandler h ON n.HandlerId = h.RecordId "
            "ORDER BY n.Id DESC LIMIT 15"
        ).fetchall()
        con.close()
except Exception as e:
    raise SystemExit(f"Gagal membaca database: {e!r}")

print(f"\n{len(rows)} notifikasi terakhir:\n")
for nid, pid, typ, payload in rows:
    title, body = parse_payload(payload)
    print(f"#{nid}  [{typ}]  app: {pid}")
    print(f"     judul: {title[:50]!r}   isi: {body[:50]!r}")
print("\nCari baris WhatsApp, lalu pastikan sebagian teks 'app:' itu ada di win_notif_apps pada config.json.")
