from pathlib import Path


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
