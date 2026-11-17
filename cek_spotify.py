"""Diagnosis: tampilkan apa yang dilihat Windows tentang pemutar musik.

Jalankan:  .venv\\Scripts\\python.exe cek_spotify.py   (saat Spotify sedang memutar lagu)
"""
import asyncio
import sys
import traceback

print("Python:", sys.version.split()[0])

try:
    from winrt.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager as Manager,
    )
    print("OK  paket winrt.windows.media.control")
except Exception:
    traceback.print_exc()
    print("\nGAGAL: paket winrt belum terpasang. Jalankan:")
    print("  .venv\\Scripts\\python.exe -m pip install winrt-runtime winrt-Windows.Foundation "
          "winrt-Windows.Foundation.Collections winrt-Windows.Media.Control winrt-Windows.Storage.Streams")
    sys.exit(1)

try:
    from winrt.windows.storage.streams import Buffer  # noqa: F401
    print("OK  paket winrt.windows.storage.streams")
except Exception:
    print("PERINGATAN  winrt-Windows.Storage.Streams belum terpasang (sampul album tidak tampil)")


async def main():
    mgr = await Manager.request_async()
    sessions = list(mgr.get_sessions())
    print("\nJumlah sesi media yang dilihat Windows:", len(sessions))
    for s in sessions:
        print("\n-", s.source_app_user_model_id)
        try:
            p = await s.try_get_media_properties_async()
            print("   judul :", p.title)
            print("   artis :", p.artist)
            print("   status:", s.get_playback_info().playback_status)
            tl = s.get_timeline_properties()
            print("   posisi:", tl.position, "/ durasi:", tl.end_time)
        except Exception:
            traceback.print_exc()
    cur = mgr.get_current_session()
    print("\nSesi aktif sekarang:", cur.source_app_user_model_id if cur else "(tidak ada)")
    if not sessions:
        print("\nWindows belum melihat pemutar apa pun. Putar lagu di Spotify lalu jalankan ulang skrip ini.")


try:
    asyncio.run(main())
except Exception:
    traceback.print_exc()
