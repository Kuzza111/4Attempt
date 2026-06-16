from pathlib import Path
import importlib, sys
import tools

_TOOLS_DIR = Path(__file__).parent


def save_tool(text: str) -> str:
    """Сохраняет новый инструмент в tools/ и сразу подгружает его."""
    lines = text.strip().splitlines()

    name_line = next((l for l in lines if l.strip().startswith("name:")), None)
    if not name_line:
        return "Ошибка: укажи имя в первой строке: name: имя"

    name = name_line.split(":", 1)[1].strip()
    safe = "".join(c for c in name.lower() if c.isalnum() or c == "_")
    if not safe:
        return "Ошибка: некорректное имя."
    if safe in ("__init__", "meta", "system", "memory", "web"):
        return f"Ошибка: имя '{safe}' зарезервировано."

    sep = next((i for i, l in enumerate(lines) if l.strip() == "---"), None)
    code_lines = lines[sep + 1:] if sep is not None else [l for l in lines if not l.strip().startswith("name:")]
    code = "\n".join(code_lines).strip()

    if not code:
        return "Ошибка: код пустой."
    if "TOOLS" not in code:
        return "Ошибка: код должен содержать словарь TOOLS = {...}"

    path = _TOOLS_DIR / f"{safe}.py"
    path.write_text(code, encoding="utf-8")

    module_name = f"tools.{safe}"
    sys.modules.pop(module_name, None)
    try:
        importlib.import_module(module_name)
    except Exception as e:
        return (
            f"Файл сохранён: tools/{safe}.py, но загрузить не удалось.\n"
            f"Ошибка импорта: {e}\n\n"
            f"Что делать:\n"
            f"- Если 'No module named X' — установи пакет:\n"
            f"  run_shell: pip install X --break-system-packages\n"
            f"  Затем вызови save_tool снова.\n"
            f"- Если SyntaxError — исправь код и вызови save_tool снова."
        )

    tools.reload()
    return f"OK: tools/{safe}.py загружен. Инструменты: {', '.join(tools.TOOLS.keys())}"


# Баг 1: все функции в TOOLS должны принимать один строковый аргумент
def list_tools(_arg: str = "") -> str:
    return "Загруженные инструменты: " + ", ".join(tools.TOOLS.keys())


TOOLS = {
    "save_tool":  save_tool,
    "list_tools": list_tools,
}

DESCRIPTION = """
save_tool
  Создаёт новый инструмент, сохраняет в tools/ и сразу подгружает.
  Код должен содержать TOOLS (dict) и DESCRIPTION (str).
  ВАЖНО: каждая функция в TOOLS должна принимать один строковый аргумент
  (даже если он не нужен): def my_func(_arg: str = "") -> str:
  Перед сохранением убедись что все зависимости установлены
  (проверь через run_code: import X). Если нет — установи:
  run_shell: pip install X --break-system-packages
  Формат:
    Action: save_tool
    ```
    name: имя
    ---
    def my_func(arg: str) -> str:
        return arg.upper()

    TOOLS = {"my_func": my_func}
    DESCRIPTION = "my_func\\n  Что делает.\\n"
    ```

list_tools
  Показывает все загруженные инструменты.
  Пример:
    Action: list_tools
    ```
    ```
"""