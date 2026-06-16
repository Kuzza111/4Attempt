import os
import subprocess
import sys
import tempfile

HOME = os.path.expanduser("~")


def _expand(text: str) -> str:
    """Раскрывает ~/path → абсолютный путь.
    п.3: ./file не трогаем — это легитимный CWD-путь в shell.
    Проблема была в промпте (модель писала ./file вместо ~/file).
    """
    return text.replace("~/", HOME + "/")


def run_code(code: str) -> str:
    """Выполняет Python-код, возвращает stdout/stderr."""
    code = _expand(code)
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(code)
        path = f.name
    try:
        r = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=30)
        os.unlink(path)
        out, err = r.stdout.strip(), r.stderr.strip()
        if err and out:
            return f"stdout:\n{out}\nstderr:\n{err}"
        if err:
            return f"ОШИБКА:\n{err}"
        return out if out else "OK (вывода нет)"
    except subprocess.TimeoutExpired:
        return "Ошибка: таймаут (30с)"
    except Exception as e:
        return f"Ошибка: {e}"


def run_shell(command: str) -> str:
    """Выполняет bash-команду. ~/path раскрывается автоматически."""
    BLOCKED = ["sudo", "rm -rf /", "shutdown", "reboot", "passwd", "read -p", "read -s"]
    for b in BLOCKED:
        if b in command:
            return f"Заблокировано: '{b}'. Интерактивный ввод недоступен — если нужна информация от пользователя, спроси через Final Answer."
    command = _expand(command)
    try:
        r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=15)
        out, err = r.stdout.strip(), r.stderr.strip()
        if err and out:
            return f"stdout:\n{out}\nstderr:\n{err}"
        if err:
            return f"ОШИБКА:\n{err}"
        return out if out else "OK (вывода нет)"
    except subprocess.TimeoutExpired:
        return "Ошибка: таймаут (15с)"
    except Exception as e:
        return f"Ошибка: {e}"


TOOLS = {
    "run_code":  run_code,
    "run_shell": run_shell,
}

DESCRIPTION = """
run_code
  Выполняет Python-код. ~/path раскрывается автоматически.
  Пример:
    Action: run_code
    ```python
    print(2 + 2)
    ```

run_shell
  Выполняет bash-команду. ~/path раскрывается автоматически.
  ВАЖНО: каждый вызов — новый процесс, `cd` не сохраняется между вызовами.
  Для работы в другой директории: `cd /path && команда` в одном вызове.
  Используй ~/path или абсолютный путь — НИКОГДА ./file для файлов вне текущей директории.
  После echo/записи файла — сразу cat для проверки содержимого.
  Пример:
    Action: run_shell
    ```bash
    echo "hello" > ~/file.txt && cat ~/file.txt
    ```
"""