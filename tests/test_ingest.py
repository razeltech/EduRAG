from pathlib import Path

from app.ingest.classify import classify_text
from app.ingest.parsers import parse_file
from app.ingest.scanner import scan

FIXTURES = Path(__file__).parent / "fixtures"


def test_scan_finds_fixtures():
    files = scan(FIXTURES)
    names = {p.name for p in files}
    assert "sample_chapter.md" in names
    assert "sample_lesson.html" in names


def test_scan_skips_static_and_respects_max_files(tmp_path: Path):
    (tmp_path / "StaticFiles" / "js").mkdir(parents=True)
    (tmp_path / "StaticFiles" / "js" / "site.js").write_text("x", encoding="utf-8")
    (tmp_path / "Manual").mkdir()
    (tmp_path / "Manual" / "transform.html").write_text("<p>ok</p>", encoding="utf-8")
    (tmp_path / "Manual" / "icon.png").write_bytes(b"\x89PNG")
    docs = scan(tmp_path, include_images=False)
    names = {p.name for p in docs}
    assert "transform.html" in names
    assert "site.js" not in names
    assert "icon.png" not in names
    limited = scan(tmp_path, include_images=False, max_files=1)
    assert len(limited) == 1


def test_list_folder_shows_subdirs(tmp_path: Path):
    from app.fsbrowse import list_folder

    (tmp_path / "Manual").mkdir()
    (tmp_path / "Manual" / "page.html").write_text("<p>x</p>", encoding="utf-8")
    data = list_folder(str(tmp_path))
    names = {e["name"] for e in data["entries"]}
    assert "Manual" in names
    assert data["path"]



def test_markdown_preserves_structure():
    doc = parse_file(FIXTURES / "sample_chapter.md", use_ocr=False)
    types = [b.type for b in doc.blocks]
    assert types[0] == "heading"
    assert doc.title == "Chapter 1 Motion"
    assert any(b.type == "table" for b in doc.blocks)
    assert any(b.type == "code" for b in doc.blocks)
    assert any(b.type == "example" for b in doc.blocks)
    assert any(b.type == "definition" for b in doc.blocks)
    assert any(b.type == "qa" for b in doc.blocks)
    chapter = next(b.chapter for b in doc.blocks if b.chapter)
    assert "Motion" in chapter


def test_html_headings_tables_code():
    doc = parse_file(FIXTURES / "sample_lesson.html", use_ocr=False)
    assert doc.title == "Photosynthesis"
    assert any(b.type == "heading" and b.text == "Photosynthesis" for b in doc.blocks)
    assert any(b.type == "table" for b in doc.blocks)
    assert any(b.type == "code" for b in doc.blocks)


def test_classify_textbook_cues():
    assert classify_text("Example 2: A stone is dropped.") == "example"
    assert classify_text("Definition. Acceleration is rate of change of velocity.") == "definition"
    assert classify_text("Q1. What is inertia?") == "qa"


def test_pdf_native_text(tmp_path: Path):
    import fitz

    pdf = tmp_path / "motion.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Chapter 1 Motion", fontsize=22)
    page.insert_text((72, 120), "Uniform motion has constant velocity.", fontsize=12)
    doc.save(pdf)
    doc.close()

    parsed = parse_file(pdf, use_ocr=False)
    assert parsed.format == "pdf"
    assert parsed.native_pages == 1
    assert parsed.ocr_pages == 0
    assert "Motion" in parsed.text
    assert "constant velocity" in parsed.text
