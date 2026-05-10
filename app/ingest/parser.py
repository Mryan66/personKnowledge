import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree
from zipfile import ZipFile

TEXT_EXTENSIONS = {".md", ".txt"}
HTML_EXTENSIONS = {".html", ".htm"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


class UnsupportedFileTypeError(ValueError):
    pass


class DocumentParseError(RuntimeError):
    pass


class MissingParserDependencyError(DocumentParseError):
    pass


class OCRDisabledError(DocumentParseError):
    pass


class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts = []

    def handle_data(self, data: str) -> None:
        if data and data.strip():
            self._parts.append(data.strip())

    def get_text(self) -> str:
        return "\n".join(self._parts).strip()


def parse_text_document(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def parse_html_document(path: Path) -> str:
    content = path.read_text(encoding="utf-8").strip()
    parser = _HTMLTextExtractor()
    parser.feed(content)
    parser.close()
    extracted = parser.get_text()
    if extracted:
        return normalize_whitespace(extracted)
    return normalize_whitespace(strip_html_tags(content))


def parse_docx_document(path: Path) -> str:
    try:
        with ZipFile(path) as archive:
            document_xml = archive.read("word/document.xml")
    except KeyError as error:
        raise DocumentParseError(f"Invalid DOCX file structure: {path}") from error
    except OSError as error:
        raise DocumentParseError(f"Failed to read DOCX file: {path}") from error

    try:
        root = ElementTree.fromstring(document_xml)
    except ElementTree.ParseError as error:
        raise DocumentParseError(f"Failed to parse DOCX XML: {path}") from error

    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []
    for paragraph in root.findall(".//w:p", namespace):
        texts = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
        combined = "".join(texts).strip()
        if combined:
            paragraphs.append(combined)
    return "\n\n".join(paragraphs).strip()


def parse_pdf_document(path: Path, enable_ocr: bool = False) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise MissingParserDependencyError(
            "PDF parsing requires the 'pypdf' package. Install with: pip install -e ."
        ) from error

    try:
        reader = PdfReader(str(path))
        if getattr(reader, "is_encrypted", False):
            try:
                reader.decrypt("")
            except Exception as error:
                raise DocumentParseError(f"PDF is encrypted and cannot be read: {path}") from error

        page_texts = []
        has_text = False

        for page_number, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception as error:
                raise DocumentParseError(
                    f"Failed to extract text from page {page_number} in PDF: {path}"
                ) from error
            normalized_text = text.strip()
            if normalized_text:
                has_text = True
                page_texts.append(normalized_text)

        # If no text extracted and OCR is enabled, try OCR
        if not has_text and enable_ocr:
            ocr_text = try_ocr_pdf(path)
            if ocr_text:
                return ocr_text

        # If still no text and we have OCR disabled, warn
        if not has_text:
            if enable_ocr:
                raise DocumentParseError(f"PDF has no extractable text and OCR failed: {path}")
            else:
                raise DocumentParseError(f"PDF has no extractable text (OCR disabled): {path}")

    except DocumentParseError:
        raise
    except Exception as error:
        raise DocumentParseError(f"Failed to parse PDF: {path}") from error

    return "\n\n".join(page_texts).strip()


def try_ocr_pdf(path: Path) -> Optional[str]:
    """Try OCR on a PDF file. Returns extracted text or None if OCR not available/failed."""
    try:
        # Try with pytesseract + pdf2image
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError:
        return None

    try:
        images = convert_from_path(str(path))
        page_texts = []
        for image in images:
            text = pytesseract.image_to_string(image, lang="chi_sim+eng")
            if text.strip():
                page_texts.append(text.strip())
        if page_texts:
            return "\n\n".join(page_texts)
    except Exception:
        pass

    return None


def parse_image_document(path: Path, enable_ocr: bool = False) -> str:
    if not enable_ocr:
        raise OCRDisabledError(f"Image OCR is disabled: {path}")

    text = try_ocr_image(path)
    if text:
        return text
    raise DocumentParseError(f"Image OCR failed or produced no text: {path}")


def try_ocr_image(path: Path) -> Optional[str]:
    try:
        from PIL import Image
        import pytesseract
    except ImportError:
        return None

    try:
        image = Image.open(path)
        text = pytesseract.image_to_string(image, lang="chi_sim+eng")
    except Exception:
        return None
    return text.strip() or None


def strip_html_tags(content: str) -> str:
    return re.sub(r"<[^>]+>", " ", content)


def normalize_whitespace(content: str) -> str:
    normalized = re.sub(r"\r\n?", "\n", content)
    normalized = re.sub(r"[ \t]+\n", "\n", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def parse_document(path: Path, enable_ocr: bool = False) -> str:
    extension = path.suffix.lower()
    if extension in TEXT_EXTENSIONS:
        return parse_text_document(path)
    if extension == ".docx":
        return parse_docx_document(path)
    if extension in HTML_EXTENSIONS:
        return parse_html_document(path)
    if extension == ".pdf":
        return parse_pdf_document(path, enable_ocr=enable_ocr)
    if extension in IMAGE_EXTENSIONS:
        return parse_image_document(path, enable_ocr=enable_ocr)
    raise UnsupportedFileTypeError(f"Unsupported file type: {extension}")
