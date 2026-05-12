from html import escape
from pathlib import Path

from app.config import Settings
from app.ui.rendering import render_template


ENVIRONMENT_KEYS = [
    "OPENAI_API_KEY",
    "KB_OPENAI_API_KEY",
    "KB_FRONTEND_ASSETS",
    "KB_OPENAI_MODEL",
    "KB_OPENAI_EMBEDDING_MODEL",
    "KB_OPENAI_BASE_URL",
    "KB_OPENAI_TIMEOUT_SECONDS",
    "KB_WORKSPACE_DIR",
    "KB_INBOX_DIR",
    "KB_KNOWLEDGE_DIR",
    "KB_DATA_DIR",
    "KB_DATABASE_PATH",
    "KB_DEFAULT_LANGUAGE",
    "KB_ENABLE_OCR",
]


def render_settings(settings: Settings, template_path: Path, message: str = "") -> str:
    context = {
        "app_name": settings.app_name,
        "active_nav": "settings",
        "page_name": "settings",
        "frontend_assets_enabled": settings.frontend_assets_enabled,
        "openai_status": "已配置" if settings.openai_api_key else "未配置",
        "openai_status_class": "status-ok" if settings.openai_api_key else "status-warn",
        "message_panel": render_message_panel(message),
        "path_settings": render_path_settings(settings),
        "openai_settings": render_openai_settings(settings),
        "openai_form": render_openai_form(settings),
        "retrieval_settings": render_retrieval_settings(settings),
        "environment_keys": render_environment_keys(),
    }
    return render_template(template_path, context)


def render_message_panel(message: str) -> str:
    if not message:
        return ""
    return f'<section class="panel result-panel"><p class="notice">{escape(message)}</p></section>'


def render_path_settings(settings: Settings) -> str:
    rows = [
        ("Workspace", settings.workspace_dir),
        ("Inbox", settings.resolved_inbox_dir),
        ("Knowledge", settings.resolved_knowledge_dir),
        ("Data", settings.resolved_data_dir),
        ("SQLite", settings.resolved_database_path),
        ("默认语言", settings.default_language),
    ]
    return render_settings_rows(rows)


def render_openai_settings(settings: Settings) -> str:
    rows = [
        ("API Key", "已加密保存/已配置" if settings.openai_api_key else "未配置"),
        ("RAG 模型", settings.openai_model),
        ("Embedding 模型", settings.openai_embedding_model),
        ("Base URL", settings.openai_base_url),
        ("Timeout", f"{settings.openai_timeout_seconds}s"),
        ("OCR 支持", "已启用" if settings.enable_ocr else "已禁用"),
    ]
    return render_settings_rows(rows)


def render_openai_form(settings: Settings) -> str:
    api_key_placeholder = "保留当前 API Key" if settings.openai_api_key else "输入 API Key"
    ocr_checked = ' checked' if settings.enable_ocr else ''
    return f"""
<form class="settings-form" method="post" action="/settings/openai">
  <label>
    API Key
    <input type="password" name="openai_api_key" value="" placeholder="{escape(api_key_placeholder)}">
    <small>留空表示不修改当前 API Key；保存后优先加密写入 macOS Keychain，非敏感配置写入 .env。</small>
  </label>
  <label>
    RAG 模型
    <input type="text" name="openai_model" value="{escape(settings.openai_model)}">
  </label>
  <label>
    Embedding 模型
    <input type="text" name="openai_embedding_model" value="{escape(settings.openai_embedding_model)}">
  </label>
  <label>
    Base URL
    <input type="text" name="openai_base_url" value="{escape(settings.openai_base_url)}">
  </label>
  <label>
    Timeout 秒数
    <input type="number" name="openai_timeout_seconds" min="1" max="600" value="{settings.openai_timeout_seconds}">
  </label>
  <label class="checkbox-label">
    <input type="checkbox" name="enable_ocr" value="1"{ocr_checked}>
    启用 OCR（扫描件 PDF 解析，需安装 pytesseract 和 pdf2image）
  </label>
  <div class="form-actions">
    <button type="submit">保存配置</button>
    <button type="submit" formaction="/settings/openai/test">测试连接</button>
  </div>
</form>
""".strip()


def render_retrieval_settings(settings: Settings) -> str:
    rows = [
        ("默认搜索模式", "Auto：混合搜索（关键词 + 向量）"),
        ("关键词检索", "标题、标签、分类、摘要、正文 chunk"),
        ("向量检索", "Embedding + SQLite JSON 向量 + cosine similarity"),
        ("Rerank", "基于标题/标签/分类匹配度重排"),
        ("默认生成 Embedding", "Web/CLI ingest 在有 API Key 时启用"),
        ("默认启用 LLM", "Ask 页面勾选且有 API Key 时启用"),
        ("OCR", "扫描件 PDF 支持（需手动安装依赖）"),
    ]
    return render_settings_rows(rows)


def render_environment_keys() -> str:
    return "\n".join(f'<code>{escape(key)}</code>' for key in ENVIRONMENT_KEYS)


def render_settings_rows(rows) -> str:
    rendered = []
    for label, value in rows:
        rendered.append(
            "<tr>"
            f"<th>{escape(str(label))}</th>"
            f"<td>{escape(str(value))}</td>"
            "</tr>"
        )
    return "\n".join(rendered)
