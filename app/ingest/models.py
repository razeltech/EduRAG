from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ContentType = Literal["text", "code", "table", "example", "definition", "figure", "qa"]
BlockType = Literal[
    "heading",
    "paragraph",
    "list_item",
    "table",
    "code",
    "figure",
    "example",
    "definition",
    "qa",
]


@dataclass
class Block:
    type: BlockType
    text: str
    page: int | None = None
    level: int | None = None
    content_type: ContentType = "text"
    chapter: str | None = None
    section: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ParsedDocument:
    source_path: str
    source_name: str
    format: str
    title: str | None = None
    page_count: int = 0
    native_pages: int = 0
    ocr_pages: int = 0
    empty_pages: int = 0
    blocks: list[Block] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        parts: list[str] = []
        for block in self.blocks:
            if block.type == "heading" and block.level:
                parts.append("#" * block.level + " " + block.text)
            elif block.type == "table":
                parts.append(block.text)
            elif block.type == "code":
                parts.append("```\n" + block.text + "\n```")
            else:
                parts.append(block.text)
        return "\n\n".join(p for p in parts if p.strip())

    def block_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for block in self.blocks:
            counts[block.type] = counts.get(block.type, 0) + 1
        return counts

    def outline(self) -> list[Block]:
        return [b for b in self.blocks if b.type == "heading"]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["block_counts"] = self.block_counts()
        data["char_count"] = len(self.text)
        return data
