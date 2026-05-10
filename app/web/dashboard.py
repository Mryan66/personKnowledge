from html import escape
from pathlib import Path

from app.config import Settings
from app.memory.database import get_dashboard_stats, get_document_growth_stats


PLACEHOLDER_CARDS = [
    ("每日导入统计", "预留：展示每天导入成功/失败数量"),
    ("Token 成本统计", "预留：统计 OpenAI 调用与费用"),
    ("待办提醒", "预留：展示从笔记提取的 Todo"),
    ("过期知识提醒", "预留：提示长期未复习或可能过期内容"),
]


def render_dashboard(settings: Settings, template_path: Path) -> str:
    stats = get_dashboard_stats(settings.resolved_database_path)
    growth_stats = get_document_growth_stats(settings.resolved_database_path, days=30)
    template = template_path.read_text(encoding="utf-8")
    replacements = {
        "app_name": settings.app_name,
        "document_count": str(stats["document_count"]),
        "chunk_count": str(stats["chunk_count"]),
        "embedding_count": str(stats["embedding_count"]),
        "tag_count": str(stats["tag_count"]),
        "recent_documents": render_recent_documents(stats["recent_documents"]),
        "recent_review": render_recent_review(settings.resolved_knowledge_dir / "reviews"),
        "openai_status": "已配置" if settings.openai_api_key else "未配置",
        "openai_status_class": "status-ok" if settings.openai_api_key else "status-warn",
        "search_status": "Auto：混合搜索（关键词 + 向量）+ Rerank",
        "growth_panel": render_growth_panel(growth_stats),
        "placeholder_cards": render_placeholder_cards(),
    }
    for key, value in replacements.items():
        template = template.replace("{{ " + key + " }}", value)
    return template


def render_recent_documents(documents) -> str:
    if not documents:
        return '<li class="muted">暂无入库文档，先从 Inbox 导入文件。</li>'
    items = []
    for document in documents:
        title = escape(document.title or "Untitled")
        category = escape(document.category or "uncategorized")
        source_path = escape(document.source_path)
        items.append(
            f'<li><strong>{title}</strong><span>{category}</span><small>{source_path}</small></li>'
        )
    return "\n".join(items)


def render_recent_review(reviews_dir: Path) -> str:
    if not reviews_dir.exists():
        return "暂无 Review"
    review_files = sorted(reviews_dir.glob("*.md"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not review_files:
        return "暂无 Review"
    return escape(review_files[0].name)


def render_growth_panel(growth_stats: list) -> str:
    if not growth_stats:
        return '<section class="panel"><p class="muted">暂无增长数据。</p></section>'
    total = sum(item["count"] for item in growth_stats)
    max_count = max(item["count"] for item in growth_stats) if growth_stats else 1
    lines = ['<section class="panel">', '<div class="panel-heading"><h2>知识增长</h2><p>最近 30 天文档增长趋势。</p></div>']
    lines.append(f'<p><strong>总计新增：{total} 篇文档</strong></p>')
    lines.append('<div class="growth-chart">')
    for item in growth_stats:
        width_pct = (item["count"] / max_count) * 100 if max_count > 0 else 0
        lines.append(
            f'<div class="growth-bar-item">'
            f'<span class="growth-date">{escape(item["date"])}</span>'
            f'<div class="growth-bar" style="width: {width_pct:.1f}%"></div>'
            f'<span class="growth-count">{item["count"]}</span>'
            '</div>'
        )
    lines.append("</div>")
    lines.append("</section>")
    return "\n".join(lines)


def render_placeholder_cards() -> str:
    cards = []
    for title, description in PLACEHOLDER_CARDS:
        cards.append(
            f'<article class="placeholder-card"><h3>{escape(title)}</h3><p>{escape(description)}</p></article>'
        )
    return "\n".join(cards)
