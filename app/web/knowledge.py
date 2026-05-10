from html import escape
from pathlib import Path
import re
from typing import Optional

from app.config import Settings
from app.memory.database import DocumentRecord, ChunkRecord, get_dashboard_stats, list_document_overviews


def render_knowledge(
    settings: Settings,
    template_path: Path,
    limit: int = 100,
    selected_document: Optional[DocumentRecord] = None,
    chunks: Optional[list[ChunkRecord]] = None,
    similar_documents: Optional[list[dict]] = None,
    preview_html: str = "",
    preview_mode: str = "rendered",
    selected_chunk: Optional[int] = None,
    message: str = "",
) -> str:
    stats = get_dashboard_stats(settings.resolved_database_path)
    documents = list_document_overviews(settings.resolved_database_path, limit=limit)
    template = template_path.read_text(encoding="utf-8")
    replacements = {
        "app_name": settings.app_name,
        "document_count": str(stats["document_count"]),
        "chunk_count": str(stats["chunk_count"]),
        "embedding_count": str(stats["embedding_count"]),
        "tag_count": str(stats["tag_count"]),
        "limit": str(limit),
        "document_rows": render_document_rows(documents),
        "category_filters": render_category_filters(documents),
        "tag_cloud": render_tag_cloud(documents),
        "message_panel": render_message_panel(message),
        "document_detail_panel": render_document_detail_panel(
            selected_document,
            chunks or [],
            similar_documents or [],
            preview_html,
            preview_mode,
            selected_chunk,
        ),
    }
    for key, value in replacements.items():
        template = template.replace("{{ " + key + " }}", value)
    return template


def render_document_rows(documents: list) -> str:
    if not documents:
        return '<tr><td colspan="9" class="muted center">暂无入库文档，请先到 Inbox 导入文件。</td></tr>'
    rows = []
    for document in documents:
        tags = render_inline_tags(document["tags"])
        embedding_status = render_embedding_status(document["chunk_count"], document["embedding_count"])
        summary = build_snippet(document["summary"], max_length=150)
        rows.append(
            "<tr>"
            f'<td><input type="checkbox" name="selected_document_id" value="{document["id"]}"></td>'
            f'<td><strong><a class="table-link" data-detail-link="1" href="/knowledge?document_id={document["id"]}#document-detail-panel">{escape(document["title"] or "Untitled")}</a></strong><small>{escape(document["source_path"])}</small></td>'
            f'<td>{escape(document["category"] or "uncategorized")}</td>'
            f'<td>{tags}</td>'
            f'<td>{escape(summary)}</td>'
            f'<td>{document["chunk_count"]}</td>'
            f'<td>{embedding_status}</td>'
            f'<td>{render_document_status(document)}</td>'
            f'<td>{escape(document["updated_at"] or "-")}</td>'
            "</tr>"
        )
    return "\n".join(rows)


def render_inline_tags(tags: list) -> str:
    if not tags:
        return '<span class="muted">暂无</span>'
    return " ".join(f'<span class="tag-chip">{escape(tag)}</span>' for tag in tags[:6])


def render_embedding_status(chunk_count: int, embedding_count: int) -> str:
    if chunk_count == 0:
        return '<span class="status-warn">无 chunk</span>'
    if embedding_count >= chunk_count:
        return f'<span class="status-ok">{embedding_count}/{chunk_count}</span>'
    if embedding_count == 0:
        return f'<span class="status-warn">0/{chunk_count}</span>'
    return f'<span class="status-warn">{embedding_count}/{chunk_count}</span>'


def render_document_status(document: dict) -> str:
    status = (document.get("status") or "-").strip()
    if status == "duplicate":
        return '<span class="status-warn">duplicate</span>'
    if status == "similar":
        return '<span class="status-warn">similar</span>'
    if status == "ingested":
        return '<span class="status-ok">ingested</span>'
    return escape(status or "-")


def render_category_filters(documents: list) -> str:
    categories = {}
    for document in documents:
        category = document["category"] or "uncategorized"
        categories[category] = categories.get(category, 0) + 1
    if not categories:
        return '<span class="muted">暂无分类</span>'
    return " ".join(
        f'<span class="filter-chip">{escape(category)} <strong>{count}</strong></span>'
        for category, count in sorted(categories.items(), key=lambda item: (-item[1], item[0]))[:12]
    )


def render_tag_cloud(documents: list) -> str:
    counts = {}
    for document in documents:
        for tag in document["tags"]:
            counts[tag] = counts.get(tag, 0) + 1
    if not counts:
        return '<span class="muted">暂无标签</span>'
    return " ".join(
        f'<span class="tag-chip">{escape(tag)} <strong>{count}</strong></span>'
        for tag, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:24]
    )


def render_message_panel(message: str) -> str:
    if not message:
        return ""
    return f'<section class="panel result-panel"><p class="notice">{escape(message)}</p></section>'


