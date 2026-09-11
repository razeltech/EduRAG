"""CLI: python -m app <command>"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.discovery import discover, format_report as format_discovery, write_config
from app.system_info import collect, format_report as format_system


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app", description="EduRAG")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("system-info")
    sub.add_parser("model-discovery")

    ingest = sub.add_parser("ingest", help="Parse files; print structure. Does not index.")
    ingest.add_argument("path")
    ingest.add_argument("--no-ocr", action="store_true")
    ingest.add_argument("--json", action="store_true", dest="as_json")
    ingest.add_argument("--out", type=Path)
    ingest.add_argument("--list", action="store_true")

    chunk = sub.add_parser("chunk", help="Parse then print teachable-unit chunks.")
    chunk.add_argument("path")
    chunk.add_argument("--no-ocr", action="store_true")

    index = sub.add_parser("index", help="Parse, chunk, embed, store in a course.")
    index.add_argument("path")
    index.add_argument("--course", required=True)
    index.add_argument("--no-ocr", action="store_true")
    index.add_argument("--max-files", type=int, default=None)

    search = sub.add_parser("search", help="Hybrid retrieval over an indexed course.")
    search.add_argument("query")
    search.add_argument("--course", required=True)
    search.add_argument("--top-k", type=int, default=5)

    load = sub.add_parser("load-test", help="Hit a running server with concurrent LAN clients.")
    load.add_argument("--host", default="127.0.0.1")
    load.add_argument("--port", type=int, default=None)
    load.add_argument("--clients", type=int, default=32)
    load.add_argument("--per-client", type=int, default=8)
    load.add_argument("--path", default="/v1/health")

    sub.add_parser("package-check", help="Verify this folder is ready to copy to another PC.")

    chat = sub.add_parser("chat", help="Grounded Q&A (needs Ollama).")
    chat.add_argument("question")
    chat.add_argument("--course", required=True)
    chat.add_argument("--persona", default="chat")
    chat.add_argument("--debug", action="store_true")

    sub.add_parser("setup", help="Install demo users, English OCR, pull Ollama model.")

    serve = sub.add_parser("serve", help="LAN web UI + API.")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)

    sub.add_parser(
        "ensure-ollama",
        help="Start Ollama on 11434 only if it is not already answering.",
    )
    models = sub.add_parser("list-models", help="List selectable chat models (Ollama).")
    setm = sub.add_parser("set-model", help="Switch active chat model (writes config.yaml).")
    setm.add_argument("model", help="Model id, e.g. qwen2.5:7b-instruct or gpt-oss:20b")
    pullm = sub.add_parser("pull-model", help="Download a chat model via ollama pull.")
    pullm.add_argument("model", help="Model id or Ollama tag to pull")
    sub.add_parser(
        "stop",
        help="Stop EduRAG on 4747; stop Ollama only if we started it and nothing else is using it.",
    )
    pack = sub.add_parser("pack-client", help="Refresh prod-deliverables/ for a client handoff.")
    pack.add_argument("--zip", action="store_true", help="Also write EduRAG-client.zip")

    args = parser.parse_args(argv)

    if args.command == "system-info":
        print(format_system(collect()))
        return 0
    if args.command == "model-discovery":
        system = collect()
        report = discover()
        print(format_discovery(report))
        print(f"\nWrote {write_config(report, system)}")
        return 0
    if args.command == "ingest":
        return _run_ingest(args)
    if args.command == "chunk":
        return _run_chunk(args)
    if args.command == "index":
        return _run_index(args)
    if args.command == "search":
        return _run_search(args)
    if args.command == "load-test":
        return _run_load_test(args)
    if args.command == "package-check":
        return _run_package_check()
    if args.command == "chat":
        return _run_chat(args)
    if args.command == "setup":
        return _run_setup()
    if args.command == "serve":
        return _run_serve(args)
    if args.command == "ensure-ollama":
        return _run_ensure_ollama()
    if args.command == "list-models":
        return _run_list_models()
    if args.command == "set-model":
        return _run_set_model(args)
    if args.command == "pull-model":
        return _run_pull_model(args)
    if args.command == "stop":
        return _run_stop()
    if args.command == "pack-client":
        return _run_pack_client(args)
    parser.error(args.command)
    return 2


def _run_ingest(args: argparse.Namespace) -> int:
    from app.ingest.report import format_batch
    from app.ingest.scanner import scan
    from app.ingest.service import ingest_path

    target = Path(args.path)
    try:
        files = scan(target)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.list:
        print(f"SCAN: {len(files)} supported file(s)")
        for file in files:
            print(f"  {file}")
        return 0
    if not files:
        print("No supported files found.")
        return 1
    docs = ingest_path(target, use_ocr=not args.no_ocr)
    payload = [doc.to_dict() for doc in docs]
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Wrote {args.out}", file=sys.stderr)
    print(json.dumps(payload, indent=2, ensure_ascii=False) if args.as_json else format_batch(docs))
    return 0


def _run_chunk(args: argparse.Namespace) -> int:
    from app.chunker import chunk_document, format_chunks
    from app.ingest.service import ingest_path

    docs = ingest_path(Path(args.path), use_ocr=not args.no_ocr)
    for doc in docs:
        chunks = chunk_document(doc)
        print(format_chunks(doc, chunks))
    return 0


def _run_index(args: argparse.Namespace) -> int:
    from app.pipeline import index_path

    result = index_path(
        Path(args.path),
        args.course,
        use_ocr=not args.no_ocr,
        max_files=args.max_files,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _run_search(args: argparse.Namespace) -> int:
    from app.db import init_db
    from app.db.store import Store
    from app.rag import retrieve_for_course

    store = Store(init_db())
    course = store.get_or_create_course(args.course)
    debug = retrieve_for_course(course["id"], args.query, store, top_k=args.top_k)
    print("SEARCH")
    print("======")
    print(f"rerank={debug.get('rerank') or 'none'}")
    for label in ("vector", "bm25", "exact", "fused", "reranked", "final"):
        hits = debug.get(label) or []
        print(f"\n{label.upper()} ({len(hits)})")
        for hit in hits[: args.top_k]:
            snippet = (hit.get("text") or hit.get("snippet") or "").replace("\n", " ")[:140]
            print(f"  {hit.get('score')}  {hit.get('source_file')} | {hit.get('heading_path')}")
            print(f"    {snippet}")
    return 0


def _run_load_test(args: argparse.Namespace) -> int:
    from app.config_load import load_config
    from app.loadtest import format_report, run_load_test

    cfg = load_config()
    port = args.port or int((cfg.get("server") or {}).get("port") or 4747)
    result = run_load_test(
        host=args.host,
        port=port,
        clients=args.clients,
        per_client=args.per_client,
        path=args.path,
    )
    print(format_report(result))
    return 0 if result.get("ok") else 1


def _run_package_check() -> int:
    from app.package_check import format_report, run_package_check

    result = run_package_check()
    print(format_report(result))
    return 0 if result.get("ok") else 1


def _run_chat(args: argparse.Namespace) -> int:
    from app.db import init_db
    from app.db.store import Store
    from app.rag import generate_answer

    store = Store(init_db())
    course = store.get_or_create_course(args.course)
    print(f"persona={args.persona}  course={course['name']}\n")
    for event in generate_answer(
        question=args.question,
        persona_id=args.persona,
        course_id=course["id"],
        history=[],
        store=store,
    ):
        name = event.get("event")
        if name == "token":
            sys.stdout.write(event.get("text") or "")
            sys.stdout.flush()
        elif name == "done":
            print("\n")
            cites = event.get("citations") or []
            if cites:
                print("Citations:")
                for c in cites:
                    print(f"  [{c['n']}] {c.get('source_file')} {c.get('heading_path') or ''}")
            if args.debug:
                print("\nDEBUG")
                print(json.dumps(event.get("debug") or {}, indent=2, ensure_ascii=False)[:4000])
            if event.get("quiz"):
                print("\nQUIZ", json.dumps(event["quiz"], ensure_ascii=False))
        elif name == "escalation":
            print(f"\n[staff flag: {event.get('reason')}]\n")
    return 0


def _run_setup() -> int:
    from app.bootstrap import run_setup

    result = run_setup()
    print("SETUP")
    print("=====")
    for key, value in result.items():
        print(f"{key}: {value}")
    print("\nDefault logins (click them on the sign-in screen):")
    print("  Admin    admin@edurag.local    admin123")
    print("  Teacher  teacher@edurag.local  teacher123")
    print("  Student  student@edurag.local  student123")
    return 0


def _run_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from app.auth import jwt_secret
    from app.config_load import load_config
    from app.db import init_db
    from app.server import local_ip

    jwt_secret()
    init_db()
    from app.bootstrap import seed_demo_users

    seed_demo_users()
    cfg = load_config()
    host = args.host or (cfg.get("server") or {}).get("host") or "0.0.0.0"
    port = args.port or int((cfg.get("server") or {}).get("port") or 4747)
    print(f"EduRAG  http://127.0.0.1:{port}")
    print(f"LAN     http://{local_ip()}:{port}")
    print(f"Firewall: inbound TCP {port}, Private/LAN profile only.")
    print("Stop with Stop-EduRAG.bat (frees 4747; Ollama only if nothing else needs it).")
    uvicorn.run("app.server:app", host=host, port=port, reload=False)
    from app.shutdown import stop_local

    # Window closed / Ctrl+C: same smart stop as Stop-EduRAG.bat
    result = stop_local()
    print(result.get("ollama_note") or "Stopped.")
    return 0


def _run_ensure_ollama() -> int:
    from app.shutdown import ensure_ollama

    result = ensure_ollama()
    print(result["message"])
    if "not found" in (result.get("message") or "").lower():
        return 1
    # Not answering yet is a warning; Start.bat still launches the HTML server.
    return 0


def _run_list_models() -> int:
    from app.llm import list_models, llm_settings

    active = llm_settings().get("model")
    print(f"Active: {active}")
    print(f"Ollama: {llm_settings().get('base_url')}")
    for m in list_models():
        mark = "*" if m.get("active") else " "
        inst = "installed" if m.get("installed") else "not pulled"
        print(f" {mark} {m['id']:28} {m.get('label')}  [{inst}]")
        if m.get("notes"):
            print(f"     {m['notes']}")
    print("\nSwitch:  python -m app set-model gpt-oss:20b")
    print("Pull:    python -m app pull-model gpt-oss:20b")
    return 0


def _run_set_model(args: argparse.Namespace) -> int:
    from app.llm import set_active_model

    try:
        result = set_active_model(args.model)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Active model: {result['model']} ({result.get('label')})")
    if not result.get("installed"):
        print(f"Not on disk yet. Pull with: python -m app pull-model {result['model']}")
    return 0


def _run_pull_model(args: argparse.Namespace) -> int:
    from app.llm import OllamaError, get_model_entry, pull_model

    entry = get_model_entry(args.model)
    name = entry.get("ollama_name") or entry["id"]
    print(f"Pulling {name} via Ollama (this can take a while)…")
    try:
        result = pull_model(name)
    except OllamaError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(result.get("log") or "done")
    print(f"Ready: {result['model']}")
    return 0


def _run_stop() -> int:
    from app.shutdown import stop_local

    result = stop_local()
    print(f"Stopped listeners on {result['port']}: {result['killed'] or 'none'}")
    if result.get("killed_ollama"):
        print(f"Stopped Ollama pids: {result['killed_ollama']}")
    print(result.get("ollama_note") or "Done.")
    return 0


def _run_pack_client(args: argparse.Namespace) -> int:
    from app.pack_client import write_deliverables

    result = write_deliverables(make_zip=bool(args.zip))
    print(result["report"])
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
