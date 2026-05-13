import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.config import Settings
from app.memory.database import create_manual_task
from app.web.tasks import render_tasks_page


class TasksWebTests(unittest.TestCase):
    def test_render_tasks_page_includes_counts_and_create_form(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            template_path = root / "tasks.html"
            template_path.write_text(
                "{{ open_count }} {{ done_count }} {{ archived_count }} {{ status_tabs }} {{ task_cards }}",
                encoding="utf-8",
            )
            settings = Settings(workspace_dir=root, database_path=root / "metadata.sqlite")
            create_manual_task(settings.resolved_database_path, "开放任务")
            second = create_manual_task(settings.resolved_database_path, "已完成任务")
            third = create_manual_task(settings.resolved_database_path, "归档任务")
            from app.memory.database import update_task_status
            update_task_status(settings.resolved_database_path, second, "done")
            update_task_status(settings.resolved_database_path, third, "archived")

            html = render_tasks_page(settings, template_path, status="open")

        self.assertIn("1", html)
        self.assertIn("open", html)

    def test_render_tasks_page_includes_existing_open_task(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings = Settings(workspace_dir=root, database_path=root / "metadata.sqlite")
            create_manual_task(settings.resolved_database_path, "补充案例")

            html = render_tasks_page(settings, Path("/Library/temp/personKnowledge/app/ui/templates/tasks.html"), status="open")

        self.assertIn("补充案例", html)
        self.assertIn("创建任务", html)
        self.assertIn("待办", html)


if __name__ == "__main__":
    unittest.main()
