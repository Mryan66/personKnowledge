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
        "session_id": escape(session_id),
        "session_options": render_session_options(sessions, session_id),
        "prefill_context_panel": render_prefill_context_panel(prefill_context),
        "conversation_panel": render_conversation_panel(messages),
        "session_history_panel": render_session_history_panel(sessions, session_id),
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


def render_prefill_context_panel(prefill_context: str) -> str:
    if not prefill_context:
        return ""
    return (
        '<section class="panel">'
        '<div class="panel-heading"><h2>已带入搜索上下文</h2><p>你是从一条搜索结果继续来到这里的，可以直接在此基础上追问。</p></div>'
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

    parts = ['<section class="panel answer-panel" data-result-panel>', '<div class="panel-heading"><h2>回答</h2><p>先看结论，再决定是否继续追问或保存为笔记。</p></div>', '<p class="sr-only" aria-live="polite" data-live-region></p>']
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
        parts.append('<dl class="meta-grid answer-meta">')
        parts.append(f'<div><dt>回答方式</dt><dd>{escape(answer.mode)}</dd></div>')
        parts.append(f'<div><dt>可信度</dt><dd>{escape(answer.confidence)}</dd></div>')
        parts.append(f'<div><dt>引用来源</dt><dd>{len(answer.sources)}</dd></div>')
        parts.append(f'<div><dt>回答风格</dt><dd>{escape(ANSWER_STYLES.get(answer.style, answer.style))}</dd></div>')
        parts.append(f'<div><dt>问题</dt><dd>{escape(answer.question[:40])}</dd></div>')
        parts.append('</dl>')
        parts.append(f'<pre class="answer-text">{escape(answer.text)}</pre>')
        if session_id:
            parts.append(
                '<div class="toolbar">'
                '<form method="post" action="/ask/save-note" class="inline-action-form">'
                f'<input type="hidden" name="session_id" value="{escape(session_id)}">'
                '<button type="submit">保存为笔记</button>'
                '</form>'
                '<a class="secondary-button" href="/ask?session_id={session_id}">继续追问</a>'
                '</div>'.format(session_id=escape(session_id))
            )
        if answer.citations:
            parts.append('<h3>引用高亮</h3><div class="citation-grid">')
            for citation in answer.citations:
                parts.append(
                    '<article class="citation-card">'
                    f'<h4>{escape(citation.title or "Untitled")}</h4>'
                    f'<small>{escape(citation.source)}</small>'
                    f'<mark>{escape(citation.snippet)}</mark>'
                    '</article>'
                )
            parts.append('</div>')
        if answer.sources:
            parts.append('<h3>来源</h3><ul class="source-list">')
            for source in answer.sources:
                parts.append(f'<li>{escape(source)}</li>')
            parts.append('</ul>')
    parts.append("</section>")
    return "\n".join(parts)


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
        return '<div class="summary-card">已根据知识库整理出来源摘要。你可以继续追问，或保存为笔记。</div>'
    return '<div class="summary-card">回答已生成。先看结论，再查看引用来源和后续建议。</div>'


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


def render_conversation_panel(messages: list) -> str:
    if not messages:
        return ""
    parts = ['<section class="panel">', '<div class="panel-heading"><h2>多轮对话</h2><p>保留当前会话上下文，支持继续追问。</p></div>', '<div class="chat-thread">']
    for message in messages:
        role_class = "chat-user" if message.role == "user" else "chat-assistant"
        role_label = "你" if message.role == "user" else "AI"
        parts.append(
            f'<article class="chat-bubble {role_class}"><strong>{role_label}</strong><pre>{escape(message.content)}</pre></article>'
        )
    parts.append("</div></section>")
    return "\n".join(parts)


def render_session_history_panel(sessions: list, selected_session_id: str) -> str:
    if not sessions:
        return ""
    parts = ['<section class="panel">', '<div class="panel-heading"><h2>对话历史</h2><p>快速切换最近会话。</p></div>', '<ul class="history-list">']
    for session in sessions:
        active = ' class="active-history"' if str(session.id) == str(selected_session_id) else ""
        parts.append(
            f'<li{active}><a href="/ask?session_id={session.id}">{escape(session.title)}</a><small>{escape(session.updated_at)}</small></li>'
        )
    parts.append("</ul></section>")
    return "\n".join(parts)
