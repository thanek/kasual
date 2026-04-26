"""VIDEO mode — fullscreen video playback."""

import threading
from pathlib import Path
from urllib.request import urlopen

import qtawesome as qta
from PyQt6.QtCore import Qt, QRect, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtMultimediaWidgets import QGraphicsVideoItem
from PyQt6.QtWidgets import QFrame, QGraphicsScene, QGraphicsView, QVBoxLayout, QWidget


_ACCENT = QColor(136, 192, 208)
_BAR_COLOR = QColor(0, 0, 0, 200)
_BAR_H = 90
_MARGIN = 64
_AUDIO_CIRCLE_COLOR = QColor(70, 70, 70)
_AUDIO_ICON_COLOR = QColor(25, 25, 25)


def _fmt_time(ms: int) -> str:
    s = ms // 1000
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _paint_controls(painter: QPainter, w: int, h: int,
                    player: QMediaPlayer, audio: QAudioOutput) -> None:
    muted = audio.isMuted()
    duration = player.duration()
    position = player.position()
    is_playing = player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    bar_y = h - _BAR_H
    painter.fillRect(QRect(0, bar_y, w, _BAR_H), _BAR_COLOR)

    prog_y = bar_y + 14
    prog_w = w - 2 * _MARGIN
    painter.fillRect(QRect(_MARGIN, prog_y, prog_w, 5), QColor(255, 255, 255, 50))
    if duration > 0:
        filled = int(prog_w * position / duration)
        painter.fillRect(QRect(_MARGIN, prog_y, filled, 5), _ACCENT)

    f = QFont()
    f.setPointSize(14)
    painter.setFont(f)
    painter.setPen(QColor(236, 239, 244))
    painter.drawText(QRect(_MARGIN, prog_y + 12, prog_w, 32),
                     Qt.AlignmentFlag.AlignCenter,
                     f"{_fmt_time(position)}  /  {_fmt_time(duration)}")

    f2 = QFont()
    f2.setPointSize(22)
    painter.setFont(f2)
    painter.drawText(QRect(0, bar_y, _MARGIN, _BAR_H),
                     Qt.AlignmentFlag.AlignCenter,
                     "⏸" if is_playing else "▶")
    painter.drawText(QRect(w - _MARGIN, bar_y, _MARGIN, _BAR_H),
                     Qt.AlignmentFlag.AlignCenter,
                     "🔇" if muted else "🔊")


