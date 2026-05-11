from html import escape
from pathlib import Path
from typing import Optional

from app.agents.query_agent import Answer
from app.config import Settings
from app.web.search import SEARCH_MODES, render_mode_options

ANSWER_STYLES = {
    "concise": "简洁",
    "balanced": "平衡",
    "detailed": "详细",
    "report": "报告",
}


def render_ask(
    settings: Settings,
    template_path: Path,
    question: str = "",
    search_mode: str = "auto",
    limit: int = 3,
    use_llm: bool = True,
    use_embeddings: bool = True,
    model: str = "",
    answer_style: str = "balanced",
    session_id: str = "",
    sessions: list = None,
    messages: list = None,
    answer: Optional[Answer] = None,
    message: str = "",
    answer_state: str = "idle",
    prefill_context: str = "",
) -> str:
    sessions = sessions or []
    messages = messages or []
    normalized_mode = search_mode if search_mode in SEARCH_MODES else "auto"
    selected_model = model or settings.openai_model
    template = template_path.read_text(encoding="utf-8")
    replacements = {
        "app_name": settings.app_name,
        "question": escape(question),
        "limit": str(limit),
        "model": escape(selected_model),
        "search_mode_options": render_mode_options(normalized_mode),
        "search_mode_description": SEARCH_MODES[normalized_mode],
        "answer_style_options": render_style_options(answer_style),
        "use_llm_checked": "checked" if use_llm else "",
        "use_embeddings_checked": "checked" if use_embeddings else "",
        "openai_status": "已配置" if settings.openai_api_key else "未配置",
        "openai_status_class": "status-ok" if settings.openai_api_key else "status-warn",
        "answer_mode": escape(answer.mode if answer else "未提问"),
        "answer_confidence": escape(answer.confidence if answer else "-"),
        "chat_status_bar": render_chat_status_bar(
            openai_status="已配置" if settings.openai_api_key else "未配置",
            openai_status_class="status-ok" if settings.openai_api_key else "status-warn",
            answer_mode=answer.mode if answer else "未提问",
            answer_confidence=answer.confidence if answer else "-",
        ),
        "session_id": escape(session_id),
        "session_options": render_session_options(sessions, session_id),
        "ask_status_badge": render_ask_status_badge(answer, answer_state),
        "prefill_context_panel": render_prefill_context_panel(prefill_context),
        "conversation_panel": render_conversation_panel(messages, answer=answer, message=message),
        "session_history_drawer": render_session_history_drawer(sessions, session_id),
        "ask_sidebar": render_ask_sidebar(
            sessions=sessions,
            selected_session_id=session_id,
            answer=answer,
            answer_state=answer_state,
            prefill_context=prefill_context,
            openai_ready=bool(settings.openai_api_key),
        ),
        "answer_panel": render_answer_panel(
            answer,
            message,
            session_id=session_id,
            question=question,
            search_mode=normalized_mode,
            limit=limit,
            use_llm=use_llm,
            use_embeddings=use_embeddings,
            model=selected_model,
            answer_style=answer_style,
            answer_state=answer_state,
        ),
    }
    for key, value in replacements.items():
        template = template.replace("{{ " + key + " }}", value)
    return template


def render_chat_status_bar(openai_status: str, openai_status_class: str, answer_mode: str, answer_confidence: str) -> str:
    return (
        '<span class="tag-chip">OpenAI：<strong class="{status_class}">{openai_status}</strong></span>'
        '<span class="tag-chip">模式：{answer_mode}</span>'
        '<span class="tag-chip">置信度：{answer_confidence}</span>'
    ).format(
        status_class=escape(openai_status_class),
        openai_status=escape(openai_status),
        answer_mode=escape(answer_mode),
        answer_confidence=escape(answer_confidence),
    )


def render_ask_status_badge(answer: Optional[Answer], answer_state: str) -> str:
    if answer_state == "model_error":
        return '<span class="tag-chip">已切换到来源摘要</span>'
    if answer_state == "config_error":
        return '<span class="tag-chip">需要检查设置</span>'
    if answer and answer.mode == "rag":
        return '<span class="tag-chip">智能回答</span>'
    if answer and answer.mode == "extractive":
        return '<span class="tag-chip">来源摘要</span>'
    return '<span class="tag-chip">直接提问</span>'


