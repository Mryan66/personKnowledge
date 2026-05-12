from html import escape
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from app.agents.review_agent import ReviewReport
from app.config import Settings
from app.ui.rendering import render_template


REVIEW_PERIODS = {
    "daily": "每日复盘",
    "weekly": "每周复盘",
    "monthly": "每月复盘",
}


def render_review(
    settings: Settings,
    template_path: Path,
    limit: int = 20,
    period: str = "daily",
    write_file: bool = True,
    report: Optional[ReviewReport] = None,
    selected_review: str = "",
    selected_body: str = "",
    message: str = "",
) -> str:
    reviews_dir = settings.resolved_knowledge_dir / "reviews"
    context = {
        "app_name": settings.app_name,
        "active_nav": "review",
        "page_name": "review",
        "frontend_assets_enabled": settings.frontend_assets_enabled,
        "limit": str(limit),
        "period": escape(period),
        "period_options": render_period_options(period),
        "write_file_checked": "checked" if write_file else "",
        "reviews_dir": escape(str(reviews_dir)),
        "review_count": str(len(list_review_files(reviews_dir))),
        "latest_review": escape(get_latest_review_name(reviews_dir)),
        "report_panel": render_report_panel(report, message),
        "history_list": render_history_list(reviews_dir, selected_review),
        "selected_review_panel": render_selected_review_panel(selected_review, selected_body),
    }
    return render_template(template_path, context)


def render_period_options(selected_period: str) -> str:
    options = []
    for value, label in REVIEW_PERIODS.items():
        selected = " selected" if value == selected_period else ""
        options.append(f'<option value="{escape(value)}"{selected}>{escape(label)}</option>')
    return "\n".join(options)


def list_review_files(reviews_dir: Path) -> list:
    if not reviews_dir.exists():
        return []
    return sorted(reviews_dir.glob("*.md"), key=lambda path: path.stat().st_mtime, reverse=True)


def get_latest_review_name(reviews_dir: Path) -> str:
    files = list_review_files(reviews_dir)
    return files[0].name if files else "还没有复盘"


def read_review_file(reviews_dir: Path, filename: str) -> str:
    if not filename:
        return ""
    target = reviews_dir / filename
    try:
        target.resolve().relative_to(reviews_dir.resolve())
    except ValueError:
        return ""
    if not target.exists() or target.suffix != ".md":
        return ""
    return target.read_text(encoding="utf-8")


def render_report_panel(report: Optional[ReviewReport], message: str = "") -> str:
    if report is None and not message:
        return ""
    parts = ['<section class="panel review-panel" data-result-panel>', '<div class="panel-heading"><h2>生成结果</h2><p>展示本次复盘摘要和 Markdown 内容。</p></div>', '<p class="sr-only" aria-live="polite" data-live-region></p>']
    if message:
        parts.append(f'<p class="notice">{escape(message)}</p>')
    if report:
        parts.append('<div class="summary-card">复盘已生成。这是你最近知识变化的精简总结，可以继续对比历史复盘。</div>')
        parts.append(render_review_action_panel(report.body))
        if report.path:
            parts.append(f'<p class="muted">已写入：{escape(str(report.path))}</p>')
        parts.append(f'<pre class="markdown-preview">{escape(report.body)}</pre>')
    parts.append("</section>")
    return "\n".join(parts)


def render_history_list(reviews_dir: Path, selected_review: str = "") -> str:
    files = list_review_files(reviews_dir)
    if not files:
        return '<li class="muted">暂无历史 Review。</li>'
    items = []
    for path in files:
        active = " class=\"active-history\"" if path.name == selected_review else ""
        items.append(
            f'<li{active}><a href="/review?file={escape(path.name)}">{escape(path.name)}</a>'
            f'<small>{format_size(path.stat().st_size)}</small></li>'
        )
    return "\n".join(items)


def render_selected_review_panel(selected_review: str, selected_body: str) -> str:
    if not selected_review:
        return ""
    if not selected_body:
        return '<section class="panel"><p class="muted">未能读取选中的 Review 文件。</p></section>'
    return (
        '<section class="panel review-panel">'
        f'<div class="panel-heading"><h2>{escape(selected_review)}</h2><p>历史 Review 内容。</p></div>'
        f'{render_review_action_panel(selected_body)}'
        f'<pre class="markdown-preview">{escape(selected_body)}</pre>'
        '</section>'
    )


def format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / 1024 / 1024:.1f} MB"


def render_review_action_panel(body: str) -> str:
    insights = extract_review_insights(body)
    actions = []
    for tag in insights["top_tags"][:3]:
        actions.append(build_action_link(f"搜索标签：{tag}", f"/search?q={quote(tag)}"))
        actions.append(build_action_link(f"追问主题：{tag}", f"/ask?question={quote(f'请总结我知识库里和 {tag} 相关的重点')}"))
    for category in insights["top_categories"][:2]:
        actions.append(build_action_link(f"查看分类：{category}", f"/search?q={quote(category)}"))
    for title in insights["document_titles"][:2]:
        actions.append(build_action_link(f"围绕《{title}》继续问", f"/ask?question={quote(f'请基于《{title}》总结重点，并给出下一步建议')}"))
    if not actions:
        return ""
    return (
        '<div class="panel-heading"><h2>基于这份复盘，你可以马上做</h2><p>把复盘里的主题直接带回搜索或问答，减少来回切换。</p></div>'
        '<div class="card-actions">' + "".join(actions) + '</div>'
    )


def extract_review_insights(body: str) -> dict:
    top_tags = []
    top_categories = []
    document_titles = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if line.startswith("- 高频标签："):
            top_tags = split_review_values(line.removeprefix("- 高频标签："))
        elif line.startswith("- 主要分类："):
            top_categories = split_review_values(line.removeprefix("- 主要分类："))
        elif line.startswith("- **") and "**" in line[4:]:
            title = line[4:].split("**", 1)[0].strip()
            if title:
                document_titles.append(title)
    return {
        "top_tags": top_tags,
        "top_categories": top_categories,
        "document_titles": document_titles,
    }


def split_review_values(text: str) -> list[str]:
    normalized = (text or "").strip()
    if not normalized or normalized == "暂无":
        return []
    return [item.strip() for item in normalized.split(",") if item.strip()]


def build_action_link(label: str, href: str) -> str:
    return f'<a href="{escape(href)}">{escape(label)}</a>'
