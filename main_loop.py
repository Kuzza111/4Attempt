"""
MainLoop — основной цикл взаимодействия.

Inner voice: раз в INNER_TIMEOUT секунд агент получает случайный внутренний
промпт и может что-то сделать или сохранить. Результат печатается в терминал
только если не пустой и не IDLE.

Команды пользователя:
  /voice on|off     — включить/выключить inner voice
  /timeout <сек>    — сменить интервал (например /timeout 60)
  /inject <текст>   — вручную запустить inner voice с произвольным промптом
"""

import random
import threading
import queue

from agent import Agent

INNER_TIMEOUT = 300  # секунд между срабатываниями

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
        self.agent        = agent
        self.timeout      = timeout
        self._voice_on    = True
        self._input_queue: queue.Queue = queue.Queue()

    def run(self):
        self._start_input_thread()
        print("Agent ready. Empty line = exit.")
        print(f"Inner voice: every {self.timeout}s. Commands: /voice on|off, /timeout <s>, /inject <text>\n")

        try:
            while True:
                try:
                    user_input = self._input_queue.get(timeout=self.timeout)
                except queue.Empty:
                    if self._voice_on:
                        self._inner_voice()
                    continue

                if not user_input:
                    print("Bye.")
                    break

                # ── встроенные команды ────────────────────────────────────
                if user_input.startswith("/"):
                    self._handle_command(user_input)
                    continue

                print("[думает...]")
                answer = self.agent.respond(user_input)
                print(f"\nАгент: {answer}\n[готов]\n")

        except KeyboardInterrupt:
            print("\nBye.")

    # ─── inner voice ─────────────────────────────────────────────────────────

    def _inner_voice(self, prompt: str | None = None):
        prompt = prompt or random.choice(INNER_PROMPTS)
        print(f"\n[inner voice] {prompt}\n[inner voice думает...]")

        result = self.agent.inject(prompt)

        if result and "IDLE" not in result.upper():
            print(f"[inner voice] → {result}")
        else:
            print("[inner voice] → (тихо)")

    # ─── встроенные команды ──────────────────────────────────────────────────

    def _handle_command(self, text: str):
        parts = text.strip().split(maxsplit=1)
        cmd   = parts[0].lower()
        arg   = parts[1] if len(parts) > 1 else ""

        if cmd == "/voice":
            if arg == "on":
                self._voice_on = True
                print("[inner voice включён]")
            elif arg == "off":
                self._voice_on = False
                print("[inner voice выключен]")
            else:
                print(f"[inner voice: {'on' if self._voice_on else 'off'}]")

        elif cmd == "/timeout":
            try:
                self.timeout = int(arg)
                print(f"[inner voice timeout: {self.timeout}s]")
            except ValueError:
                print(f"[ошибка: /timeout <число секунд>]")

        elif cmd == "/inject":
            if arg:
                self._inner_voice(prompt=arg)
            else:
                self._inner_voice()

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