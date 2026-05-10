from dataclasses import dataclass, field
import ast
import json
import logging
from pathlib import Path
import re
from typing import Optional

from app.ingest.summarizer import extract_title, generate_tags, suggest_category, summarize
from app.tools.openai_client import OpenAIClient, OpenAIClientError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OrganizationDiagnostics:
    strategy: str = "rules"
    llm_attempts: int = 0
    used_repair_prompt: bool = False
    fallback_fields: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OrganizationResult:
    source_path: Path
    title: str
    summary: str
    tags: list[str]
    category: str
    action_items: list[str]
    authors: list[str] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)
    people: list[str] = field(default_factory=list)
    organizations: list[str] = field(default_factory=list)
    source_url: str = ""
    diagnostics: OrganizationDiagnostics = field(default_factory=OrganizationDiagnostics)


class OrganizerAgent:
    def __init__(self, openai_client: Optional[OpenAIClient] = None):
        self.openai_client = openai_client

    def organize(self, source_path: Path, content: str) -> OrganizationResult:
        if self.openai_client:
            try:
                return self._organize_with_llm(source_path, content)
            except (OpenAIClientError, ValueError, json.JSONDecodeError, KeyError):
                logger.warning("OrganizerAgent LLM path failed for %s; falling back to rules.", source_path, exc_info=True)
                pass
        return self._organize_with_rules(source_path, content)

    def _organize_with_rules(self, source_path: Path, content: str) -> OrganizationResult:
        tags = generate_tags(content)
        return OrganizationResult(
            source_path=source_path,
            title=extract_title(content, fallback=source_path.stem),
            summary=summarize(content),
            tags=tags,
            category=suggest_category(tags),
            action_items=[],
            authors=extract_authors(content),
            dates=extract_dates(content),
            people=extract_people(content),
            organizations=extract_organizations(content),
            source_url=extract_source_url(content),
            diagnostics=OrganizationDiagnostics(strategy="rules"),
        )

    def _organize_with_llm(self, source_path: Path, content: str) -> OrganizationResult:
        warnings = []
        response = self.openai_client.generate_text(
            instructions=ORGANIZER_INSTRUCTIONS,
            input_text=build_organizer_input(source_path, content),
            max_output_tokens=500,
        )
        payload, used_repair_prompt = self._parse_or_repair_payload(response.text, source_path, warnings)
        payload = unwrap_payload(payload)
        title_fallback = extract_title(content, fallback=source_path.stem)
        summary_fallback = summarize(content)
        tags_fallback = generate_tags(content)
        tags = normalize_tags(payload.get("tags"))
        title, title_used_fallback = normalize_title(payload.get("title"), fallback=title_fallback)
        summary, summary_used_fallback = normalize_summary(payload.get("summary"), fallback=summary_fallback)
        action_items = normalize_action_items(payload.get("action_items"))
        authors = normalize_entity_list(payload.get("authors")) or extract_authors(content)
        dates = normalize_entity_list(payload.get("dates")) or extract_dates(content)
        people = normalize_entity_list(payload.get("people")) or extract_people(content)
        organizations = normalize_entity_list(payload.get("organizations")) or extract_organizations(content)
        source_url = normalize_plain_text(payload.get("source_url")) or extract_source_url(content)
        if not action_items and infer_has_action_items(content):
            warnings.append("llm_action_items_empty")
        tag_used_fallback = not tags
        category, category_used_fallback = normalize_category(payload.get("category"), tags=tags or tags_fallback)
        fallback_fields = []
        if title_used_fallback:
            fallback_fields.append("title")
        if summary_used_fallback:
            fallback_fields.append("summary")
        if tag_used_fallback:
            fallback_fields.append("tags")
            tags = tags_fallback
        if category_used_fallback:
            fallback_fields.append("category")
        return OrganizationResult(
            source_path=source_path,
            title=title,
            summary=summary,
            tags=tags,
            category=category,
            action_items=action_items,
            authors=authors[:6],
            dates=dates[:10],
            people=people[:10],
            organizations=organizations[:10],
            source_url=source_url,
            diagnostics=OrganizationDiagnostics(
                strategy="llm" if not fallback_fields else "llm_partial_fallback",
                llm_attempts=2 if used_repair_prompt else 1,
                used_repair_prompt=used_repair_prompt,
                fallback_fields=fallback_fields,
                warnings=warnings,
            ),
        )

    def _parse_or_repair_payload(self, text: str, source_path: Path, warnings: list[str]) -> tuple[dict, bool]:
        try:
            return parse_json_object(text), False
        except (ValueError, json.JSONDecodeError, SyntaxError) as error:
            warnings.append("initial_parse_failed")
            logger.info("OrganizerAgent attempting repair prompt for %s: %s", source_path, error)
            repaired_text = self._repair_payload_with_llm(text)
            warnings.append("repair_prompt_used")
            return parse_json_object(repaired_text), True

    def _repair_payload_with_llm(self, bad_output: str) -> str:
        response = self.openai_client.generate_text(
            instructions=ORGANIZER_REPAIR_INSTRUCTIONS,
            input_text=bad_output,
            max_output_tokens=400,
        )
        return response.text