def render_prefill_context_panel(prefill_context: str) -> str:
    if not prefill_context:
        return ""
    return (
        '<section class="context-strip">'
        '<span class="task-step">已带入搜索上下文</span>'
        f'<div class="summary-card">{escape(prefill_context)}</div>'
        '</section>'
    )


def render_answer_panel(
    answer: Optional[Answer],
    message: str = "",
    session_id: str = "",
    question: str = "",
    search_mode: str = "auto",
    limit: int = 3,
    use_llm: bool = True,
    use_embeddings: bool = True,
    model: str = "",
    answer_style: str = "balanced",
    answer_state: str = "idle",
) -> str:
    if answer is None and not message:
        return ""

    parts = ['<details class="answer-drawer" data-result-panel>', '<summary><span>查看引用与操作</span></summary>', '<p class="sr-only" aria-live="polite" data-live-region></p>']
    if message:
        parts.append(f'<p class="notice">{escape(message)}</p>')
    if answer:
        parts.append(
            render_answer_summary(
                answer,
                answer_state=answer_state,
                question=question,
                search_mode=search_mode,
                limit=limit,
                use_llm=use_llm,
                use_embeddings=use_embeddings,
                model=model,
                answer_style=answer_style,
                session_id=session_id,
            )
        )
        parts.append('<div class="answer-stack">')
        parts.append('<article class="answer-block answer-block-inline"><h3>最新回答</h3>')
        parts.append(f'<pre class="answer-text">{escape(answer.text)}</pre></article>')
        parts.append('<article class="answer-block answer-block-inline"><h3>回答信息</h3><dl class="meta-grid answer-meta">')
        parts.append(f'<div><dt>回答方式</dt><dd>{escape(describe_answer_mode(answer.mode))}</dd></div>')
        parts.append(f'<div><dt>可信度</dt><dd>{escape(answer.confidence)}</dd></div>')
        parts.append(f'<div><dt>引用来源</dt><dd>{len(answer.sources)}</dd></div>')
        parts.append(f'<div><dt>回答风格</dt><dd>{escape(ANSWER_STYLES.get(answer.style, answer.style))}</dd></div>')
        parts.append(f'<div><dt>当前问题</dt><dd>{escape(answer.question[:40])}</dd></div>')
        parts.append('</dl></article>')
        if answer.sources:
            parts.append('<article class="answer-block answer-block-inline"><h3>依据来源</h3><ul class="source-list">')
            for source in answer.sources:
                parts.append(f'<li>{escape(source)}</li>')
            parts.append('</ul></article>')
        if session_id:
            parts.append(
                (
                    '<article class="answer-block answer-block-inline"><h3>下一步可以做</h3><div class="toolbar">'
                    '<form method="post" action="/ask/save-note" class="inline-action-form">'
                    f'<input type="hidden" name="session_id" value="{escape(session_id)}">'
                    '<button type="submit">保存为笔记</button>'
                    '</form>'
                    '<a class="secondary-button" href="/ask?session_id={session_id}">继续追问</a>'
                    '{follow_up_link}'
                    '</div></article>'
                ).format(
                    session_id=escape(session_id),
                    follow_up_link=build_follow_up_link(answer),
                )
            )
        if answer.citations:
            parts.append('<article class="answer-block answer-block-inline"><h3>引用片段</h3><div class="citation-grid">')
            for citation in answer.citations:
                parts.append(
                    '<article class="citation-card">'
                    f'<h4>{escape(citation.title or "Untitled")}</h4>'
                    f'<small>{escape(citation.source)}</small>'
                    f'<mark>{escape(citation.snippet)}</mark>'
                    '</article>'
                )
            parts.append('</div></article>')
        parts.append('</div>')
    parts.append("</details>")
    return "\n".join(parts)


def describe_answer_mode(mode: str) -> str:
    mapping = {
        "rag": "智能回答",
        "extractive": "来源摘要",
        "fallback": "来源摘要（模型失败后切换）",
        "none": "暂无结果",
    }
    return mapping.get(mode, mode)


