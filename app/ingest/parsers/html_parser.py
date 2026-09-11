from __future__ import annotations

from pathlib import Path

from app.ingest.classify import apply_structure, content_type_for
from app.ingest.models import Block, ParsedDocument

_HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_CONSUME = _HEADINGS | {"p", "li", "pre", "table", "figcaption", "blockquote"}


def parse_html(path: Path, *, use_ocr: bool = True) -> ParsedDocument:
    del use_ocr
    try:
        from bs4 import BeautifulSoup
        from bs4.element import Tag
    except ImportError as exc:
        raise RuntimeError("beautifulsoup4 is not installed.") from exc

    html = path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "iframe"]):
        tag.decompose()

    blocks: list[Block] = []

    def walk(node: Tag) -> None:
        for child in list(node.children):
            if not isinstance(child, Tag):
                continue
            name = child.name.lower()
            if name in _HEADINGS:
                text = child.get_text(" ", strip=True)
                if text:
                    blocks.append(
                        Block(
                            type="heading",
                            text=text,
                            level=int(name[1]),
                            content_type="text",
                        )
                    )
                continue
            if name == "p":
                text = child.get_text(" ", strip=True)
                if text:
                    blocks.append(
                        Block(
                            type="paragraph",
                            text=text,
                            content_type=content_type_for("paragraph"),
                        )
                    )
                continue
            if name == "li":
                text = child.get_text(" ", strip=True)
                if text:
                    blocks.append(
                        Block(type="list_item", text=text, content_type="text")
                    )
                continue
            if name == "pre":
                text = child.get_text("\n", strip=False).strip()
                if text:
                    blocks.append(Block(type="code", text=text, content_type="code"))
                continue
            if name == "table":
                rows = []
                for tr in child.find_all("tr", recursive=True):
                    cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"], recursive=False)]
                    if not cells:
                        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
                    if any(cells):
                        rows.append(" | ".join(cells))
                if rows:
                    blocks.append(Block(type="table", text="\n".join(rows), content_type="table"))
                continue
            if name in {"figcaption", "blockquote"}:
                text = child.get_text(" ", strip=True)
                if text:
                    kind = "figure" if name == "figcaption" else "paragraph"
                    blocks.append(
                        Block(type=kind, text=text, content_type=content_type_for(kind))
                    )
                continue
            walk(child)

    root = (
        soup.select_one("#content, .content, article, main, #manual-content")
        or soup.body
        or soup
    )
    walk(root)
    if not blocks and root is not (soup.body or soup):
        walk(soup.body or soup)
    blocks = apply_structure(blocks)
    title_tag = soup.find("title")
    title = (
        title_tag.get_text(strip=True)
        if title_tag and title_tag.get_text(strip=True)
        else next((b.text for b in blocks if b.type == "heading"), path.stem)
    )
    return ParsedDocument(
        source_path=str(path),
        source_name=path.name,
        format="html",
        title=title,
        page_count=1,
        native_pages=1 if blocks else 0,
        empty_pages=0 if blocks else 1,
        blocks=blocks,
    )
