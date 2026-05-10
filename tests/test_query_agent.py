import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.agents.query_agent import QueryAgent, build_rag_input, build_snippet
from app.ingest.pipeline import ingest_file


class FakeOpenAIClient:
    def __init__(self, text):
        self.text = text
        self.input_text = None

    def generate_text(self, instructions, input_text, max_output_tokens=700):
        from app.tools.openai_client import OpenAIResponse

        self.input_text = input_text
        return OpenAIResponse(text=self.text, raw={})


class QueryAgentTests(unittest.TestCase):
    def test_build_snippet_truncates_long_content(self):
        snippet = build_snippet("a" * 30, max_length=10)

        self.assertEqual(snippet, "aaaaaaaaa…")

    def test_answer_returns_cited_search_results(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            note = root / "rag.md"
            note.write_text("# RAG 问答\n\nRAG 可以检索知识库并生成带来源的回答。", encoding="utf-8")
            ingest_file(note, database_path)

            answer = QueryAgent(database_path).answer("RAG", limit=1)

        self.assertIn("根据当前知识库", answer.text)
        self.assertIn("RAG 问答", answer.text)
        self.assertEqual(len(answer.sources), 1)
        self.assertTrue(answer.sources[0].endswith("#chunk-0"))
        self.assertEqual(answer.confidence, "high")

    def test_answer_handles_no_results(self):
        with TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "metadata.sqlite"

            answer = QueryAgent(database_path).answer("不存在的问题")

        self.assertEqual(answer.sources, [])
        self.assertEqual(answer.confidence, "none")
        self.assertIn("没有在知识库中找到", answer.text)

    def test_answer_uses_openai_when_enabled(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            note = root / "rag.md"
            note.write_text("# RAG 问答\n\nRAG 可以检索知识库并生成带来源的回答。", encoding="utf-8")
            ingest_file(note, database_path)
            fake_client = FakeOpenAIClient("RAG 可以生成带来源的总结。来源：rag.md#chunk-0")

            answer = QueryAgent(database_path, openai_client=fake_client, use_llm=True).answer("RAG", limit=1)

        self.assertEqual(answer.mode, "rag")
        self.assertIn("带来源的总结", answer.text)
        self.assertIn("用户问题：RAG", fake_client.input_text)
        self.assertEqual(answer.style, "balanced")
        self.assertEqual(len(answer.citations), 1)

    def test_answer_falls_back_when_openai_fails(self):
        from app.tools.openai_client import OpenAIClientError

        class FailingOpenAIClient:
            def generate_text(self, instructions, input_text, max_output_tokens=700):
                raise OpenAIClientError("boom")

        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            note = root / "rag.md"
            note.write_text("# RAG 问答\n\nRAG 可以检索知识库并生成带来源的回答。", encoding="utf-8")
            ingest_file(note, database_path)

            answer = QueryAgent(database_path, openai_client=FailingOpenAIClient(), use_llm=True).answer("RAG", limit=1)

        self.assertEqual(answer.mode, "fallback")
        self.assertIn("OpenAI RAG 生成失败", answer.text)

    def test_answer_supports_detailed_style(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            note = root / "rag.md"
            note.write_text("# RAG 问答\n\nRAG 可以检索知识库并生成带来源的回答。", encoding="utf-8")
            ingest_file(note, database_path)

            answer = QueryAgent(database_path, answer_style="detailed").answer("RAG", limit=1)

        self.assertEqual(answer.style, "detailed")
        self.assertIn("分类：", answer.text)

    def test_build_rag_input_includes_history(self):
        class FakeResult:
            title = "RAG"
            source_path = "rag.md"
            chunk_index = 0
            category = "rag"
            tags = ["rag"]
            content = "RAG content"

        text = build_rag_input(
            "继续解释",
            [FakeResult()],
            history=[{"role": "user", "content": "先介绍 RAG"}, {"role": "assistant", "content": "RAG 是..."}],
            style="report",
        )

        self.assertIn("最近对话", text)
        self.assertIn("回答风格：report", text)


if __name__ == "__main__":
    unittest.main()
