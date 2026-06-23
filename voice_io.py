"""
Голосовой ввод/вывод для агента.

STT: Vosk (офлайн). Модель скачивается ВРУЧНУЮ с https://alphacephei.com/vosk/models
(не Hugging Face — другой хост, обходит блокировки HF CDN) и кладётся в папку,
путь к которой указан в VOSK_MODEL_PATH ниже (или через переменную окружения).

Запись через класс Recorder: старт/стоп не блокируют — управляются снаружи
(см. main_loop.py: /talk запускает запись в фоне, обычный Enter в консоли
её останавливает).

TTS: Silero (офлайн, нейросетевой, звучит заметно естественнее Piper/espeak
для русского языка). Модель грузится через torch.hub при первом вызове
(кешируется в ~/.cache/torch/hub) — хостинг на GitHub, не Hugging Face.
Озвучивает только финальный ответ агента, не Thought/Action-трейс.

Установка:
    pip install vosk torch sounddevice numpy --break-system-packages

STT-модель (вручную, см. https://alphacephei.com/vosk/models):
    mkdir -p ~/models
    unzip vosk-model-small-ru-0.22.zip -d ~/models/
    # путь получится ~/models/vosk-model-small-ru-0.22
    # если лежит не там — export VOSK_MODEL_PATH=...

TTS-голос: ничего скачивать руками не нужно — модель Silero сама
скачается через torch.hub при первом вызове speak() (один раз, ~50МБ).
Доступные дикторы (v4_ru): aidar, baya, kseniya, xenia, eugene, random.
Выбрать диктора:
    export SILERO_SPEAKER=xenia

Linux: для sounddevice нужен portaudio: sudo pacman -S portaudio (Arch)
                                         sudo apt install portaudio19-dev (Debian/Ubuntu)
       для воспроизведения через sounddevice нужен рабочий ALSA/PulseAudio
       (обычно уже есть из коробки).

Числа и латиница (английские слова/аббревиатуры) перед озвучкой нормализуются
вручную (_normalize_for_speech) — сам Silero их не разворачивает.

Установка:
    pip install vosk torch sounddevice numpy num2words --break-system-packages
"""

import json
import os
import re
import tempfile
import wave
from pathlib import Path

SAMPLE_RATE = 16000

_DEFAULT_MODEL_PATH = os.path.expanduser("~/models/vosk-model-small-ru-0.22")

_vosk_model   = None
_silero_model = None

# Частые технические акронимы — произношение по буквам "как слышится"
_ACRONYMS = {
    "CPU": "си пи ю", "GPU": "джи пи ю", "RAM": "рам", "ROM": "ром",
    "SSD": "эс эс ди", "HDD": "эйч ди ди", "API": "эй пи ай",
    "URL": "ю эр эл", "OS": "оу эс", "AI": "эй ай", "USB": "ю эс би",
    "HTTP": "эйч ти ти пи", "HTTPS": "эйч ти ти пи эс", "IP": "ай пи",
    "PDF": "пи ди эф", "ID": "ай ди", "OK": "окей", "TTS": "ти ти эс",
    "STT": "эс ти ти", "LLM": "эл эл эм", "JSON": "джейсон", "SQL": "эс кью эл",
}

# Фонетичные названия латинских букв (запасной вариант для неизвестной латиницы)
_LETTER_NAMES = {
    "A": "эй", "B": "би", "C": "си", "D": "ди", "E": "и", "F": "эф",
    "G": "джи", "H": "эйч", "I": "ай", "J": "джей", "K": "кей", "L": "эл",
    "M": "эм", "N": "эн", "O": "оу", "P": "пи", "Q": "кью", "R": "ар",
    "S": "эс", "T": "ти", "U": "ю", "V": "ви", "W": "дабл-ю", "X": "икс",
    "Y": "уай", "Z": "зед",
}


def _latin_to_speech(word: str) -> str:
    upper = word.upper()
    if upper in _ACRONYMS:
        return _ACRONYMS[upper]
    # Любая нераспознанная латиница — спеллим по буквам (неидеально, но разборчиво)
    return " ".join(_LETTER_NAMES.get(c, c) for c in upper)


def _percent_word(n: int) -> str:
    """Склонение слова 'процент' под число: 1 процент, 2 процента, 5 процентов."""
    n_abs = abs(n)
    last_two = n_abs % 100
    last = n_abs % 10
    if 11 <= last_two <= 14:
        return "процентов"
    if last == 1:
        return "процент"
    if 2 <= last <= 4:
        return "процента"
    return "процентов"


