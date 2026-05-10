import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.ingest.pipeline import ingest_file
from app.memory.database import search_documents
from app.tools.search_tool import SearchTool


class SearchTests(unittest.TestCase):
    def test_search_documents_finds_matching_chunk(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            agent_note = root / "agent.md"
            cooking_note = root / "cooking.md"
            agent_note.write_text("# Agent 框架\n\nRAG 和 Agent 可以用于知识库问答。", encoding="utf-8")
            cooking_note.write_text("# 烹饪笔记\n\n番茄炒蛋需要控制火候。", encoding="utf-8")
            ingest_file(agent_note, database_path)
            ingest_file(cooking_note, database_path)

            results = search_documents(database_path, "RAG")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Agent 框架")
        self.assertIn("RAG", results[0].content)

    def test_search_documents_scores_title_higher_than_content(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            title_match = root / "title.md"
            content_match = root / "content.md"
            title_match.write_text("# RAG 优化\n\n检索增强生成。", encoding="utf-8")
            content_match.write_text("# 普通笔记\n\n这里提到了 RAG。", encoding="utf-8")
            ingest_file(content_match, database_path)
            ingest_file(title_match, database_path)

            results = search_documents(database_path, "RAG", limit=2)

        self.assertEqual([result.title for result in results], ["RAG 优化", "普通笔记"])
        self.assertGreater(results[0].score, results[1].score)

    def test_search_documents_returns_empty_for_blank_query(self):
        with TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "metadata.sqlite"

            results = search_documents(database_path, "   ")

        self.assertEqual(results, [])

    def test_search_tool_maps_database_records(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            note = root / "note.md"
            note.write_text("# 个人知识库\n\n用于 Agent 检索。", encoding="utf-8")
            ingest_file(note, database_path)

            results = SearchTool(database_path).search("Agent")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "个人知识库")
        self.assertEqual(results[0].chunk_index, 0)


if __name__ == "__main__":
    unittest.main()
