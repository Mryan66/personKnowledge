import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.ingest.pipeline import ingest_file
from app.memory.database import count_documents, get_document, get_document_by_id


class DedupTests(unittest.TestCase):
    def test_same_content_twice_creates_one_document(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            first = root / "first.md"
            second = root / "second.md"
            content = "# Agent 笔记\n\nSame   CONTENT"
            first.write_text(content, encoding="utf-8")
            second.write_text("  # Agent 笔记\n\nsame content  ", encoding="utf-8")

            first_result = ingest_file(first, database_path)
            second_result = ingest_file(second, database_path)
            document_count = count_documents(database_path)

        self.assertEqual(first_result.status, "ingested")
        self.assertEqual(second_result.status, "duplicate")
        self.assertEqual(second_result.duplicate_of_document_id, first_result.document_id)
        self.assertEqual(document_count, 1)

    def test_force_mode_reprocesses_existing_content(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            first = root / "first.md"
            second = root / "second.md"
            first.write_text("# Agent 笔记\n\nSame content", encoding="utf-8")
            second.write_text("# Agent 笔记\n\nSame content", encoding="utf-8")

            first_result = ingest_file(first, database_path)
            forced_result = ingest_file(second, database_path, force=True)
            document_count = count_documents(database_path)
            reused_document = get_document_by_id(database_path, first_result.document_id)
            old_path_record = get_document(database_path, first)

        self.assertEqual(forced_result.status, "ingested")
        self.assertEqual(forced_result.document_id, first_result.document_id)
        self.assertEqual(document_count, 1)
        self.assertIsNotNone(reused_document)
        self.assertEqual(reused_document.source_path, str(second))
        self.assertIsNone(old_path_record)


if __name__ == "__main__":
    unittest.main()
