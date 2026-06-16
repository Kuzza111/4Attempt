import re
from llm import LLM
from tools import TOOLS, DESCRIPTION
from tools.memory import load_core
from logger import SessionLogger

MAX_STEPS    = 10
MAX_HISTORY  = 40
MAX_SAME_OBS = 3


def build_system(home: str) -> str:
    return f"""Ты — агент, решающий задачи поэтапно. Домашняя директория: {home}

ФОРМАТ — строго один блок за раз:

Thought: <что делаю и зачем>
Action: <название инструмента>
```<python|bash|текст>
<аргумент>
```

Когда задача выполнена:
Final Answer: <ответ пользователю>

ПРАВИЛА:
- Один Action за шаг. НИКОГДА не пиши два и более Action в одном блоке.
- Final Answer пиши ТОЛЬКО если в этом блоке нет ни одного Action. Сначала действие → получи Observation → только потом Final Answer в следующем блоке.
- НИКОГДА не пиши Final Answer об успехе операции если не получил Observation от неё.
- Если Observation совпадает с ожидаемым результатом из Thought — пиши Final Answer, не продолжай цикл.
- После каждого изменяющего действия (создание/запись файла, переименование) — следующий шаг проверяет результат (ls, cat).
- После echo/записи файла — сразу cat для проверки содержимого.
- "OK (вывода нет)" не означает успех — проверь результат явно.
- Не повторяй одну команду дважды подряд.
- Используй ~/path или абсолютный путь. НИКОГДА не используй ./file для файлов вне текущей директории.
- ~ раскрывается автоматически.
- ВАЖНО: каждый run_shell — новый процесс, `cd` не сохраняется между вызовами. Если нужно выполнить команду в другой директории — используй `cd dir && команда` в одном вызове, или абсолютный путь.
- Если пользователь прислал только URL — это задача для web_fetch. Используй инструмент, не отказывайся.
- НИКОГДА не говори "я не могу открыть ссылки" или "у меня нет доступа к интернету" — у тебя есть web_fetch и web_search.
- НИКОГДА не говори "я не могу показать память" или "я не могу предоставить содержимое core" — используй memory_read.
- НИКОГДА не отвечай на вопросы о системе, железе, дисках, памяти от себя — используй computer_state или run_shell.
- Если не знаешь ответа — используй инструмент. Не выдумывай и не говори "я не могу".
- Вопросы "как сделать X", "что такое X", "объясни X" — просьба объяснить, не выполнять. Отвечай через Final Answer.
- А: если пользователь говорит "поищи", "найди в интернете", "проверь наличие" — ОБЯЗАТЕЛЬНО используй web_search или run_shell. Отвечать от себя без инструментов в таких случаях ЗАПРЕЩЕНО.
- Б: если нужна установка пакета и sudo заблокирован — используй `pip install X --break-system-packages`. Никогда не сдавайся после блокировки sudo — ищи альтернативу.
- В: перед `mv`/`cp` с glob-паттерном (*.txt и т.д.) — сначала `ls *.txt` чтобы убедиться что файлы существуют.
- Перед созданием инструмента через save_tool — проверь зависимости: run_code с `import X`. Если пакет не найден — сначала установи: run_shell `pip install X --break-system-packages`, потом save_tool.
- Тестируй логику инструмента через run_code (как обычный Python-код, без импорта из tools). Не пытайся делать `from tools.X import` в run_code — это не работает.
- Используй memory_save для сохранения: layer=core для фактов о пользователе и постоянных предпочтений, layer=topic для знаний по теме, без layer — для результатов текущей задачи.
- Используй memory_search если задача может быть связана с прошлым опытом.
- Используй memory_cleanup раз в несколько дней для сжатия старых сессий.
- Используй web_search для актуальной информации, новостей, документации. Затем web_fetch для получения полного содержимого страницы.
{DESCRIPTION}{load_core()}"""


def _parse_action(text: str):
    actions = re.findall(r"Action:\s*(\w+)", text)
    warning = ""
    if len(actions) > 1:
        warning = (
            f"ПРЕДУПРЕЖДЕНИЕ: обнаружено {len(actions)} Action в одном блоке "
            f"({', '.join(actions)}). Выполнен только первый. "
            "Остальные проигнорированы. В следующем блоке — только один Action."
        )
    if not actions:
        return None, None, ""
    tool = actions[0]
    code_block = re.search(r"```(?:\w*\n)?(.*?)```", text, re.DOTALL)
    code = code_block.group(1).strip() if code_block else ""
    return tool, code, warning


def _parse_final(text: str):
    m = re.search(r"Final Answer:\s*(.+)", text, re.DOTALL)
    return m.group(1).strip() if m else None