def render_document_detail_panel(
    document: Optional[DocumentRecord],
    chunks: list[ChunkRecord],
    similar_documents: list[dict],
    preview_html: str,
    preview_mode: str,
    selected_chunk: Optional[int],
) -> str:
    if document is None:
        return ""
    tag_value = ", ".join(document.tags)
    chunk_items = render_chunk_items(chunks, selected_chunk=selected_chunk)
    similar_items = render_similar_documents(similar_documents)
    preview_toolbar = render_preview_toolbar(document, preview_mode)
    return f"""
<section class="panel" id="document-detail-panel">
  <div class="panel-heading">
    <div>
      <h2>文档详情</h2>
      <p>查看元数据、编辑字段、重新导入或删除该文档。</p>
    </div>
    <div class="actions">
      <a href="/knowledge">返回列表</a>
    </div>
  </div>
  <div class="detail-grid">
    <div class="detail-card">
      <h3>{escape(document.title or "Untitled")}</h3>
      <p class="muted">{escape(document.source_path)}</p>
      <dl class="status-list">
        <div><dt>分类</dt><dd>{escape(document.category or "uncategorized")}</dd></div>
        <div><dt>标签数</dt><dd>{len(document.tags)}</dd></div>
        <div><dt>Chunk 数</dt><dd>{len(chunks)}</dd></div>
        <div><dt>状态</dt><dd>{escape(document.status or "-")}</dd></div>
      </dl>
      {render_metadata_facts(document)}
    </div>
    <div class="detail-card">
      <h3>编辑元数据</h3>
      <form class="settings-form" method="post" action="/knowledge/update">
        <input type="hidden" name="document_id" value="{document.id}">
        <label>
          标题
          <input type="text" name="title" value="{escape(document.title)}">
        </label>
        <label>
          摘要
          <textarea name="summary" rows="4">{escape(document.summary)}</textarea>
        </label>
        <label>
          标签
          <input type="text" name="tags" value="{escape(tag_value)}" placeholder="用逗号分隔">
        </label>
        <label>
          分类
          <input type="text" name="category" value="{escape(document.category)}">
        </label>
        <div class="form-actions">
          <button type="submit">保存元数据</button>
          <button type="submit" formaction="/knowledge/reingest">重新导入</button>
          <button type="submit" formaction="/knowledge/delete">删除文档</button>
        </div>
      </form>
    </div>
  </div>
  <div class="panel-heading">
    <h2>文档预览</h2>
    <p>在当前页面查看源文档的可读预览。</p>
  </div>
  {preview_toolbar}
  <div class="preview-panel">{preview_html or '<p class="muted">暂时无法预览该文档内容。</p>'}</div>
  <div class="panel-heading">
    <h2>Chunk 明细</h2>
    <p>展示当前文档已入库的文本分块。你可以从搜索结果直接定位到对应片段。</p>
  </div>
  <div class="chunk-list">{chunk_items}</div>
  <div class="panel-heading">
    <h2>相似文档</h2>
    <p>基于分类、标签和文本词项的本地相似度匹配。</p>
  </div>
  <div class="similar-list">{similar_items}</div>
</section>
""".strip()


def render_chunk_items(chunks: list[ChunkRecord], selected_chunk: Optional[int] = None) -> str:
    if not chunks:
        return '<p class="muted">当前文档暂无 chunk。</p>'
    items = []
    for chunk in chunks:
        active_class = " chunk-card-active" if selected_chunk == chunk.chunk_index else ""
        active_note = '<p class="notice">这是当前搜索结果命中的片段。</p>' if selected_chunk == chunk.chunk_index else ""
        items.append(
            f'<article class="chunk-card{active_class}" id="chunk-{chunk.chunk_index}">'
            f'<h3>Chunk #{chunk.chunk_index}</h3>'
            f'{active_note}'
            f'<pre>{escape(chunk.content)}</pre>'
            '</article>'
        )
    return "\n".join(items)


def render_similar_documents(documents: list[dict]) -> str:
    if not documents:
        return '<p class="muted">暂无足够相似的文档。</p>'
    items = []
    for document in documents:
        score = document.get("similarity_score", 0)
        items.append(
            '<article class="similar-card">'
            f'<h3><a class="table-link" data-detail-link="1" href="/knowledge?document_id={document["id"]}#document-detail-panel">{escape(document.get("title") or "Untitled")}</a></h3>'
            f'<p>{escape(build_snippet(document.get("summary") or "", max_length=120))}</p>'
            f'<small>{escape(document.get("category") or "uncategorized")} · score {score}</small>'
            '</article>'
        )
    return "\n".join(items)


