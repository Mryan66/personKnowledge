import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.agents.organizer_agent import OrganizationResult
from app.ingest.chunker import chunk_text
from app.ingest.pipeline import ingest_file, ingest_path
from app.ingest.summarizer import extract_title, generate_tags, summarize
from app.memory.database import count_chunks, get_document


class IngestPipelineTests(unittest.TestCase):
    def test_summarizer_extracts_basic_metadata(self):
        content = "# Agent 知识管家\n\nAgent 可以整理知识，Agent 可以生成摘要。"

        self.assertEqual(extract_title(content, "fallback"), "Agent 知识管家")
        self.assertTrue(summarize(content).startswith("# Agent 知识管家"))
        self.assertIn("agent", generate_tags(content))

    def test_chunk_text_splits_long_content(self):
        chunks = chunk_text("a" * 30, chunk_size=10, overlap=2)

        self.assertEqual(chunks, ["a" * 10, "a" * 10, "a" * 10, "a" * 6])

    def test_ingest_file_writes_document_and_chunks(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            document_path = root / "note.md"
            database_path = root / "metadata.sqlite"
            document_path.write_text("# Agent 知识管家\n\n用于整理个人知识。", encoding="utf-8")

            result = ingest_file(document_path, database_path)
            record = get_document(database_path, document_path)
            chunk_count = count_chunks(database_path, result.document_id)

        self.assertEqual(result.title, "Agent 知识管家")
        self.assertIsNotNone(record)
        self.assertEqual(record.title, "Agent 知识管家")
        self.assertEqual(chunk_count, 1)

    def test_ingest_file_uses_organizer_agent_output(self):
        class StubOrganizerAgent:
            def organize(self, source_path, content):
                return OrganizationResult(
                    source_path=source_path,
                    title="整理后的标题",
                    summary="整理后的摘要",
                    tags=["agent", "memory"],
                    category="agent",
                    action_items=["补充示例"],
                )

        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            document_path = root / "note.md"
            database_path = root / "metadata.sqlite"
            document_path.write_text("# 原始标题\n\n用于整理个人知识。", encoding="utf-8")

            result = ingest_file(document_path, database_path, organizer_agent=StubOrganizerAgent())
            record = get_document(database_path, document_path)

        self.assertEqual(result.title, "整理后的标题")
        self.assertEqual(result.summary, "整理后的摘要")
        self.assertEqual(result.tags, ["agent", "memory"])
        self.assertEqual(record.title, "整理后的标题")

    def test_ingest_path_skips_unsupported_files(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "note.md").write_text("# Note", encoding="utf-8")
            (root / "archive.bin").write_text("Nope", encoding="utf-8")
            database_path = root / "metadata.sqlite"

            batch = ingest_path(root, database_path)

        self.assertEqual(len(batch), 1)
        self.assertEqual(batch[0].title, "Note")
        self.assertEqual(batch.failures, [])

    def test_ingest_path_reports_image_ocr_failure_when_disabled(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "image.png").write_bytes(b"fake-image")
            database_path = root / "metadata.sqlite"

            batch = ingest_path(root, database_path, enable_ocr=False)

        self.assertEqual(batch.successes, [])
        self.assertEqual(len(batch.failures), 1)
        self.assertIn("Image OCR is disabled", batch.failures[0].reason)

    def test_ingest_file_marks_duplicate_when_same_hash_exists(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            original = root / "original.md"
            duplicate = root / "duplicate.md"
            content = "# Agent 知识\n\n同一份内容。"
            original.write_text(content, encoding="utf-8")
            duplicate.write_text(content, encoding="utf-8")

            first = ingest_file(original, database_path)
            second = ingest_file(duplicate, database_path)

        self.assertEqual(first.status, "ingested")
        self.assertEqual(second.status, "duplicate")
        self.assertEqual(second.duplicate_of_document_id, first.document_id)

    def test_ingest_file_marks_similar_when_candidate_exists(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            first = root / "first.md"
            second = root / "second.md"
            first.write_text("# Agent 方案\n\nRAG memory 设计。", encoding="utf-8")
            second.write_text("# Agent 方案实践\n\nRAG memory 设计细节。", encoding="utf-8")

            ingest_file(first, database_path)
            result = ingest_file(second, database_path)

        self.assertEqual(result.status, "similar")
        self.assertGreaterEqual(len(result.duplicate_candidates), 1)

    def test_ingest_path_reports_empty_document_failure(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "empty.md").write_text("   ", encoding="utf-8")
            database_path = root / "metadata.sqlite"

            batch = ingest_path(root, database_path)

        self.assertEqual(batch.successes, [])
        self.assertEqual(len(batch.failures), 1)
        self.assertIn("no extractable text", batch.failures[0].reason)


if __name__ == "__main__":
    unittest.main()
