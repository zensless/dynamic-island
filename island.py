"""Tampilan Dynamic Island: mode garis (dua mata) dan mode mengembang (Musik, Sistem, Notif, Catatan)."""
from __future__ import annotations

import math
import random
import re
import time
import webbrowser

import config as _config

from PySide6.QtCore import (
    QAbstractAnimation, QEasingCurve, QPointF, QPropertyAnimation, QRect, QRectF,
    Qt, QTimer, QVariantAnimation, Signal,
)
from PySide6.QtGui import (
    QColor, QCursor, QFont, QFontMetrics, QGuiApplication, QPainter, QPainterPath, QPen,
    QPixmap, QPolygonF,
)
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget,
)

# ---------------------------------------------------------------- ukuran
IDLE_W, IDLE_H = 200, 22
OPEN_W = 440
CHROME_H = 74  # 14 atas + 28 header + 14 jarak + 18 bawah

# ---------------------------------------------------------------- warna
THEMES = {
    "amber": {
        "bg": "#050506", "text": "#EDE8DE", "muted": "#8A867D", "accent": "#F0A83A",
        "off": "#26262A", "line": "#2A2A2E", "field": "#0F0F11", "sep": "#1E1E21",
        "body": "#B5B0A5", "art": "#1B1B1E", "eye": "#FFFFFF", "ripple": False,
    },
    "air": {
        "bg": "#060D17", "text": "#E8F1F8", "muted": "#8196AB", "accent": "#6EC1F5",
        "off": "#13263A", "line": "#1D3552", "field": "#0A1522", "sep": "#12233A",
        "body": "#B3C4D4", "art": "#0E1D2E", "eye": "#FFFFFF", "ripple": True,
    },
}


def _load_theme() -> dict:
    cfg = _config.load()
    t = dict(THEMES["amber"])
    t.update(THEMES.get(cfg.get("theme", "air"), THEMES["air"]))
    for k, v in (cfg.get("colors") or {}).items():
        if k == "ripple" and isinstance(v, bool):
            t[k] = v
        elif k in t and k != "ripple" and isinstance(v, str) and QColor(v).isValid():
            t[k] = v
    return t


T = _load_theme()
BG = QColor(T["bg"])
HAIR = QColor(255, 255, 255, 24)
TEXT = QColor(T["text"])
MUTED = QColor(T["muted"])
AMBER = QColor(T["accent"])  # warna aksen (nama lama dipertahankan)
RED = QColor("#E5484D")
OFF = QColor(T["off"])
LINE = QColor(T["line"])
WHITE = QColor(T["eye"])
INK = QColor("#0B0B0C")

# warna lama di string stylesheet -> warna tema
_LEGACY = {"#8A867D": "muted", "#F0A83A": "accent", "#EDE8DE": "text", "#2A2A2E": "line",
           "#26262A": "off", "#0F0F11": "field", "#1E1E21": "sep", "#B5B0A5": "body"}
_LEG_RE = re.compile("|".join(re.escape(k) for k in _LEGACY), re.I)


def qss(css: str) -> str:
    return _LEG_RE.sub(lambda m: T[_LEGACY[m.group(0).upper()]], css)

MONO = ["JetBrains Mono", "Cascadia Mono", "Consolas", "monospace"]
UI = ["Schibsted Grotesk", "Segoe UI Variable Text", "Segoe UI", "sans-serif"]


def make_font(families, px, weight=QFont.Weight.Normal, spacing=0.0) -> QFont:
    f = QFont()
    f.setFamilies(families)
    f.setPixelSize(px)
    f.setWeight(weight)
    if spacing:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    return f


# Pose mata: sx/sy = skala lebar/tinggi, tilt = kemiringan kelopak atas (>0 menegang),
# lid = kelopak atas turun (mengantuk), sl/sr = lengkung senyum mata kiri/kanan.
POSES = {
    "normal":    {"sx": 1.0,  "sy": 1.0,  "tilt": 0.0, "lid": 0.0, "sl": 0.0, "sr": 0.0},
    "happy":     {"sx": 1.05, "sy": 1.0,  "tilt": 0.0, "lid": 0.0, "sl": 1.0, "sr": 1.0},
    "wink":      {"sx": 1.0,  "sy": 1.0,  "tilt": 0.0, "lid": 0.0, "sl": 0.0, "sr": 1.0},
    "surprised": {"sx": 1.12, "sy": 1.35, "tilt": 0.0, "lid": 0.0, "sl": 0.0, "sr": 0.0},
    "sleepy":    {"sx": 1.0,  "sy": 0.9,  "tilt": 0.0, "lid": 1.0, "sl": 0.0, "sr": 0.0},
    "tense":     {"sx": 1.0,  "sy": 0.85, "tilt": 1.0, "lid": 0.0, "sl": 0.0, "sr": 0.0},
}


def fmt_time(sec: float) -> str:
    sec = max(0, int(sec))
    return f"{sec // 60}:{sec % 60:02d}"


# ================================================================ widget kecil
class ElideLabel(QWidget):
    """Label satu baris yang dipotong dengan elipsis."""

    def __init__(self, font: QFont, color: QColor, height: int):
        super().__init__()
        self._t, self._f, self._c = "", font, color
        self.setFixedHeight(height)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def setText(self, t: str):
        self._t = t
        self.update()

    def setColor(self, c: QColor):
        self._c = c
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setFont(self._f)
        p.setPen(self._c)
        t = p.fontMetrics().elidedText(self._t, Qt.TextElideMode.ElideRight, self.width())
        p.drawText(QRect(0, 0, self.width(), self.height()),
                   int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), t)