def _normalize_for_speech(text: str) -> str:
    """Разворачивает числа, %, и латиницу в фонетичное произношение."""
    from num2words import num2words

    def _percent_repl(m: re.Match) -> str:
        try:
            n = int(m.group(1))
            return f"{num2words(n, lang='ru')} {_percent_word(n)}"
        except Exception:
            return m.group(0)

    def _num_repl(m: re.Match) -> str:
        try:
            return num2words(int(m.group(0)), lang="ru")
        except Exception:
            return m.group(0)

    text = re.sub(r"(\d+)\s*%", _percent_repl, text)
    text = re.sub(r"\d+", _num_repl, text)
    text = re.sub(r"[A-Za-z]+", lambda m: _latin_to_speech(m.group(0)), text)
    return text

def _get_vosk_model():
    global _vosk_model
    if _vosk_model is None:
        from vosk import Model

        model_path = os.environ.get("VOSK_MODEL_PATH", _DEFAULT_MODEL_PATH)
        if not Path(model_path).exists():
            raise FileNotFoundError(
                f"Модель Vosk не найдена: {model_path}\n"
                "Скачай вручную с https://alphacephei.com/vosk/models, "
                "распакуй и/или укажи путь через VOSK_MODEL_PATH."
            )
        _vosk_model = Model(model_path)
    return _vosk_model


def _get_silero_model():
    """Грузит модель Silero TTS (один раз, кешируется torch.hub)."""
    global _silero_model
    if _silero_model is None:
        import torch

        torch.set_num_threads(4)
        model, _example_text = torch.hub.load(
            repo_or_dir="snakers4/silero-models",
            model="silero_tts",
            language="ru",
            speaker="v4_ru",
        )
        model.to(torch.device("cpu"))
        _silero_model = model
    return _silero_model


def speak(text: str) -> None:
    """Озвучивает текст через Silero (синхронно, блокирует до конца фразы)."""
    text = _clean(text)
    text = _normalize_for_speech(text)
    if not text:
        return

    speaker = os.environ.get("SILERO_SPEAKER", "xenia")
    sample_rate = 48000

    try:
        model = _get_silero_model()
        audio = model.apply_tts(text=text, speaker=speaker, sample_rate=sample_rate)
    except Exception as e:
        print(f"[TTS ошибка]: {e}")
        return

    _play_audio(audio.numpy(), sample_rate)


def _play_audio(audio, sample_rate: int) -> None:
    """Проигрывает float32-массив через sounddevice (блокирует до конца)."""
    import sounddevice as sd

    sd.play(audio, sample_rate)
    sd.wait()


class Recorder:
    """
    Неблокирующая запись с микрофона. Старт и стоп вызываются снаружи —
    управление тем, "когда стоп", остаётся за вызывающим кодом
    (в main_loop.py это обычный Enter в консоли).
    """

    def __init__(self):
        self._frames = []
        self._stream = None

    def start(self) -> None:
        import sounddevice as sd

        self._frames = []

        def callback(indata, _frames, _time, _status):
            self._frames.append(indata.copy())

        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="int16", callback=callback
        )
        self._stream.start()

    def stop(self) -> Path:
        import numpy as np

        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        audio = (
            np.concatenate(self._frames, axis=0)
            if self._frames else np.zeros((0, 1), dtype="int16")
        )

        path = Path(tempfile.mktemp(suffix=".wav"))
        with wave.open(str(path), "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(SAMPLE_RATE)
            f.writeframes(audio.tobytes())
        return path


def transcribe(wav_path: Path) -> str:
    """Распознаёт речь из wav-файла (16kHz, mono, 16-bit) через Vosk."""
    from vosk import KaldiRecognizer

    model = _get_vosk_model()
    rec = KaldiRecognizer(model, SAMPLE_RATE)

    text_parts = []
    with wave.open(str(wav_path), "rb") as wf:
        while True:
            data = wf.readframes(4000)
            if not data:
                break
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                if result.get("text"):
                    text_parts.append(result["text"])

    final = json.loads(rec.FinalResult())
    if final.get("text"):
        text_parts.append(final["text"])

    try:
        wav_path.unlink()
    except OSError:
        pass

    return " ".join(text_parts).strip()


# ─── TTS ────────────────────────────────────────────────────────────────────

_MD_NOISE = re.compile(r"[*_`#>]+|```.*?```", re.DOTALL)


def _clean(text: str) -> str:
    """Убирает markdown-мусор перед озвучкой."""
    text = _MD_NOISE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()