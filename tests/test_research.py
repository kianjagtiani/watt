from assistant import research


class FakeDDGS:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def text(self, query, max_results=5):
        return [{"title": "T", "href": "http://x", "body": "B"}]


class BrokenDDGS(FakeDDGS):
    def text(self, query, max_results=5):
        raise RuntimeError("rate limited")


def test_search_web_maps_fields(monkeypatch):
    monkeypatch.setattr(research, "DDGS", FakeDDGS)
    assert research.search_web("qs jobs") == [
        {"title": "T", "url": "http://x", "snippet": "B"}
    ]


def test_search_web_swallows_errors(monkeypatch):
    monkeypatch.setattr(research, "DDGS", BrokenDDGS)
    assert research.search_web("anything") == []