class _VideoView(QGraphicsView):
    def __init__(self, player: QMediaPlayer, audio: QAudioOutput, parent: QWidget,
                 is_audio: bool = False) -> None:
        super().__init__(parent)
        self._player = player
        self._audio = audio
        self._controls_visible = False
        self._is_audio = is_audio
        self._audio_pixmap: QPixmap | None = None
        if is_audio:
            # fa5s glyph U+F8CF (music-note, FA5 Pro); falls back to fa5s.music in free builds
            self._audio_icon = qta.icon("fa5s.music", color=_AUDIO_ICON_COLOR)

        scene = QGraphicsScene(self)
        self.setScene(scene)

        self._item = QGraphicsVideoItem()
        scene.addItem(self._item)
        player.setVideoOutput(self._item)

        self.setBackgroundBrush(QColor(0, 0, 0))
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._item.nativeSizeChanged.connect(lambda _: self._fit())

    def set_audio_pixmap(self, pix: QPixmap) -> None:
        self._audio_pixmap = pix
        self.viewport().update()

    def _fit(self) -> None:
        self.fitInView(self._item, Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit()

    def _draw_audio_bg(self, painter: QPainter) -> None:
        vw = self.viewport().width()
        vh = self.viewport().height()
        r = min(vw, vh) * 9 // 32
        cx, cy = vw // 2, vh // 2

        if self._audio_pixmap and not self._audio_pixmap.isNull():
            scaled = self._audio_pixmap.scaled(
                r * 2, r * 2,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter.drawPixmap(cx - scaled.width() // 2, cy - scaled.height() // 2, scaled)
        else:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(_AUDIO_CIRCLE_COLOR)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)
            icon_size = r * 5 // 6
            self._audio_icon.paint(
                painter,
                QRect(cx - icon_size // 2, cy - icon_size // 2, icon_size, icon_size),
            )

    def drawForeground(self, painter: QPainter, rect) -> None:
        painter.save()
        painter.resetTransform()
        if self._is_audio:
            self._draw_audio_bg(painter)
        if self._controls_visible:
            _paint_controls(painter, self.viewport().width(), self.viewport().height(),
                            self._player, self._audio)
        painter.restore()


class VideoMode(QWidget):
    _thumbnail_ready = pyqtSignal(bytes)

    def __init__(self, source: 'Path | str', is_audio: bool = False,
                 thumbnail: 'Path | str | None' = None):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._audio = QAudioOutput(self)
        self._player = QMediaPlayer(self)
        self._player.setAudioOutput(self._audio)

        self._view = _VideoView(self._player, self._audio, self, is_audio=is_audio)
        layout.addWidget(self._view)

        if isinstance(source, Path):
            qurl = QUrl.fromLocalFile(str(source.resolve()))
        else:
            qurl = QUrl(source)
        self._player.setSource(qurl)
        self._player.play()

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(3000)
        self._hide_timer.timeout.connect(self._hide_controls)

        self._player.positionChanged.connect(
            lambda _: self._view.viewport().update() if self._view._controls_visible else None
        )
        self._player.mediaStatusChanged.connect(self._on_media_status)

        if is_audio and thumbnail is not None:
            self._load_thumbnail(thumbnail)

    def _load_thumbnail(self, thumbnail: 'Path | str') -> None:
        if isinstance(thumbnail, Path):
            pix = QPixmap(str(thumbnail))
            if not pix.isNull():
                self._view.set_audio_pixmap(pix)
        elif isinstance(thumbnail, str) and thumbnail:
            self._thumbnail_ready.connect(self._on_thumbnail_data)
            threading.Thread(
                target=self._fetch_thumbnail,
                args=(thumbnail,),
                daemon=True,
            ).start()

    def _fetch_thumbnail(self, url: str) -> None:
        try:
            with urlopen(url, timeout=5) as resp:
                data = resp.read()
        except Exception:
            data = b""
        self._thumbnail_ready.emit(data)

    def _on_thumbnail_data(self, data: bytes) -> None:
        if not data:
            return
        pix = QPixmap()
        if pix.loadFromData(data) and not pix.isNull():
            self._view.set_audio_pixmap(pix)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.black)

    def handle_key(self, key: int) -> bool:
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._toggle_pause()
            return True
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Minus):
            self._seek(-5000)
            return True
        if key in (Qt.Key.Key_Right, Qt.Key.Key_Equal, Qt.Key.Key_Plus):
            self._seek(+5000)
            return True
        if key == Qt.Key.Key_H:
            self._toggle_mute()
            return True
        if key == Qt.Key.Key_Escape:
            if self._view._controls_visible:
                self._hide_controls()
                return True
            return False
        return False

    def set_listener(self, listener) -> None:
        pass

    def stop(self) -> None:
        self._player.stop()

    def _restart_hide_timer_if_playing(self) -> None:
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._hide_timer.start()

    def _toggle_pause(self) -> None:
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
            self._show_controls()
            self._hide_timer.stop()
        else:
            self._player.play()
            self._show_controls()
            self._restart_hide_timer_if_playing()

    def _toggle_mute(self) -> None:
        self._audio.setMuted(not self._audio.isMuted())
        self._show_controls()
        self._restart_hide_timer_if_playing()

    def _seek(self, delta_ms: int) -> None:
        pos = max(0, min(self._player.position() + delta_ms, self._player.duration()))
        self._player.setPosition(pos)
        self._show_controls()
        self._restart_hide_timer_if_playing()

    def _show_controls(self) -> None:
        self._view._controls_visible = True
        self._view.viewport().update()

    def _hide_controls(self) -> None:
        self._hide_timer.stop()
        self._view._controls_visible = False
        self._view.viewport().update()

    def _on_media_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._player.pause()
            self._show_controls()
            self._hide_timer.stop()
