from html import escape
from pathlib import Path
from typing import Optional

from app.config import Settings
from app.ingest.pipeline import IngestBatchResult
from app.ingest.scanner import scan_inbox
from app.ui.rendering import render_template


def render_inbox(settings: Settings, template_path: Path, batch: Optional[IngestBatchResult] = None, message: str = "") -> str:
    files = scan_inbox(settings.resolved_inbox_dir)
    context = {
        "app_name": settings.app_name,
        "active_nav": "inbox",
        "page_name": "inbox",
        "frontend_assets_enabled": settings.frontend_assets_enabled,
        "inbox_path": escape(str(settings.resolved_inbox_dir)),
        "openai_status": "已配置" if settings.openai_api_key else "未配置",
        "openai_status_class": "status-ok" if settings.openai_api_key else "status-warn",
        "file_count": str(len(files)),
        "inbox_files": render_inbox_files(files),
        "result_panel": render_result_panel(batch, message),
        "getting_started_panel": render_getting_started_panel(settings, files),
    }
    return render_template(template_path, context)


def render_inbox_files(files) -> str:
    if not files:
        return (
            '<tr><td colspan="5" class="muted center">'
            '还没有可导入的文件。把笔记、PDF 或网页资料放进 Inbox 文件夹后，再回来点击导入。'
            '<br><small>支持 .md / .txt / .pdf / .docx / .html / .png / .jpg。</small>'
            '</td></tr>'
        )
    rows = []
    for file_path in files:
        parse_mode = describe_parse_mode(file_path)
        rows.append(
            "<tr>"
            f"<td><strong>{escape(file_path.name)}</strong><small>{escape(str(file_path))}</small></td>"
            f"<td>{escape(file_path.suffix.lower())}</td>"
            f"<td>{format_size(file_path.stat().st_size)}</td>"
            f"<td>{escape(parse_mode)}</td>"
            f"<td><button type=\"submit\" name=\"path\" value=\"{escape(str(file_path))}\" data-loading-label=\"正在导入...\">导入</button></td>"
            "</tr>"
        )
    return "\n".join(rows)


def render_result_panel(batch: Optional[IngestBatchResult], message: str = "") -> str:
    if batch is None and not message:
        return ""

    parts = ['<section class="panel result-panel" data-result-panel>', '<div class="panel-heading"><h2>导入结果</h2><p>显示本次导入的成功、失败与下一步建议。</p></div>', '<p class="sr-only" aria-live="polite" data-live-region></p>']
    if message:
        parts.append(f'<p class="notice">{escape(message)}</p>')
    if batch:
        summary = build_batch_summary(batch)
        if summary:
            parts.append(f'<div class="summary-card">{summary}</div>')
        if batch.successes:
            parts.append('<h3>成功</h3><ul class="result-list success-list">')
            for result in batch.successes:
                status_text = build_result_status_text(result)
                parts.append(
                    f'<li><strong>{escape(result.title)}</strong><span>{escape(str(result.source_path))}</span>'
                    f'<small>chunks: {result.chunk_count} · embeddings: {result.embedding_count} · {escape(status_text)}</small></li>'
                )
            parts.append("</ul>")
        if batch.failures:
            parts.append('<h3>失败</h3><ul class="result-list failure-list">')
            for failure in batch.failures:
                parts.append(
                    f'<li><strong>{escape(str(failure.source_path))}</strong><span>{escape(failure.reason)}</span></li>'
                )
            parts.append("</ul>")
        if not batch.successes and not batch.failures:
            parts.append('<p class="muted">没有发现可导入文件。</p>')
    parts.append("</section>")
    return "\n".join(parts)


def render_getting_started_panel(settings: Settings, files) -> str:
    inbox_path = escape(str(settings.resolved_inbox_dir))
    if files:
        return (
            '<section class="panel result-panel" data-result-panel>'
            '<div class="panel-heading"><h2>第一步：把文件放进来</h2><p>你已经有可导入文件了，接下来可以直接开始导入。</p></div>'
            '<p class="notice">已在 Inbox 中发现文件。建议先点击“导入全部文件”，完成第一次体验。</p>'
            '<p class="sr-only" aria-live="polite" data-live-region></p>'
            '</section>'
        )
    return (
        '<section class="panel result-panel" data-result-panel>'
        '<div class="panel-heading"><h2>第一步：先放一点资料进来</h2><p>从这里开始最轻松。先把几篇笔记或 1 个 PDF 放进 Inbox 文件夹，再回来点击导入。</p></div>'
        '<div class="task-grid">'
        '<article class="task-card static-card"><span class="task-step">动作 1</span><strong>打开 Inbox 文件夹</strong><p>当前路径：{path}</p></article>'
        '<article class="task-card static-card"><span class="task-step">动作 2</span><strong>拖入你的资料</strong><p>支持 md、txt、pdf、docx、html、jpg、png。</p></article>'
        '<article class="task-card static-card"><span class="task-step">动作 3</span><strong>导入示例文件</strong><p>如果你只想先体验一次，可以先导入系统准备的示例文档。</p></article>'
        '</div>'
        '<div class="toolbar">'
        '<form method="post" action="/inbox/sample" class="inline-action-form"><button type="submit" data-loading-label="正在准备示例...">导入示例文件</button></form>'
        '<button type="button" class="secondary-button" data-copy-path="{path}">复制 Inbox 路径</button>'
        '</div>'
        '<p class="sr-only" aria-live="polite" data-live-region></p>'
        '</section>'
    ).format(path=inbox_path)


def build_batch_summary(batch: IngestBatchResult) -> str:
    success_count = sum(1 for result in batch.successes if getattr(result, "status", "") != "duplicate")
    duplicate_count = sum(1 for result in batch.successes if getattr(result, "status", "") == "duplicate")
    failure_count = len(batch.failures)
    if success_count and not failure_count:
        return f"导入完成，已新增 {success_count} 篇知识，重复跳过 {duplicate_count} 篇。现在你可以去搜索，或者直接向 AI 提问。"
    if success_count and failure_count:
        return f"本次导入新增 {success_count} 篇，重复跳过 {duplicate_count} 篇，失败 {failure_count} 篇。你可以先继续使用成功导入的内容，再查看失败原因。"
    if duplicate_count and not failure_count:
        return f"本次导入没有新增内容，重复跳过 {duplicate_count} 篇。"
    if duplicate_count and failure_count:
        return f"本次导入没有新增内容，重复跳过 {duplicate_count} 篇，失败 {failure_count} 篇。"
    if failure_count:
        return f"这次导入没有成功，失败 {failure_count} 项。请先根据下方原因调整后重试。"
    return ""


def format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / 1024 / 1024:.1f} MB"


def describe_parse_mode(file_path: Path) -> str:
    extension = file_path.suffix.lower()
    if extension == ".pdf":
        return "PDF 文本层 / OCR"
    if extension == ".docx":
        return "Word 文本提取"
    if extension in {".html", ".htm"}:
        return "HTML 文本提取"
    if extension in {".png", ".jpg", ".jpeg"}:
        return "图片 OCR"
    return "文本"


def build_result_status_text(result) -> str:
    if getattr(result, "status", "") == "duplicate":
        duplicate_of = getattr(result, "duplicate_of_document_id", None)
        return f"重复文件，已跳过（文档 #{duplicate_of}）" if duplicate_of else "重复文件，已跳过"
    if getattr(result, "status", "") == "similar":
        count = len(getattr(result, "duplicate_candidates", []) or [])
        return f"发现 {count} 个潜在重复候选"
    return "已入库"
