import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.memory.database import (
    delete_tag_alias,
    list_tag_aliases,
    list_tag_groups,
    merge_tags,
    normalize_tag_for_compare,
    upsert_document,
)


class TagGovernanceTests(unittest.TestCase):
    def test_normalize_tag_for_compare_handles_case_and_spaces(self):
        self.assertEqual(normalize_tag_for_compare("  RAG   System "), "rag system")

    def test_list_tag_groups_returns_only_multi_variant_groups(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            upsert_document(
                database_path,
                source_path=root / "one.md",
                file_hash="hash-1",
                content_hash="content-1",
                title="One",
                summary="",
                tags=["RAG", "rag", "memory"],
                category="",
                chunks=["a"],
            )
            upsert_document(
                database_path,
                source_path=root / "two.md",
                file_hash="hash-2",
                content_hash="content-2",
                title="Two",
                summary="",
                tags=["Rag", "memory"],
                category="",
                chunks=["b"],
            )

            groups = list_tag_groups(database_path)

        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["canonical"], "RAG")
        self.assertEqual(groups[0]["variants"], [("RAG", 1), ("Rag", 1), ("rag", 1)])
        self.assertEqual(groups[0]["total_count"], 3)

    def test_merge_tags_updates_documents_and_alias_history(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            upsert_document(
                database_path,
                source_path=root / "one.md",
                file_hash="hash-1",
                content_hash="content-1",
                title="One",
                summary="",
                tags=["rag", "memory", "Rag", "RAG"],
                category="",
                chunks=["a"],
            )
            upsert_document(
                database_path,
                source_path=root / "two.md",
                file_hash="hash-2",
                content_hash="content-2",
                title="Two",
                summary="",
                tags=["memory", "rag"],
                category="",
                chunks=["b"],
            )

            affected = merge_tags(database_path, canonical="RAG", aliases=["rag", "Rag"])
            aliases = list_tag_aliases(database_path)
            groups_after = list_tag_groups(database_path)

        self.assertEqual(affected, 2)
        self.assertEqual([(item["alias"], item["canonical"]) for item in aliases], [("Rag", "RAG"), ("rag", "RAG")])
        self.assertEqual(groups_after, [])

    def test_list_and_delete_tag_aliases(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            upsert_document(
                database_path,
                source_path=root / "one.md",
                file_hash="hash-1",
                content_hash="content-1",
                title="One",
                summary="",
                tags=["RAG", "rag"],
                category="",
                chunks=["a"],
            )
            merge_tags(database_path, canonical="RAG", aliases=["rag"])

            aliases_before = list_tag_aliases(database_path)
            deleted = delete_tag_alias(database_path, "rag")
            aliases_after = list_tag_aliases(database_path)

        self.assertEqual(len(aliases_before), 1)
        self.assertTrue(deleted)
        self.assertEqual(aliases_after, [])


if __name__ == "__main__":
    unittest.main()
