import os
from llm import LLM
from agent import Agent
from logger import SessionLogger
from main_loop import MainLoop

# ─── КОНФИГ ──────────────────────────────────────────────────────────────────
# Выбери нужный бэкенд — раскомментируй одну строку:

llm = LLM.ollama("qwen2.5-coder:14b")
# llm = LLM.remote("192.168.1.10", "qwen2.5-coder:14b")   # Ollama на другом ПК
# llm = LLM.llama_cpp("~/models/qwen.gguf")               # llama-cpp-python
# llm = LLM.custom("http://my-server/v1", "my-model")     # любой endpoint

HOME = os.path.expanduser("~")

# Пробрасываем в окружение — нужно для memory_cleanup
os.environ["AGENT_MODEL"]    = llm.model
os.environ["AGENT_BASE_URL"] = llm.base_url

# ─── ЗАПУСК ──────────────────────────────────────────────────────────────────

def main():
    logger = SessionLogger(logs_dir="logs")
    agent  = Agent(llm=llm, home=HOME, logger=logger)

    print(f"Агент запущен ({llm})")
    print(f"Лог: {logger.path}\n")

    MainLoop(agent).run()


if __name__ == "__main__":
    main()