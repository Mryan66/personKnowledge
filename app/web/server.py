from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from app.agents.organizer_agent import OrganizerAgent
from app.agents.query_agent import QueryAgent
from app.agents.review_agent import ReviewAgent
from app.config import get_settings, remove_env_keys, write_env_values
from app.ingest.parser import DocumentParseError, parse_document
from app.ingest.pipeline import ingest_file, ingest_path
from app.memory.database import (
    add_chat_message,
    add_search_history,
    create_or_update_chat_session,
    delete_document,
    get_chat_session,
    get_document_by_id,
    get_latest_assistant_message,
    list_chat_messages,
    list_chat_sessions,
    list_chunks,
    list_search_history,
    list_similar_documents,
    update_document_metadata,
)
from app.tools.file_tool import ensure_directory
from app.tools.embedding_tool import EmbeddingTool
from app.tools.openai_client import OpenAIClient, OpenAIClientError
from app.web.dashboard import render_dashboard
from app.web.inbox import render_inbox
from app.web.knowledge import render_document_preview, render_knowledge
from app.web.ask import render_ask
from app.web.review import read_review_file, render_review
from app.web.search import render_search
from app.web.settings import render_settings
from app.tools.secret_store import SecretStoreError, save_openai_api_key
from app.tools.search_tool import SearchTool

ROOT_DIR = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = ROOT_DIR / "app" / "ui" / "templates"
STATIC_DIR = ROOT_DIR / "app" / "ui" / "static"


class KnowledgeButlerHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in {"/", "/dashboard"}:
            self._send_html(render_dashboard(get_settings(), TEMPLATE_DIR / "dashboard.html"))
            return
        if path == "/inbox":
            self._send_html(render_inbox(get_settings(), TEMPLATE_DIR / "inbox.html"))
            return
        if path == "/knowledge":
            self._handle_knowledge_get()
            return
        if path == "/search":
            self._handle_search_get()
            return
        if path == "/ask":
            self._handle_ask_get()
            return
        if path == "/review":
            self._handle_review_get()
            return
        if path == "/settings":
            self._send_html(render_settings(get_settings(), TEMPLATE_DIR / "settings.html"))
            return
        if path == "/static/app.css":
            self._send_file(STATIC_DIR / "app.css", "text/css; charset=utf-8")
            return
        self.send_error(404, "Page not found")

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/inbox/ingest":
            self._handle_ingest_post()
            return
        if path == "/search":
            self._handle_search_post()
            return
        if path == "/ask":
            self._handle_ask_post()
            return
        if path == "/review":
            self._handle_review_post()
            return
        if path == "/ask/save-note":
            self._handle_ask_save_note_post()
            return
        if path == "/knowledge/update":
            self._handle_knowledge_update_post()
            return
        if path == "/knowledge/delete":
            self._handle_knowledge_delete_post()
            return
        if path == "/knowledge/reingest":
            self._handle_knowledge_reingest_post()
            return
        if path == "/knowledge/batch-delete":
            self._handle_knowledge_batch_delete_post()
            return
        if path == "/knowledge/batch-reingest":
            self._handle_knowledge_batch_reingest_post()
            return
        if path == "/settings/openai":
            self._handle_settings_openai_post()
            return
        if path == "/settings/openai/test":
            self._handle_settings_openai_test_post()
            return
        self.send_error(404, "Page not found")

    def log_message(self, format, *args) -> None:
        return

    def _handle_ask_get(self) -> None:
        settings = get_settings()
        query = parse_qs(urlparse(self.path).query)
        session_id = query.get("session_id", [""])[0].strip()
        sessions = list_chat_sessions(settings.resolved_database_path, limit=20)
        messages = list_chat_messages(settings.resolved_database_path, int(session_id)) if session_id.isdigit() else []
        self._send_html(
            render_ask(
                settings,
                TEMPLATE_DIR / "ask.html",
                session_id=session_id,
                sessions=sessions,
                messages=messages,
            )
        )

    def _handle_ingest_post(self) -> None:
        settings = get_settings()
        form = self._read_form()
        target = Path(form.get("path", [str(settings.resolved_inbox_dir)])[0] or str(settings.resolved_inbox_dir))
        generate_embeddings = form.get("generate_embeddings", [""])[0] == "1"
        embedding_tool = build_embedding_tool(settings) if generate_embeddings else None
        organizer_agent = build_organizer_agent(settings)
        batch = ingest_path(
            target,
            settings.resolved_database_path,
            embedding_tool=embedding_tool,
            organizer_agent=organizer_agent,
            enable_ocr=settings.enable_ocr,
        )
        message = f"已处理路径：{target}"
        self._send_html(render_inbox(settings, TEMPLATE_DIR / "inbox.html", batch=batch, message=message))

    def _handle_knowledge_get(self) -> None:
        settings = get_settings()
        query = parse_qs(urlparse(self.path).query)
        selected_document = None
        chunks = []
        preview_html = ""
        preview_mode = normalize_preview_mode(query.get("preview", ["rendered"])[0])
        message = query.get("message", [""])[0]
        document_id = query.get("document_id", [""])[0].strip()
        if document_id.isdigit():
            selected_document = get_document_by_id(settings.resolved_database_path, int(document_id))
            if selected_document:
                chunks = list_chunks(settings.resolved_database_path, selected_document.id)
                similar_documents = list_similar_documents(settings.resolved_database_path, selected_document.id)
                preview_html = build_document_preview(Path(selected_document.source_path), preview_mode=preview_mode)
            else:
                similar_documents = []
        else:
            similar_documents = []
        self._send_html(
            render_knowledge(
                settings,
                TEMPLATE_DIR / "knowledge.html",
                selected_document=selected_document,
                chunks=chunks,
                similar_documents=similar_documents,
                preview_html=preview_html,
                preview_mode=preview_mode,
                message=message,
            )
        )

    def _handle_search_get(self) -> None:
        settings = get_settings()
        query = parse_qs(urlparse(self.path).query).get("q", [""])[0].strip()
        mode = "auto"
        limit = 5
        results = []
        message = ""
        search_tool = SearchTool(settings.resolved_database_path, embedding_tool=build_embedding_tool(settings))
        if query:
            results = search_tool.search(query, limit=limit, mode=mode)
            add_search_history(settings.resolved_database_path, query, mode, len(results))
            message = f"已搜索：{query}"
        search_history = list_search_history(settings.resolved_database_path)
        self._send_html(
            render_search(
                settings,
                TEMPLATE_DIR / "search.html",
                query=query,
                mode=mode,
                limit=limit,
                results=results,
                search_history=search_history,
                message=message,
            )
        )

    def _handle_search_post(self) -> None:
        settings = get_settings()
        form = self._read_form()
        query = form.get("query", [""])[0].strip()
        mode = form.get("mode", ["auto"])[0]
        try:
            limit = max(1, min(20, int(form.get("limit", ["5"])[0])))
        except ValueError:
            limit = 5
        search_tool = SearchTool(settings.resolved_database_path, embedding_tool=build_embedding_tool(settings))
        results = search_tool.search(query, limit=limit, mode=mode) if query else []
        if query:
            add_search_history(settings.resolved_database_path, query, mode, len(results))
        message = f"已搜索：{query}" if query else "请输入搜索内容。"
        search_history = list_search_history(settings.resolved_database_path)
        self._send_html(
            render_search(
                settings,
                TEMPLATE_DIR / "search.html",
                query=query,
                mode=mode,
                limit=limit,
                results=results,
                search_history=search_history,
                message=message,
            )
        )

    def _handle_ask_post(self) -> None:
        settings = get_settings()
        form = self._read_form()
        question = form.get("question", [""])[0].strip()
        selected_session = form.get("session_id_selector", [""])[0].strip() or form.get("session_id", [""])[0].strip()
        search_mode = form.get("search_mode", ["auto"])[0]
        use_llm = form.get("use_llm", [""])[0] == "1"
        use_embeddings = form.get("use_embeddings", [""])[0] == "1"
        model = form.get("model", [settings.openai_model])[0].strip() or settings.openai_model
        answer_style = form.get("answer_style", ["balanced"])[0].strip() or "balanced"
        try:
            limit = max(1, min(10, int(form.get("limit", ["3"])[0])))
        except ValueError:
            limit = 3

        answer = None
        session_id = ""
        if question:
            session_id = str(create_or_update_chat_session(settings.resolved_database_path, int(selected_session) if selected_session.isdigit() else None, title=question[:40]))
            history_messages = list_chat_messages(settings.resolved_database_path, int(session_id), limit=12)
            history = [{"role": item.role, "content": item.content} for item in history_messages]
            openai_client = build_openai_client(settings, model=model) if settings.openai_api_key and use_llm else None
            query_agent = QueryAgent(
                settings.resolved_database_path,
                openai_client=openai_client,
                use_llm=bool(openai_client),
                embedding_tool=build_embedding_tool(settings) if use_embeddings else None,
                search_mode=search_mode,
                answer_style=answer_style,
            )
            answer = query_agent.answer(question, limit=limit, history=history)
            add_chat_message(settings.resolved_database_path, int(session_id), "user", question, style=answer_style)
            add_chat_message(settings.resolved_database_path, int(session_id), "assistant", answer.text, sources=answer.sources, style=answer_style)
        message = f"已提问：{question}" if question else "请输入问题。"
        sessions = list_chat_sessions(settings.resolved_database_path, limit=20)
        messages = list_chat_messages(settings.resolved_database_path, int(session_id), limit=100) if session_id.isdigit() else []
        self._send_html(
            render_ask(
                settings,
                TEMPLATE_DIR / "ask.html",
                question=question,
                search_mode=search_mode,
                limit=limit,
                use_llm=use_llm,
                use_embeddings=use_embeddings,
                model=model,
                answer_style=answer_style,
                session_id=session_id,
                sessions=sessions,
                messages=messages,
                answer=answer,
                message=message,
            )
        )

    def _handle_ask_save_note_post(self) -> None:
        settings = get_settings()
        form = self._read_form()
        session_id = form.get("session_id", [""])[0].strip()
        if not session_id.isdigit():
            self._send_html(render_ask(settings, TEMPLATE_DIR / "ask.html", message="会话 ID 无效。"))
            return
        session = get_chat_session(settings.resolved_database_path, int(session_id))
        latest_answer = get_latest_assistant_message(settings.resolved_database_path, int(session_id))
        if session is None or latest_answer is None:
            self._send_html(render_ask(settings, TEMPLATE_DIR / "ask.html", message="没有可保存的回答。"))
            return
        topics_dir = settings.resolved_knowledge_dir / "topics"
        ensure_directory(topics_dir)
        safe_title = slugify_filename(session.title)
        note_path = topics_dir / f"{safe_title}.md"
        source_lines = "\n".join(f"- {source}" for source in latest_answer.sources) if latest_answer.sources else "- 无"
        body = "\n".join(
            [
                f"# {session.title}",
                "",
                f"来源会话：{session.id}",
                f"回答风格：{latest_answer.style or 'balanced'}",
                "",
                "## 回答",
                latest_answer.content,
                "",
                "## 来源",
                source_lines,
                "",
            ]
        )
        note_path.write_text(body, encoding="utf-8")
        sessions = list_chat_sessions(settings.resolved_database_path, limit=20)
        messages = list_chat_messages(settings.resolved_database_path, int(session_id), limit=100)
        self._send_html(
            render_ask(
                settings,
                TEMPLATE_DIR / "ask.html",
                session_id=session_id,
                sessions=sessions,
                messages=messages,
                message=f"已保存为笔记：{note_path.name}",
            )
        )

    def _handle_review_get(self) -> None:
        settings = get_settings()
        query = parse_qs(urlparse(self.path).query)
        selected_review = query.get("file", [""])[0]
        reviews_dir = settings.resolved_knowledge_dir / "reviews"
        selected_body = read_review_file(reviews_dir, selected_review)
        self._send_html(
            render_review(
                settings,
                TEMPLATE_DIR / "review.html",
                selected_review=selected_review,
                selected_body=selected_body,
            )
        )

    def _handle_knowledge_update_post(self) -> None:
        settings = get_settings()
        form = self._read_form()
        document_id = parse_document_id(form)
        if document_id is None:
            self._send_html(render_knowledge(settings, TEMPLATE_DIR / "knowledge.html", message="文档 ID 无效。"))
            return
        tags = parse_tag_string(form.get("tags", [""])[0])
        updated = update_document_metadata(
            settings.resolved_database_path,
            document_id,
            title=form.get("title", [""])[0],
            summary=form.get("summary", [""])[0],
            tags=tags,
            category=form.get("category", [""])[0],
        )
        message = "文档元数据已更新。" if updated else "未找到要更新的文档。"
        selected_document = get_document_by_id(settings.resolved_database_path, document_id)
        chunks = list_chunks(settings.resolved_database_path, document_id) if selected_document else []
        similar_documents = list_similar_documents(settings.resolved_database_path, document_id) if selected_document else []
        preview_html = build_document_preview(Path(selected_document.source_path), preview_mode="rendered") if selected_document else ""
        self._send_html(
            render_knowledge(
                settings,
                TEMPLATE_DIR / "knowledge.html",
                selected_document=selected_document,
                chunks=chunks,
                similar_documents=similar_documents,
                preview_html=preview_html,
                preview_mode="rendered",
                message=message,
            )
        )

    def _handle_knowledge_delete_post(self) -> None:
        settings = get_settings()
        form = self._read_form()
        document_id = parse_document_id(form)
        message = "文档 ID 无效。"
        if document_id is not None:
            message = "文档已删除。" if delete_document(settings.resolved_database_path, document_id) else "未找到要删除的文档。"
        self._send_html(render_knowledge(settings, TEMPLATE_DIR / "knowledge.html", message=message))

    def _handle_knowledge_reingest_post(self) -> None:
        settings = get_settings()
        form = self._read_form()
        document_id = parse_document_id(form)
        if document_id is None:
            self._send_html(render_knowledge(settings, TEMPLATE_DIR / "knowledge.html", message="文档 ID 无效。"))
            return
        document = get_document_by_id(settings.resolved_database_path, document_id)
        if document is None:
            self._send_html(render_knowledge(settings, TEMPLATE_DIR / "knowledge.html", message="未找到要重新导入的文档。"))
            return
        try:
            result = ingest_file(
                Path(document.source_path),
                settings.resolved_database_path,
                embedding_tool=build_embedding_tool(settings),
                organizer_agent=build_organizer_agent(settings),
                enable_ocr=settings.enable_ocr,
            )
            message = f"已重新导入：{result.title}"
        except (DocumentParseError, OSError, ValueError, OpenAIClientError) as error:
            message = f"重新导入失败：{error}"
        selected_document = get_document_by_id(settings.resolved_database_path, document_id)
        chunks = list_chunks(settings.resolved_database_path, document_id) if selected_document else []
        similar_documents = list_similar_documents(settings.resolved_database_path, document_id) if selected_document else []
        preview_html = build_document_preview(Path(selected_document.source_path), preview_mode="rendered") if selected_document else ""
        self._send_html(
            render_knowledge(
                settings,
                TEMPLATE_DIR / "knowledge.html",
                selected_document=selected_document,
                chunks=chunks,
                similar_documents=similar_documents,
                preview_html=preview_html,
                preview_mode="rendered",
                message=message,
            )
        )

    def _handle_knowledge_batch_delete_post(self) -> None:
        settings = get_settings()
        form = self._read_form()
        document_ids = parse_document_ids(form)
        if not document_ids:
            self._send_html(render_knowledge(settings, TEMPLATE_DIR / "knowledge.html", message="请先选择要删除的文档。"))
            return
        deleted_count = 0
        for document_id in document_ids:
            if delete_document(settings.resolved_database_path, document_id):
                deleted_count += 1
        self._send_html(
            render_knowledge(
                settings,
                TEMPLATE_DIR / "knowledge.html",
                message=f"批量删除完成：成功 {deleted_count} 篇，选中 {len(document_ids)} 篇。",
            )
        )

    def _handle_knowledge_batch_reingest_post(self) -> None:
        settings = get_settings()
        form = self._read_form()
        document_ids = parse_document_ids(form)
        if not document_ids:
            self._send_html(render_knowledge(settings, TEMPLATE_DIR / "knowledge.html", message="请先选择要重新导入的文档。"))
            return
        success_count = 0
        failure_count = 0
        for document_id in document_ids:
            document = get_document_by_id(settings.resolved_database_path, document_id)
            if document is None:
                failure_count += 1
                continue
            try:
                ingest_file(
                    Path(document.source_path),
                    settings.resolved_database_path,
                    embedding_tool=build_embedding_tool(settings),
                    organizer_agent=build_organizer_agent(settings),
                    enable_ocr=settings.enable_ocr,
                )
                success_count += 1
            except (DocumentParseError, OSError, ValueError, OpenAIClientError):
                failure_count += 1
        self._send_html(
            render_knowledge(
                settings,
                TEMPLATE_DIR / "knowledge.html",
                message=f"批量重新导入完成：成功 {success_count} 篇，失败 {failure_count} 篇。",
            )
        )

    def _handle_review_get(self) -> None:
        settings = get_settings()
        query = parse_qs(urlparse(self.path).query)
        selected_review = query.get("file", [""])[0]
        reviews_dir = settings.resolved_knowledge_dir / "reviews"
        selected_body = read_review_file(reviews_dir, selected_review)
        self._send_html(
            render_review(
                settings,
                TEMPLATE_DIR / "review.html",
                selected_review=selected_review,
                selected_body=selected_body,
            )
        )

    def _handle_review_post(self) -> None:
        settings = get_settings()
        form = self._read_form()
        try:
            limit = max(1, min(100, int(form.get("limit", ["20"])[0])))
        except ValueError:
            limit = 20
        period = form.get("period", ["daily"])[0]
        write_file = form.get("write_file", [""])[0] == "1"
        review_agent = ReviewAgent(settings.resolved_database_path, settings.resolved_knowledge_dir / "reviews")
        if period == "weekly":
            report = review_agent.generate_weekly_review(limit=limit, write_file=write_file)
            message = "已生成周复盘。"
        elif period == "monthly":
            report = review_agent.generate_monthly_review(limit=limit, write_file=write_file)
            message = "已生成月复盘。"
        else:
            report = review_agent.generate_daily_review(limit=limit, write_file=write_file)
            message = "已生成日复盘。"
        self._send_html(
            render_review(
                settings,
                TEMPLATE_DIR / "review.html",
                limit=limit,
                period=period,
                write_file=write_file,
                report=report,
                message=message,
            )
        )

    def _handle_settings_openai_post(self) -> None:
        form = self._read_form()
        message = save_openai_settings_from_form(form)
        settings = get_settings()
        self._send_html(
            render_settings(
                settings,
                TEMPLATE_DIR / "settings.html",
                message=message,
            )
        )

    def _handle_settings_openai_test_post(self) -> None:
        form = self._read_form()
        message = save_openai_settings_from_form(form)
        settings = get_settings()
        if not settings.openai_api_key:
            message += " 但未配置 API Key，无法测试连接。"
        else:
            try:
                client = build_openai_client(settings, model=settings.openai_model)
                response_text = client.test_connection()
                message += f" 测试连接成功：{response_text}"
            except OpenAIClientError as error:
                message += f" 测试连接失败：{error}"
        self._send_html(
            render_settings(
                settings,
                TEMPLATE_DIR / "settings.html",
                message=message,
            )
        )

    def _read_form(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(content_length).decode("utf-8") if content_length else ""
        return parse_qs(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self.send_error(404, "Static file not found")
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def parse_openai_settings_form(form: dict, current_settings):
    timeout_value = form.get("openai_timeout_seconds", [str(current_settings.openai_timeout_seconds)])[0]
    try:
        timeout_seconds = max(1, min(600, int(timeout_value)))
    except ValueError:
        timeout_seconds = current_settings.openai_timeout_seconds
    enable_ocr = form.get("enable_ocr", [""])[0] == "1"
    return {
        "api_key": form.get("openai_api_key", [""])[0].strip(),
        "updates": {
            "KB_OPENAI_MODEL": form.get("openai_model", [current_settings.openai_model])[0].strip() or current_settings.openai_model,
            "KB_OPENAI_EMBEDDING_MODEL": form.get("openai_embedding_model", [current_settings.openai_embedding_model])[0].strip() or current_settings.openai_embedding_model,
            "KB_OPENAI_BASE_URL": form.get("openai_base_url", [current_settings.openai_base_url])[0].strip() or current_settings.openai_base_url,
            "KB_OPENAI_TIMEOUT_SECONDS": str(timeout_seconds),
            "KB_ENABLE_OCR": "true" if enable_ocr else "false",
        },
    }


def save_openai_settings_from_form(form: dict) -> str:
    current_settings = get_settings()
    parsed = parse_openai_settings_form(form, current_settings)
    env_path = Path.cwd() / ".env"
    write_env_values(env_path, parsed["updates"])
    if not parsed["api_key"]:
        return "OpenAI 非敏感配置已保存到 .env；API Key 未修改。"
    try:
        save_openai_api_key(parsed["api_key"])
        remove_env_keys(env_path, {"OPENAI_API_KEY", "KB_OPENAI_API_KEY"})
        return "OpenAI 配置已保存：API Key 已加密保存到 macOS Keychain，非敏感配置已保存到 .env。"
    except SecretStoreError as error:
        return f"OpenAI 非敏感配置已保存，但 API Key 加密保存失败：{error}"


def build_openai_client(settings, model=None):
    return OpenAIClient(
        api_key=settings.openai_api_key,
        model=model or settings.openai_model,
        base_url=settings.openai_base_url,
        timeout_seconds=settings.openai_timeout_seconds,
    )


def build_embedding_tool(settings):
    if not settings.openai_api_key:
        return None
    client = build_openai_client(settings)
    return EmbeddingTool(client, model=settings.openai_embedding_model)


def build_organizer_agent(settings):
    if not settings.openai_api_key:
        return OrganizerAgent()
    return OrganizerAgent(openai_client=build_openai_client(settings))


def parse_document_id(form: dict):
    raw = form.get("document_id", [""])[0].strip()
    if not raw.isdigit():
        return None
    return int(raw)


def parse_document_ids(form: dict) -> list[int]:
    values = []
    for raw in form.get("selected_document_id", []):
        raw_value = raw.strip()
        if raw_value.isdigit():
            values.append(int(raw_value))
    return values


def parse_tag_string(raw: str) -> list[str]:
    return [tag.strip() for tag in raw.split(",") if tag.strip()]


def slugify_filename(text: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in text.strip())
    slug = "-".join(part for part in slug.split("-") if part)
    return slug[:80] or "ask-note"


def build_document_preview(source_path: Path, preview_mode: str = "rendered") -> str:
    settings = get_settings()
    try:
        content = parse_document(source_path, enable_ocr=settings.enable_ocr)
    except (DocumentParseError, OSError, UnicodeDecodeError, ValueError):
        return '<p class="muted">暂时无法读取源文档预览。</p>'
    if not content:
        return '<p class="muted">源文档没有可预览的内容。</p>'
    if normalize_preview_mode(preview_mode) == "raw":
        return f'<pre class="document-preview-text">{escape(content)}</pre>'
    return render_document_preview(source_path, content)


def normalize_preview_mode(preview_mode: str) -> str:
    return preview_mode if preview_mode in {"rendered", "raw"} else "rendered"


def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ThreadingHTTPServer((host, port), KnowledgeButlerHandler)
    print(f"Knowledge Butler Web UI: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Web UI.")
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
