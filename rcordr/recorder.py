"""Grabación de pantalla (ffmpeg gdigrab) + sonido del ordenador (WASAPI loopback).

El vídeo se graba con ffmpeg a un .mkv temporal y el audio con PyAudioWPatch
a un .raw temporal. Al parar se combinan en un .mp4 H.264 + AAC compatible
con WhatsApp. La sincronía se calcula con la marca de tiempo real del primer
fotograma que informa ffmpeg ("start: ...") y la del inicio del audio.
"""

import re
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

import pyaudiowpatch as pyaudio

from .config import TEMP_DIR

CREATE_NO_WINDOW = 0x08000000


def ffmpeg_exe() -> str:
    """Ruta del ffmpeg incluido en imageio-ffmpeg (verificado por hash al instalar).

    No se busca en el PATH ni se acepta la variable IMAGEIO_FFMPEG_EXE, para
    que no se pueda sustituir por otro ejecutable.
    """
    import imageio_ffmpeg
    binaries = Path(imageio_ffmpeg.__file__).parent / "binaries"
    found = sorted(binaries.glob("ffmpeg-win*.exe"))
    if not found:
        raise RuntimeError(f"No se encontró ffmpeg en {binaries}")
    return str(found[-1])


class AudioCapture(threading.Thread):
    """Graba lo que suena por la salida predeterminada (PCM s16le intercalado).

    El loopback de WASAPI no entrega datos mientras no suena nada, lo que
    acortaría el audio y lo desincronizaría. Para evitarlo se reproduce
    silencio en esa misma salida: así el flujo es continuo.
    """

    CHUNK = 1024

    def __init__(self, path: Path):
        super().__init__(daemon=True, name="audio")
        self.path = path
        self.rate = 48000
        self.channels = 2
        self.start_time: float | None = None
        self.error: Exception | None = None
        self.ready = threading.Event()
        self._stop = threading.Event()

    def run(self):
        pa = pyaudio.PyAudio()
        keepalive = capture = None
        try:
            loopback = pa.get_default_wasapi_loopback()
            self.rate = int(loopback["defaultSampleRate"])
            self.channels = loopback["maxInputChannels"]
            speaker = pa.get_device_info_by_index(
                pa.get_host_api_info_by_type(pyaudio.paWASAPI)["defaultOutputDevice"])

            silence = bytes(2 * self.channels * self.CHUNK)
            keepalive = pa.open(
                format=pyaudio.paInt16, channels=self.channels, rate=self.rate,
                output=True, output_device_index=speaker["index"],
                frames_per_buffer=self.CHUNK,
                stream_callback=lambda *a: (silence, pyaudio.paContinue))
            capture = pa.open(
                format=pyaudio.paInt16, channels=self.channels, rate=self.rate,
                input=True, input_device_index=loopback["index"],
                frames_per_buffer=self.CHUNK)
            self.start_time = time.time()
            self.ready.set()
            with open(self.path, "wb") as f:
                while not self._stop.is_set():
                    f.write(capture.read(self.CHUNK, exception_on_overflow=False))
        except Exception as e:  # sin dispositivo, se desconectó, etc.
            self.error = e
        finally:
            self.ready.set()
            for stream in (capture, keepalive):
                if stream:
                    stream.stop_stream()
                    stream.close()
            pa.terminate()

    def stop(self):
        self._stop.set()
        self.join(5)


class _Session:
    """Estado de una grabación (independiente de la siguiente)."""

    def __init__(self):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.tmp_video = TEMP_DIR / f"{stamp}.mkv"
        self.tmp_audio = TEMP_DIR / f"{stamp}.raw"
        self.proc: subprocess.Popen | None = None
        self.audio: AudioCapture | None = None
        self.video_start: float | None = None
        self.log: list[str] = []
        self.ready = threading.Event()

    def read_log(self):
        for raw in self.proc.stderr:
            line = raw.decode("utf-8", "replace").rstrip()
            self.log.append(line)
            if self.video_start is None:
                m = re.search(r"start: (\d+\.\d+)", line)
                if m:  # gdigrab marca los fotogramas con la hora real del sistema
                    self.video_start = float(m.group(1))
            if line.lstrip().startswith("Output #0"):
                self.ready.set()
        self.ready.set()

    def tail(self, n=5) -> str:
        return "\n".join(self.log[-n:])


