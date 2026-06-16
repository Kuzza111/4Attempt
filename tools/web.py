import urllib.request
import re

try:
    from ddgs import DDGS
    _DDGS_OK = True
except ImportError:
    _DDGS_OK = False


def web_search(query: str) -> str:
    """Ищет информацию в интернете через DuckDuckGo."""
    if not _DDGS_OK:
        return "Ошибка: установи ddgs — pip install ddgs"
    try:
        results = list(DDGS().text(query, max_results=5))
        if not results:
            return "Ничего не найдено."
        lines = []
        for i, r in enumerate(results, 1):
            lines.append(f"[{i}] {r['title']}\n{r['href']}\n{r['body']}")
        return "\n\n".join(lines)
    except Exception as e:
        return f"Ошибка поиска: {e}"


def web_fetch(url: str) -> str:
    """Загружает содержимое страницы по URL."""
    try:
        # Кодируем не-ASCII символы в URL (кириллица и т.д.)
        from urllib.parse import quote, urlsplit, urlunsplit
        parts = urlsplit(url.strip())
        encoded = urlunsplit((
            parts.scheme,
            parts.netloc,
            quote(parts.path, safe="/:@!$&'()*+,;="),
            quote(parts.query, safe="=&"),
            parts.fragment,
        ))
        req = urllib.request.Request(encoded, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
            "Accept-Language": "ru,en;q=0.9",
        })
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read().decode("utf-8", errors="ignore")
        text = re.sub(r"<style[^>]*>.*?</style>", " ", raw, flags=re.DOTALL)
        text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:4000]
    except Exception as e:
        return f"Ошибка загрузки: {e}"


TOOLS = {
    "web_search": web_search,
    "web_fetch":  web_fetch,
}

DESCRIPTION = """
web_search
  Ищет актуальную информацию в интернете (DuckDuckGo).
  Используй для новостей, документации, фактов которые могли измениться.
  Пример:
    Action: web_search
    ```
    python asyncio tutorial 2024
    ```

web_fetch
  Загружает полное содержимое страницы по URL.
  Используй после web_search чтобы получить детали из конкретной ссылки.
  Пример:
    Action: web_fetch
    ```
    https://docs.python.org/3/library/asyncio.html
    ```
"""