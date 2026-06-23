"""
MainLoop — основной цикл взаимодействия.

Inner voice: раз в INNER_TIMEOUT секунд агент получает случайный внутренний
промпт и может что-то сделать или сохранить. Результат печатается в терминал
только если не пустой и не IDLE.

Команды пользователя:
  /inner on|off     — включить/выключить inner voice (фоновые мысли агента)
  /timeout <сек>    — сменить интервал inner voice (например /timeout 60)
  /inject <текст>   — вручную запустить inner voice с произвольным промптом
  /talk             — голосовой ввод: начинает запись с микрофона.
                       Любой следующий Enter в консоли (даже пустой) — стоп записи.
  /speak on|off     — озвучивать финальные ответы агента (TTS)
"""

import random
import threading
import queue

from agent import Agent

INNER_TIMEOUT = 300  # секунд между срабатываниями inner voice

INNER_PROMPTS = [
    "Check your current focus in memory. Is there anything worth doing or noting right now?",
    "Review what you've learned recently. Any patterns or insights worth saving?",
    "Is there anything incomplete or worth revisiting from recent conversations?",
    "What would you explore if there were no tasks right now?",
    "Think freely. Any random thought, question or observation worth recording?",
    "Look at your memory and recent sessions. Is anything outdated or worth cleaning up?",
    "Is there a tool you wish you had? If yes — outline what it would do.",
]


class MainLoop:
    def __init__(self, agent: Agent, timeout: int = INNER_TIMEOUT):
        self.agent         = agent
        self.timeout       = timeout
        self._inner_on     = True   # фоновый "внутренний голос" агента
        self._speak_on     = False  # озвучивать финальные ответы (TTS)
        self._recorder      = None  # активный voice_io.Recorder, если идёт запись
        self._input_queue: queue.Queue = queue.Queue()

    def run(self):
        self._start_input_thread()
        print("Agent ready. Empty line = exit.")
        print(
            f"Inner voice: every {self.timeout}s. "
            f"Commands: /inner on|off, /timeout <s>, /inject <text>, /talk, /speak on|off\n"
        )

        try:
            while True:
                try:
                    user_input = self._input_queue.get(timeout=self.timeout)
                except queue.Empty:
                    if self._inner_on:
                        self._inner_voice()
                    continue

                # ── идёт запись голоса: ЛЮБОЙ ввод (включая пустую строку) ──
                # ── трактуется как сигнал "стоп записи", а не как обычный ──
                # ── текст или команда выхода.                              ──
                if self._recorder is not None:
                    self._finish_voice_turn()
                    continue

                if not user_input:
                    print("Bye.")
                    break

                # ── встроенные команды ────────────────────────────────────
                if user_input.startswith("/"):
                    self._handle_command(user_input)
                    continue

                self._process_turn(user_input)

        except KeyboardInterrupt:
            print("\nBye.")

    # ─── обработка одного хода (текстового или голосового) ───────────────────

    def _process_turn(self, user_input: str):
        print("[думает...]")
        answer = self.agent.respond(user_input)
        print(f"\nАгент: {answer}\n[готов]\n")
        if self._speak_on:
            self._speak(answer)

    # ─── inner voice ─────────────────────────────────────────────────────────

    def _inner_voice(self, prompt: str | None = None):
        prompt = prompt or random.choice(INNER_PROMPTS)
        print(f"\n[inner voice] {prompt}\n[inner voice думает...]")

        result = self.agent.inject(prompt)

        if result and "IDLE" not in result.upper():
            print(f"[inner voice] → {result}")
        else:
            print("[inner voice] → (тихо)")

    # ─── голосовой ввод/вывод ──────────────────────────────────────────────

    def _start_voice_turn(self):
        if self._recorder is not None:
            print("[запись уже идёт — нажми Enter чтобы остановить]")
            return
        try:
            import voice_io
        except ImportError as e:
            print(f"[голосовой ввод недоступен: {e}]")
            print("Установи зависимости: pip install faster-whisper sounddevice numpy --break-system-packages")
            return

        self._recorder = voice_io.Recorder()
        self._recorder.start()
        print("[🎤 запись... нажми Enter в консоли чтобы остановить]")

    def _finish_voice_turn(self):
        import voice_io  # уже импортирован выше, кеш модулей делает это бесплатным

        recorder = self._recorder
        self._recorder = None

        wav_path = recorder.stop()
        print("[распознаю...]")
        try:
            text = voice_io.transcribe(wav_path)
        except FileNotFoundError as e:
            print(f"[STT недоступен]: {e}")
            return

        if not text:
            print("[не распознано]")
            return
        print(f"[вы сказали]: {text}")
        self._process_turn(text)

    def _speak(self, text: str):
        try:
            import voice_io
        except ImportError as e:
            print(f"[TTS недоступен: {e}]")
            print("Установи зависимости: pip install pyttsx3 --break-system-packages")
            self._speak_on = False
            return
        voice_io.speak(text)

    # ─── встроенные команды ──────────────────────────────────────────────────

    def _handle_command(self, text: str):
        parts = text.strip().split(maxsplit=1)
        cmd   = parts[0].lower()
        arg   = parts[1] if len(parts) > 1 else ""

        if cmd == "/inner":
            if arg == "on":
                self._inner_on = True
                print("[inner voice включён]")
            elif arg == "off":
                self._inner_on = False
                print("[inner voice выключен]")
            else:
                print(f"[inner voice: {'on' if self._inner_on else 'off'}]")

        elif cmd == "/timeout":
            try:
                self.timeout = int(arg)
                print(f"[inner voice timeout: {self.timeout}s]")
            except ValueError:
                print("[ошибка: /timeout <число секунд>]")

        elif cmd == "/inject":
            if arg:
                self._inner_voice(prompt=arg)
            else:
                self._inner_voice()

        elif cmd == "/talk":
            self._start_voice_turn()

        elif cmd == "/speak":
            if arg == "on":
                self._speak_on = True
                print("[TTS включён — финальные ответы будут озвучиваться]")
            elif arg == "off":
                self._speak_on = False
                print("[TTS выключен]")
            else:
                print(f"[TTS: {'on' if self._speak_on else 'off'}]")

        else:
            print(f"[неизвестная команда: {cmd}]")

    # ─── input thread ────────────────────────────────────────────────────────

    def _start_input_thread(self):
        t = threading.Thread(target=self._read_input, daemon=True)
        t.start()

    def _read_input(self):
        while True:
            try:
                line = input("\nВы: ")
                self._input_queue.put(line)
            except EOFError:
                self._input_queue.put("")
                break