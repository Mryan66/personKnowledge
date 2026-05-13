import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from mimetypes import guess_type
from pathlib import Path
from urllib.parse import urlencode
from urllib.parse import parse_qs, urlparse

from app.agents.organizer_agent import OrganizerAgent
from app.agents.query_agent import Answer, QueryAgent
from app.agents.review_agent import ReviewAgent
from app.config import get_settings, remove_env_keys, write_env_values
from app.ingest.parser import DocumentParseError, parse_document
from app.ingest.pipeline import ingest_file, ingest_path
from app.memory.database import (
    ChatMessageRecord,
    add_chat_message,
    add_search_history,
    count_tasks_by_status,
    create_manual_task,
    create_or_update_chat_session,
    delete_task,
    delete_document,
    get_chat_session,
    get_document_by_id,
    get_latest_assistant_message,
    list_all_categories,
    list_all_tags,
    list_chat_messages,
    list_chat_sessions,
    list_tasks,
    record_review_run,
    list_chunks,
    list_search_history,
    list_similar_documents,
    update_task_fields,
    update_task_status,
    update_document_metadata,
)
from app.tools.file_tool import ensure_directory
from app.tools.embedding_tool import EmbeddingTool
from app.tools.openai_client import OpenAIClient, OpenAIClientError
from app.web.dashboard import render_dashboard
from app.web.inbox import render_inbox
from app.web.knowledge import render_document_preview, render_knowledge
from app.web.ask import (
    render_ask,
    render_answer_panel,
    render_chat_message,
    render_chat_status_bar,
    render_conversation_panel,
    render_save_note_notice,
    render_session_history_drawer,
)
from app.web.review import read_review_file, render_review
from app.web.search import render_search
from app.web.settings import render_settings
from app.web.tasks import render_tasks_page
from app.tools.secret_store import SecretStoreError, save_openai_api_key
from app.tools.search_tool import SearchTool