ORGANIZER_INSTRUCTIONS = """你是个人知识库整理助手。请根据输入文档提炼结构化元数据。
仅输出一个 JSON 对象，不要输出 markdown，不要附加解释。
JSON 字段必须包含：
- title: 字符串
- summary: 字符串，1-3 句
- tags: 字符串数组，最多 6 个
- category: 字符串
- action_items: 字符串数组，可为空
- authors: 字符串数组，可为空
- dates: 字符串数组，可为空
- people: 字符串数组，可为空
- organizations: 字符串数组，可为空
- source_url: 字符串，可为空
要求：
1. 默认使用中文输出。
2. title 要简洁准确。
3. tags 不能重复。
4. 如果没有明确行动项，action_items 返回空数组。"""

ORGANIZER_REPAIR_INSTRUCTIONS = """你会收到一个格式不稳定的整理结果。
请把它修复为一个合法 JSON 对象，只保留以下字段：
- title
- summary
- tags
- category
- action_items
- authors
- dates
- people
- organizations
- source_url
不要输出 markdown，不要解释，不要补充其他字段。"""


def build_organizer_input(source_path: Path, content: str) -> str:
    snippet = content.strip()
    if len(snippet) > 6000:
        snippet = snippet[:6000]
    return f"文件路径：{source_path}\n\n文档内容：\n{snippet}"


