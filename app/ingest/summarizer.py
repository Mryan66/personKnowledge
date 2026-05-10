import re
from collections import Counter

STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "are", "was", "were",
    "一个", "我们", "你们", "他们", "以及", "或者", "但是", "因为", "所以", "进行",
}


def extract_title(content: str, fallback: str) -> str:
    for line in content.splitlines():
        stripped_line = line.strip()
        if not stripped_line:
            continue
        if stripped_line.startswith("#"):
            return stripped_line.lstrip("#").strip() or fallback
        return stripped_line[:80]
    return fallback


def summarize(content: str, max_length: int = 180) -> str:
    normalized = " ".join(content.split())
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 1].rstrip() + "…"


def generate_tags(content: str, limit: int = 5) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}|[\u4e00-\u9fff]{2,}", content.lower())
    candidates = [word for word in words if word not in STOPWORDS]
    counts = Counter(candidates)
    return [word for word, _ in counts.most_common(limit)]


def suggest_category(tags: list[str]) -> str:
    if not tags:
        return "uncategorized"
    return tags[0]
