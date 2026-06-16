"""
Логгер сессий агента.

Пишет Markdown-файл в logs/ рядом с проектом:
logs/
└── 2025-06-07_143022.md   ← одна сессия = один файл

Формат:
  # Сессия 2025-06-07 14:30:22
  ## [1] Пользователь
  ...
  ## [1.1] Шаг 1 — Thought/Action
  ...
  ### Observation
  ...
  ## [1] Ответ агента
  ...
"""

from datetime import datetime
from pathlib import Path


class SessionLogger:
    def __init__(self, logs_dir: str | Path = "logs"):
        self._dir  = Path(logs_dir)
        self._dir.mkdir(exist_ok=True)
        ts         = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        self._path = self._dir / f"{ts}.md"
        self._turn = 0  # номер вопроса пользователя в сессии

        self._write(f"# Сессия {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # ─── публичный API ────────────────────────────────────────────────────────

    def user(self, text: str) -> None:
        """Логирует вопрос пользователя, увеличивает счётчик хода."""
        self._turn += 1
        self._step  = 0
        self._write(f"\n## [{self._turn}] Пользователь\n{text}\n")

    def agent_step(self, text: str) -> None:
        """Логирует один шаг ReAct (Thought + Action)."""
        self._step += 1
        self._write(f"\n### [{self._turn}.{self._step}] Шаг {self._step}\n{text}\n")

    def observation(self, text: str) -> None:
        """Логирует Observation после выполнения инструмента."""
        self._write(f"\n**Observation:**\n```\n{text}\n```\n")

    def final(self, text: str) -> None:
        """Логирует финальный ответ агента."""
        self._write(f"\n## [{self._turn}] Ответ агента\n{text}\n\n---\n")

    def inner(self, prompt: str, result: str) -> None:
        """Логирует срабатывание inner voice."""
        self._write(f"\n## [inner voice]\n**Промпт:** {prompt}\n**Результат:** {result}\n")

    def error(self, text: str) -> None:
        """Логирует ошибку / нештатную ситуацию."""
        self._write(f"\n> ⚠ {text}\n")

    @property
    def path(self) -> Path:
        return self._path

    # ─── внутреннее ──────────────────────────────────────────────────────────

    def _write(self, text: str) -> None:
        with self._path.open("a", encoding="utf-8") as f:
            f.write(text)