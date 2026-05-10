import unittest

from app.ingest.scanner import scan_inbox


class ScannerTests(unittest.TestCase):
    def test_scan_inbox_returns_supported_files(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path

        with TemporaryDirectory() as temporary_directory:
            inbox_dir = Path(temporary_directory)
            (inbox_dir / "note.md").write_text("hello", encoding="utf-8")
            (inbox_dir / "raw.txt").write_text("hello", encoding="utf-8")
            (inbox_dir / "page.html").write_text("<p>hello</p>", encoding="utf-8")
            (inbox_dir / "image.png").write_bytes(b"nope")

            files = scan_inbox(inbox_dir)

        self.assertEqual([file.name for file in files], ["image.png", "note.md", "page.html", "raw.txt"])

    def test_scan_inbox_missing_directory(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path

        with TemporaryDirectory() as temporary_directory:
            files = scan_inbox(Path(temporary_directory) / "missing")

        self.assertEqual(files, [])


if __name__ == "__main__":
    unittest.main()