class Agent:
    def __init__(self, llm: LLM, home: str,
                 logger: SessionLogger | None = None):
        self.llm     = llm
        self.home    = home
        self.logger  = logger
        self.history: list = []

    def inject(self, prompt: str) -> str:
        """Inner voice — не трогает основную историю разговора."""
        messages = [
            {"role": "system", "content": build_system(self.home)},
            {"role": "user",   "content": prompt},
        ]
        obs_counter: dict[str, int] = {}
        last_action = None

        for _ in range(MAX_STEPS):
            text = self.llm.call(messages, temperature=0.4, max_tokens=1024)

            tool, code, multi_warn = _parse_action(text)
            if tool and tool in TOOLS:
                action_key = (tool, code)
                if action_key == last_action:
                    break
                observation = TOOLS[tool](code)
                if len(observation) > 2000:
                    observation = observation[:2000] + "\n[...обрезано]"
                obs_counter[observation] = obs_counter.get(observation, 0) + 1
                if obs_counter[observation] >= 2:
                    break
                if multi_warn:
                    observation = multi_warn + "\n\n" + observation
                last_action = action_key
                messages.append({"role": "assistant", "content": text})
                messages.append({"role": "user",      "content": f"Observation: {observation}"})
                continue

            final = _parse_final(text)
            if final:
                if self.logger:
                    self.logger.inner(prompt, final)
                return final
            return text.strip()

        return ""

    def respond(self, user_input: str) -> str:
        if self.logger:
            self.logger.user(user_input)

        self.history.append({"role": "user", "content": user_input})
        self._maybe_compress()

        messages    = [{"role": "system", "content": build_system(self.home)}] + self.history
        last_action = None
        obs_counter: dict[str, int] = {}

        for step in range(MAX_STEPS):
            text = self.llm.call(messages, temperature=0.1, max_tokens=2048)
            print(f"\n[шаг {step + 1}]\n{text}\n{'─'*60}")

            if self.logger:
                self.logger.agent_step(text)

            tool, code, multi_warn = _parse_action(text)

            if tool:
                note = ""
                final_in_block = _parse_final(text)
                if final_in_block:
                    note = (
                        "ПРЕДУПРЕЖДЕНИЕ: Final Answer в блоке с Action проигнорирован. "
                        "Сначала получи Observation, потом пиши Final Answer отдельным блоком."
                    )
                    if self.logger:
                        self.logger.error(note)
                    print(f"[warn] {note}")

                if tool not in TOOLS:
                    obs = f"Ошибка: инструмент '{tool}' не найден. Доступны: {', '.join(TOOLS.keys())}"
                    if self.logger:
                        self.logger.error(obs)
                    messages.append({"role": "assistant", "content": text})
                    messages.append({"role": "user", "content": f"Observation: {obs}"})
                    continue

                action_key = (tool, code)
                if action_key == last_action:
                    obs = (
                        "Ты повторяешь ту же команду. "
                        "Попробуй другую проверку или напиши Final Answer."
                    )
                    if self.logger:
                        self.logger.observation(f"[повтор] {obs}")
                    messages.append({"role": "assistant", "content": text})
                    messages.append({"role": "user", "content": f"Observation: {obs}"})
                    continue

                observation = TOOLS[tool](code)
                if len(observation) > 3000:
                    observation = observation[:3000] + "\n[...обрезано]"

                obs_counter[observation] = obs_counter.get(observation, 0) + 1
                if obs_counter[observation] >= MAX_SAME_OBS:
                    observation += (
                        f"\n[Система: этот Observation повторяется {obs_counter[observation]} раз. "
                        "Если задача выполнена — напиши Final Answer. "
                        "Если нет — попробуй другой подход.]"
                    )

                if multi_warn:
                    observation = multi_warn + "\n\n" + observation
                if note:
                    observation = note + "\n\n" + observation

                print(f"[Observation] {observation}")
                if self.logger:
                    self.logger.observation(observation)

                last_action = action_key
                messages.append({"role": "assistant", "content": text})
                messages.append({"role": "user", "content": f"Observation: {observation}"})
                continue

            final = _parse_final(text)
            if final:
                if self.logger:
                    self.logger.final(final)
                self.history.append({"role": "assistant", "content": final})
                return final

            if self.logger:
                self.logger.final(text.strip())
            self.history.append({"role": "assistant", "content": text})
            return text.strip()

        result = "Превышено максимальное количество шагов."
        if self.logger:
            self.logger.error(result)
        self.history.append({"role": "assistant", "content": result})
        return result

    def _maybe_compress(self):
        if len(self.history) <= MAX_HISTORY:
            return
        keep         = MAX_HISTORY // 2
        to_summarize = self.history[:-keep]
        self.history = self.history[-keep:]
        summary = self.llm.call_raw(
            prompt="\n".join(
                f"{m['role'].upper()}: {m.get('content', '')}" for m in to_summarize
            ),
            system="Сожми диалог кратко. Сохрани ключевые факты и результаты.",
            max_tokens=512,
        )
        self.history.insert(0, {"role": "user", "content": f"[Резюме предыдущего разговора]: {summary}"})
        if self.logger:
            self.logger.error(f"[история сжата, оставлено {keep} сообщений]")
        print(f"[история сжата, оставлено {keep} сообщений]")