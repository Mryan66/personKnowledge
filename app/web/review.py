from html import escape
from pathlib import Path
from typing import Optional

from app.agents.review_agent import ReviewReport
from app.config import Settings


REVIEW_PERIODS = {
    "daily": "Daily：每日复盘",
    "weekly": "Weekly：每周复盘",
    "monthly": "Monthly：每月复盘",
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
    template = template_path.read_text(encoding="utf-8")
    reviews_dir = settings.resolved_knowledge_dir / "reviews"
    replacements = {
        "app_name": settings.app_name,
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
    for key, value in replacements.items():
        template = template.replace("{{ " + key + " }}", value)
    return template


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
    return files[0].name if files else "暂无 Review"


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
    parts = ['<section class="panel review-panel">', '<div class="panel-heading"><h2>生成结果</h2><p>展示本次生成的 Review Markdown。</p></div>']
    if message:
        parts.append(f'<p class="notice">{escape(message)}</p>')
    if report:
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
        f'<pre class="markdown-preview">{escape(selected_body)}</pre>'
        '</section>'
    )


def format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / 1024 / 1024:.1f} MB"
