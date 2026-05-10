from html import escape
from pathlib import Path
from typing import Optional

from app.config import Settings
from app.ingest.pipeline import IngestBatchResult
from app.ingest.scanner import scan_inbox


def render_inbox(settings: Settings, template_path: Path, batch: Optional[IngestBatchResult] = None, message: str = "") -> str:
    template = template_path.read_text(encoding="utf-8")
    files = scan_inbox(settings.resolved_inbox_dir)
    replacements = {
        "app_name": settings.app_name,
        "inbox_path": escape(str(settings.resolved_inbox_dir)),
        "openai_status": "已配置" if settings.openai_api_key else "未配置",
        "openai_status_class": "status-ok" if settings.openai_api_key else "status-warn",
        "file_count": str(len(files)),
        "inbox_files": render_inbox_files(files),
        "result_panel": render_result_panel(batch, message),
    }
    for key, value in replacements.items():
        template = template.replace("{{ " + key + " }}", value)
    return template


def render_inbox_files(files) -> str:
    if not files:
        return '<tr><td colspan="5" class="muted center">Inbox 暂无可导入文件。支持 .md / .txt / .pdf。</td></tr>'
    rows = []
    for file_path in files:
        rows.append(
            "<tr>"
            f"<td><strong>{escape(file_path.name)}</strong><small>{escape(str(file_path))}</small></td>"
            f"<td>{escape(file_path.suffix.lower())}</td>"
            f"<td>{format_size(file_path.stat().st_size)}</td>"
            f"<td>{'PDF 文本层' if file_path.suffix.lower() == '.pdf' else '文本'}</td>"
            f"<td><button type=\"submit\" name=\"path\" value=\"{escape(str(file_path))}\">导入</button></td>"
            "</tr>"
        )
    return "\n".join(rows)


def render_result_panel(batch: Optional[IngestBatchResult], message: str = "") -> str:
    if batch is None and not message:
        return ""

    parts = ['<section class="panel result-panel">', '<div class="panel-heading"><h2>导入结果</h2><p>显示本次导入的成功与失败文档。</p></div>']
    if message:
        parts.append(f'<p class="notice">{escape(message)}</p>')
    if batch:
        if batch.successes:
            parts.append('<h3>成功</h3><ul class="result-list success-list">')
            for result in batch.successes:
                parts.append(
                    f'<li><strong>{escape(result.title)}</strong><span>{escape(str(result.source_path))}</span>'
                    f'<small>chunks: {result.chunk_count} · embeddings: {result.embedding_count}</small></li>'
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


def format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / 1024 / 1024:.1f} MB"
