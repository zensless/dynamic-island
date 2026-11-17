"""Kirim notifikasi ke Dynamic Island.

Contoh:
    python kirim_notif.py "Build selesai" "Semua tes lulus" --app "Skrip saya"
    python kirim_notif.py "Unduhan" "file.zip selesai" --url https://example.com
"""
import argparse
import json
import sys
import urllib.request


def main():
    ap = argparse.ArgumentParser(description="Kirim notifikasi ke Dynamic Island")
    ap.add_argument("title")
    ap.add_argument("body", nargs="?", default="")
    ap.add_argument("--app", default="Skrip")
    ap.add_argument("--url", default="")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()

    req = urllib.request.Request(
        f"http://127.0.0.1:{a.port}/notify",
        data=json.dumps({"app": a.app, "title": a.title, "body": a.body, "url": a.url}).encode(),
        headers={"Content-Type": "application/json", "X-Island": "1"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=2).read()
    except Exception as e:
        print("Gagal mengirim (apakah Dynamic Island sedang berjalan?):", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
