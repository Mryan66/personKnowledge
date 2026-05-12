from html import escape
from pathlib import Path

from app.config import Settings
from app.ui.rendering import render_template
from app.memory.database import get_dashboard_stats, get_document_growth_stats


PLACEHOLDER_CARDS = [
    ("生成一次复盘", "把最近导入的内容整理成一份可回看的总结"),
    ("围绕主题继续追问", "从搜索结果直接进入 AI 问答，沉淀更完整的理解"),
    ("整理标签与分类", "让后续搜索和复盘更稳定、更容易找到重点"),
    ("保存答案为笔记", "把高价值问答回写到知识库，形成长期积累"),
]


def render_dashboard(settings: Settings, template_path: Path) -> str:
    stats = get_dashboard_stats(settings.resolved_database_path)
    growth_stats = get_document_growth_stats(settings.resolved_database_path, days=30)
    review_count = count_reviews(settings.resolved_knowledge_dir / "reviews")
    context = {
        "app_name": settings.app_name,
        "active_nav": "dashboard",
        "page_name": "dashboard",
        "frontend_assets_enabled": settings.frontend_assets_enabled,
        "document_count": str(stats["document_count"]),
        "chunk_count": str(stats["chunk_count"]),
        "embedding_count": str(stats["embedding_count"]),
        "tag_count": str(stats["tag_count"]),
        "recent_documents": render_recent_documents(stats["recent_documents"]),
        "recent_review": render_recent_review(settings.resolved_knowledge_dir / "reviews"),
        "openai_status": "已配置" if settings.openai_api_key else "未配置",
        "openai_status_class": "status-ok" if settings.openai_api_key else "status-warn",
        "search_status": "智能搜索（关键词 + 语义理解）",
        "growth_panel": render_growth_panel(growth_stats),
        "onboarding_panel": render_onboarding_panel(
            document_count=stats["document_count"],
            search_count=stats["search_count"],
            ask_count=stats["ask_count"],
            review_count=review_count,
        ),
        "placeholder_cards": render_placeholder_cards(),
    }
    return render_template(template_path, context)


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
        return "还没有复盘"
    review_files = sorted(reviews_dir.glob("*.md"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not review_files:
        return "还没有复盘"
    return escape(review_files[0].name)


def render_onboarding_panel(document_count: int, search_count: int, ask_count: int, review_count: int) -> str:
    steps = [
        (1, "放入文件", "把笔记、PDF 或网页资料放进 Inbox 文件夹", "/inbox"),
        (2, "导入知识", "点击一次导入，让资料进入知识库", "/inbox"),
        (3, "完成一次搜索", "用自然语言搜一个主题，看看结果结构", "/search"),
        (4, "完成一次 AI 提问", "围绕搜索结果继续追问，生成一份回答", "/ask"),
        (5, "生成首份复盘", "把最近导入和提问过的内容总结成一份回顾", "/review"),
    ]
    completion_map = {
        1: document_count > 0,
        2: document_count > 0,
        3: search_count > 0,
        4: ask_count > 0,
        5: review_count > 0,
    }
    cards = ['<div class="task-grid">']
    for index, title, description, href in steps:
        status = "已完成" if completion_map.get(index) else "下一步"
        status_class = "task-done" if completion_map.get(index) else "task-next"
        cards.append(
            '<a class="task-card" href="{href}">'
            '<span class="task-step">步骤 {index}</span>'
            '<strong>{title}</strong>'
            '<p>{description}</p>'
            '<small class="{status_class}">{status}</small>'
            '</a>'.format(
                href=escape(href),
                index=index,
                title=escape(title),
                description=escape(description),
                status_class=status_class,
                status=escape(status),
            )
        )
    cards.append("</div>")
    return "\n".join(cards)


def count_reviews(reviews_dir: Path) -> int:
    if not reviews_dir.exists():
        return 0
    return len(list(reviews_dir.glob("*.md")))


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
