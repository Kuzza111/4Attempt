"""
Единый интерфейс к LLM-бэкендам.

Поддерживаемые бэкенды:
  ollama        — локальный Ollama (http://localhost:11434/v1)
  ollama_remote — Ollama на другом ПК (указать host)
  llama_cpp     — llama-cpp-python сервер (http://localhost:8080/v1)
  openai        — OpenAI API (требует api_key)
  custom        — любой OpenAI-совместимый endpoint

Все бэкенды используют OpenAI-совместимый API — один клиент, разные base_url.

Пример использования:
  llm = LLM.ollama("qwen2.5-coder:14b")
  llm = LLM.remote("192.168.1.10", "qwen2.5-coder:14b")
  llm = LLM.llama_cpp()
  llm = LLM.custom("http://my-server/v1", "my-model", api_key="sk-...")
"""

from openai import OpenAI
from dataclasses import dataclass


@dataclass
class Response:
    content:    str | None
    tool_calls: list | None

    @property
    def has_tools(self) -> bool:
        return bool(self.tool_calls)


class LLM:
    def __init__(self, model: str, base_url: str, api_key: str = "ollama",
                 timeout: int = 120):
        self.model   = model
        self.client  = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
        self.base_url = base_url

    # ─── фабричные методы ────────────────────────────────────────────────────

    @classmethod
    def ollama(cls, model: str, timeout: int = 120) -> "LLM":
        """Локальный Ollama."""
        return cls(model=model, base_url="http://localhost:11434/v1", timeout=timeout)

    @classmethod
    def remote(cls, host: str, model: str, port: int = 11434,
               timeout: int = 120) -> "LLM":
        """Ollama на другом ПК в сети. host = IP или hostname."""
        base_url = f"http://{host}:{port}/v1"
        return cls(model=model, base_url=base_url, timeout=timeout)

    @classmethod
    def llama_cpp(cls, model: str = "local", host: str = "localhost",
                  port: int = 8080, timeout: int = 120) -> "LLM":
        """llama-cpp-python сервер (python -m llama_cpp.server)."""
        base_url = f"http://{host}:{port}/v1"
        return cls(model=model, base_url=base_url, timeout=timeout)

    @classmethod
    def custom(cls, base_url: str, model: str, api_key: str = "none",
               timeout: int = 120) -> "LLM":
        """Любой OpenAI-совместимый endpoint."""
        return cls(model=model, base_url=base_url, api_key=api_key, timeout=timeout)

    # ─── методы вызова ───────────────────────────────────────────────────────

    def call(self, messages: list, temperature: float = 0.1,
             max_tokens: int = 2048) -> str:
        """Основной вызов. Возвращает строку."""
        try:
            return (
                self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ).choices[0].message.content or ""
            )
        except Exception as e:
            return f"[LLM error]: {e}"

    def call_raw(self, prompt: str, system: str | None = None,
                 temperature: float = 0.1, max_tokens: int = 512) -> str:
        """Простой вызов без истории."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.call(messages, temperature=temperature, max_tokens=max_tokens)

    def __repr__(self) -> str:
        return f"LLM(model={self.model!r}, base_url={self.base_url!r})"