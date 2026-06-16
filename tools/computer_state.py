import psutil
from datetime import datetime

def computer_state(_arg: str = "") -> str:
    from datetime import datetime
    cpu  = psutil.cpu_percent(interval=1)
    mem  = psutil.virtual_memory()
    swap = psutil.swap_memory()
    time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    lines = [
        f"Время загрузки: {time}",
        f"CPU: {cpu}%",
        f"RAM: {mem.percent}% ({mem.used // 1024**2} / {mem.total // 1024**2} МБ)",
        f"SWAP: {swap.percent}% ({swap.used // 1024**2} / {swap.total // 1024**2} МБ)",
    ]

    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            lines.append(f"Диск {part.mountpoint}: {usage.percent}% ({usage.used // 1024**3} / {usage.total // 1024**3} ГБ)")
        except Exception:
            pass

    try:
        import subprocess
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0:
            for line in r.stdout.strip().splitlines():
                name, util, mem_used, mem_total = [x.strip() for x in line.split(",")]
                lines.append(f"GPU {name}: {util}% / RAM {mem_used}/{mem_total} МБ")
    except Exception:
        pass

    return "\n".join(lines)


TOOLS = {"computer_state": computer_state}
DESCRIPTION = """
computer_state
  Показывает состояние компьютера: время загрузки, CPU, RAM, диски, GPU.
  Пример:
    Action: computer_state
    ```
    ```
"""