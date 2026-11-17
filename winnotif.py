"""Membaca notifikasi Windows (mis. WhatsApp) dari database notifikasi milik pengguna sendiri.

Catatan penting:
- Memakai berkas internal Windows (wpndatabase.db) yang tidak didokumentasikan, jadi sifatnya
  "usaha terbaik": bisa berhenti bekerja setelah pembaruan Windows.
- Semua dibaca secara lokal pada komputer ini; tidak ada data yang dikirim ke mana pun.
- Hanya notifikasi yang benar-benar dimunculkan Windows yang tercatat. Pastikan notifikasi
  aplikasi tersebut aktif di Pengaturan Windows dan mode Fokus/Jangan Ganggu tidak menyembunyikannya.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from PySide6.QtCore import QObject, Signal


def default_db() -> Path:
    base = os.environ.get("LOCALAPPDATA") or ""
    return Path(base) / "Microsoft" / "Windows" / "Notifications" / "wpndatabase.db"


def app_label(primary_id: str) -> str:
    low = (primary_id or "").lower()
    if "whatsapp" in low:
        return "WhatsApp"
    name = (primary_id or "Notifikasi").split("!")[0].split("_")[0]
    name = name.split(".")[-1] or name
    return name[:24]


def parse_payload(raw) -> tuple[str, str]:
    """Ambil (judul, isi) dari XML toast."""
    if raw is None:
        return "", ""
    if isinstance(raw, (bytes, bytearray)):
        try:
            raw = bytes(raw).decode("utf-8")
        except UnicodeDecodeError:
            raw = bytes(raw).decode("utf-16", errors="ignore")
    raw = str(raw).strip("\x00 \r\n﻿")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return "", ""
    texts = [(t.text or "").strip() for t in root.iter("text")]
    texts = [t for t in texts if t]
    if not texts:
        return "", ""
    return texts[0], "\n".join(texts[1:])


class WinNotifHub(QObject):
    received = Signal(dict)

    def __init__(self, apps, show_body: bool = True, db_path=None, interval: float = 1.5):
        super().__init__()
        self.apps = [str(a).lower() for a in (apps or [])]
        self.show_body = show_body
        self.db = Path(db_path) if db_path else default_db()
        self.interval = interval
        self._last = None

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while True:
            try:
                for d in self.poll_once():
                    self.received.emit(d)
            except Exception:
                pass
            time.sleep(self.interval)

    def _open_copy(self, tmp: str) -> sqlite3.Connection:
        """Salin database (beserta -wal/-shm) ke folder sementara agar tidak mengganggu Windows."""
        dst = Path(tmp) / "w.db"
        shutil.copy2(self.db, dst)
        for suf in ("-wal", "-shm"):
            src = Path(str(self.db) + suf)
            if src.exists():
                try:
                    shutil.copy2(src, Path(str(dst) + suf))
                except Exception:
                    pass
        return sqlite3.connect(str(dst))

    def poll_once(self) -> list[dict]:
        if not self.db.exists():
            return []
        with tempfile.TemporaryDirectory() as tmp:
            con = self._open_copy(tmp)
            try:
                cur = con.cursor()
                if self._last is None:  # pemanggilan pertama: jangan putar ulang notifikasi lama
                    row = cur.execute("SELECT MAX(Id) FROM Notification").fetchone()
                    self._last = (row[0] if row else None) or 0
                    return []
                rows = cur.execute(
                    "SELECT n.Id, h.PrimaryId, n.Type, n.Payload FROM Notification n "
                    "LEFT JOIN NotificationHandler h ON n.HandlerId = h.RecordId "
                    "WHERE n.Id > ? ORDER BY n.Id",
                    (self._last,),
                ).fetchall()
            finally:
                con.close()
        out = []
        for nid, pid, typ, payload in rows:
            self._last = max(self._last, nid)
            if (typ or "toast").lower() != "toast":
                continue
            title, body = parse_payload(payload)
            if not title and not body:
                continue
            if self.apps and not any(a in (pid or "").lower() for a in self.apps):
                continue
            out.append({"app": app_label(pid), "title": title,
                        "body": body if self.show_body else "", "url": ""})
        return out
