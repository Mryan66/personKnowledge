import argparse
from pathlib import Path
from typing import Optional

from app.agents.organizer_agent import OrganizerAgent
from app.agents.query_agent import QueryAgent
from app.agents.review_agent import ReviewAgent
from app.config import get_settings
from app.ingest.pipeline import ingest_path
from app.ingest.scanner import scan_inbox
from app.memory.database import initialize_database
from app.tools.embedding_tool import EmbeddingTool
from app.tools.openai_client import OpenAIClient
from app.tools.search_tool import SearchTool
from app.web.server import run as run_web_server


def build_openai_client(settings) -> OpenAIClient:
    return OpenAIClient(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        base_url=settings.openai_base_url,
        timeout_seconds=settings.openai_timeout_seconds,
    )


def build_embedding_tool(settings):
    if not settings.openai_api_key:
        return None
    return EmbeddingTool(build_openai_client(settings), model=settings.openai_embedding_model)


def build_organizer_agent(settings) -> OrganizerAgent:
    if not settings.openai_api_key:
        return OrganizerAgent()
    return OrganizerAgent(openai_client=build_openai_client(settings))


def init_workspace(args: argparse.Namespace) -> None:
    settings = get_settings()
    for directory in [
        settings.resolved_inbox_dir,
        settings.resolved_knowledge_dir,
        settings.resolved_data_dir,
        settings.resolved_data_dir / "vectors",
        settings.resolved_knowledge_dir / "reviews",
        settings.resolved_knowledge_dir / "topics",
    ]:
        directory.mkdir(parents=True, exist_ok=True)
    initialize_database(settings.resolved_database_path)
    print("Knowledge Butler workspace initialized.")


def scan(args: argparse.Namespace) -> None:
    settings = get_settings()
    files = scan_inbox(settings.resolved_inbox_dir)
    print("Inbox Files")
    print("-----------")
    for file_path in files:
        print(f"{file_path}\t{file_path.suffix.lower()}\t{file_path.stat().st_size} bytes")
    print(f"Found {len(files)} file(s).")


def ingest(args: argparse.Namespace) -> None:
    settings = get_settings()
    target = Path(args.path) if args.path else settings.resolved_inbox_dir
    embedding_tool = None if args.no_embeddings else build_embedding_tool(settings)
    batch = ingest_path(
        target,
        settings.resolved_database_path,
        embedding_tool=embedding_tool,
        organizer_agent=build_organizer_agent(settings),
    )
    if not batch.successes and not batch.failures:
        print(f"No supported documents ingested from: {target}")
        return

    if batch.successes:
        print("Ingested Documents")
        print("------------------")
    for result in batch.successes:
        tag_text = ", ".join(result.tags) if result.tags else "-"
        print(f"[{result.document_id}] {result.title}")
        print(f"  path: {result.source_path}")
        print(f"  category: {result.category}")
        print(f"  tags: {tag_text}")
        print(f"  chunks: {result.chunk_count}")
        print(f"  embeddings: {result.embedding_count}")
    if batch.failures:
        print("Failed Documents")
        print("----------------")
        for failure in batch.failures:
            print(f"- {failure.source_path}: {failure.reason}")
    print(f"Ingested {len(batch.successes)} document(s), failed {len(batch.failures)} document(s).")


def search(args: argparse.Namespace) -> None:
    settings = get_settings()
    search_tool = SearchTool(settings.resolved_database_path, embedding_tool=build_embedding_tool(settings))
    results = search_tool.search(args.query, limit=args.limit, mode=args.mode)
    if not results:
        print(f"No results found for: {args.query}")
        return

    print("Search Results")
    print("--------------")
    for index, result in enumerate(results, start=1):
        tag_text = ", ".join(result.tags) if result.tags else "-"
        snippet = " ".join(result.content.split())[:160]
        if len(result.content) > 160:
            snippet += "…"
        print(f"{index}. {result.title} (score: {result.score:g}, mode: {result.mode})")
        print(f"   path: {result.source_path}")
        print(f"   category: {result.category}")
        print(f"   tags: {tag_text}")
        print(f"   chunk: {result.chunk_index}")
        print(f"   snippet: {snippet}")