def parse_json_object(text: str) -> dict:
    normalized = text.strip()
    normalized = strip_code_fences(normalized)
    start = normalized.find("{")
    end = normalized.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("OrganizerAgent did not return a JSON object.")
    candidate = normalized[start : end + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        repaired = repair_json_like_text(candidate)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            parsed = ast.literal_eval(candidate)
            if not isinstance(parsed, dict):
                raise ValueError("OrganizerAgent returned a non-object payload.")
            return parsed


def strip_code_fences(text: str) -> str:
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if len(lines) >= 3 and lines[-1].strip().startswith("```"):
        return "\n".join(lines[1:-1]).strip()
    return text


def repair_json_like_text(text: str) -> str:
    repaired = text.strip()
    repaired = re.sub(r",(\s*[}\]])", r"\1", repaired)
    repaired = repaired.replace("\u201c", '"').replace("\u201d", '"')
    repaired = repaired.replace("\u2018", "'").replace("\u2019", "'")
    return repaired


def unwrap_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("OrganizerAgent returned an invalid payload.")
    for key in ("result", "data", "metadata", "organization"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            return nested
    return payload


def normalize_title(value, fallback: str) -> tuple[str, bool]:
    text = normalize_plain_text(value)
    if not text:
        return fallback, True
    text = text.lstrip("#").strip().strip('"').strip("'")
    text = re.sub(r"\s+", " ", text)
    normalized = text[:80] or fallback
    return normalized, normalized == fallback


def normalize_summary(value, fallback: str) -> tuple[str, bool]:
    text = normalize_plain_text(value)
    if not text:
        return fallback, True
    text = re.sub(r"\s+", " ", text)
    normalized = text[:240] if len(text) > 240 else text
    if is_generic_summary(normalized):
        return fallback, True
    return normalized, False


def normalize_plain_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        joined = " ".join(str(item).strip() for item in value if str(item).strip())
        return joined.strip()
    return str(value).strip()


def normalize_tags(value) -> list[str]:
    items = coerce_list(value)
    tags = []
    seen = set()
    for item in items:
        tag = normalize_tag(item)
        if not tag or tag in seen:
            continue
        seen.add(tag)
        tags.append(tag)
    return tags[:6]


def normalize_action_items(value) -> list[str]:
    items = coerce_list(value)
    items = []
    seen = set()
    for item in coerce_list(value):
        text = normalize_action_text(item)
        if text:
            if text in seen:
                continue
            seen.add(text)
            items.append(text)
    return items[:6]


def normalize_category(value, tags: list[str]) -> tuple[str, bool]:
    text = normalize_plain_text(value).lower()
    if not text or text in {"uncategorized", "other", "others", "misc", "general", "unknown", "未分类", "其他"}:
        return suggest_category(tags), True
    text = re.sub(r"\s+", " ", text)
    return text[:40], False


def normalize_tag(value) -> str:
    tag = normalize_plain_text(value).lower()
    tag = tag.strip("#").strip()
    tag = re.sub(r"^[\-\*\d\.\)\(]+", "", tag).strip()
    tag = re.sub(r"\s+", "-", tag)
    return tag[:32]


def normalize_action_text(value) -> str:
    text = normalize_plain_text(value)
    text = re.sub(r"^[\-\*\d\.\)\(]+\s*", "", text).strip()
    text = re.sub(r"\s+", " ", text)
    return text[:120]


def normalize_entity_list(value) -> list[str]:
    items = []
    seen = set()
    for item in coerce_list(value):
        text = normalize_plain_text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        items.append(text[:80])
    return items


def extract_source_url(content: str) -> str:
    match = re.search(r"https?://[^\s<>\]\)\"']+", content)
    return match.group(0) if match else ""


def extract_authors(content: str) -> list[str]:
    patterns = [
        r"(?:作者|Author)\s*[:：]\s*([^\n]+)",
        r"(?:by|By)\s+([A-Z][A-Za-z ._-]{1,60})",
    ]
    return extract_matches(content, patterns, limit=4)


def extract_dates(content: str) -> list[str]:
    patterns = [
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\b\d{4}/\d{1,2}/\d{1,2}\b",
        r"\b\d{4}\.\d{1,2}\.\d{1,2}\b",
        r"\b\d{4}年\d{1,2}月\d{1,2}日\b",
    ]
    return extract_matches(content, patterns, limit=10, full_match=True)


def extract_people(content: str) -> list[str]:
    patterns = [
        r"(?:人物|Person|联系人)\s*[:：]\s*([^\n]+)",
        r"(?:与|和|包括)\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})",
    ]
    return extract_matches(content, patterns, limit=10)


def extract_organizations(content: str) -> list[str]:
    patterns = [
        r"(?:公司|组织|机构|Company|Organization)\s*[:：]\s*([^\n]+)",
        r"\b([A-Z][A-Za-z&.\- ]+(?:Inc|LLC|Ltd|Corp|Technologies|Labs|AI))\b",
        r"\b(OpenAI|Google|Microsoft|Anthropic|Meta|Notion|Obsidian|飞书|腾讯|阿里巴巴|字节跳动)\b",
    ]
    return extract_matches(content, patterns, limit=10)


def extract_matches(content: str, patterns: list[str], limit: int = 10, full_match: bool = False) -> list[str]:
    items = []
    seen = set()
    for pattern in patterns:
        for match in re.finditer(pattern, content, flags=re.IGNORECASE):
            text = match.group(0) if full_match else (match.group(1) if match.lastindex else match.group(0))
            for candidate in split_entities(text):
                normalized = candidate.strip().strip("，,;；")
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                items.append(normalized[:80])
                if len(items) >= limit:
                    return items
    return items


def split_entities(text: str) -> list[str]:
    parts = re.split(r"[，,；;、/]|(?:\sand\s)|(?:\sor\s)", text)
    return [part.strip() for part in parts if part.strip()]


def coerce_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        parts = re.split(r"[\n,，;；]+", text)
        return [part.strip(" -\t") for part in parts if part.strip(" -\t")]
    return [str(value)]


def is_generic_summary(text: str) -> bool:
    normalized = text.strip().lower()
    if not normalized:
        return True
    generic_values = {
        "摘要", "总结", "summary", "暂无摘要", "none", "n/a", "待补充", "待整理",
    }
    return normalized in generic_values


def infer_has_action_items(content: str) -> bool:
    markers = ("todo", "待办", "下一步", "行动项", "计划", "follow up", "next step")
    lowered = content.lower()
    return any(marker in lowered for marker in markers)
