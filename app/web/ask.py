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
        "conversation_panel": render_conversation_panel(messages),
        "session_history_panel": render_session_history_panel(sessions, session_id),
        "answer_panel": render_answer_panel(answer, message, session_id=session_id),
    }
    for key, value in replacements.items():
        template = template.replace("{{ " + key + " }}", value)
    return template


def render_answer_panel(answer: Optional[Answer], message: str = "", session_id: str = "") -> str:
    if answer is None and not message:
        return ""

    parts = ['<section class="panel answer-panel">', '<div class="panel-heading"><h2>回答</h2><p>显示 RAG 或来源型回答结果。</p></div>']
    if message:
        parts.append(f'<p class="notice">{escape(message)}</p>')
    if answer:
        parts.append('<dl class="meta-grid answer-meta">')
        parts.append(f'<div><dt>Mode</dt><dd>{escape(answer.mode)}</dd></div>')
        parts.append(f'<div><dt>Confidence</dt><dd>{escape(answer.confidence)}</dd></div>')
        parts.append(f'<div><dt>Sources</dt><dd>{len(answer.sources)}</dd></div>')
        parts.append(f'<div><dt>Style</dt><dd>{escape(ANSWER_STYLES.get(answer.style, answer.style))}</dd></div>')
        parts.append(f'<div><dt>Question</dt><dd>{escape(answer.question[:40])}</dd></div>')
        parts.append('</dl>')
        parts.append(f'<pre class="answer-text">{escape(answer.text)}</pre>')
        if session_id:
            parts.append(
                '<form method="post" action="/ask/save-note" class="inline-action-form">'
                f'<input type="hidden" name="session_id" value="{escape(session_id)}">'
                '<button type="submit">保存为笔记</button>'
                '</form>'
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