ROOT_DIR = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = ROOT_DIR / "app" / "ui" / "templates"
STATIC_DIR = ROOT_DIR / "app" / "ui" / "static"
FRONTEND_DIST_DIR = ROOT_DIR / "frontend" / "dist"


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
        if path == "/knowledge/detail":
            self._handle_knowledge_detail_get()
            return
        if path == "/search":
            self._handle_search_get()
            return
        if path == "/ask":
            self._handle_ask_get()
            return
        if path == "/ask/stream":
            self._handle_ask_stream_get()
            return
        if path == "/review":
            self._handle_review_get()
            return
        if path == "/settings":
            self._send_html(render_settings(get_settings(), TEMPLATE_DIR / "settings.html"))
            return
        if path == "/tasks":
            self._handle_tasks_get()
            return
        if path == "/static/app.css":
            self._send_file(STATIC_DIR / "app.css", "text/css; charset=utf-8")
            return
        if path.startswith("/assets/"):
            self._handle_asset_get(path)
            return
        self.send_error(404, "Page not found")

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/inbox/ingest":
            self._handle_ingest_post()
            return
        if path == "/inbox/sample":
            self._handle_ingest_sample_post()
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
        if path == "/tasks/create":
            self._handle_tasks_create_post()
            return
        if path == "/tasks/update":
            self._handle_tasks_update_post()
            return
        if path == "/tasks/status":
            self._handle_tasks_status_post()
            return
        if path == "/tasks/delete":
            self._handle_tasks_delete_post()
            return
        self.send_error(404, "Page not found")

    def log_message(self, format, *args) -> None:
        return

    def _handle_ask_get(self) -> None:
        settings = get_settings()
        query = parse_qs(urlparse(self.path).query)
        session_id = query.get("session_id", [""])[0].strip()
        question = query.get("question", [""])[0].strip()
        context_title = query.get("context_title", [""])[0].strip()
        context_source = query.get("context_source", [""])[0].strip()
        sessions = list_chat_sessions(settings.resolved_database_path, limit=20)
        messages = list_chat_messages(settings.resolved_database_path, int(session_id)) if session_id.isdigit() else []
        self._send_html(
            render_ask(
                settings,
                TEMPLATE_DIR / "ask.html",
                question=question,
                session_id=session_id,
                sessions=sessions,
                messages=messages,
                prefill_context=build_prefill_context(context_title, context_source),
                answer_state="idle",
            )
        )

    def _handle_ingest_post(self) -> None:
        settings = get_settings()
        form = self._read_form()
        target = Path(form.get("path", [str(settings.resolved_inbox_dir)])[0] or str(settings.resolved_inbox_dir))
        generate_embeddings = form.get("generate_embeddings", [""])[0] == "1"
        embedding_tool = build_embedding_tool(settings) if generate_embeddings else None
        organizer_agent = build_organizer_agent(settings)
        try:
            batch = ingest_path(
                target,
                settings.resolved_database_path,
                embedding_tool=embedding_tool,
                organizer_agent=organizer_agent,
                enable_ocr=settings.enable_ocr,
            )
            new_count = sum(1 for result in batch.successes if result.status != "duplicate")
            duplicate_count = sum(1 for result in batch.successes if result.status == "duplicate")
            message = f"已处理路径：{target}。{new_count} 个新增，{duplicate_count} 个重复跳过。"
        except (DocumentParseError, OSError, ValueError, OpenAIClientError) as error:
            batch = None
            message = f"导入失败：{error}"
        self._send_html(render_inbox(settings, TEMPLATE_DIR / "inbox.html", batch=batch, message=message))

    def _handle_ingest_sample_post(self) -> None:
        settings = get_settings()
        ensure_directory(settings.resolved_inbox_dir)
        sample_path = settings.resolved_inbox_dir / "sample-getting-started.md"
        sample_path.write_text(
            "\n".join(
                [
                    "# 我的第一份知识样例",
                    "",
                    "这是一个用于快速体验的示例文档。",
                    "",
                    "## 你可以马上试的事",
                    "- 去搜索“知识样例”",
                    "- 去问“这份资料讲了什么？”",
                    "- 去生成一次知识复盘",
                    "",
                    "## 主题",
                    "个人知识管理、AI 问答、复盘",
                ]
            ),
            encoding="utf-8",
        )
        self._send_html(render_inbox(settings, TEMPLATE_DIR / "inbox.html", message=f"示例文件已准备好：{sample_path.name}"))

    def _handle_knowledge_get(self) -> None:
        settings = get_settings()
        query = parse_qs(urlparse(self.path).query)
        selected_document, chunks, similar_documents, preview_html, preview_mode, selected_chunk = self._build_knowledge_detail_context(settings, query)
        message = query.get("message", [""])[0]
        self._send_html(
            render_knowledge(
                settings,
                TEMPLATE_DIR / "knowledge.html",
                selected_document=selected_document,
                chunks=chunks,
                similar_documents=similar_documents,
                preview_html=preview_html,
                preview_mode=preview_mode,
                selected_chunk=selected_chunk,
                message=message,
            )
        )

    def _handle_knowledge_detail_get(self) -> None:
        settings = get_settings()
        query = parse_qs(urlparse(self.path).query)
        selected_document, chunks, similar_documents, preview_html, preview_mode, selected_chunk = self._build_knowledge_detail_context(settings, query)
        self._send_html(
            render_knowledge_detail_panel(
                selected_document,
                chunks,
                similar_documents,
                preview_html,
                preview_mode,
                selected_chunk,
            )
        )

    def _build_knowledge_detail_context(self, settings, query: dict):
        selected_document = None
        chunks = []
        preview_html = ""
        preview_mode = normalize_preview_mode(query.get("preview", ["rendered"])[0])
        document_id = query.get("document_id", [""])[0].strip()
        selected_chunk = parse_chunk_index(query.get("selected_chunk", [""])[0])
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
        return selected_document, chunks, similar_documents, preview_html, preview_mode, selected_chunk

    def _handle_search_get(self) -> None:
        settings = get_settings()
        request_query = parse_qs(urlparse(self.path).query)
        query = request_query.get("q", [""])[0].strip()
        mode = request_query.get("mode", ["auto"])[0]
        limit = 5
        filters = extract_search_filters(request_query)
        common_tags = list_all_tags(settings.resolved_database_path)
        common_categories = list_all_categories(settings.resolved_database_path)
        results = []
        message = ""
        search_tool = SearchTool(settings.resolved_database_path, embedding_tool=build_embedding_tool(settings))
        if query:
            results = search_tool.search(query, limit=limit, mode=mode, filters=filters)
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
                filters=filters,
                results=results,
                search_history=search_history,
                message=message,
                common_tags=common_tags,
                common_categories=common_categories,
            )
        )

    def _handle_search_post(self) -> None:
        settings = get_settings()
        form = self._read_form()
        query = form.get("query", [""])[0].strip()
        mode = form.get("mode", ["auto"])[0]
        filters = extract_search_filters(form)
        try:
            limit = max(1, min(20, int(form.get("limit", ["5"])[0])))
        except ValueError:
            limit = 5
        search_tool = SearchTool(settings.resolved_database_path, embedding_tool=build_embedding_tool(settings))
        results = search_tool.search(query, limit=limit, mode=mode, filters=filters) if query else []
        if query:
            add_search_history(settings.resolved_database_path, query, mode, len(results))
        message = f"已搜索：{query}" if query else "请输入搜索内容。"
        search_history = list_search_history(settings.resolved_database_path)
        common_tags = list_all_tags(settings.resolved_database_path)
        common_categories = list_all_categories(settings.resolved_database_path)
        self._send_html(
            render_search(
                settings,
                TEMPLATE_DIR / "search.html",
                query=query,
                mode=mode,
                limit=limit,
                filters=filters,
                results=results,
                search_history=search_history,
                message=message,
                common_tags=common_tags,
                common_categories=common_categories,
            )
        )

    def _handle_ask_post(self) -> None:
        settings = get_settings()
        form = self._read_form()
        ask_state = self._process_ask_form(settings, form)
        if self.headers.get("HX-Request", "").lower() == "true":
            self._send_html(render_ask_partial_payload(settings, ask_state))
            return
        self._send_html(
            render_ask(
                settings,
                TEMPLATE_DIR / "ask.html",
                question=ask_state["question"],
                search_mode=ask_state["search_mode"],
                limit=ask_state["limit"],
                use_llm=ask_state["use_llm"],
                use_embeddings=ask_state["use_embeddings"],
                model=ask_state["model"],
                answer_style=ask_state["answer_style"],
                session_id=ask_state["session_id"],
                sessions=ask_state["sessions"],
                messages=ask_state["messages"],
                answer=ask_state["answer"],
                message=ask_state["message"],
                answer_state=ask_state["answer_state"],
            )
        )

    def _handle_ask_stream_get(self) -> None:
        settings = get_settings()
        query = parse_qs(urlparse(self.path).query)
        self._send_sse_headers()
        try:
            self._stream_ask_flow(settings, query)
        except BrokenPipeError:
            return
        except ConnectionResetError:
            return

    def _handle_asset_get(self, path: str) -> None:
        relative_path = path.removeprefix("/assets/")
        asset_path = (FRONTEND_DIST_DIR / relative_path).resolve()
        if FRONTEND_DIST_DIR.resolve() not in asset_path.parents and asset_path != FRONTEND_DIST_DIR.resolve():
            self.send_error(403, "Invalid asset path")
            return
        content_type = guess_type(str(asset_path))[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in {"application/javascript", "application/json"}:
            content_type = f"{content_type}; charset=utf-8"
        self._send_file(asset_path, content_type)

    def _process_ask_form(self, settings, form: dict) -> dict:
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
        answer_state = "idle"
        if question:
            try:
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
                if answer.mode == "none":
                    answer_state = "no_results"
                    message = "你的知识库里暂时没有足够相关的信息。试试换个问法，或者先导入相关资料。"
                elif answer.mode == "general":
                    answer_state = "success"
                    message = "没有检索到知识库内容，已切换到通用 AI 兜底回答。"
                elif answer.mode == "fallback":
                    answer_state = "model_error"
                    message = "AI 回答未完整生成，已切换为来源摘要模式。你可以立即重试。"
                else:
                    answer_state = "success"
                    message = f"已提问：{question}"
            except OpenAIClientError as error:
                answer_state = "model_error"
                message = f"模型调用超时或失败：{error}。你可以立即重试，或先改用来源摘要回答。"
            except Exception as error:
                answer_state = "config_error"
                message = f"提问失败：{error}。请检查配置，或稍后重试。"
        else:
            message = "请输入问题。"
        sessions = list_chat_sessions(settings.resolved_database_path, limit=20)
        messages = list_chat_messages(settings.resolved_database_path, int(session_id), limit=100) if session_id.isdigit() else []
        return {
            "question": question,
            "search_mode": search_mode,
            "limit": limit,
            "use_llm": use_llm,
            "use_embeddings": use_embeddings,
            "model": model,
            "answer_style": answer_style,
            "session_id": session_id,
            "sessions": sessions,
            "messages": messages,
            "answer": answer,
            "message": message,
            "answer_state": answer_state,
        }

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
        note_result = None
        action_notice = ""
        try:
            note_result = ingest_file(
                note_path,
                settings.resolved_database_path,
                embedding_tool=build_embedding_tool(settings),
                organizer_agent=OrganizerAgent(),
                enable_ocr=settings.enable_ocr,
            )
            message = f"已保存并加入知识库：{note_path.name}"
            if note_result.status == "duplicate":
                message = f"已保存为笔记：{note_path.name}。检测到与已有文档重复，已复用原条目。"
            elif note_result.status == "similar":
                message = f"已保存并加入知识库：{note_path.name}。系统还发现了相似文档。"
            action_notice = render_save_note_notice(
                note_name=note_path.name,
                note_path=str(note_path),
                document_id=str(note_result.document_id),
            )
        except (DocumentParseError, OSError, ValueError, OpenAIClientError) as error:
            message = f"笔记已保存到文件：{note_path.name}，但加入知识库失败：{error}"
            action_notice = render_save_note_notice(
                note_name=note_path.name,
                note_path=str(note_path),
                document_id="",
            )
        sessions = list_chat_sessions(settings.resolved_database_path, limit=20)
        messages = list_chat_messages(settings.resolved_database_path, int(session_id), limit=100)
        self._send_html(
            render_ask(
                settings,
                TEMPLATE_DIR / "ask.html",
                session_id=session_id,
                sessions=sessions,
                messages=messages,
                message=message,
                action_notice=action_notice,
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

    def _handle_tasks_get(self) -> None:
        settings = get_settings()
        query = parse_qs(urlparse(self.path).query)
        status = query.get("status", ["open"])[0].strip() or "open"
        message = query.get("message", [""])[0]
        try:
            self._send_html(render_tasks_page(settings, TEMPLATE_DIR / "tasks.html", status=status, message=message))
        except ValueError:
            self._send_html(render_tasks_page(settings, TEMPLATE_DIR / "tasks.html", status="open", message="任务状态无效。"))

    def _handle_tasks_create_post(self) -> None:
        settings = get_settings()
        form = self._read_form()
        try:
            create_manual_task(
                settings.resolved_database_path,
                content=form.get("content", [""])[0],
                due_date=form.get("due_date", [""])[0],
                priority=form.get("priority", ["normal"])[0],
            )
            message = "任务已创建。"
        except ValueError as error:
            message = f"创建任务失败：{error}"
        self._send_html(render_tasks_page(settings, TEMPLATE_DIR / "tasks.html", status="open", message=message))

    def _handle_tasks_update_post(self) -> None:
        settings = get_settings()
        form = self._read_form()
        task_id = parse_task_id(form)
        if task_id is None:
            self._send_html(render_tasks_page(settings, TEMPLATE_DIR / "tasks.html", status="open", message="任务 ID 无效。"))
            return
        try:
            updated = update_task_fields(
                settings.resolved_database_path,
                task_id,
                content=form.get("content", [""])[0],
                due_date=form.get("due_date", [""])[0],
                priority=form.get("priority", ["normal"])[0],
            )
            message = "任务已更新。" if updated else "未找到要更新的任务。"
        except ValueError as error:
            message = f"更新任务失败：{error}"
        self._send_html(render_tasks_page(settings, TEMPLATE_DIR / "tasks.html", status="open", message=message))

    def _handle_tasks_status_post(self) -> None:
        settings = get_settings()
        form = self._read_form()
        task_id = parse_task_id(form)
        status = form.get("status", ["open"])[0]
        if task_id is None:
            self._send_html(render_tasks_page(settings, TEMPLATE_DIR / "tasks.html", status="open", message="任务 ID 无效。"))
            return
        try:
            updated = update_task_status(settings.resolved_database_path, task_id, status)
            message = "任务状态已更新。" if updated else "未找到要更新的任务。"
            selected_status = status if status in {"open", "done", "archived"} else "open"
        except ValueError as error:
            message = f"更新任务状态失败：{error}"
            selected_status = "open"
        self._send_html(render_tasks_page(settings, TEMPLATE_DIR / "tasks.html", status=selected_status, message=message))

    def _handle_tasks_delete_post(self) -> None:
        settings = get_settings()
        form = self._read_form()
        task_id = parse_task_id(form)
        if task_id is None:
            self._send_html(render_tasks_page(settings, TEMPLATE_DIR / "tasks.html", status="open", message="任务 ID 无效。"))
            return
        message = "任务已删除。" if delete_task(settings.resolved_database_path, task_id) else "未找到要删除的任务。"
        self._send_html(render_tasks_page(settings, TEMPLATE_DIR / "tasks.html", status="open", message=message))

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
                selected_chunk=None,
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
                force=True,
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
                selected_chunk=None,
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
                    force=True,
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
        started_at = datetime.now(timezone.utc).isoformat()
        try:
            if period == "weekly":
                report = review_agent.generate_weekly_review(limit=limit, write_file=write_file)
                message = "已生成周复盘。"
            elif period == "monthly":
                report = review_agent.generate_monthly_review(limit=limit, write_file=write_file)
                message = "已生成月复盘。"
            else:
                report = review_agent.generate_daily_review(limit=limit, write_file=write_file)
                message = "已生成日复盘。"
            record_review_run(
                settings.resolved_database_path,
                period=period,
                triggered_by="web",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc).isoformat(),
                status="success",
                document_count=report.body.count("- **"),
                output_path=str(report.path) if report.path else "",
                error_message="",
            )
        except Exception as error:
            report = None
            message = f"复盘生成失败：{error}。请稍后重试。"
            record_review_run(
                settings.resolved_database_path,
                period=period,
                triggered_by="web",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc).isoformat(),
                status="failed",
                document_count=None,
                output_path="",
                error_message=str(error),
            )
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

    def _send_sse_headers(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

    def _send_sse_event(self, event: str, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False)
        self.wfile.write(f"event: {event}\n".encode("utf-8"))
        self.wfile.write(f"data: {body}\n\n".encode("utf-8"))
        self.wfile.flush()

    def _send_sse_patch(self, settings, ask_state: dict, include_answer: bool = True, include_static_regions: bool = True) -> None:
        payload = {
                "conversation": render_conversation_panel(
                    ask_state["messages"],
                    answer=ask_state["answer"],
                    message=ask_state["message"],
                    session_id=ask_state["session_id"],
                ),
            "answer": render_answer_panel(
                ask_state["answer"] if include_answer else None,
                ask_state["message"],
                session_id=ask_state["session_id"],
                question=ask_state["question"],
                search_mode=ask_state["search_mode"],
                limit=ask_state["limit"],
                use_llm=ask_state["use_llm"],
                use_embeddings=ask_state["use_embeddings"],
                model=ask_state["model"],
                answer_style=ask_state["answer_style"],
                answer_state=ask_state["answer_state"],
            ),
        }
        if include_static_regions:
            payload.update(
                {
                    "status_bar": render_chat_status_bar(
                        openai_status="已配置" if settings.openai_api_key else "未配置",
                        openai_status_class="status-ok" if settings.openai_api_key else "status-warn",
                        answer_mode=ask_state["answer"].mode if ask_state["answer"] else "处理中",
                        answer_confidence=ask_state["answer"].confidence if ask_state["answer"] else "-",
                    ),
                    "session_drawer": render_session_history_drawer(ask_state["sessions"], ask_state["session_id"]),
                }
            )
        self._send_sse_event("patch", payload)

    def _send_sse_stream_delta(self, content: str) -> None:
        self._send_sse_event(
            "stream_delta",
            {
                "content": content,
            },
        )

    def _send_sse_stream_start(self, content: str = "") -> None:
        self._send_sse_event(
            "stream_start",
            {
                "html": render_chat_message("assistant", content, "处理中", streaming=True),
            },
        )

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
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

    def _stream_ask_flow(self, settings, values: dict) -> None:
        question = values.get("question", [""])[0].strip()
        selected_session = values.get("session_id_selector", [""])[0].strip() or values.get("session_id", [""])[0].strip()
        search_mode = values.get("search_mode", ["auto"])[0]
        use_llm = values.get("use_llm", [""])[0] == "1"
        use_embeddings = values.get("use_embeddings", [""])[0] == "1"
        model = values.get("model", [settings.openai_model])[0].strip() or settings.openai_model
        answer_style = values.get("answer_style", ["balanced"])[0].strip() or "balanced"
        try:
            limit = max(1, min(10, int(values.get("limit", ["3"])[0])))
        except ValueError:
            limit = 3

        if not question:
            self._send_sse_event("error", {"message": "请输入问题。"})
            self._send_sse_event("done", {})
            return

        session_id = str(
            create_or_update_chat_session(
                settings.resolved_database_path,
                int(selected_session) if selected_session.isdigit() else None,
                title=question[:40],
            )
        )
        history_messages = list_chat_messages(settings.resolved_database_path, int(session_id), limit=12)
        history = [{"role": item.role, "content": item.content} for item in history_messages]
        add_chat_message(settings.resolved_database_path, int(session_id), "user", question, style=answer_style)
        user_messages = list_chat_messages(settings.resolved_database_path, int(session_id), limit=100)

        self._send_sse_event("phase", {"label": "正在检索相关知识..."})
        self._send_sse_patch(
            settings,
            {
                "question": question,
                "search_mode": search_mode,
                "limit": limit,
                "use_llm": use_llm,
                "use_embeddings": use_embeddings,
                "model": model,
                "answer_style": answer_style,
                "session_id": session_id,
                "sessions": list_chat_sessions(settings.resolved_database_path, limit=20),
                "messages": user_messages,
                "answer": None,
                "message": "正在检索相关知识...",
                "answer_state": "streaming",
            },
            include_answer=False,
            include_static_regions=True,
        )

        try:
            openai_client = build_openai_client(settings, model=model) if settings.openai_api_key and use_llm else None
            query_agent = QueryAgent(
                settings.resolved_database_path,
                openai_client=openai_client,
                use_llm=bool(openai_client),
                embedding_tool=build_embedding_tool(settings) if use_embeddings else None,
                search_mode=search_mode,
                answer_style=answer_style,
            )
            self._send_sse_event("phase", {"label": "正在生成最终回答..."})
            self._send_sse_stream_start("")

            def push_partial_answer(partial_answer: Answer) -> None:
                self._send_sse_stream_delta(partial_answer.text)

            answer = query_agent.stream_answer(question, on_delta=push_partial_answer, limit=limit, history=history)
            add_chat_message(settings.resolved_database_path, int(session_id), "assistant", answer.text, sources=answer.sources, style=answer_style)
            final_messages = list_chat_messages(settings.resolved_database_path, int(session_id), limit=100)
            answer_state, message = resolve_answer_feedback(answer, question)
            final_state = {
                "question": question,
                "search_mode": search_mode,
                "limit": limit,
                "use_llm": use_llm,
                "use_embeddings": use_embeddings,
                "model": model,
                "answer_style": answer_style,
                "session_id": session_id,
                "sessions": list_chat_sessions(settings.resolved_database_path, limit=20),
                "messages": final_messages,
                "answer": answer,
                "message": message,
                "answer_state": answer_state,
            }
            self._send_sse_patch(settings, final_state, include_answer=True, include_static_regions=True)
            self._send_sse_event("done", {"session_id": session_id, "redirect": f"/ask?{urlencode({'session_id': session_id})}"})
        except OpenAIClientError as error:
            self._send_sse_event("error", {"message": f"模型调用超时或失败：{error}。你可以立即重试，或先改用来源摘要回答。"})
            self._send_sse_event("done", {"session_id": session_id})
        except Exception as error:
            self._send_sse_event("error", {"message": f"提问失败：{error}。请检查配置，或稍后重试。"})
            self._send_sse_event("done", {"session_id": session_id})


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


def parse_task_id(form: dict):
    raw = form.get("id", [""])[0].strip()
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


def parse_chunk_index(raw: str):
    value = (raw or "").strip()
    if not value.isdigit():
        return None
    return int(value)


def extract_search_filters(values: dict) -> dict:
    tags = _merge_filter_values(values.get("tag", []), values.get("tags", []))
    categories = _merge_filter_values(values.get("category", []), values.get("categories", []))
    return {
        "category": values.get("category", [""])[0].strip(),
        "tag": values.get("tag", [""])[0].strip(),
        "categories": categories,
        "tags": tags,
        "person": values.get("person", [""])[0].strip(),
        "date_from": values.get("date_from", [""])[0].strip(),
        "date_to": values.get("date_to", [""])[0].strip(),
    }


def _merge_filter_values(*groups: list[str]) -> list[str]:
    merged = []
    seen = set()
    for group in groups:
        for raw in group or []:
            value = (raw or "").strip()
            if not value:
                continue
            normalized = value.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            merged.append(value)
    return merged


def build_prefill_context(context_title: str, context_source: str) -> str:
    title = (context_title or "").strip()
    source = (context_source or "").strip()
    if not title and not source:
        return ""
    if title and source:
        return f"当前问题将围绕《{title}》展开，来源片段：{source}"
    return f"当前问题将围绕这条搜索结果展开：{title or source}"


def build_streaming_messages(messages: list, answer: Answer) -> list:
    session_id = messages[0].session_id if messages else 0
    assistant_message = ChatMessageRecord(
        id=0,
        session_id=session_id,
        role="assistant",
        content=answer.text,
        sources=answer.sources,
        style=answer.style,
        created_at="处理中",
    )
    return list(messages) + [assistant_message]


def resolve_answer_feedback(answer: Answer, question: str) -> tuple[str, str]:
    if answer.mode == "none":
        return "no_results", "你的知识库里暂时没有足够相关的信息。试试换个问法，或者先导入相关资料。"
    if answer.mode == "general":
        return "success", "没有检索到知识库内容，已切换到通用 AI 兜底回答。"
    if answer.mode == "fallback":
        return "model_error", "AI 回答未完整生成，已切换为来源摘要模式。你可以立即重试。"
    return "success", f"已提问：{question}"


def render_ask_partial_payload(settings, ask_state: dict) -> str:
    fragments = [
        (
            "ask-status-bar",
            render_chat_status_bar(
                openai_status="已配置" if settings.openai_api_key else "未配置",
                openai_status_class="status-ok" if settings.openai_api_key else "status-warn",
                answer_mode=ask_state["answer"].mode if ask_state["answer"] else "未提问",
                answer_confidence=ask_state["answer"].confidence if ask_state["answer"] else "-",
            ),
        ),
        (
            "ask-session-drawer",
            render_session_history_drawer(ask_state["sessions"], ask_state["session_id"]),
        ),
        (
            "ask-conversation-region",
            render_conversation_panel(
                ask_state["messages"],
                answer=ask_state["answer"],
                message=ask_state["message"],
                session_id=ask_state["session_id"],
            ),
        ),
        (
            "ask-answer-region",
            render_answer_panel(
                ask_state["answer"],
                ask_state["message"],
                session_id=ask_state["session_id"],
                question=ask_state["question"],
                search_mode=ask_state["search_mode"],
                limit=ask_state["limit"],
                use_llm=ask_state["use_llm"],
                use_embeddings=ask_state["use_embeddings"],
                model=ask_state["model"],
                answer_style=ask_state["answer_style"],
                answer_state=ask_state["answer_state"],
            ),
        ),
    ]
    parts = []
    for target_id, html in fragments:
        parts.append(f'<div id="{target_id}" hx-swap-oob="innerHTML">{html}</div>')
    return "\n".join(parts)


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
