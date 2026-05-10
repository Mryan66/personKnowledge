import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.ingest.parser import (
    DocumentParseError,
    MissingParserDependencyError,
    UnsupportedFileTypeError,
    parse_document,
    parse_pdf_document,
)


class ParserTests(unittest.TestCase):
    def test_parse_text_document_strips_content(self):
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "note.txt"
            path.write_text("  hello\n", encoding="utf-8")

            content = parse_document(path)

        self.assertEqual(content, "hello")

    def test_parse_unsupported_file_type_raises(self):
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "image.png"
            path.write_text("nope", encoding="utf-8")

            with self.assertRaises(UnsupportedFileTypeError):
                parse_document(path)

    def test_parse_pdf_document_requires_pypdf(self):
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "doc.pdf"
            path.write_bytes(b"%PDF")

            with patch.dict(sys.modules, {"pypdf": None}):
                with self.assertRaises(MissingParserDependencyError):
                    parse_pdf_document(path)

    def test_parse_pdf_document_extracts_pages(self):
        class FakePage:
            def __init__(self, text):
                self.text = text

            def extract_text(self):
                return self.text

        class FakePdfReader:
            is_encrypted = False

            def __init__(self, path):
                self.pages = [FakePage("第一页"), FakePage("  "), FakePage("第二页")]

        fake_module = types.SimpleNamespace(PdfReader=FakePdfReader)
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "doc.pdf"
            path.write_bytes(b"%PDF")

            with patch.dict(sys.modules, {"pypdf": fake_module}):
                content = parse_pdf_document(path)

        self.assertEqual(content, "第一页\n\n第二页")

    def test_parse_pdf_document_wraps_page_errors(self):
        class BrokenPage:
            def extract_text(self):
                raise RuntimeError("bad page")

        class FakePdfReader:
            is_encrypted = False

            def __init__(self, path):
                self.pages = [BrokenPage()]

        fake_module = types.SimpleNamespace(PdfReader=FakePdfReader)
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "doc.pdf"
            path.write_bytes(b"%PDF")

            with patch.dict(sys.modules, {"pypdf": fake_module}):
                with self.assertRaises(DocumentParseError):
                    parse_pdf_document(path)


if __name__ == "__main__":
    unittest.main()