def render_answer_summary(
    answer: Answer,
    answer_state: str = "idle",
    question: str = "",
    search_mode: str = "auto",
    limit: int = 3,
    use_llm: bool = True,
    use_embeddings: bool = True,
    model: str = "",
    answer_style: str = "balanced",
    session_id: str = "",
) -> str:
    if answer.mode == "none":
        return (
            '<div class="summary-card">你的知识库里暂时没有足够相关的信息。试试换个问法，或者先导入相关资料。</div>'
            + render_retry_actions(
                question=question,
                search_mode=search_mode,
                limit=limit,
                use_llm=use_llm,
                use_embeddings=use_embeddings,
                model=model,
                answer_style=answer_style,
                session_id=session_id,
                include_source_only=False,
            )
        )
    if answer.mode == "fallback" or answer_state == "model_error":
        return (
            '<div class="summary-card warn-card">模型调用这次没有成功，已自动切换为来源摘要模式。你可以一键重试，或继续使用来源摘要回答。</div>'
            + render_retry_actions(
                question=question,
                search_mode=search_mode,
                limit=limit,
                use_llm=use_llm,
                use_embeddings=use_embeddings,
                model=model,
                answer_style=answer_style,
                session_id=session_id,
                include_source_only=True,
            )
        )
    if answer_state == "config_error":
        return (
            '<div class="summary-card warn-card">当前配置还不完整，暂时无法稳定生成 AI 回答。你可以先查看来源摘要，或去设置页检查模型配置。</div>'
            + render_retry_actions(
                question=question,
                search_mode=search_mode,
                limit=limit,
                use_llm=False,
                use_embeddings=use_embeddings,
                model=model,
                answer_style=answer_style,
                session_id=session_id,
                include_source_only=False,
            )
            + '<div class="toolbar"><a class="secondary-button" href="/settings">检查设置</a></div>'
        )
    if answer.mode == "extractive":
        return '<div class="summary-card">我已经先根据现有资料整理出来源摘要，你可以继续追问，或先检查引用依据。</div>'
    return '<div class="summary-card">回答已生成。我先给你结论，再把依据和后续建议一起展开。</div>'


def render_retry_actions(
    question: str,
    search_mode: str,
    limit: int,
    use_llm: bool,
    use_embeddings: bool,
    model: str,
    answer_style: str,
    session_id: str = "",
    include_source_only: bool = False,
) -> str:
    if not question:
        return ""
    parts = ['<div class="toolbar">']
    parts.append(
        build_retry_form(
            label="立即重试",
            question=question,
            search_mode=search_mode,
            limit=limit,
            use_llm=use_llm,
            use_embeddings=use_embeddings,
            model=model,
            answer_style=answer_style,
            session_id=session_id,
        )
    )
    if include_source_only:
        parts.append(
            build_retry_form(
                label="改用来源摘要",
                question=question,
                search_mode=search_mode,
                limit=limit,
                use_llm=False,
                use_embeddings=use_embeddings,
                model=model,
                answer_style=answer_style,
                session_id=session_id,
            )
        )
    parts.append("</div>")
    return "".join(parts)


def build_retry_form(
    label: str,
    question: str,
    search_mode: str,
    limit: int,
    use_llm: bool,
    use_embeddings: bool,
    model: str,
    answer_style: str,
    session_id: str = "",
) -> str:
    hidden_fields = [
        f'<input type="hidden" name="question" value="{escape(question)}">',
        f'<input type="hidden" name="search_mode" value="{escape(search_mode)}">',
        f'<input type="hidden" name="limit" value="{limit}">',
        f'<input type="hidden" name="model" value="{escape(model)}">',
        f'<input type="hidden" name="answer_style" value="{escape(answer_style)}">',
        f'<input type="hidden" name="session_id" value="{escape(session_id)}">',
        f'<input type="hidden" name="session_id_selector" value="{escape(session_id)}">',
    ]
    if use_llm:
        hidden_fields.append('<input type="hidden" name="use_llm" value="1">')
    if use_embeddings:
        hidden_fields.append('<input type="hidden" name="use_embeddings" value="1">')
    return (
        '<form method="post" action="/ask" class="inline-action-form">'
        + "".join(hidden_fields)
        + f'<button type="submit">{escape(label)}</button>'
        + "</form>"
    )


def render_style_options(selected_style: str) -> str:
    options = []
    normalized = selected_style if selected_style in ANSWER_STYLES else "balanced"
    for value, label in ANSWER_STYLES.items():
        selected = " selected" if value == normalized else ""
        options.append(f'<option value="{escape(value)}"{selected}>{escape(label)}</option>')
    return "\n".join(options)


