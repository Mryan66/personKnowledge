from html import escape
from pathlib import Path

from app.config import Settings
from app.memory.database import count_tasks_by_status, list_tasks
from app.ui.rendering import render_template


def render_tasks_page(
    settings: Settings,
    template_path: Path,
    status: str = "open",
    message: str = "",
) -> str:
    counts = count_tasks_by_status(settings.resolved_database_path)
    tasks = list_tasks(settings.resolved_database_path, status_filter=status, limit=50)
    context = {
        "app_name": settings.app_name,
        "active_nav": "tasks",
        "page_name": "tasks",
        "frontend_assets_enabled": settings.frontend_assets_enabled,
        "open_count": str(counts["open"]),
        "done_count": str(counts["done"]),
        "archived_count": str(counts["archived"]),
        "status_tabs": render_status_tabs(status),
        "message_panel": render_message_panel(message),
        "task_cards": render_task_cards(tasks, status),
        "selected_status": escape(status),
    }
    return render_template(template_path, context)


def render_status_tabs(active_status: str) -> str:
    tabs = [("open", "待办"), ("done", "已完成"), ("archived", "归档")]
    parts = []
    for value, label in tabs:
        css_class = "filter-chip active" if value == active_status else "filter-chip"
        parts.append(f'<a class="{css_class}" href="/tasks?status={value}">{escape(label)}</a>')
    return "\n".join(parts)


def render_message_panel(message: str) -> str:
    if not message:
        return ""
    return f'<section class="panel result-panel"><p class="notice">{escape(message)}</p></section>'


def render_task_cards(tasks: list[dict], current_status: str) -> str:
    if not tasks:
        return '<p class="muted">当前筛选下还没有任务。</p>'
    return "\n".join(render_task_card(task, current_status) for task in tasks)


def render_task_card(task: dict, current_status: str) -> str:
    source_html = render_task_source(task)
    due_html = escape(task["due_date"] or "未设置")
    priority_html = render_priority_chip(task["priority"])
    status_action = render_status_action(task, current_status)
    return f"""
<article class="panel">
  <div class="panel-heading">
    <div>
      <h2>{escape(task["content"])}</h2>
      <p>来源：{source_html} · 截止日期：{due_html} · 优先级：{priority_html}</p>
    </div>
    <div class="chip-row">
      {status_action}
      <a class="btn-secondary" href="#task-edit-{task['id']}">编辑</a>
      <form method="post" action="/tasks/delete">
        <input type="hidden" name="id" value="{task['id']}">
        <button class="btn-secondary" type="submit">删除</button>
      </form>
    </div>
  </div>
  <form class="settings-form" id="task-edit-{task['id']}" method="post" action="/tasks/update">
    <input type="hidden" name="id" value="{task['id']}">
    <label>
      任务内容
      <input type="text" name="content" value="{escape(task['content'])}">
    </label>
    <label>
      截止日期
      <input type="date" name="due_date" value="{escape(task['due_date'])}">
    </label>
    <label>
      优先级
      <select name="priority">{render_priority_options(task["priority"])}</select>
    </label>
    <div class="form-actions">
      <button type="submit">保存</button>
    </div>
  </form>
</article>
""".strip()


def render_task_source(task: dict) -> str:
    if task["source_type"] == "auto" and task["document_id"]:
        label = escape(task["document_title"] or task["document_source_path"] or f"文档 #{task['document_id']}")
        return f'<a class="table-link" href="/knowledge?document_id={task["document_id"]}#document-detail-panel">{label}</a>'
    if task["source_type"] == "manual":
        return "手动创建"
    return "自动抽取"


def render_priority_chip(priority: str) -> str:
    label_map = {"high": "高", "normal": "中", "low": "低"}
    return f'<span class="filter-chip">{escape(label_map.get(priority, priority))}</span>'


def render_priority_options(selected: str) -> str:
    options = [("high", "高"), ("normal", "中"), ("low", "低")]
    return "".join(
        f'<option value="{value}"{" selected" if value == selected else ""}>{escape(label)}</option>'
        for value, label in options
    )


def render_status_action(task: dict, current_status: str) -> str:
    next_status = ""
    label = ""
    if current_status == "open":
        next_status = "done"
        label = "标记完成"
    elif current_status == "done":
        next_status = "archived"
        label = "归档"
    else:
        next_status = "open"
        label = "恢复待办"
    return (
        f'<form method="post" action="/tasks/status">'
        f'<input type="hidden" name="id" value="{task["id"]}">'
        f'<input type="hidden" name="status" value="{next_status}">'
        f'<button class="btn-secondary" type="submit">{escape(label)}</button>'
        f"</form>"
    )
