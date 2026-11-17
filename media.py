"""Spotify (dan pemutar media lain) lewat Windows System Media Transport Controls.

Tidak butuh akun, API key, maupun login: Windows sudah mengetahui lagu yang sedang diputar.
"""
from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timezone

from PySide6.QtCore import QObject, Signal

IMPORT_ERR = ""
try:
    from winrt.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager as Manager,
        GlobalSystemMediaTransportControlsSessionPlaybackStatus as Status,
    )

    HAVE_WINRT = True
except Exception as _e:  # bukan Windows / paket winrt belum terpasang
    HAVE_WINRT = False
    IMPORT_ERR = repr(_e)[:90]

# sampul album bersifat opsional: kegagalan di sini tidak boleh mematikan fitur musik
try:
    from winrt.windows.storage.streams import Buffer, InputStreamOptions

    HAVE_STREAMS = True
except Exception:
    HAVE_STREAMS = False


class MediaHub(QObject):
    changed = Signal(dict)

    def __init__(self):
        super().__init__()
        self._loop = asyncio.new_event_loop()
        self._mgr = None
        self._art_key = None
        self._art = None

    # ---- siklus hidup ----
    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._main())

    async def _main(self):
        if not HAVE_WINRT:
            self.changed.emit({"available": False, "error": IMPORT_ERR})
            return
        try:
            self._mgr = await Manager.request_async()
        except Exception as e:
            self.changed.emit({"available": False, "error": repr(e)[:90]})
            return
        last_err = None
        while True:
            try:
                await self._poll()
                last_err = None
            except Exception as e:
                err = repr(e)[:90]
                if err != last_err:  # tampilkan galat, jangan disembunyikan
                    last_err = err
                    self.changed.emit({"available": True, "session": False, "error": err})
            await asyncio.sleep(1.0)

    # ---- pembacaan ----
    def _pick(self):
        try:
            for s in self._mgr.get_sessions():
                if "spotify" in (s.source_app_user_model_id or "").lower():
                    return s
        except Exception:
            pass
        return self._mgr.get_current_session()

    async def _poll(self):
        s = self._pick()
        if s is None:
            self.changed.emit({"available": True, "session": False})
            return
        props = await s.try_get_media_properties_async()
        info = s.get_playback_info()
        tl = s.get_timeline_properties()
        playing = info.playback_status == Status.PLAYING

        dur = max(0.0, (tl.end_time - tl.start_time).total_seconds())
        pos = tl.position.total_seconds()
        if playing:
            try:
                lu = tl.last_updated_time
                if lu.tzinfo is None:
                    lu = lu.replace(tzinfo=timezone.utc)
                pos += max(0.0, (datetime.now(timezone.utc) - lu).total_seconds())
            except Exception:
                pass
        if dur:
            pos = min(pos, dur)

        key = (props.title, props.artist)
        if key != self._art_key:
            self._art = await self._read_thumb(props.thumbnail)
            self._art_key = key

        self.changed.emit({
            "available": True,
            "session": True,
            "title": props.title or "",
            "artist": props.artist or "",
            "playing": playing,
            "pos": pos,
            "dur": dur,
            "art": self._art,
            "app": s.source_app_user_model_id or "",
        })

    async def _read_thumb(self, ref):
        if ref is None or not HAVE_STREAMS:
            return None
        try:
            stream = await ref.open_read_async()
            buf = Buffer(5_000_000)
            await stream.read_async(buf, buf.capacity, InputStreamOptions.READ_AHEAD)
            try:
                return bytes(memoryview(buf))[: buf.length]
            except Exception:
                from winrt.windows.storage.streams import DataReader

                reader = DataReader.from_buffer(buf)
                arr = bytearray(buf.length)
                reader.read_bytes(arr)
                return bytes(arr)
        except Exception:
            return None

    # ---- kontrol ----
    def toggle(self):
        self._cmd("toggle")

    def next(self):
        self._cmd("next")

    def prev(self):
        self._cmd("prev")

    def _cmd(self, name):
        if HAVE_WINRT and self._mgr is not None:
            asyncio.run_coroutine_threadsafe(self._do(name), self._loop)

    async def _do(self, name):
        s = self._pick()
        if s is None:
            return
        try:
            if name == "toggle":
                await s.try_toggle_play_pause_async()
            elif name == "next":
                await s.try_skip_next_async()
            elif name == "prev":
                await s.try_skip_previous_async()
        except Exception:
            pass
