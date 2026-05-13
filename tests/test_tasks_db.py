import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.memory.database import (
    count_tasks_by_status,
    create_manual_task,
    delete_task,
    initialize_database,
    list_tasks,
    record_tasks_from_organizer,
    update_task_fields,
    update_task_status,
    upsert_document,
)


class TasksDatabaseTests(unittest.TestCase):
    def test_record_tasks_from_organizer_deduplicates(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            document_id = upsert_document(
                database_path,
                source_path=root / "note.md",
                file_hash="file-hash",
                content_hash="content-hash",
                title="任务文档",
                summary="摘要",
                tags=[],
                category="notes",
                chunks=["chunk"],
            )

            first_count = record_tasks_from_organizer(database_path, document_id, ["补充案例", "补充案例", "更新摘要"])
            second_count = record_tasks_from_organizer(database_path, document_id, ["补充案例", "更新摘要"])
            tasks = list_tasks(database_path, status_filter="open", document_id=document_id, limit=10)

        self.assertEqual(first_count, 2)
        self.assertEqual(second_count, 0)
        self.assertEqual(len(tasks), 2)

    def test_create_manual_task_and_list_tasks_crud(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            task_id = create_manual_task(database_path, "手动任务", due_date="2026-05-20", priority="high")
            updated = update_task_fields(database_path, task_id, content="手动任务已更新", due_date="2026-05-21", priority="low")
            tasks = list_tasks(database_path, status_filter="open", limit=10)
            deleted = delete_task(database_path, task_id)
            tasks_after_delete = list_tasks(database_path, status_filter="open", limit=10)

        self.assertTrue(updated)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["content"], "手动任务已更新")
        self.assertEqual(tasks[0]["due_date"], "2026-05-21")
        self.assertEqual(tasks[0]["priority"], "low")
        self.assertTrue(deleted)
        self.assertEqual(tasks_after_delete, [])

    def test_update_task_status_done_sets_done_at(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            task_id = create_manual_task(database_path, "完成任务")

            updated = update_task_status(database_path, task_id, "done")
            done_tasks = list_tasks(database_path, status_filter="done", limit=10)

        self.assertTrue(updated)
        self.assertEqual(len(done_tasks), 1)
        self.assertEqual(done_tasks[0]["status"], "done")
        self.assertTrue(done_tasks[0]["done_at"])

    def test_count_tasks_by_status_groups_correctly(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            initialize_database(database_path)
            first = create_manual_task(database_path, "任务一")
            second = create_manual_task(database_path, "任务二")
            third = create_manual_task(database_path, "任务三")
            update_task_status(database_path, second, "done")
            update_task_status(database_path, third, "archived")

            counts = count_tasks_by_status(database_path)

        self.assertEqual(counts, {"open": 1, "done": 1, "archived": 1})


if __name__ == "__main__":
    unittest.main()