def render_metadata_facts(document: DocumentRecord) -> str:
    rows = []
    rows.append(render_metadata_row("作者", document.authors))
    rows.append(render_metadata_row("日期", document.dates))
    rows.append(render_metadata_row("人物", document.people))
    rows.append(render_metadata_row("组织", document.organizations))
    if document.source_url:
        rows.append(
            f'<div><dt>来源链接</dt><dd><a class="table-link" href="{escape(document.source_url)}">{escape(document.source_url)}</a></dd></div>'
        )
    rendered_rows = "".join(row for row in rows if row)
    if not rendered_rows:
        return ""
    return f'<dl class="status-list">{rendered_rows}</dl>'


def render_metadata_row(label: str, values: list[str]) -> str:
    if not values:
        return ""
    return f"<div><dt>{escape(label)}</dt><dd>{escape(', '.join(values))}</dd></div>"


def render_document_preview(source_path: Path, content: str) -> str:
    extension = source_path.suffix.lower()
    if extension == ".md":
        return render_markdown_preview(content)
    return f'<pre class="document-preview-text">{escape(content)}</pre>'


def render_preview_toolbar(document: DocumentRecord, preview_mode: str) -> str:
    source_path = Path(document.source_path)
    normalized_mode = normalize_preview_mode(preview_mode)
    rendered_class = " preview-tab-active" if normalized_mode == "rendered" else ""
    raw_class = " preview-tab-active" if normalized_mode == "raw" else ""
    raw_link = f"/knowledge?document_id={document.id}&preview=raw#document-detail-panel"
    rendered_link = f"/knowledge?document_id={document.id}&preview=rendered#document-detail-panel"
    source_info = render_source_info(source_path)
    return (
        '<div class="preview-toolbar">'
        '<div class="preview-tabs">'
        f'<a class="preview-tab{rendered_class}" href="{rendered_link}">渲染预览</a>'
        f'<a class="preview-tab{raw_class}" href="{raw_link}">原始文本</a>'
        '</div>'
        f'<div class="preview-meta">{source_info}</div>'
        '</div>'
    )


def render_source_info(source_path: Path) -> str:
    extension = source_path.suffix.lower() or "unknown"
    size_text = "未知大小"
    if source_path.exists():
        try:
            size_text = format_character_hint(source_path)
        except OSError:
            size_text = "未知大小"
    return (
        f'<span class="preview-chip">{escape(extension)}</span>'
        f'<span class="preview-chip">{escape(size_text)}</span>'
        f'<code class="source-file-path">{escape(str(source_path))}</code>'
    )


def normalize_preview_mode(preview_mode: str) -> str:
    return preview_mode if preview_mode in {"rendered", "raw"} else "rendered"


def format_character_hint(source_path: Path) -> str:
    size_bytes = source_path.stat().st_size
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / 1024 / 1024:.1f} MB"


def render_markdown_preview(content: str) -> str:
    lines = content.splitlines()
    blocks = []
    paragraph_lines = []
    list_items = []
    in_code_block = False
    code_lines = []

    def flush_paragraph():
        nonlocal paragraph_lines
        if paragraph_lines:
            text = " ".join(line.strip() for line in paragraph_lines if line.strip())
            if text:
                blocks.append(f"<p>{escape(text)}</p>")
            paragraph_lines = []

    def flush_list():
        nonlocal list_items
        if list_items:
            items = "".join(f"<li>{escape(item)}</li>" for item in list_items)
            blocks.append(f"<ul>{items}</ul>")
            list_items = []

    def flush_code():
        nonlocal code_lines
        if code_lines:
            blocks.append(f'<pre class="document-preview-text">{escape(chr(10).join(code_lines))}</pre>')
            code_lines = []

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.startswith("```"):
            flush_paragraph()
            flush_list()
            if in_code_block:
                flush_code()
                in_code_block = False
            else:
                in_code_block = True
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        if not stripped:
            flush_paragraph()
            flush_list()
            continue

        heading_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading_match:
            flush_paragraph()
            flush_list()
            level = min(len(heading_match.group(1)), 6)
            blocks.append(f"<h{level + 1}>{escape(heading_match.group(2).strip())}</h{level + 1}>")
            continue

        list_match = re.match(r"^[-*]\s+(.*)$", stripped)
        if list_match:
            flush_paragraph()
            list_items.append(list_match.group(1).strip())
            continue

        numbered_match = re.match(r"^\d+\.\s+(.*)$", stripped)
        if numbered_match:
            flush_paragraph()
            list_items.append(numbered_match.group(1).strip())
            continue

        flush_list()
        paragraph_lines.append(stripped)

    flush_paragraph()
    flush_list()
    if in_code_block:
        flush_code()

    if not blocks:
        return '<p class="muted">文档没有可预览的内容。</p>'
    return "".join(blocks)


def build_snippet(content: str, max_length: int = 160) -> str:
    normalized = " ".join((content or "").split())
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 1].rstrip() + "…"
