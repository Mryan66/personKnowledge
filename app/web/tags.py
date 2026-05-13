from html import escape
from pathlib import Path

from app.config import Settings
from app.memory.database import list_all_tags, list_tag_aliases, list_tag_groups
from app.ui.rendering import render_template


def render_tags_page(
    settings: Settings,
    template_path: Path,
    message: str = "",
) -> str:
    all_tags = list_all_tags(settings.resolved_database_path, limit=10000)
    groups = list_tag_groups(settings.resolved_database_path)
    aliases = list_tag_aliases(settings.resolved_database_path, limit=100)
    context = {
        "app_name": settings.app_name,
        "active_nav": "tags",
        "page_name": "tags",
        "frontend_assets_enabled": settings.frontend_assets_enabled,
        "tag_count": str(len(all_tags)),
        "group_count": str(len(groups)),
        "alias_count": str(len(aliases)),
        "message_panel": render_message_panel(message),
        "candidate_groups_panel": render_candidate_groups_panel(groups),
        "alias_history_panel": render_alias_history_panel(aliases),
    }
    return render_template(template_path, context)


def render_message_panel(message: str) -> str:
    if not message:
        return ""
    return f'<section class="panel result-panel"><p class="notice">{escape(message)}</p></section>'


def render_candidate_groups_panel(groups: list[dict]) -> str:
    if not groups:
        return '<section class="panel"><div class="panel-heading"><h2>候选合并组</h2><p>当前没有需要治理的多变体标签组。</p></div></section>'
    cards = "\n".join(render_group_card(index, group) for index, group in enumerate(groups, start=1))
    return (
        '<section class="panel">'
        '<div class="panel-heading"><h2>候选合并组</h2><p>默认全选所有变体，可取消不想合并的项。</p></div>'
        f"{cards}</section>"
    )


def render_group_card(index: int, group: dict) -> str:
    variants = []
    canonical = group["canonical"]
    for variant, count in group["variants"]:
        checked = "" if variant == canonical else " checked"
        disabled = " disabled" if variant == canonical else ""
        variants.append(
            f'<label class="filter-chip"><input type="checkbox" name="aliases" value="{escape(variant)}"{checked}{disabled}>'
            f'{escape(variant)} <strong>{count}</strong></label>'
        )
    variants_html = f'<div class="chip-row">{" ".join(variants)}</div>'
    return f"""
<article class="panel">
  <div class="panel-heading">
    <div>
      <h3>组 #{index}</h3>
      <p>总计 {group["total_count"]} 次出现，规范候选为当前最高频写法。</p>
    </div>
  </div>
  <form class="settings-form" method="post" action="/tags/merge">
    <label>
      规范标签
      <input type="text" name="canonical" value="{escape(canonical)}">
    </label>
    {variants_html}
    <div class="form-actions">
      <button type="submit">合并</button>
    </div>
  </form>
</article>
""".strip()


def render_alias_history_panel(aliases: list[dict]) -> str:
    if not aliases:
        return '<section class="panel"><div class="panel-heading"><h2>合并历史</h2><p>还没有已保存的别名合并记录。</p></div></section>'
    rows = []
    for item in aliases:
        rows.append(
            "<tr>"
            f"<td>{escape(item['alias'])}</td>"
            f"<td>{escape(item['canonical'])}</td>"
            f"<td>{escape(item['created_at'])}</td>"
            '<td>'
            '<form method="post" action="/tags/alias/delete">'
            f'<input type="hidden" name="alias" value="{escape(item["alias"])}">'
            '<button class="btn-secondary" type="submit">删除</button>'
            "</form>"
            "</td>"
            "</tr>"
        )
    return (
        '<section class="panel">'
        '<div class="panel-heading"><h2>合并历史</h2><p>删除记录只会恢复未来候选，不会回滚已写入文档的标签。</p></div>'
        '<table><thead><tr><th>alias</th><th>canonical</th><th>时间</th><th>操作</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table></section>"
    )
