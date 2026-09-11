from __future__ import annotations

from pathlib import Path

DOC_EXTS = {
    ".pdf",
    ".docx",
    ".pptx",
    ".html",
    ".htm",
    ".md",
    ".markdown",
    ".txt",
    ".xml",
}

IMAGE_EXTS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".tif",
    ".tiff",
}

SUPPORTED = DOC_EXTS | IMAGE_EXTS

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "models",
    ".cursor",
    "staticfiles",
    "static",
    "localsearch",
    "searchindex",
    "preload",
}

SKIP_NAME_BITS = (
    "staticfiles",
    "local-search",
    "search-lucene",
    "searchindex",
)


def is_supported(path: Path, *, include_images: bool = True) -> bool:
    ext = path.suffix.lower()
    if ext in IMAGE_EXTS:
        return include_images
    return ext in DOC_EXTS


def scan(
    path: Path,
    *,
    include_images: bool = True,
    max_files: int | None = None,
) -> list[Path]:
    path = path.expanduser().resolve()
    if path.is_file():
        if not is_supported(path, include_images=True):
            raise ValueError(
                f"Unsupported file type '{path.suffix}'. "
                f"Supported: {', '.join(sorted(SUPPORTED))}"
            )
        return [path]
    if not path.is_dir():
        raise FileNotFoundError(str(path))

    found: list[Path] = []
    for item in path.rglob("*"):
        if not item.is_file():
            continue
        parts_l = [p.lower() for p in item.parts]
        if any(part in SKIP_DIRS for part in parts_l):
            continue
        joined = "/".join(parts_l)
        if any(bit in joined for bit in SKIP_NAME_BITS):
            continue
        if not is_supported(item, include_images=include_images):
            continue
        found.append(item)
        if max_files and len(found) >= max_files:
            break
    return sorted(found)
