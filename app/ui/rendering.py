import json
from functools import lru_cache
from pathlib import Path

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
except ModuleNotFoundError:  # pragma: no cover - exercised in minimal local envs
    Environment = None
    FileSystemLoader = None
    select_autoescape = None


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_TEMPLATE_DIR = ROOT_DIR / "app" / "ui" / "templates"
FRONTEND_DIST_DIR = ROOT_DIR / "frontend" / "dist"
VITE_MANIFEST_PATH = FRONTEND_DIST_DIR / ".vite" / "manifest.json"
STATIC_CSS_PATH = ROOT_DIR / "app" / "ui" / "static" / "app.css"


@lru_cache(maxsize=8)
def _build_environment(template_root: str):
    if Environment is None:
        return None
    return Environment(
        loader=FileSystemLoader(template_root),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_template(template_path: Path, context: dict) -> str:
    merged_context = dict(context)
    merged_context.setdefault(
        "asset_tags",
        render_asset_tags(
            merged_context.get("frontend_assets_enabled", False),
            include_css=merged_context.get("frontend_asset_css_enabled", True),
        ),
    )
    merged_context.setdefault("static_css_href", build_static_css_href())
    environment = _build_environment(str(template_path.parent))
    if environment is None:
        return render_template_fallback(template_path, merged_context)
    template = environment.get_template(template_path.name)
    return template.render(**merged_context)


@lru_cache(maxsize=1)
def load_vite_manifest() -> dict:
    if not VITE_MANIFEST_PATH.exists():
        return {}
    return json.loads(VITE_MANIFEST_PATH.read_text(encoding="utf-8"))


def reset_rendering_caches() -> None:
    load_vite_manifest.cache_clear()
    _build_environment.cache_clear()
    build_static_css_href.cache_clear()


@lru_cache(maxsize=1)
def build_static_css_href() -> str:
    if not STATIC_CSS_PATH.exists():
        return "/static/app.css"
    version = int(STATIC_CSS_PATH.stat().st_mtime)
    return f"/static/app.css?v={version}"


def render_asset_tags(enabled: bool = False, entry_name: str = "src/main.ts", include_css: bool = True) -> str:
    if not enabled:
        return ""
    manifest = load_vite_manifest()
    entry = manifest.get(entry_name)
    if not entry:
        return ""

    tags = []
    if include_css:
        for css_path in entry.get("css", []):
            tags.append(f'<link rel="stylesheet" href="/assets/{css_path}">')

        for import_name in entry.get("imports", []):
            imported = manifest.get(import_name, {})
            for css_path in imported.get("css", []):
                tag = f'<link rel="stylesheet" href="/assets/{css_path}">'
                if tag not in tags:
                    tags.append(tag)

    if entry.get("file"):
        tags.append(f'<script type="module" src="/assets/{entry["file"]}"></script>')
    return "\n".join(tags)


def render_template_fallback(template_path: Path, context: dict) -> str:
    template = template_path.read_text(encoding="utf-8")
    for key, value in context.items():
        template = template.replace("{{ " + key + " }}", str(value))
    return template
