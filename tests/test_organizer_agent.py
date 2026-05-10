import unittest
from pathlib import Path

from app.agents.organizer_agent import (
    OrganizerAgent,
    extract_authors,
    extract_dates,
    extract_organizations,
    extract_people,
    extract_source_url,
    normalize_action_items,
    normalize_category,
    normalize_tags,
    parse_json_object,
)
from app.tools.openai_client import OpenAIResponse


class StubOpenAIClient:
    def __init__(self, responses):
        if isinstance(responses, str):
            responses = [responses]
        self.responses = list(responses)
        self.calls = []

    def generate_text(self, instructions: str, input_text: str, max_output_tokens: int = 500):
        self.calls.append({"instructions": instructions, "input_text": input_text, "max_output_tokens": max_output_tokens})
        text = self.responses.pop(0)
        return OpenAIResponse(text=text, raw={})


class OrganizerAgentTests(unittest.TestCase):
    def test_parse_json_object_accepts_code_fence_and_trailing_comma(self):
        payload = parse_json_object(
            """```json
{"title":"测试","summary":"摘要","tags":["rag",],"category":"notes","action_items":[]}
```"""
        )

        self.assertEqual(payload["title"], "测试")
        self.assertEqual(payload["tags"], ["rag"])

    def test_parse_json_object_accepts_python_style_dict(self):
        payload = parse_json_object("{'title': '测试', 'summary': '摘要', 'tags': 'rag, agent', 'category': '其他'}")

        self.assertEqual(payload["title"], "测试")
        self.assertEqual(payload["category"], "其他")

    def test_normalize_tags_accepts_string_and_deduplicates(self):
        tags = normalize_tags("RAG, agent，RAG\nmemory")

        self.assertEqual(tags, ["rag", "agent", "memory"])

    def test_normalize_action_items_accepts_multiline_string(self):
        items = normalize_action_items("1. 补充案例\n- 更新总结\n1. 补充案例")

        self.assertEqual(items, ["补充案例", "更新总结"])

    def test_normalize_category_falls_back_for_generic_labels(self):
        category, used_fallback = normalize_category("其他", tags=["rag", "agent"])

        self.assertEqual(category, "rag")
        self.assertTrue(used_fallback)

    def test_organize_uses_partial_fallbacks_instead_of_full_failure(self):
        client = StubOpenAIClient(
            """{
                "title": "",
                "summary": ["第一句", "第二句"],
                "tags": "RAG, Agent",
                "category": "其他",
                "action_items": "1. 补充案例\\n- 更新知识卡片"
            }"""
        )
        agent = OrganizerAgent(openai_client=client)

        result = agent.organize(Path("note.md"), "# 原始标题\n\n这里是关于 RAG 和 Agent 的知识整理。")

        self.assertEqual(result.title, "原始标题")
        self.assertEqual(result.summary, "第一句 第二句")
        self.assertEqual(result.tags, ["rag", "agent"])
        self.assertEqual(result.category, "rag")
        self.assertEqual(result.action_items, ["补充案例", "更新知识卡片"])
        self.assertEqual(result.diagnostics.strategy, "llm_partial_fallback")
        self.assertIn("title", result.diagnostics.fallback_fields)
        self.assertIn("category", result.diagnostics.fallback_fields)

    def test_organize_attempts_repair_prompt_when_initial_parse_fails(self):
        client = StubOpenAIClient(
            [
                "这不是合法 JSON",
                '{"title":"修复后标题","summary":"修复后摘要","tags":["rag"],"category":"notes","action_items":[]}',
            ]
        )
        agent = OrganizerAgent(openai_client=client)

        result = agent.organize(Path("note.md"), "# 原始标题\n\n这里是测试内容。")

        self.assertEqual(result.title, "修复后标题")
        self.assertEqual(result.diagnostics.llm_attempts, 2)
        self.assertTrue(result.diagnostics.used_repair_prompt)
        self.assertIn("initial_parse_failed", result.diagnostics.warnings)
        self.assertEqual(len(client.calls), 2)

    def test_organize_marks_empty_action_items_warning_when_content_suggests_tasks(self):
        client = StubOpenAIClient(
            '{"title":"任务文档","summary":"整理任务。","tags":["tasks"],"category":"project","action_items":[]}'
        )
        agent = OrganizerAgent(openai_client=client)

        result = agent.organize(Path("note.md"), "# 原始标题\n\n待办：补充案例，下一步更新知识卡片。")

        self.assertIn("llm_action_items_empty", result.diagnostics.warnings)

    def test_rule_extractors_capture_structured_metadata(self):
        content = (
            "作者：张三\n"
            "日期：2026-05-10\n"
            "人物：李四，王五\n"
            "公司：OpenAI，Microsoft\n"
            "链接：https://example.com/report\n"
        )

        self.assertEqual(extract_authors(content), ["张三"])
        self.assertEqual(extract_dates(content), ["2026-05-10"])
        self.assertEqual(extract_people(content), ["李四", "王五"])
        self.assertIn("OpenAI", extract_organizations(content))
        self.assertEqual(extract_source_url(content), "https://example.com/report")

    def test_organize_with_rules_includes_structured_metadata(self):
        agent = OrganizerAgent()

        result = agent.organize(
            Path("note.md"),
            "# 项目纪要\n\n作者：张三\n日期：2026-05-10\n人物：李四\n公司：OpenAI\n链接：https://example.com\n",
        )

        self.assertEqual(result.authors, ["张三"])
        self.assertEqual(result.dates, ["2026-05-10"])
        self.assertEqual(result.people, ["李四"])
        self.assertIn("OpenAI", result.organizations)
        self.assertEqual(result.source_url, "https://example.com")


if __name__ == "__main__":
    unittest.main()
