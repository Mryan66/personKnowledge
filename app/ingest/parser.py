from pathlib import Path
from typing import Optional

TEXT_EXTENSIONS = {".md", ".txt"}


class UnsupportedFileTypeError(ValueError):
    pass


class DocumentParseError(RuntimeError):
    pass


class MissingParserDependencyError(DocumentParseError):
    pass


class OCRDisabledError(DocumentParseError):
    pass


def parse_text_document(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


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


def parse_document(path: Path, enable_ocr: bool = False) -> str:
    extension = path.suffix.lower()
    if extension in TEXT_EXTENSIONS:
        return parse_text_document(path)
    if extension == ".pdf":
        return parse_pdf_document(path, enable_ocr=enable_ocr)
    raise UnsupportedFileTypeError(f"Unsupported file type: {extension}")