class Recorder:
    def __init__(self):
        self.session: _Session | None = None

    @property
    def recording(self) -> bool:
        return self.session is not None

    def start(self, rect: dict, fps: int, with_audio: bool, max_height: int) -> bool:
        """Empieza a grabar. Devuelve True si se está grabando también el audio."""
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        s = _Session()

        # El audio arranca antes para que cubra el primer fotograma
        if with_audio:
            s.audio = AudioCapture(s.tmp_audio)
            s.audio.start()
            s.audio.ready.wait(3)
            if s.audio.error or s.audio.start_time is None:
                s.audio.stop()
                s.audio = None

        # Dimensiones pares (requisito de H.264 yuv420p); reduce a max_height si hace falta
        w, h = rect["width"] - rect["width"] % 2, rect["height"] - rect["height"] % 2
        vf = f"scale=-2:'trunc(min(ih,{max_height})/2)*2':flags=lanczos"
        cmd = [
            ffmpeg_exe(), "-hide_banner", "-nostats", "-y",
            "-f", "gdigrab", "-framerate", str(fps), "-draw_mouse", "1",
            "-offset_x", str(rect["left"]), "-offset_y", str(rect["top"]),
            "-video_size", f"{w}x{h}", "-i", "desktop",
            "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
            "-pix_fmt", "yuv420p", "-g", str(fps * 2),
            str(s.tmp_video),
        ]
        s.proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW,
        )
        threading.Thread(target=s.read_log, daemon=True).start()
        s.ready.wait(5)
        if s.proc.poll() is not None:
            if s.audio:
                s.audio.stop()
            s.tmp_video.unlink(missing_ok=True)
            s.tmp_audio.unlink(missing_ok=True)
            raise RuntimeError(f"ffmpeg no pudo iniciar la grabación:\n{s.tail()}")
        self.session = s
        return s.audio is not None

    def stop(self, out_dir: Path, on_done):
        """Para la grabación y genera el .mp4 en segundo plano.

        on_done(path, error) se llama desde un hilo secundario.
        """
        s, self.session = self.session, None

        def finish():
            try:
                try:
                    s.proc.stdin.write(b"q")
                    s.proc.stdin.flush()
                except OSError:
                    pass
                try:
                    s.proc.wait(15)
                except subprocess.TimeoutExpired:
                    s.proc.kill()
                if s.audio:
                    s.audio.stop()
                on_done(_mux(s, out_dir), None)
            except Exception as e:
                on_done(None, e)
            finally:
                s.tmp_video.unlink(missing_ok=True)
                s.tmp_audio.unlink(missing_ok=True)

        threading.Thread(target=finish, daemon=True, name="mux").start()


def clean_temp(out_dir: Path) -> list[Path]:
    """Vacía la carpeta temporal (restos de un cierre inesperado).

    Si queda un vídeo a medias no se pierde: se pasa a la carpeta de vídeos
    como video_recuperado_*.mp4 (sin sonido). Devuelve los vídeos recuperados.
    Llamar solo cuando no hay ninguna grabación en curso.
    """
    recovered = []
    if not TEMP_DIR.exists():
        return recovered
    for mkv in sorted(TEMP_DIR.glob("*.mkv")):
        if mkv.stat().st_size == 0:
            continue
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"video_recuperado_{mkv.stem}.mp4"
        r = subprocess.run(
            [ffmpeg_exe(), "-hide_banner", "-y", "-i", str(mkv), "-c", "copy",
             "-movflags", "+faststart", str(out)],
            capture_output=True, creationflags=CREATE_NO_WINDOW)
        if r.returncode == 0:
            recovered.append(out)
        else:
            out.unlink(missing_ok=True)
    for f in TEMP_DIR.iterdir():
        if f.is_file():
            f.unlink(missing_ok=True)
    return recovered


def _mux(s: _Session, out_dir: Path) -> Path:
    if not s.tmp_video.exists() or s.tmp_video.stat().st_size == 0:
        raise RuntimeError("La grabación está vacía.\n" + s.tail())
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"video_{datetime.now():%Y%m%d_%H%M%S}.mp4"

    cmd = [ffmpeg_exe(), "-hide_banner", "-y", "-i", str(s.tmp_video)]
    if s.audio and s.tmp_audio.exists() and s.tmp_audio.stat().st_size > 0:
        cmd += ["-f", "s16le", "-ar", str(s.audio.rate), "-ac", str(s.audio.channels),
                "-i", str(s.tmp_audio)]
        offset = (s.video_start - s.audio.start_time) if s.video_start else 0.0
        if offset >= 0:  # lo normal: el audio empezó antes, se recorta
            af = f"atrim=start={offset:.3f},asetpts=PTS-STARTPTS"
        else:
            af = f"adelay={int(-offset * 1000)}:all=1"
        cmd += ["-map", "0:v", "-map", "1:a", "-af", af, "-c:a", "aac", "-b:a", "160k", "-ac", "2"]
    cmd += ["-c:v", "copy", "-movflags", "+faststart", str(out)]

    r = subprocess.run(cmd, capture_output=True, creationflags=CREATE_NO_WINDOW)
    if r.returncode != 0:
        tail = r.stderr.decode("utf-8", "replace").strip().splitlines()[-5:]
        raise RuntimeError("Error al generar el MP4:\n" + "\n".join(tail))
    return out
