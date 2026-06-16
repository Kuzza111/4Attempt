"""
Трёхслойная память агента.

memory/
├── core.md           — постоянное: цели, факты о пользователе, предпочтения
├── topics/           — по темам: python.md, hardware.md и т.д.
└── sessions/         — по дням: 2025-06-07.md
"""

from datetime import date, datetime
from pathlib import Path

_MEM   = Path(__file__).parent.parent / "memory"
_CORE  = _MEM / "core.md"
_TOPICS = _MEM / "topics"
_SESSIONS = _MEM / "sessions"

_CORE_TEMPLATE = """\
# Core memory

## Пользователь
_Факты о пользователе: имя, система, предпочтения._

## Цели
_Долгосрочные цели и задачи._

## Важные факты
_Всё остальное что стоит помнить всегда._
"""


def _init():
    _MEM.mkdir(exist_ok=True)
    _TOPICS.mkdir(exist_ok=True)
    _SESSIONS.mkdir(exist_ok=True)
    if not _CORE.exists():
        _CORE.write_text(_CORE_TEMPLATE, encoding="utf-8")


def _safe(name: str) -> str:
    return "".join(c for c in name.lower() if c.isalnum() or c in "-_")


# ─── SAVE ────────────────────────────────────────────────────────────────────

def memory_save(text: str) -> str:
    """
    Сохраняет информацию в память.

    Формат аргумента:
        layer: core | topic | session     (по умолчанию: session)
        topic: название_темы              (только для layer=topic)
        ---
        Текст который нужно запомнить.

    Если формат не указан — сохраняет в сессию текущего дня.
    """
    _init()
    lines  = text.strip().splitlines()
    params = {}
    sep    = next((i for i, l in enumerate(lines) if l.strip() == "---"), None)

    if sep is not None:
        for l in lines[:sep]:
            if ":" in l:
                k, v = l.split(":", 1)
                params[k.strip().lower()] = v.strip()
        content = "\n".join(lines[sep + 1:]).strip()
    else:
        content = text.strip()

    if not content:
        return "Ошибка: нечего сохранять."

    layer = params.get("layer", "session")
    ts    = datetime.now().strftime("%H:%M")
    today = date.today().isoformat()

    if layer == "core":
        with _CORE.open("a", encoding="utf-8") as f:
            f.write(f"\n- [{today}] {content}\n")
        return f"Сохранено в core."

    elif layer == "topic":
        topic = _safe(params.get("topic", "general"))
        path  = _TOPICS / f"{topic}.md"
        first = not path.exists()
        with path.open("a", encoding="utf-8") as f:
            if first:
                f.write(f"# {topic}\n")
            f.write(f"\n- [{today}] {content}\n")
        return f"Сохранено в topics/{topic}.md."

    else:  # session
        path = _SESSIONS / f"{today}.md"
        first = not path.exists()
        with path.open("a", encoding="utf-8") as f:
            if first:
                f.write(f"# Сессия {today}\n")
            f.write(f"\n- [{ts}] {content}\n")
        return f"Сохранено в sessions/{today}.md."


# ─── SEARCH ──────────────────────────────────────────────────────────────────

def memory_search(query: str) -> str:
    """Ищет по всем файлам памяти."""
    _init()
    keywords = query.lower().split()
    results  = []

    for path in sorted(_MEM.rglob("*.md")):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        for i, line in enumerate(lines):
            if any(kw in line.lower() for kw in keywords):
                rel = path.relative_to(_MEM)
                results.append(f"[{rel}:{i+1}] {line.strip()}")

    return "\n".join(results[:20]) if results else "Ничего не найдено."


# ─── CLEANUP ─────────────────────────────────────────────────────────────────

