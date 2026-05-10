import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.memory.database import (
    add_chat_message,
    create_chat_session,
    delete_document,
    get_latest_assistant_message,
    get_document_by_id,
    get_chat_session,
    initialize_database,
    list_chat_messages,
    list_chat_sessions,
    list_chunks,
    list_similar_documents,
    update_document_metadata,
    upsert_document,
)


class DatabaseTests(unittest.TestCase):
    def test_initialize_database_creates_tables(self):
        with TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "metadata.sqlite"

            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                table_names = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }

        self.assertIn("documents", table_names)
        self.assertIn("chunks", table_names)

    def test_update_and_delete_document_metadata(self):
        with TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "metadata.sqlite"
            document_id = upsert_document(
                database_path,
                source_path=Path(temporary_directory) / "note.md",
                title="原始标题",
                summary="原始摘要",
                tags=["one"],
                category="notes",
                chunks=["chunk-1"],
            )

            updated = update_document_metadata(
                database_path,
                document_id,
                title="更新标题",
                summary="更新摘要",
                tags=["agent", "rag"],
                category="knowledge",
            )
            record = get_document_by_id(database_path, document_id)
            chunks_before_delete = list_chunks(database_path, document_id)
            deleted = delete_document(database_path, document_id)
            deleted_record = get_document_by_id(database_path, document_id)

        self.assertTrue(updated)
        self.assertEqual(record.title, "更新标题")
        self.assertEqual(record.tags, ["agent", "rag"])
        self.assertEqual(record.category, "knowledge")
        self.assertEqual(len(chunks_before_delete), 1)
        self.assertTrue(deleted)
        self.assertIsNone(deleted_record)

    def test_list_similar_documents_prefers_shared_tags_and_category(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            target_id = upsert_document(
                database_path,
                source_path=root / "target.md",
                title="RAG 方案",
                summary="关于 agent 与 memory 的总结",
                tags=["rag", "agent", "memory"],
                category="ai",
                chunks=["a"],
            )
            upsert_document(
                database_path,
                source_path=root / "close.md",
                title="Agent Memory 实践",
                summary="RAG 与 memory 的组合",
                tags=["rag", "memory"],
                category="ai",
                chunks=["b"],
            )
            upsert_document(
                database_path,
                source_path=root / "far.md",
                title="旅游清单",
                summary="周末出行准备",
                tags=["travel"],
                category="life",
                chunks=["c"],
            )

            similar = list_similar_documents(database_path, target_id, limit=5)

        self.assertEqual(len(similar), 1)
        self.assertEqual(similar[0]["title"], "Agent Memory 实践")
        self.assertGreater(similar[0]["similarity_score"], 0)

    def test_chat_sessions_and_messages_round_trip(self):
        with TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "metadata.sqlite"
            session_id = create_chat_session(database_path, "RAG 对话")
            add_chat_message(database_path, session_id, "user", "什么是 RAG？", style="concise")
            add_chat_message(
                database_path,
                session_id,
                "assistant",
                "RAG 是检索增强生成。",
                sources=["rag.md#chunk-0"],
                style="concise",
            )

            session = get_chat_session(database_path, session_id)
            sessions = list_chat_sessions(database_path)
            messages = list_chat_messages(database_path, session_id)
            latest_answer = get_latest_assistant_message(database_path, session_id)

        self.assertEqual(session.title, "RAG 对话")
        self.assertEqual(len(sessions), 1)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[1].sources, ["rag.md#chunk-0"])
        self.assertEqual(latest_answer.content, "RAG 是检索增强生成。")


if __name__ == "__main__":
    unittest.main()
