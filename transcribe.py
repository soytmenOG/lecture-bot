"""Расшифровка звука (faster-whisper). Всё локально на сервере.

Основной режим — вторая видеокарта (на первой работает Ollama). Если её нет —
процессор: точно, но примерно в 1,5 раза дольше самой записи.
"""
import logging
import os
import re
import subprocess
import threading

import numpy as np

log = logging.getLogger("transcribe")

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "mobiuslabsgmbh/faster-whisper-large-v3-turbo")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "auto")     # auto | cuda | cpu
WHISPER_INDEX = int(os.getenv("WHISPER_INDEX", "1"))     # номер карты при CUDA_DEVICE_ORDER=PCI_BUS_ID
WHISPER_CPU_THREADS = int(os.getenv("WHISPER_CPU_THREADS", "8"))
SR = 16000

_model = None
_device = "?"
_lock = threading.Lock()


class Cancelled(Exception):
    pass


def device() -> str:
    return _device


def kind() -> str:
    """gpu или cpu — для сообщений пользователю на его языке."""
    return "cpu" if _device == "процессор" else "gpu"


def load() -> None:
    global _model, _device
    from faster_whisper import WhisperModel
    if WHISPER_DEVICE in ("auto", "cuda"):
        try:
            _model = WhisperModel(WHISPER_MODEL, device="cuda", device_index=WHISPER_INDEX, compute_type="int8")
            _device = f"видеокарта {WHISPER_INDEX}"
            log.info("Whisper на видеокарте %s", WHISPER_INDEX)
            return
        except Exception as e:  # noqa: BLE001
            log.warning("видеокарта %s недоступна (%s) — работаю на процессоре", WHISPER_INDEX, e)
    _model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8", cpu_threads=WHISPER_CPU_THREADS)
    _device = "процессор"


def decode(path: str) -> np.ndarray:
    """Любое аудио/видео → 16 кГц моно float32 через ffmpeg (видеодорожка отбрасывается)."""
    raw = subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-i", path, "-vn", "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"],
        capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


def media_seconds(path: str) -> float:
    """Длительность по заголовку файла (быстро, без декодирования); 0 — если не удалось."""
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                             capture_output=True, text=True, timeout=60).stdout.strip()
        return float(out)
    except Exception:  # noqa: BLE001
        return 0.0


_WORD = re.compile(r"[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё\-]{4,}")


def transcribe(audio: np.ndarray, on_progress=None, cancelled=None) -> tuple[str, list[str], str]:
    """Возвращает (текст по абзацам, сомнительные слова, язык записи — код Whisper: ru, en…).

    on_progress(доля 0..1) вызывается из рабочего потока; cancelled() → True прерывает работу.
    """
    total = max(len(audio) / SR, 1)
    with _lock:
        segs, info = _model.transcribe(audio, language=None, beam_size=5, vad_filter=True,
                                    word_timestamps=True, condition_on_previous_text=False)
        paras, cur, last_end = [], [], 0.0
        doubt: dict[str, float] = {}
        for s in segs:
            if cancelled and cancelled():
                raise Cancelled
            # новая смысловая пауза или длинный абзац → новый абзац
            if cur and (s.start - last_end > 2.5 or sum(len(x) for x in cur) > 900):
                paras.append(" ".join(cur))
                cur = []
            cur.append(s.text.strip())
            last_end = s.end
            for w in s.words or []:
                word = w.word.strip(" .,!?:;«»\"()—")
                if w.probability < 0.5 and _WORD.fullmatch(word):
                    key = word.lower()
                    doubt[key] = min(doubt.get(key, 1.0), w.probability)
            if on_progress:
                on_progress(min(s.end / total, 1.0))
        if cur:
            paras.append(" ".join(cur))
    words = [w for w, _ in sorted(doubt.items(), key=lambda x: x[1])][:30]
    return "\n\n".join(p for p in paras if p), words, info.language
