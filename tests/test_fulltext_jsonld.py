import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core import article_extractor


class _FakeTrafilatura:
    def __init__(self, precision_text: str, recall_text: str) -> None:
        self.precision_text = precision_text
        self.recall_text = recall_text
        self.calls = []

    def extract(self, _html: str, url=None, **kwargs):  # noqa: ARG002
        self.calls.append({"url": url, **kwargs})
        if kwargs.get("favor_precision"):
            return self.precision_text
        if kwargs.get("favor_recall"):
            return self.recall_text
        return ""


def test_json_ld_used_when_trafilatura_empty(monkeypatch):
    json_body = ("JSON-LD full text " * 20).strip()
    html = f"""
    <html><head>
      <script type="application/ld+json">
        {{"@type": "NewsArticle", "articleBody": "{json_body}"}}
      </script>
    </head><body><article><p>fallback</p></article></body></html>
    """

    fake = _FakeTrafilatura(precision_text="short", recall_text="")
    monkeypatch.setattr(article_extractor, "trafilatura", fake)

    out = article_extractor._extract_text_any(html, url="https://example.com/x")
    assert json_body[:40] in out


def test_json_ld_preferred_when_longer_than_trafilatura(monkeypatch):
    precision_text = ("precision " * 25).strip()  # ~225 chars
    json_body = ("json-body " * 50).strip()  # significantly longer
    html = f"""
    <html><head>
      <script type="application/ld+json">
        {{"@type": "Article", "articleBody": "{json_body}"}}
      </script>
    </head><body><article><p>fallback</p></article></body></html>
    """

    fake = _FakeTrafilatura(precision_text=precision_text, recall_text="")
    monkeypatch.setattr(article_extractor, "trafilatura", fake)

    out = article_extractor._extract_text_any(html, url="https://example.com/x")
    assert out.startswith("json-body")
