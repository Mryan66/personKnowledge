import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.tools.secret_store import load_openai_api_key


@dataclass(frozen=True)
class Settings:
    app_name: str = "Personal AI Knowledge Butler"
    workspace_dir: Path = field(default_factory=lambda: Path.cwd())
    inbox_dir: Path = Path("inbox")
    knowledge_dir: Path = Path("knowledge")
    data_dir: Path = Path("data")
    database_path: Path = Path("data/metadata.sqlite")
    default_language: str = "zh-CN"
    openai_api_key: Optional[str] = None
    openai_model: str = "doubao-seed-2.0-code"
    openai_embedding_model: str = "doubao-embedding-2.0-text-16k"
    openai_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    openai_timeout_seconds: int = 60
    enable_ocr: bool = False

    def resolve_path(self, path: Path) -> Path:
        if path.is_absolute():
            return path
        return self.workspace_dir / path

    @property
    def resolved_inbox_dir(self) -> Path:
        return self.resolve_path(self.inbox_dir)

    @property
    def resolved_knowledge_dir(self) -> Path:
        return self.resolve_path(self.knowledge_dir)

    @property
    def resolved_data_dir(self) -> Path:
        return self.resolve_path(self.data_dir)

    @property
    def resolved_database_path(self) -> Path:
        return self.resolve_path(self.database_path)


def get_settings() -> Settings:
    env_file_values = read_env_file(Path.cwd() / ".env")
    workspace_dir = Path(get_config_value("KB_WORKSPACE_DIR", str(Path.cwd()), env_file_values))
    return Settings(
        workspace_dir=workspace_dir,
        inbox_dir=Path(get_config_value("KB_INBOX_DIR", "inbox", env_file_values)),
        knowledge_dir=Path(get_config_value("KB_KNOWLEDGE_DIR", "knowledge", env_file_values)),
        data_dir=Path(get_config_value("KB_DATA_DIR", "data", env_file_values)),
        database_path=Path(get_config_value("KB_DATABASE_PATH", "data/metadata.sqlite", env_file_values)),
        default_language=get_config_value("KB_DEFAULT_LANGUAGE", "zh-CN", env_file_values),
        openai_api_key=get_openai_api_key(env_file_values),
        openai_model=get_config_value("KB_OPENAI_MODEL", "doubao-seed-2.0-code", env_file_values),
        openai_embedding_model=get_config_value("KB_OPENAI_EMBEDDING_MODEL", "doubao-embedding-2.0-text-16k", env_file_values),
        openai_base_url=get_config_value("KB_OPENAI_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3", env_file_values),
        openai_timeout_seconds=int(get_config_value("KB_OPENAI_TIMEOUT_SECONDS", "60", env_file_values)),
        enable_ocr=get_config_value("KB_ENABLE_OCR", "false", env_file_values).lower() in ("true", "1", "yes"),
    )


def get_openai_api_key(env_file_values: dict) -> Optional[str]:
    return (
        os.getenv("OPENAI_API_KEY")
        or os.getenv("KB_OPENAI_API_KEY")
        or load_openai_api_key()
        or env_file_values.get("OPENAI_API_KEY")
        or env_file_values.get("KB_OPENAI_API_KEY")
        or None
    )


def get_config_value(key: str, default: str, env_file_values: dict) -> str:
    return os.getenv(key) or env_file_values.get(key) or default


def read_env_file(path: Path) -> dict:
    if not path.exists():
        return {}
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = unquote_env_value(value.strip())
    return values


def unquote_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def write_env_values(path: Path, updates: dict) -> None:
    existing = read_env_file(path)
    existing.update({key: value for key, value in updates.items() if value is not None})
    lines = [f"{key}={quote_env_value(value)}" for key, value in sorted(existing.items()) if value != ""]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def remove_env_keys(path: Path, keys: set) -> None:
    values = read_env_file(path)
    for key in keys:
        values.pop(key, None)
    lines = [f"{key}={quote_env_value(value)}" for key, value in sorted(values.items()) if value != ""]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def quote_env_value(value: str) -> str:
    escaped = str(value).replace('"', '\\"')
    return f'"{escaped}"'