def ask(args: argparse.Namespace) -> None:
    settings = get_settings()
    openai_client = None
    use_llm = bool(settings.openai_api_key) and not args.no_llm
    if use_llm:
        openai_client = OpenAIClient(
            api_key=settings.openai_api_key,
            model=args.model or settings.openai_model,
            base_url=settings.openai_base_url,
            timeout_seconds=settings.openai_timeout_seconds,
        )
    query_agent = QueryAgent(
        settings.resolved_database_path,
        openai_client=openai_client,
        use_llm=use_llm,
        embedding_tool=None if args.no_embeddings else build_embedding_tool(settings),
        search_mode=args.search_mode,
    )
    answer = query_agent.answer(args.question, limit=args.limit)
    print("Answer")
    print("------")
    print(answer.text)
    print(f"Mode: {answer.mode}")
    print(f"Confidence: {answer.confidence}")
    if answer.sources:
        print("Sources:")
        for source in answer.sources:
            print(f"- {source}")


def review(args: argparse.Namespace) -> None:
    settings = get_settings()
    review_agent = ReviewAgent(
        settings.resolved_database_path,
        settings.resolved_knowledge_dir / "reviews",
    )
    report = review_agent.generate_daily_review(limit=args.limit, write_file=not args.no_write)
    print(report.body)
    if report.path:
        print(f"Review written to: {report.path}")


def web(args: argparse.Namespace) -> None:
    run_web_server(host=args.host, port=args.port)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Personal AI Knowledge Butler CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize workspace folders and metadata storage.")
    init_parser.set_defaults(func=init_workspace)

    scan_parser = subparsers.add_parser("scan", help="List supported files waiting in the inbox.")
    scan_parser.set_defaults(func=scan)

    ingest_parser = subparsers.add_parser("ingest", help="Placeholder for document ingestion.")
    ingest_parser.add_argument("path", nargs="?", help="Optional file or folder to ingest.")
    ingest_parser.add_argument("--no-embeddings", action="store_true", help="Skip OpenAI embedding generation during ingest.")
    ingest_parser.set_defaults(func=ingest)

    search_parser = subparsers.add_parser("search", help="Search ingested knowledge with keywords.")
    search_parser.add_argument("query", help="Keyword or phrase to search.")
    search_parser.add_argument("--limit", type=int, default=5, help="Maximum number of results.")
    search_parser.add_argument("--mode", choices=["auto", "keyword", "vector"], default="auto", help="Search mode.")
    search_parser.set_defaults(func=search)

    ask_parser = subparsers.add_parser("ask", help="Answer from ingested knowledge with source citations.")
    ask_parser.add_argument("question", help="Question to ask the knowledge base.")
    ask_parser.add_argument("--limit", type=int, default=3, help="Maximum number of source chunks.")
    ask_parser.add_argument("--model", help="OpenAI model override for this request.")
    ask_parser.add_argument("--no-llm", action="store_true", help="Disable OpenAI generation and use extractive answers.")
    ask_parser.add_argument("--search-mode", choices=["auto", "keyword", "vector"], default="auto", help="Retrieval mode for source chunks.")
    ask_parser.add_argument("--no-embeddings", action="store_true", help="Disable vector retrieval for this request.")
    ask_parser.set_defaults(func=ask)


    web_parser = subparsers.add_parser("web", help="Start the local Web UI dashboard.")
    web_parser.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    web_parser.add_argument("--port", type=int, default=8765, help="Port to bind.")
    web_parser.set_defaults(func=web)

    review_parser = subparsers.add_parser("review", help="Generate a daily knowledge review markdown report.")
    review_parser.add_argument("--limit", type=int, default=20, help="Maximum number of recent documents.")
    review_parser.add_argument("--no-write", action="store_true", help="Print only; do not write a review file.")
    review_parser.set_defaults(func=review)

    return parser


def main(argv: Optional[list] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