class TabButton(QPushButton):
    def __init__(self, label: str):
        super().__init__()
        self.label, self.active, self.badge = label, False, 0
        self._font = make_font(MONO, 11, QFont.Weight.Medium, 0.9)
        self.setFlat(True)
        self.setFixedHeight(28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._resize()

    def _resize(self):
        fm = QFontMetrics(self._font)
        w = fm.horizontalAdvance(self.label) + 20
        if self.badge:
            w += fm.horizontalAdvance(str(self.badge)) + 6
        self.setFixedWidth(w)

    def set_active(self, a: bool):
        self.active = a
        self.update()

    def set_badge(self, n: int):
        self.badge = n
        self._resize()
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setFont(self._font)
        fm = p.fontMetrics()
        base = (self.height() + fm.ascent() - fm.descent()) // 2 - 2
        p.setPen(TEXT if (self.active or self.underMouse()) else MUTED)
        p.drawText(10, base, self.label)
        if self.badge:
            p.setPen(AMBER)
            p.drawText(10 + fm.horizontalAdvance(self.label) + 6, base, str(self.badge))
        if self.active:
            p.fillRect(QRect(0, self.height() - 2, self.width(), 2), AMBER)


class IconButton(QPushButton):
    def __init__(self, kind: str, size: int = 36, filled: bool = False):
        super().__init__()
        self.kind, self.filled = kind, filled
        self.setFlat(True)
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def set_kind(self, k: str):
        self.kind = k
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            p.setOpacity(0.35)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        color = TEXT
        p.setPen(Qt.PenStyle.NoPen)
        if self.filled:
            p.setBrush(TEXT)
            p.drawEllipse(QRectF(0, 0, w, h))
            color = INK
        elif self.underMouse() and self.isEnabled():
            p.setBrush(QColor(255, 255, 255, 22))
            p.drawEllipse(QRectF(0, 0, w, h))
        s = min(w, h) * 0.22
        k = self.kind
        if k in ("left", "right"):
            d = -1 if k == "left" else 1
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(MUTED, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            path = QPainterPath()
            path.moveTo(cx - d * s * 0.4, cy - s * 0.8)
            path.lineTo(cx + d * s * 0.4, cy)
            path.lineTo(cx - d * s * 0.4, cy + s * 0.8)
            p.drawPath(path)
            return
        p.setBrush(color)
        if k == "play":
            p.drawPolygon(QPolygonF([QPointF(cx - s * .6, cy - s), QPointF(cx - s * .6, cy + s), QPointF(cx + s, cy)]))
        elif k == "pause":
            p.drawRoundedRect(QRectF(cx - s * .85, cy - s, s * .65, s * 2), 1.2, 1.2)
            p.drawRoundedRect(QRectF(cx + s * .2, cy - s, s * .65, s * 2), 1.2, 1.2)
        elif k == "next":
            p.drawPolygon(QPolygonF([QPointF(cx - s, cy - s), QPointF(cx - s, cy + s), QPointF(cx + s * .7, cy)]))
            p.drawRoundedRect(QRectF(cx + s * .85, cy - s, 2, s * 2), 1, 1)
        elif k == "prev":
            p.drawPolygon(QPolygonF([QPointF(cx + s, cy - s), QPointF(cx + s, cy + s), QPointF(cx - s * .7, cy)]))
            p.drawRoundedRect(QRectF(cx - s * .85 - 2, cy - s, 2, s * 2), 1, 1)


class ArtWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(64, 64)
        self.pix: QPixmap | None = None

    def set_pixmap(self, pix):
        self.pix = pix
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0.5, 0.5, 63, 63), 10, 10)
        if self.pix and not self.pix.isNull():
            p.setClipPath(clip)
            sc = self.pix.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                 Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap((64 - sc.width()) // 2, (64 - sc.height()) // 2, sc)
            p.setClipping(False)
            p.setPen(QPen(HAIR, 1))
            p.drawPath(clip)
            return
        p.fillPath(clip, QColor(T["art"]))
        p.setPen(QPen(LINE, 1))
        p.drawPath(clip)
        p.setPen(QPen(MUTED, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        cx, cy = 32, 32
        p.drawEllipse(QPointF(cx - 6, cy + 8), 3.4, 3.4)
        p.drawEllipse(QPointF(cx + 6, cy + 5), 3.4, 3.4)
        p.drawLine(QPointF(cx - 2.6, cy + 8), QPointF(cx - 2.6, cy - 8))
        p.drawLine(QPointF(cx + 9.4, cy + 5), QPointF(cx + 9.4, cy - 10))
        p.drawLine(QPointF(cx - 2.6, cy - 8), QPointF(cx + 9.4, cy - 10))


class Progress(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(14)
        self.pos, self.dur = 0.0, 0.0
        self.f = make_font(MONO, 11)

    def set(self, pos, dur):
        self.pos, self.dur = pos, dur
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(self.f)
        fm = p.fontMetrics()
        w, cy = self.width(), self.height() / 2
        lt = fmt_time(self.pos)
        rt = fmt_time(self.dur) if self.dur > 0 else "-:--"
        lw = fm.horizontalAdvance("00:00")
        base = cy + (fm.ascent() - fm.descent()) / 2
        p.setPen(MUTED)
        p.drawText(QPointF(0, base), lt)
        p.drawText(QPointF(w - fm.horizontalAdvance(rt), base), rt)
        x0, x1 = lw + 10, w - lw - 10
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(LINE)
        p.drawRoundedRect(QRectF(x0, cy - 1, x1 - x0, 2), 1, 1)
        if self.dur > 0:
            xf = x0 + (x1 - x0) * min(1.0, self.pos / self.dur)
            p.setBrush(AMBER)
            p.drawRoundedRect(QRectF(x0, cy - 1, max(0, xf - x0), 2), 1, 1)
            p.drawRoundedRect(QRectF(xf - 1, cy - 5, 2, 10), 1, 1)


# ================================================================ halaman
class MusicPage(QWidget):
    cmd = Signal(str)

    def __init__(self):
        super().__init__()
        self.setFixedHeight(92)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(14)
        row = QHBoxLayout()
        row.setSpacing(16)
        self.art = ArtWidget()
        row.addWidget(self.art)
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addStretch()
        self.title = ElideLabel(make_font(UI, 16, QFont.Weight.DemiBold), TEXT, 22)
        self.artist = ElideLabel(make_font(UI, 13), MUTED, 18)
        col.addWidget(self.title)
        col.addWidget(self.artist)
        col.addStretch()
        row.addLayout(col, 1)
        ctl = QHBoxLayout()
        ctl.setSpacing(4)
        self.b_prev = IconButton("prev", 36)
        self.b_play = IconButton("play", 40, True)
        self.b_next = IconButton("next", 36)
        for b, name in ((self.b_prev, "prev"), (self.b_play, "toggle"), (self.b_next, "next")):
            b.clicked.connect(lambda _=False, n=name: self.cmd.emit(n))
            ctl.addWidget(b)
        row.addLayout(ctl)
        v.addLayout(row)
        self.progress = Progress()
        v.addWidget(self.progress)

        self.playing, self._pos, self._dur = False, 0.0, 0.0
        self._t0 = time.monotonic()
        self._art_bytes = None
        self._tick = QTimer(self)
        self._tick.setInterval(250)
        self._tick.timeout.connect(self._advance)
        self._tick.start()
        self._enable(False)
        self.title.setText("Tidak ada musik")
        self.artist.setText("Putar sesuatu di Spotify")

    def _enable(self, on: bool):
        for b in (self.b_prev, self.b_play, self.b_next):
            b.setEnabled(on)

    def _advance(self):
        if self.playing and self._dur > 0:
            pos = min(self._dur, self._pos + (time.monotonic() - self._t0))
            self.progress.set(pos, self._dur)

    def optimistic_toggle(self):
        self.playing = not self.playing
        self._pos = self.progress.pos
        self._t0 = time.monotonic()
        self.b_play.set_kind("pause" if self.playing else "play")

    def apply(self, d: dict):
        if not d.get("available", True):
            self.playing = False
            self.title.setText("Kontrol media tidak tersedia")
            self.artist.setText(d.get("error") or "Pasang paket winrt (lihat README)")
            self._enable(False)
            return
        if not d.get("session"):
            self.playing = False
            if d.get("error"):
                self.title.setText("Galat membaca media")
                self.artist.setText(d["error"])
            else:
                self.title.setText("Tidak ada musik")
                self.artist.setText("Putar sesuatu di Spotify")
            self.progress.set(0, 0)
            self.art.set_pixmap(None)
            self._art_bytes = None
            self.b_play.set_kind("play")
            self._enable(False)
            return
        self._enable(True)
        self.title.setText(d.get("title") or "Tanpa judul")
        self.artist.setText(d.get("artist") or "")
        self.playing = bool(d.get("playing"))
        self._pos, self._dur = d.get("pos", 0.0), d.get("dur", 0.0)
        self._t0 = time.monotonic()
        self.progress.set(self._pos, self._dur)
        self.b_play.set_kind("pause" if self.playing else "play")
        art = d.get("art")
        if art != self._art_bytes:
            self._art_bytes = art
            pix = QPixmap()
            self.art.set_pixmap(pix if art and pix.loadFromData(art) else None)


class SystemPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(134)
        self.s: dict = {}
        self.f_label = make_font(MONO, 10, QFont.Weight.Normal, 1.0)
        self.f_val = make_font(MONO, 22, QFont.Weight.Medium)
        self.f_unit = make_font(MONO, 12)
        self.f_small = make_font(MONO, 11)
        self.f_temp = make_font(MONO, 15, QFont.Weight.Medium)

    def set_stats(self, d: dict):
        self.s = d
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        gap = 16
        cw = (self.width() - gap * 2) / 3.0
        cells = [("CPU", "cpu"), ("GPU", "gpu"), ("RAM", "ram"), ("VRAM", "vram"), ("FPS", None), ("SUHU", None)]
        for i, (label, key) in enumerate(cells):
            x = (i % 3) * (cw + gap)
            y = (i // 3) * (56 + 18)
            p.setFont(self.f_label)
            p.setPen(MUTED)
            p.drawText(QPointF(x, y + 10), label)
            if key:
                self._meter(p, x, y, cw, self.s.get(key))
            elif label == "FPS":
                self._fps(p, x, y, cw)
            else:
                self._temps(p, x, y, cw)

    def _ticks(self, p, x, y, cw, val):
        n = 0 if val is None else max(0, min(20, round(val / 5)))
        on = RED if (val is not None and val >= 85) else AMBER
        tw = (cw - 19 * 2) / 20.0
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(20):
            p.setBrush(on if i < n else OFF)
            p.drawRoundedRect(QRectF(x + i * (tw + 2), y + 44, tw, 10), 1, 1)

    def _value(self, p, x, y, text, unit, muted=False):
        p.setFont(self.f_val)
        p.setPen(MUTED if muted else TEXT)
        p.drawText(QPointF(x, y + 34), text)
        if unit:
            w = p.fontMetrics().horizontalAdvance(text)
            p.setFont(self.f_unit)
            p.setPen(MUTED)
            p.drawText(QPointF(x + w + 3, y + 34), unit)

    def _meter(self, p, x, y, cw, val):
        if val is None:
            self._value(p, x, y, "—", "", True)
        else:
            self._value(p, x, y, f"{round(val)}", "%")
        self._ticks(p, x, y, cw, val)

    def _fps(self, p, x, y, cw):
        fps, ms = self.s.get("fps"), self.s.get("frame_ms")
        if fps is not None:
            self._value(p, x, y, f"{round(fps)}", "fps")
            cap = f"{ms:.1f} ms / frame".replace(".", ",") if ms else ""
        else:
            self._value(p, x, y, "—", "", True)
            cap = {
                "unset": "belum diatur",
                "missing": "path salah",
                "starting": "memulai…",
                "running": "menunggu game",
                "exited": "butuh admin?",
                "error": "gagal start",
            }.get(self.s.get("fps_status", "unset"), "belum diatur")
        p.setFont(self.f_small)
        p.setPen(MUTED)
        p.drawText(QPointF(x, y + 53), cap)

    def _temps(self, p, x, y, cw):
        for j, (lab, key) in enumerate((("CPU", "cpu_temp"), ("GPU", "gpu_temp"))):
            by = y + 32 + j * 20
            p.setFont(self.f_label)
            p.setPen(MUTED)
            p.drawText(QPointF(x, by), lab)
            v = self.s.get(key)
            txt = "—" if v is None else f"{round(v)}°C"
            p.setFont(self.f_temp)
            p.setPen(MUTED if v is None else (RED if v >= 85 else TEXT))
            p.drawText(QPointF(x + cw - p.fontMetrics().horizontalAdvance(txt), by), txt)


BTN_PRIMARY = qss("QPushButton{background:#EDE8DE;color:#0B0B0C;border:0;border-radius:16px;padding:0 14px;font-weight:600}"
               "QPushButton:disabled{background:#26262A;color:#8A867D}")
BTN_GHOST = qss("QPushButton{background:transparent;color:#8A867D;border:0;border-radius:16px;padding:0 14px}"
             "QPushButton:hover{color:#EDE8DE}QPushButton:disabled{color:#3A3A3E}")


class NotifPage(QWidget):
    seen = Signal()

    def __init__(self):
        super().__init__()
        self.setFixedHeight(146)
        self.items: list[dict] = []
        self.idx = 0
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        top = QHBoxLayout()
        self.app = ElideLabel(make_font(MONO, 10, QFont.Weight.Normal, 1.0), MUTED, 14)
        self.time = QLabel()
        self.time.setFont(make_font(MONO, 10, QFont.Weight.Normal, 1.0))
        self.time.setStyleSheet("QLabel{color:#8A867D;background:transparent}")
        top.addWidget(self.app, 1)
        top.addWidget(self.time)
        self.title = ElideLabel(make_font(UI, 16, QFont.Weight.DemiBold), TEXT, 22)
        self.body = QLabel()
        self.body.setWordWrap(True)
        self.body.setFixedHeight(38)
        self.body.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.body.setFont(make_font(UI, 13))
        self.body.setStyleSheet("QLabel{color:#B5B0A5;background:transparent}")
        v.addLayout(top)
        v.addWidget(self.title)
        v.addWidget(self.body)
        v.addStretch()
        sep = QFrame()
        sep.setObjectName("sep")
        sep.setFixedHeight(1)
        sep.setStyleSheet("QFrame#sep{background:#1E1E21;border:0}")
        v.addWidget(sep)
        foot = QHBoxLayout()
        foot.setSpacing(6)
        self.b_open = QPushButton("Buka")
        self.b_close = QPushButton("Tutup")
        for b, css in ((self.b_open, BTN_PRIMARY), (self.b_close, BTN_GHOST)):
            b.setFixedHeight(32)
            b.setFont(make_font(UI, 13, QFont.Weight.Medium))
            b.setStyleSheet(css)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            foot.addWidget(b)
        foot.addStretch()
        self.b_left, self.b_right = IconButton("left", 28), IconButton("right", 28)
        self.count = QLabel("0 / 0")
        self.count.setFont(make_font(MONO, 11))
        self.count.setStyleSheet("QLabel{color:#8A867D;background:transparent}")
        foot.addWidget(self.b_left)
        foot.addWidget(self.count)
        foot.addWidget(self.b_right)
        v.addLayout(foot)
        self.b_open.clicked.connect(self._open_url)
        self.b_close.clicked.connect(self.dismiss)
        self.b_left.clicked.connect(lambda: self._go(-1))
        self.b_right.clicked.connect(lambda: self._go(1))
        self.refresh()

    def add(self, d: dict):
        d = dict(d)
        d["time"] = time.strftime("%H:%M")
        self.items.insert(0, d)
        del self.items[20:]
        self.idx = 0
        self.refresh()

    def dismiss(self):
        if self.items:
            self.items.pop(self.idx)
            self.idx = max(0, min(self.idx, len(self.items) - 1))
        self.refresh()

    def _go(self, step):
        if self.items:
            self.idx = (self.idx + step) % len(self.items)
            self.refresh()

    def _open_url(self):
        if self.items:
            url = self.items[self.idx].get("url", "")
            if url.lower().startswith(("http://", "https://")):
                webbrowser.open(url)

    def refresh(self):
        n = len(self.items)
        if not n:
            self.app.setText("")
            self.time.setText("")
            self.title.setText("Belum ada notifikasi")
            self.title.setColor(MUTED)
            self.body.setText("")
        else:
            it = self.items[self.idx]
            self.app.setText((it.get("app") or "NOTIFIKASI").upper())
            self.time.setText(it.get("time", ""))
            self.title.setText(it.get("title") or "(tanpa judul)")
            self.title.setColor(TEXT)
            body = it.get("body", "")
            self.body.setText(body if len(body) <= 120 else body[:119] + "…")
        has_url = bool(n and self.items[self.idx].get("url", "").lower().startswith(("http://", "https://")))
        self.b_open.setEnabled(has_url)
        self.b_close.setEnabled(n > 0)
        self.b_left.setEnabled(n > 1)
        self.b_right.setEnabled(n > 1)
        self.count.setText(f"{self.idx + 1 if n else 0} / {n}")


CHECK_QSS = qss("QCheckBox{color:#EDE8DE;spacing:12px;background:transparent}"
             "QCheckBox:checked{color:#8A867D}"
             "QCheckBox::indicator{width:14px;height:14px;border:1.5px solid #8A867D;border-radius:4px;background:transparent}"
             "QCheckBox::indicator:checked{background:#F0A83A;border-color:#F0A83A}")


class NotesPage(QWidget):
    def __init__(self, notes):
        super().__init__()
        self.notes = notes
        self.setFixedHeight(146)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("notescroll")
        self.scroll.setFixedHeight(96)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea#notescroll{background:transparent;border:0}")
        self.scroll.viewport().setStyleSheet("background:transparent")
        self.inner = QWidget()
        self.inner.setStyleSheet("background:transparent")
        self.rows = QVBoxLayout(self.inner)
        self.rows.setContentsMargins(0, 0, 0, 0)
        self.rows.setSpacing(2)
        self.scroll.setWidget(self.inner)
        v.addWidget(self.scroll)

        box = QFrame()
        box.setObjectName("inputbox")
        box.setFixedHeight(40)
        box.setStyleSheet("QFrame#inputbox{background:#0F0F11;border:1px solid #2A2A2E;border-radius:12px}")
        h = QHBoxLayout(box)
        h.setContentsMargins(14, 0, 14, 0)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Tulis catatan…")
        self.input.setFont(make_font(UI, 14))
        self.input.setStyleSheet("QLineEdit{background:transparent;border:0;color:#EDE8DE}")
        self.input.setMaxLength(200)
        hint = QLabel("ENTER")
        hint.setFont(make_font(MONO, 10, QFont.Weight.Normal, 0.6))
        hint.setStyleSheet("QLabel{color:#8A867D;background:transparent;border:0}")
        h.addWidget(self.input, 1)
        h.addWidget(hint)
        v.addWidget(box)
        self.input.returnPressed.connect(self._add)
        self.rebuild()

    def _add(self):
        self.notes.add(self.input.text())
        self.input.clear()
        self.rebuild()
        self.scroll.verticalScrollBar().setValue(0)

    def rebuild(self):
        while self.rows.count():
            it = self.rows.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        if not self.notes.items:
            lab = QLabel("Belum ada catatan")
            lab.setFont(make_font(UI, 14))
            lab.setStyleSheet(qss("QLabel{color:#8A867D;background:transparent}"))
            lab.setFixedHeight(32)
            self.rows.addWidget(lab)
        for i, item in enumerate(self.notes.items):
            row = QWidget()
            row.setFixedHeight(32)
            rh = QHBoxLayout(row)
            rh.setContentsMargins(0, 0, 0, 0)
            text = item["text"] if len(item["text"]) <= 42 else item["text"][:41] + "…"
            cb = QCheckBox(text)
            f = make_font(UI, 14)
            f.setStrikeOut(item["done"])
            cb.setFont(f)
            cb.setStyleSheet(CHECK_QSS)
            cb.setChecked(item["done"])
            cb.setCursor(Qt.CursorShape.PointingHandCursor)
            cb.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            cb.clicked.connect(lambda _=False, n=i: self._toggle(n))
            x = QPushButton("×")
            x.setFixedSize(24, 24)
            x.setFlat(True)
            x.setCursor(Qt.CursorShape.PointingHandCursor)
            x.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            x.setStyleSheet(qss("QPushButton{color:#8A867D;background:transparent;border:0;font-size:16px}"
                                "QPushButton:hover{color:#E5484D}"))
            x.clicked.connect(lambda _=False, n=i: self._remove(n))
            rh.addWidget(cb, 1)
            rh.addWidget(x)
            self.rows.addWidget(row)
        self.rows.addStretch()

    def _toggle(self, i):
        self.notes.toggle(i)
        self.rebuild()

    def _remove(self, i):
        self.notes.remove(i)
        self.rebuild()


# ================================================================ island
class Island(QWidget):
    def __init__(self, cfg: dict, notes):
        flags = (Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                 | Qt.WindowType.Tool | Qt.WindowType.NoDropShadowWindowHint)
        super().__init__(None, flags)
        self.cfg = cfg
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("Dynamic Island")

        self._open = False
        self.eye_open = 1.0
        self.playing = False
        self.unread = 0
        self.cur = "music"
        self.media = None

        # ---- isi (hanya tampil saat mengembang)
        self.content = QWidget(self)
        lay = QVBoxLayout(self.content)
        lay.setContentsMargins(20, 14, 20, 18)
        lay.setSpacing(14)
        head = QHBoxLayout()
        head.setSpacing(2)
        head.addSpacing(30)
        head.addStretch()
        self.tabs = {}
        for key, label in (("music", "MUSIK"), ("system", "SISTEM"), ("notif", "NOTIF"), ("notes", "CATATAN")):
            b = TabButton(label)
            b.clicked.connect(lambda _=False, k=key: self.set_tab(k))
            self.tabs[key] = b
            head.addWidget(b)
        lay.addLayout(head)
        self.stack = QStackedWidget()
        self.music_page = MusicPage()
        self.system_page = SystemPage()
        self.notif_page = NotifPage()
        self.notes_page = NotesPage(notes)
        self.pages = {"music": self.music_page, "system": self.system_page,
                      "notif": self.notif_page, "notes": self.notes_page}
        for pg in self.pages.values():
            self.stack.addWidget(pg)
        lay.addWidget(self.stack)
        self.music_page.cmd.connect(self._media_cmd)
        # terapkan warna tema ke stylesheet bawaan widget
        for w in self.content.findChildren(QWidget):
            ss = w.styleSheet()
            if ss:
                w.setStyleSheet(qss(ss))

        self._fx = QGraphicsOpacityEffect(self.content)
        self._fx.setOpacity(0.0)
        self.content.setGraphicsEffect(self._fx)
        self.content.hide()
        self._fade = QPropertyAnimation(self._fx, b"opacity", self)
        self._fade.setDuration(160)
        self._fade.finished.connect(self._after_fade)

        # ---- animasi ukuran
        self._anim = QPropertyAnimation(self, b"geometry", self)
        self._anim.setDuration(300)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        # ---- timer
        self.hover_timer = QTimer(self, singleShot=True)
        self.hover_timer.timeout.connect(lambda: self.expand())
        self.collapse_timer = QTimer(self, singleShot=True)
        self.collapse_timer.timeout.connect(self._try_collapse)
        self.eq_timer = QTimer(self)
        self.eq_timer.setInterval(60)
        self.eq_timer.timeout.connect(self.update)
        self._schedule_blink()

        # ---- ekspresi mata
        self.pose = dict(POSES["normal"])
        self.gaze = [0.0, 0.0]
        self._bob = 0.0
        now = time.monotonic()
        self._last_pos = QCursor.pos()
        self._last_move = now
        self._sleepy = False
        self._stress = False
        self._surprise_until = 0.0
        self._happy_until = 0.0
        self._happy_kind = "happy"
        self._next_happy = now + random.uniform(6, 14)
        self.pose_timer = QTimer(self)
        self.pose_timer.setInterval(33)
        self.pose_timer.timeout.connect(self._tick)
        self.pose_timer.start()

        self.set_tab("music")
        self.setGeometry(self._idle_rect())

    # ------------------------------------------------ geometri
    def _screen_geo(self):
        screens = QGuiApplication.screens()
        i = self.cfg.get("screen_index", 0)
        s = screens[i] if 0 <= i < len(screens) else QGuiApplication.primaryScreen()
        return s.geometry()

    def _idle_rect(self) -> QRect:
        g = self._screen_geo()
        return QRect(g.center().x() - IDLE_W // 2, g.top() + self.cfg["top_margin"], IDLE_W, IDLE_H)

    def total_h(self) -> int:
        return self.pages[self.cur].height() + CHROME_H

    def _open_rect(self) -> QRect:
        g = self._screen_geo()
        return QRect(g.center().x() - OPEN_W // 2, g.top() + self.cfg["top_margin"], OPEN_W, self.total_h())

    def _animate_to(self, rect: QRect, ms: int = 300):
        self._anim.stop()
        self._anim.setDuration(ms)
        self._anim.setStartValue(self.geometry())
        self._anim.setEndValue(rect)
        self._anim.start()

    # ------------------------------------------------ buka / tutup
    def expand(self, tab: str | None = None):
        self.collapse_timer.stop()
        self.hover_timer.stop()
        if tab:
            self.set_tab(tab)
        was_open = self._open
        self._open = True
        self.content.setFixedSize(OPEN_W, self.total_h())
        self.content.move(0, 0)
        self._animate_to(self._open_rect())
        if not was_open:
            QTimer.singleShot(140, self._reveal)

    def _reveal(self):
        if not self._open:
            return
        self.content.show()
        self._fade.stop()
        self._fade.setStartValue(self._fx.opacity())
        self._fade.setEndValue(1.0)
        self._fade.start()

    def collapse(self):
        if not self._open:
            return
        self._open = False
        self._fade.stop()
        self._fade.setStartValue(self._fx.opacity())
        self._fade.setEndValue(0.0)
        self._fade.start()
        self._animate_to(self._idle_rect(), 260)

    def _after_fade(self):
        if not self._open and self._fx.opacity() == 0.0:
            self.content.hide()

    def _try_collapse(self):
        if self.underMouse() or (self.notes_page.input.hasFocus() and self.isActiveWindow()):
            self.collapse_timer.start(1500)
            return
        self.collapse()

    def set_tab(self, key: str):
        self.cur = key
        for k, b in self.tabs.items():
            b.set_active(k == key)
        self.stack.setCurrentWidget(self.pages[key])
        self.stack.setFixedHeight(self.pages[key].height())
        if key == "notif":
            self.unread = 0
            self.tabs["notif"].set_badge(0)
        if self._open:
            self.content.setFixedSize(OPEN_W, self.total_h())
            self._animate_to(self._open_rect(), 240)
            if key == "notes":
                QTimer.singleShot(260, self._focus_notes)

    def _focus_notes(self):
        self.activateWindow()
        self.notes_page.input.setFocus()

    # ------------------------------------------------ mouse
    def enterEvent(self, e):
        self.collapse_timer.stop()
        if not self._open and self.cfg.get("hover_expand", True):
            self.hover_timer.start(self.cfg.get("hover_delay_ms", 250))
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.hover_timer.stop()
        if self._open:
            self.collapse_timer.start(self.cfg.get("collapse_delay_ms", 900))
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if not self._open and e.button() == Qt.MouseButton.LeftButton:
            self.expand()
        super().mousePressEvent(e)

    # ------------------------------------------------ data masuk
    def on_stats(self, d: dict):
        self.system_page.set_stats(d)
        # mata menegang jika beban/suhu sangat tinggi (dengan histeresis agar tidak berkedip-kedip)
        load = [d.get("cpu"), d.get("gpu")]
        temps = [d.get("cpu_temp"), d.get("gpu_temp")]
        hot = any(v is not None and v >= 95 for v in load) or any(t is not None and t >= 85 for t in temps)
        calm = all(v is None or v < 80 for v in load) and all(t is None or t < 78 for t in temps)
        if hot:
            self._stress = True
        elif calm:
            self._stress = False

    def on_media(self, d: dict):
        self.music_page.apply(d)
        playing = bool(d.get("session") and d.get("playing"))
        if playing != self.playing:
            self.playing = playing
            if playing:
                self.eq_timer.start()
            else:
                self.eq_timer.stop()
            self.update()

    def on_notify(self, d: dict):
        self.notif_page.add(d)
        self._surprise_until = time.monotonic() + 1.4  # mata kaget
        self._last_move = time.monotonic()
        self._sleepy = False
        self.unread += 1
        self.tabs["notif"].set_badge(self.unread)
        self.set_tab("notif")
        self.expand()
        self.collapse_timer.start(int(self.cfg.get("notif_seconds", 6) * 1000))

    def set_media_hub(self, hub):
        self.media = hub

    def _media_cmd(self, name: str):
        if not self.media:
            return
        if name == "toggle":
            self.media.toggle()
            self.music_page.optimistic_toggle()
        elif name == "next":
            self.media.next()
        elif name == "prev":
            self.media.prev()

    # ------------------------------------------------ kedip
    def _schedule_blink(self):
        QTimer.singleShot(random.randint(3000, 9000), self._blink)

    def _blink(self):
        a = QVariantAnimation(self)
        if self._sleepy:  # kedip lambat saat mengantuk
            a.setDuration(750)
            keys = {0.0: 1.0, 0.5: 0.04, 1.0: 1.0}
        elif random.random() < 0.35:  # kedip ganda
            a.setDuration(620)
            keys = {0.0: 1.0, 0.14: 0.06, 0.30: 1.0, 0.46: 1.0, 0.60: 0.06, 0.78: 1.0, 1.0: 1.0}
        else:
            a.setDuration(240)
            keys = {0.0: 1.0, 0.5: 0.06, 1.0: 1.0}
        for k, v in keys.items():
            a.setKeyValueAt(k, v)
        a.valueChanged.connect(self._set_eye)
        a.finished.connect(self._schedule_blink)
        a.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

    def _set_eye(self, v):
        self.eye_open = float(v)
        self.update()

    # ------------------------------------------------ gambar
    # ------------------------------------------------ ekspresi
    def _pick_mood(self, now: float, moved: bool) -> str:
        if not self.cfg.get("eye_expressions", True):
            return "normal"
        if self._stress:
            return "tense"
        if now < self._surprise_until:
            return "surprised"
        if self._sleepy:
            if moved:  # terbangun
                self._sleepy = False
                self._surprise_until = now + 0.9
                return "surprised"
            return "sleepy"
        if not self.playing:
            self._happy_until = 0.0
        elif now >= self._next_happy:
            self._happy_until = now + random.uniform(2.5, 4.0)
            self._happy_kind = "wink" if random.random() < 0.3 else "happy"
            self._next_happy = self._happy_until + random.uniform(8, 18)
        if now < self._happy_until:
            return self._happy_kind
        return "normal"

    def _tick(self):
        now = time.monotonic()
        pos = QCursor.pos()
        moved = (pos - self._last_pos).manhattanLength() > 2
        if moved:
            self._last_pos = pos
            self._last_move = now
        if (not self._sleepy and not self._stress and not self._open
                and now - self._last_move > 180):
            self._sleepy = True

        mood = self._pick_mood(now, moved)
        changed = False
        for k, v in POSES[mood].items():
            c = self.pose[k]
            d = v - c
            if abs(d) > 0.004:
                self.pose[k] = c + d * 0.25
                changed = True
            elif d:
                self.pose[k] = v
                changed = True

        # arah pandang mengikuti kursor
        if not self.cfg.get("eye_expressions", True):
            tx = ty = 0.0
        elif self._sleepy:
            tx, ty = 0.0, 0.8
        else:
            g = self.geometry()
            if self._open:
                ex, ey, sx, sy, mx, my = g.x() + 29, g.y() + 28, 200.0, 150.0, 2.0, 1.2
            else:
                ex, ey, sx, sy, mx, my = g.center().x(), g.center().y(), 500.0, 300.0, 3.0, 1.6
            tx = max(-1.0, min(1.0, (pos.x() - ex) / sx)) * mx
            ty = max(-1.0, min(1.0, (pos.y() - ey) / sy)) * my
        for i, t in enumerate((tx, ty)):
            d = t - self.gaze[i]
            if abs(d) > 0.01:
                self.gaze[i] += d * 0.2
                changed = True

        # mengangguk mengikuti irama saat musik diputar (hanya di mode garis)
        bob = 0.8 * math.sin(now * 11.3) if (self.playing and not self._open
                                              and self.cfg.get("eye_expressions", True)) else 0.0
        if abs(bob - self._bob) > 0.01:
            self._bob = bob
            changed = True
        if changed:
            self.update()

    def _eye_shape(self, w: float, h: float, side: int, smile: float) -> QPainterPath:
        P = self.pose
        w *= P["sx"]
        h = max(1.4, h * P["sy"] * self.eye_open)
        e = QPainterPath()
        e.addEllipse(QPointF(0, 0), w / 2, h / 2)
        if smile > 0.02:  # mata tersenyum: bentuk busur "^"
            cut = QPainterPath()
            cut.addEllipse(QPointF(0, h * (1.05 - 0.5 * smile)), w / 2 * 1.08, h / 2 * 1.05)
            e = e.subtracted(cut)
        lid, tilt = P["lid"], P["tilt"]
        if lid > 0.02 or abs(tilt) > 0.02:  # kelopak atas: turun (mengantuk) / miring (tegang)
            d = -side
            base = -h / 2 + lid * 0.6 * h
            k = tilt * 0.55 * h

            def yl(x):
                return base + k * (d * x / (w / 2))

            cut = QPainterPath()
            cut.addPolygon(QPolygonF([QPointF(-w, -h * 2), QPointF(w, -h * 2),
                                      QPointF(w, yl(w)), QPointF(-w, yl(-w))]))
            cut.closeSubpath()
            e = e.subtracted(cut)
        return e

    def _eye(self, p: QPainter, cx, cy, ew, eh, alpha, side=-1, smile=0.0):
        cx, cy = cx + self.gaze[0], cy + self.gaze[1] + self._bob
        p.setOpacity(alpha)
        if T.get("ripple") and self.eye_open < 0.98:  # riak halus saat berkedip
            k = 1.0 - self.eye_open
            ring = QColor(AMBER)
            ring.setAlphaF(0.55 * k)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(ring, 1.0))
            p.drawEllipse(QPointF(cx, cy), ew / 2 + 2 + 4 * k, eh / 2 + 1 + 2.5 * k)
        p.save()
        p.translate(cx, cy)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(WHITE)
        p.drawPath(self._eye_shape(ew, eh, side, smile))
        p.restore()
        p.setOpacity(1.0)
        p.setOpacity(1.0)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        r = min(28.0, h / 2)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), r, r)
        p.fillPath(path, BG)
        p.setPen(QPen(HAIR, 1))
        p.drawPath(path)

        prog = max(0.0, min(1.0, (w - IDLE_W) / (OPEN_W - IDLE_W)))
        idle_a = max(0.0, 1.0 - prog * 2)
        open_a = max(0.0, prog * 2 - 1)
        if idle_a > 0:
            cy = h / 2
            self._eye(p, w / 2 - 12, cy, 14, 11, idle_a, -1, self.pose["sl"])
            self._eye(p, w / 2 + 12, cy, 14, 11, idle_a, 1, self.pose["sr"])
            if self.playing:
                p.setOpacity(idle_a)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(AMBER)
                t = time.monotonic()
                for i, speed in enumerate((6.5, 5.0, 8.2)):
                    bh = 9 * (0.3 + 0.7 * abs(math.sin(t * speed + i)))
                    p.drawRoundedRect(QRectF(w - 20 + i * 4, cy + 4.5 - bh, 2, bh), 1, 1)
                p.setOpacity(1.0)
        if open_a > 0:
            self._eye(p, 29, 28, 18, 14, open_a, -1, self.pose["sl"])
