from html import escape
from pathlib import Path
from typing import List

from app.config import Settings
from app.tools.search_tool import SearchResult

SEARCH_MODES = {
    "auto": "Auto：混合搜索（关键词 + 向量）+ Rerank",
    "keyword": "Keyword：按标题、标签、分类、摘要和正文匹配",
    "vector": "Vector：使用 Embedding 语义相似度检索",
}


def render_search(
    settings: Settings,
    template_path: Path,
    query: str = "",
    mode: str = "auto",
    limit: int = 5,
    filters: dict = None,
    results: List[SearchResult] = None,
    search_history: List[dict] = None,
    message: str = "",
) -> str:
    results = results or []
    search_history = search_history or []
    filters = filters or {}
    normalized_mode = mode if mode in SEARCH_MODES else "auto"
    template = template_path.read_text(encoding="utf-8")
    replacements = {
        "app_name": settings.app_name,
        "query": escape(query),
        "limit": str(limit),
        "category_filter": escape(filters.get("category", "")),
        "tag_filter": escape(filters.get("tag", "")),
        "person_filter": escape(filters.get("person", "")),
        "date_from_filter": escape(filters.get("date_from", "")),
        "date_to_filter": escape(filters.get("date_to", "")),
        "mode_options": render_mode_options(normalized_mode),
        "mode_description": SEARCH_MODES[normalized_mode],
        "openai_status": "已配置" if settings.openai_api_key else "未配置",
        "openai_status_class": "status-ok" if settings.openai_api_key else "status-warn",
        "result_count": str(len(results)),
        "results_panel": render_results_panel(results, query, message, filters=filters),
        "search_history_panel": render_search_history_panel(search_history),
    }
    for key, value in replacements.items():
        template = template.replace("{{ " + key + " }}", value)
    return template


def render_mode_options(selected_mode: str) -> str:
    options = []
    for value, label in SEARCH_MODES.items():
        selected = " selected" if value == selected_mode else ""
        options.append(f'<option value="{escape(value)}"{selected}>{escape(label)}</option>')
    return "\n".join(options)


def render_results_panel(results: List[SearchResult], query: str, message: str = "", filters: dict = None) -> str:
    filters = filters or {}
    if not query and not message:
        return ""

    parts = ['<section class="panel result-panel">', '<div class="panel-heading"><h2>搜索结果</h2><p>展示匹配的知识库 chunk。</p></div>']
    if message:
        parts.append(f'<p class="notice">{escape(message)}</p>')
    active_filters = render_active_filters(filters)
    if active_filters:
        parts.append(active_filters)
    if query and not results:
        parts.append(f'<p class="muted">没有找到与 “{escape(query)}” 相关的结果。</p>')
    if results:
        parts.append('<div class="search-results">')
        for index, result in enumerate(results, start=1):
            tag_text = ", ".join(result.tags) if result.tags else "暂无标签"
            snippet = build_snippet(result.content)
            parts.append(
                '<article class="search-result">'
                f'<div class="result-rank">{index}</div>'
                '<div class="result-body">'
                f'<h3>{escape(result.title or "Untitled")}</h3>'
                f'<p>{escape(snippet)}</p>'
                '<dl class="meta-grid">'
                f'<div><dt>Score</dt><dd>{result.score:.4g}</dd></div>'
                f'<div><dt>Mode</dt><dd>{escape(result.mode)}</dd></div>'
                f'<div><dt>Category</dt><dd>{escape(result.category or "uncategorized")}</dd></div>'
                f'<div><dt>Chunk</dt><dd>{result.chunk_index}</dd></div>'
                '</dl>'
                f'<small class="source-path">{escape(result.source_path)}#chunk-{result.chunk_index}</small>'
                f'<div class="tag-line">{escape(tag_text)}</div>'
                '</div>'
                '</article>'
            )
        parts.append("</div>")
    parts.append("</section>")
    return "\n".join(parts)


def render_active_filters(filters: dict) -> str:
    items = []
    labels = {
        "category": "分类",
        "tag": "标签",
        "person": "人物",
        "date_from": "开始日期",
        "date_to": "结束日期",
    }
    for key, label in labels.items():
        value = (filters.get(key) or "").strip()
        if value:
            items.append(f'<span class="filter-chip">{escape(label)}: <strong>{escape(value)}</strong></span>')
    if not items:
        return ""
    return '<div class="chip-row">' + " ".join(items) + "</div>"


def render_search_history_panel(history: List[dict]) -> str:
    if not history:
        return '<section class="panel"><p class="muted">暂无搜索历史。</p></section>'

    parts = ['<section class="panel">', '<div class="panel-heading"><h2>搜索历史</h2><p>点击可快速再次搜索。</p></div>']
    parts.append('<div class="history-list">')
    for item in history:
        query_text = item["query"]
        mode_text = item["mode"]
        count_text = item["result_count"]
        parts.append(
            f'<a class="history-item" href="/search?q={escape(query_text)}">'
            f'<span class="history-query">{escape(query_text)}</span>'
            f'<span class="history-meta">{escape(mode_text)} · {count_text} 条结果</span>'
            '</a>'
        )
    parts.append("</div>")
    parts.append("</section>")
    return "\n".join(parts)


def build_snippet(content: str, max_length: int = 260) -> str:
    normalized = " ".join(content.split())
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 1].rstrip() + "…"