def render_session_options(sessions: list, selected_session_id: str) -> str:
    options = ['<option value="">新对话</option>']
    for session in sessions:
        selected = " selected" if str(session.id) == str(selected_session_id) else ""
        options.append(f'<option value="{session.id}"{selected}>{escape(session.title)}</option>')
    return "\n".join(options)


def render_conversation_panel(messages: list, answer: Optional[Answer] = None, message: str = "") -> str:
    if not messages and answer is None and not message:
        return (
            '<section class="panel conversation-shell chat-surface">'
            '<div class="panel-heading"><h2>开始聊天</h2><p>像和知识助手聊天一样直接输入问题，我会先找资料，再给答案。</p></div>'
            '<div class="empty-conversation-state">'
            '<strong>你可以直接问：</strong>'
            '<p>“我最近关于 RAG 的重点结论是什么？”</p>'
            '<p>“这些资料里下一步最值得补什么？”</p>'
            '</div></section>'
        )
    parts = ['<section class="panel conversation-shell chat-surface">', '<div class="panel-heading"><h2>聊天记录</h2><p>像即时聊天一样浏览问题、回答和引用上下文。</p></div>', '<div class="chat-thread">']
    for chat_message in messages:
        role_class = "chat-user" if chat_message.role == "user" else "chat-assistant"
        role_label = "你" if chat_message.role == "user" else "知识助手"
        parts.append(
            f'<article class="chat-bubble {role_class}"><div class="chat-bubble-head"><strong>{role_label}</strong></div><pre>{escape(chat_message.content)}</pre></article>'
        )
    if answer is None and message:
        parts.append(
            '<article class="chat-bubble chat-assistant chat-loading">'
            '<div class="chat-bubble-head"><strong>知识助手</strong></div>'
            f'<p>{escape(message)}</p>'
            '</article>'
        )
    parts.append("</div></section>")
    return "\n".join(parts)


def render_session_history_panel(sessions: list, selected_session_id: str) -> str:
    if not sessions:
        return ""
    parts = ['<section class="panel">', '<div class="panel-heading"><h2>最近会话</h2><p>快速切换最近的问答上下文。</p></div>', '<ul class="history-list">']
    for session in sessions:
        active = ' class="active-history"' if str(session.id) == str(selected_session_id) else ""
        parts.append(
            f'<li{active}><a href="/ask?session_id={session.id}">{escape(session.title)}</a><small>{escape(session.updated_at)}</small></li>'
        )
    parts.append("</ul></section>")
    return "\n".join(parts)


def render_session_history_drawer(sessions: list, selected_session_id: str) -> str:
    if not sessions:
        return ""
    parts = ['<details class="session-drawer">', '<summary>历史会话</summary>', '<ul class="history-list compact-history-list">']
    for session in sessions:
        active = ' class="active-history"' if str(session.id) == str(selected_session_id) else ""
        parts.append(
            f'<li{active}><a href="/ask?session_id={session.id}">{escape(session.title)}</a><small>{escape(session.updated_at)}</small></li>'
        )
    parts.append("</ul></details>")
    return "\n".join(parts)


def render_ask_sidebar(sessions: list, selected_session_id: str, answer: Optional[Answer], answer_state: str, prefill_context: str, openai_ready: bool) -> str:
    del sessions, selected_session_id, answer, answer_state, prefill_context, openai_ready
    return ""


def resolve_session_title(sessions: list, selected_session_id: str) -> str:
    for session in sessions:
        if str(session.id) == str(selected_session_id):
            return session.title
    return "新对话"


def resolve_answer_state_label(answer: Optional[Answer], answer_state: str) -> str:
    if answer_state == "model_error":
        return "已切换为来源摘要"
    if answer_state == "config_error":
        return "需要检查设置"
    if answer and answer.mode == "rag":
        return "已生成智能回答"
    if answer and answer.mode == "extractive":
        return "已生成来源摘要"
    return "等待提问"


def build_follow_up_link(answer: Answer) -> str:
    prompt = f"基于刚才这次回答，请继续展开：{answer.question}"
    return f'<a class="secondary-button" href="/ask?question={escape(prompt)}">继续追问这个结论</a>'