def memory_cleanup(_arg: str = "") -> str:
    """
    Сжимает старые сессии (старше 7 дней) в краткие резюме.
    Запускай редко — раз в несколько дней.
    """
    _init()
    from openai import OpenAI
    import os

    # Берём клиент из окружения — BASE_URL и модель из main.py
    base_url = os.environ.get("AGENT_BASE_URL", "http://localhost:11434/v1")
    model    = os.environ.get("AGENT_MODEL", "qwen2.5-coder:14b")
    client   = OpenAI(base_url=base_url, api_key="ollama")

    today    = date.today()
    cleaned  = []

    for path in sorted(_SESSIONS.glob("*.md")):
        try:
            session_date = date.fromisoformat(path.stem)
        except ValueError:
            continue
        if (today - session_date).days < 7:
            continue

        text = path.read_text(encoding="utf-8").strip()
        if len(text) < 200:
            continue

        try:
            summary = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system",  "content": "Сожми этот дневник сессии в 3-5 строк. Только ключевые факты и результаты. Без воды."},
                    {"role": "user",    "content": text},
                ],
                temperature=0.1, max_tokens=300
            ).choices[0].message.content or ""

            path.write_text(f"# Сессия {path.stem} [сжато]\n\n{summary}\n", encoding="utf-8")
            cleaned.append(path.name)
        except Exception as e:
            cleaned.append(f"{path.name} (ошибка: {e})")

    return f"Сжато сессий: {', '.join(cleaned)}" if cleaned else "Нечего сжимать (все сессии свежие или короткие)."


# ─── LOAD (для системного промпта) ───────────────────────────────────────────

def load_core() -> str:
    """Возвращает core.md + последние 2 сессии для системного промпта."""
    _init()

    parts = []

    core = _CORE.read_text(encoding="utf-8").strip()
    if core:
        parts.append(f"## Постоянная память\n{core}")

    # Последние 2 сессии
    sessions = sorted(_SESSIONS.glob("*.md"))[-2:]
    for s in sessions:
        text = s.read_text(encoding="utf-8").strip()
        if text:
            parts.append(f"## Сессия {s.stem}\n{text}")

    if not parts:
        return ""
    return "\n\n---\n" + "\n\n".join(parts)


# ─── РЕГИСТРАЦИЯ ─────────────────────────────────────────────────────────────

TOOLS = {
    "memory_save":    memory_save,
    "memory_search":  memory_search,
    "memory_cleanup": memory_cleanup,
}

DESCRIPTION = """
memory_save
  Сохраняет информацию в долгосрочную память.
  Слои: core (важные факты навсегда), topic (по теме), session (текущий день).
  Примеры:
    Action: memory_save
    ```
    layer: core
    ---
    Пользователь предпочитает краткие ответы без лишних объяснений.
    ```

    Action: memory_save
    ```
    layer: topic
    topic: python
    ---
    asyncio.run() нельзя вызывать внутри уже работающего event loop.
    ```

    Action: memory_save
    ```
    Установил psutil через pip, работает нормально.
    ```

memory_search
  Ищет по всем слоям памяти.
  Пример:
    Action: memory_search
    ```
    psutil установка
    ```

memory_cleanup
  Сжимает старые сессии (>7 дней) в резюме. Запускай редко.
  Пример:
    Action: memory_cleanup
    ```
    ```
"""


def memory_read(layer: str = "") -> str:
    """Читает содержимое памяти. layer: core | topics | sessions | all"""
    _init()
    layer = layer.strip().lower()
    parts = []

    if layer in ("core", "all", ""):
        text = _CORE.read_text(encoding="utf-8").strip()
        if text:
            parts.append(f"=== core.md ===\n{text}")

    if layer in ("topics", "all"):
        for p in sorted(_TOPICS.glob("*.md")):
            text = p.read_text(encoding="utf-8").strip()
            if text:
                parts.append(f"=== topics/{p.name} ===\n{text}")

    if layer in ("sessions", "all"):
        for p in sorted(_SESSIONS.glob("*.md"))[-5:]:
            text = p.read_text(encoding="utf-8").strip()
            if text:
                parts.append(f"=== sessions/{p.name} ===\n{text}")

    return "\n\n".join(parts) if parts else "Память пуста."


# Добавляем в уже существующий TOOLS
TOOLS["memory_read"] = memory_read

DESCRIPTION += """
memory_read
  Читает содержимое памяти напрямую.
  Аргументы: core | topics | sessions | all (или пусто = core).
  Используй когда пользователь просит показать что сохранено в памяти.
  Примеры:
    Action: memory_read
    ```
    core
    ```

    Action: memory_read
    ```
    all
    ```
"""