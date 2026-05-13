import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.ingest.pipeline import ingest_file
from app.memory.database import apply_search_filters, list_all_tags, search_documents, upsert_document
from app.web.server import extract_search_filters


class SearchFilterTests(unittest.TestCase):
    def test_apply_search_filters_supports_multi_tag_or(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            first = root / "rag.md"
            second = root / "memory.md"
            third = root / "other.md"
            first.write_text("# RAG 方案\n\n标签：rag\n关于检索增强生成。", encoding="utf-8")
            second.write_text("# Memory 方案\n\n标签：memory\n关于长期记忆。", encoding="utf-8")
            third.write_text("# 其他方案\n\n标签：ops\n关于运维。", encoding="utf-8")
            ingest_file(first, database_path)
            ingest_file(second, database_path)
            ingest_file(third, database_path)

            records = search_documents(database_path, "方案", limit=10)
            filtered = apply_search_filters(records, tags=["rag", "memory"])

        self.assertEqual({record.title for record in filtered}, {"RAG 方案", "Memory 方案"})

    def test_list_all_tags_returns_deduplicated_counts(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            first = root / "first.md"
            second = root / "second.md"
            third = root / "third.md"
            upsert_document(
                database_path,
                source_path=first,
                file_hash="hash-1",
                content_hash="content-1",
                title="文档一",
                summary="摘要一",
                tags=["rag", "memory"],
                category="ai",
                chunks=["内容 A"],
            )
            upsert_document(
                database_path,
                source_path=second,
                file_hash="hash-2",
                content_hash="content-2",
                title="文档二",
                summary="摘要二",
                tags=["rag"],
                category="ai",
                chunks=["内容 B"],
            )
            upsert_document(
                database_path,
                source_path=third,
                file_hash="hash-3",
                content_hash="content-3",
                title="文档三",
                summary="摘要三",
                tags=["agent"],
                category="ops",
                chunks=["内容 C"],
            )

            tags = list_all_tags(database_path)

        self.assertEqual(tags[:3], [("rag", 2), ("agent", 1), ("memory", 1)])

    def test_extract_search_filters_merges_tag_and_tags(self):
        filters = extract_search_filters(
            {
                "tag": ["rag"],
                "tags": ["memory", "rag", " "],
                "category": ["project"],
                "categories": ["ai", "project"],
                "person": ["张三"],
                "date_from": ["2026-05-01"],
                "date_to": ["2026-05-31"],
            }
        )

        self.assertEqual(filters["tag"], "rag")
        self.assertEqual(filters["tags"], ["rag", "memory"])
        self.assertEqual(filters["category"], "project")
        self.assertEqual(filters["categories"], ["project", "ai"])


if __name__ == "__main__":
    unittest.main()
