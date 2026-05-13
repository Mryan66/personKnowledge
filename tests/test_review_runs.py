import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.memory.database import get_last_review_run, list_recent_review_runs, record_review_run


class ReviewRunTests(unittest.TestCase):
    def test_record_and_list_recent_review_runs(self):
        with TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "metadata.sqlite"
            record_review_run(
                database_path,
                period="daily",
                triggered_by="auto",
                started_at="2026-05-14T08:30:00+00:00",
                finished_at="2026-05-14T08:30:05+00:00",
                status="success",
                document_count=12,
                output_path="/tmp/daily.md",
                error_message="",
            )

            runs = list_recent_review_runs(database_path, limit=10)

        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["period"], "daily")
        self.assertEqual(runs[0]["triggered_by"], "auto")
        self.assertEqual(runs[0]["status"], "success")
        self.assertEqual(runs[0]["document_count"], 12)
        self.assertEqual(runs[0]["output_path"], "/tmp/daily.md")

    def test_get_last_review_run_returns_latest_for_period(self):
        with TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "metadata.sqlite"
            record_review_run(
                database_path,
                period="daily",
                triggered_by="cli",
                started_at="2026-05-13T08:30:00+00:00",
                finished_at="2026-05-13T08:30:05+00:00",
                status="success",
                document_count=5,
                output_path="/tmp/old-daily.md",
                error_message="",
            )
            record_review_run(
                database_path,
                period="weekly",
                triggered_by="auto",
                started_at="2026-05-12T09:00:00+00:00",
                finished_at="2026-05-12T09:00:10+00:00",
                status="success",
                document_count=20,
                output_path="/tmp/weekly.md",
                error_message="",
            )
            record_review_run(
                database_path,
                period="daily",
                triggered_by="auto",
                started_at="2026-05-14T08:30:00+00:00",
                finished_at="2026-05-14T08:30:06+00:00",
                status="success",
                document_count=9,
                output_path="/tmp/new-daily.md",
                error_message="",
            )

            latest_daily = get_last_review_run(database_path, "daily")
            latest_monthly = get_last_review_run(database_path, "monthly")

        self.assertIsNotNone(latest_daily)
        self.assertEqual(latest_daily["output_path"], "/tmp/new-daily.md")
        self.assertEqual(latest_daily["document_count"], 9)
        self.assertIsNone(latest_monthly)

    def test_record_failed_review_run_persists_error_message(self):
        with TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "metadata.sqlite"
            record_review_run(
                database_path,
                period="monthly",
                triggered_by="web",
                started_at="2026-05-01T09:30:00+00:00",
                finished_at="2026-05-01T09:30:03+00:00",
                status="failed",
                document_count=None,
                output_path="",
                error_message="boom",
            )

            runs = list_recent_review_runs(database_path, limit=10)

        self.assertEqual(runs[0]["status"], "failed")
        self.assertEqual(runs[0]["error_message"], "boom")


if __name__ == "__main__":
    unittest.main()
