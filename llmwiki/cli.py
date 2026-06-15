"""Command-line interface: init, ingest, query, lint, search."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .config import ConfigError, load_config
from .ingest import ingest
from .lint import lint
from .loaders import LoaderError
from .providers import ProviderError, get_provider
from .query import answer
from .scaffold import scaffold_vault
from .search import search


_API_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
}


def _err(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)


def cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.path).expanduser().resolve()
    config = scaffold_vault(root)
    print(f"Initialized llmwiki vault at {config.root}")
    print("  - put sources in raw/sources/ (or pass any path/URL to `llmwiki ingest`)")
    print(
        f"  - set {_API_KEY_ENV.get(config.provider, 'OPENAI_API_KEY')} "
        "in your environment for ingest/query"
    )
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    config = load_config()
    provider = get_provider(config)
    result = ingest(
        config,
        provider,
        args.source,
        course=args.course,
        force_vision=args.vision,
        force=args.force,
    )
    for warning in result.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if result.status == "skipped":
        print(f"skipped (unchanged): {result.source_key}")
    else:
        print(f"ingested: {result.title}  [source: {result.source_slug}]")
        print(f"  concepts: {', '.join(result.concept_slugs) or '(none)'}")
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    config = load_config()
    provider = get_provider(config)
    result = answer(config, provider, args.question, course=args.course, save=args.save)
    print(result.answer)
    if result.pages_used:
        print(f"\n[pages: {', '.join(result.pages_used)}]", file=sys.stderr)
    if result.saved_path:
        print(f"[saved to {result.saved_path.relative_to(config.root)}]", file=sys.stderr)
    return 0


def cmd_lint(args: argparse.Namespace) -> int:
    config = load_config()
    provider = get_provider(config) if args.deep else None
    issues = lint(config, provider=provider, deep=args.deep, course=args.course)
    if not issues:
        print("No issues found.")
        return 0
    order = {"error": 0, "warning": 1, "info": 2}
    for issue in sorted(issues, key=lambda i: order.get(i.level, 3)):
        print(f"[{issue.level:7}] {issue.page}: {issue.message}")
    return 1 if any(i.level == "error" for i in issues) else 0


def cmd_serve(args: argparse.Namespace) -> int:
    config = load_config()  # fail early if we're not inside a vault
    try:
        import uvicorn

        from .web.app import create_app
    except ImportError:
        _err("the web UI needs extra packages. Install them with:\n    pip install '.[web]'")
        return 2

    app = create_app(config)
    url = f"http://{args.host}:{args.port}"
    print(f"Eric's Second Brain (web UI) at {url}  (vault: {config.root})")
    print("press Ctrl+C to stop")
    if not args.no_open:
        import threading
        import webbrowser

        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    config = load_config()
    hits = search(config, args.query, top_k=args.top_k, course=args.course)
    if not hits:
        print("No matches.")
        return 0
    for hit in hits:
        print(f"{hit.score:6.2f}  [[{hit.ref.slug}]]  {hit.ref.title}  ({hit.ref.course})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="llmwiki", description="Local-first academic LLM wiki."
    )
    parser.add_argument("--version", action="version", version=f"llmwiki {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="create a vault in the current (or given) directory")
    p_init.add_argument("path", nargs="?", default=".", help="vault directory (default: .)")
    p_init.set_defaults(func=cmd_init)

    p_ing = sub.add_parser("ingest", help="ingest a file path or URL into the wiki")
    p_ing.add_argument("source", help="path to a file or an http(s) URL")
    p_ing.add_argument("--course", help="course name (default: config default_course)")
    p_ing.add_argument(
        "--vision", action="store_true", help="force vision transcription for PDFs"
    )
    p_ing.add_argument(
        "--force", action="store_true", help="re-ingest even if the source is unchanged"
    )
    p_ing.set_defaults(func=cmd_ingest)

    p_q = sub.add_parser("query", help="ask a question answered from the wiki")
    p_q.add_argument("question")
    p_q.add_argument("--course", help="restrict retrieval to a course")
    p_q.add_argument(
        "--save", action="store_true", help="save the answer under wiki/queries/"
    )
    p_q.set_defaults(func=cmd_query)

    p_l = sub.add_parser("lint", help="check the wiki for structural/quality issues")
    p_l.add_argument("--course", help="restrict to a course")
    p_l.add_argument(
        "--deep", action="store_true", help="also run an LLM contradiction/gap review"
    )
    p_l.set_defaults(func=cmd_lint)

    p_s = sub.add_parser("search", help="keyword search over concept pages (no LLM)")
    p_s.add_argument("query")
    p_s.add_argument("--course", help="restrict to a course")
    p_s.add_argument("--top-k", type=int, default=10, dest="top_k")
    p_s.set_defaults(func=cmd_search)

    p_serve = sub.add_parser("serve", help="launch the local web UI (browse/ask/lint with math)")
    p_serve.add_argument("--host", default="127.0.0.1", help="bind host (default: 127.0.0.1)")
    p_serve.add_argument("--port", type=int, default=8000, help="bind port (default: 8000)")
    p_serve.add_argument(
        "--no-open", action="store_true", help="do not open a browser automatically"
    )
    p_serve.set_defaults(func=cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ConfigError, ProviderError, LoaderError, FileNotFoundError) as e:
        _err(str(e))
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
