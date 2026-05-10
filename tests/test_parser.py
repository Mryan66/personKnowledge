import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
from unittest.mock import patch

from app.ingest.parser import (
    DocumentParseError,
    MissingParserDependencyError,
    OCRDisabledError,
    UnsupportedFileTypeError,
    parse_document,
    parse_docx_document,
    parse_html_document,
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
            path = Path(temporary_directory) / "archive.bin"
            path.write_text("nope", encoding="utf-8")

            with self.assertRaises(UnsupportedFileTypeError):
                parse_document(path)

    def test_parse_html_document_extracts_text(self):
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "page.html"
            path.write_text("<html><body><h1>标题</h1><p>第一段</p><p>第二段</p></body></html>", encoding="utf-8")

            content = parse_html_document(path)

        self.assertIn("标题", content)
        self.assertIn("第一段", content)
        self.assertIn("第二段", content)

    def test_parse_docx_document_extracts_paragraphs(self):
        document_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body>"
            "<w:p><w:r><w:t>第一段</w:t></w:r></w:p>"
            "<w:p><w:r><w:t>第二段</w:t></w:r></w:p>"
            "</w:body>"
            "</w:document>"
        )
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "note.docx"
            with ZipFile(path, "w") as archive:
                archive.writestr("word/document.xml", document_xml)

            content = parse_docx_document(path)

        self.assertEqual(content, "第一段\n\n第二段")

    def test_parse_image_document_requires_ocr(self):
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "image.png"
            path.write_bytes(b"fake-image")

            with self.assertRaises(OCRDisabledError):
                parse_document(path, enable_ocr=False)

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
