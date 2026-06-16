"""
Динамическая подгрузка инструментов из папки tools/.

Каждый модуль (кроме __init__.py) должен экспортировать:
  TOOLS: dict[str, callable]       — {имя: функция}
  DESCRIPTION: str                 — описание для промпта

Добавить инструмент = положить файл в tools/ и перезапустить агента
(или вызвать reload() для горячей перезагрузки).
"""

import importlib
import sys
from pathlib import Path

_TOOLS_DIR = Path(__file__).parent
_SKIP = {"__init__"}

TOOLS: dict       = {}
DESCRIPTION: str  = ""


def _load_module(path: Path) -> None:
    """Загружает один модуль и добавляет его TOOLS/DESCRIPTION."""
    name = path.stem
    module_name = f"tools.{name}"

    # Перезагружаем если уже был загружен
    if module_name in sys.modules:
        mod = importlib.reload(sys.modules[module_name])
    else:
        mod = importlib.import_module(module_name)

    tools = getattr(mod, "TOOLS", {})
    desc  = getattr(mod, "DESCRIPTION", "")

    TOOLS.update(tools)
    if desc.strip():
        global DESCRIPTION
        DESCRIPTION += desc


def load_all() -> None:
    """Загружает все модули из папки tools/."""
    global TOOLS, DESCRIPTION
    TOOLS       = {}
    DESCRIPTION = "\nДоступные инструменты:"

    for path in sorted(_TOOLS_DIR.glob("*.py")):
        if path.stem in _SKIP or path.stem.startswith("_"):
            continue
        try:
            _load_module(path)
        except Exception as e:
            print(f"[tools] Не удалось загрузить {path.name}: {e}")


def reload() -> str:
    """Горячая перезагрузка всех инструментов. Вызывается агентом."""
    load_all()
    return f"Инструменты перезагружены: {', '.join(TOOLS.keys())}"


# Загружаем при импорте
load_all()