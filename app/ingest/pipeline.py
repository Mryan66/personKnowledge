from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from app.agents.organizer_agent import OrganizerAgent
from app.ingest.chunker import chunk_text
from app.ingest.parser import DocumentParseError, UnsupportedFileTypeError, parse_document
from app.ingest.scanner import scan_inbox
from app.memory.database import upsert_document
from app.tools.embedding_tool import EmbeddingTool
from app.tools.openai_client import OpenAIClientError


@dataclass(frozen=True)
class IngestResult:
    source_path: Path
    document_id: int
    title: str
    summary: str
    tags: List[str]
    category: str
    chunk_count: int
    embedding_count: int = 0


@dataclass(frozen=True)
class IngestFailure:
    source_path: Path
    reason: str


@dataclass(frozen=True)
class IngestBatchResult:
    successes: List[IngestResult] = field(default_factory=list)
    failures: List[IngestFailure] = field(default_factory=list)

    def __iter__(self):
        return iter(self.successes)

    def __len__(self) -> int:
        return len(self.successes)

    def __getitem__(self, index: int) -> IngestResult:
        return self.successes[index]


def discover_targets(path: Path) -> List[Path]:
    if path.is_dir():
        return scan_inbox(path)
    return [path]


def ingest_file(
    path: Path,
    database_path: Path,
    embedding_tool: Optional[EmbeddingTool] = None,
    organizer_agent: Optional[OrganizerAgent] = None,
    enable_ocr: bool = False,
) -> IngestResult:
    content = parse_document(path, enable_ocr=enable_ocr)
    if not content:
        raise DocumentParseError(
            f"Document has no extractable text: {path}. If this is a scanned PDF, OCR is required."
        )

    organizer = organizer_agent or OrganizerAgent()
    organization = organizer.organize(path, content)
    chunks = chunk_text(content)
    document_id = upsert_document(
        database_path=database_path,
        source_path=path,
        title=organization.title,
        summary=organization.summary,
        tags=organization.tags,
        category=organization.category,
        chunks=chunks,
    )
    embedding_count = 0
    if embedding_tool:
        embedding_count = embedding_tool.embed_document_chunks(database_path, document_id)
    return IngestResult(
        source_path=path,
        document_id=document_id,
        title=organization.title,
        summary=organization.summary,
        tags=organization.tags,
        category=organization.category,
        chunk_count=len(chunks),
        embedding_count=embedding_count,
    )


def ingest_path(
    path: Path,
    database_path: Path,
    embedding_tool: Optional[EmbeddingTool] = None,
    organizer_agent: Optional[OrganizerAgent] = None,
    enable_ocr: bool = False,
) -> IngestBatchResult:
    successes = []
    failures = []
    for target in discover_targets(path):
        try:
            successes.append(
                ingest_file(
                    target,
                    database_path,
                    embedding_tool=embedding_tool,
                    organizer_agent=organizer_agent,
                    enable_ocr=enable_ocr,
                )
            )
        except UnsupportedFileTypeError:
            continue
        except (DocumentParseError, OpenAIClientError, OSError, UnicodeDecodeError, ValueError) as error:
            failures.append(IngestFailure(source_path=target, reason=str(error)))
    return IngestBatchResult(successes=successes, failures=failures)
