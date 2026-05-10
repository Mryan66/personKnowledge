from pathlib import Path

SUPPORTED_EXTENSIONS = {".md", ".txt", ".pdf"}


def scan_inbox(inbox_dir: Path) -> list[Path]:
    if not inbox_dir.exists():
        return []
    return sorted(
        file_path
        for file_path in inbox_dir.rglob("*")
        if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS
    )
