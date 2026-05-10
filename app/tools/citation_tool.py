from typing import Optional


def format_source(path: str, chunk_index: Optional[int] = None) -> str:
    if chunk_index is None:
        return path
    return f"{path}#chunk-{chunk_index}"
