from ddgs import DDGS


def search_web(query: str, max_results: int = 5) -> list[dict]:
    try:
        with DDGS() as ddgs:
            return [
                {"title": r["title"], "url": r["href"], "snippet": r["body"]}
                for r in ddgs.text(query, max_results=max_results)
            ]
    except Exception:
        return []
