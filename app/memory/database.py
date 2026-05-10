from contextlib import closing
import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from app.tools.vector_tool import cosine_similarity

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_path TEXT NOT NULL UNIQUE,
    file_hash TEXT,
    title TEXT,
    summary TEXT,
    tags TEXT,
    category TEXT,
    authors TEXT,
    dates TEXT,
    people TEXT,
    organizations TEXT,
    source_url TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_id INTEGER NOT NULL UNIQUE,
    model TEXT NOT NULL,
    vector TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(chunk_id) REFERENCES chunks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    sources TEXT,
    style TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS search_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    mode TEXT NOT NULL,
    result_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


@dataclass(frozen=True)
class DocumentRecord:
    id: int
    source_path: str
    file_hash: str
    title: str
    summary: str
    tags: List[str]
    category: str
    authors: List[str]
    dates: List[str]
    people: List[str]
    organizations: List[str]
    source_url: str
    status: str


@dataclass(frozen=True)
class ChunkRecord:
    id: int
    document_id: int
    chunk_index: int
    content: str


@dataclass(frozen=True)
class SearchRecord:
    document_id: int
    source_path: str
    title: str
    summary: str
    tags: List[str]
    category: str
    authors: List[str]
    dates: List[str]
    people: List[str]
    organizations: List[str]
    source_url: str
    chunk_index: int
    content: str
    score: float


@dataclass(frozen=True)
class ChatSessionRecord:
    id: int
    title: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ChatMessageRecord:
    id: int
    session_id: int
    role: str
    content: str
    sources: List[str]
    style: str
    created_at: str


def initialize_database(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.executescript(SCHEMA)
    ensure_document_columns(database_path)


def upsert_document(
    database_path: Path,
    source_path: Path,
    file_hash: str,
    title: str,
    summary: str,
    tags: List[str],
    category: str,
    chunks: List[str],
    authors: Optional[List[str]] = None,
    dates: Optional[List[str]] = None,
    people: Optional[List[str]] = None,
    organizations: Optional[List[str]] = None,
    source_url: str = "",
    status: str = "ingested",
) -> int:
    initialize_database(database_path)
    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            connection.execute("PRAGMA foreign_keys = ON")
            cursor = connection.execute(
                """
                INSERT INTO documents (
                    source_path, file_hash, title, summary, tags, category, authors, dates, people, organizations, source_url, status, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(source_path) DO UPDATE SET
                    file_hash = excluded.file_hash,
                    title = excluded.title,
                    summary = excluded.summary,
                    tags = excluded.tags,
                    category = excluded.category,
                    authors = excluded.authors,
                    dates = excluded.dates,
                    people = excluded.people,
                    organizations = excluded.organizations,
                    source_url = excluded.source_url,
                    status = excluded.status,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    str(source_path),
                    file_hash,
                    title,
                    summary,
                    json.dumps(tags, ensure_ascii=False),
                    category,
                    json.dumps(authors or [], ensure_ascii=False),
                    json.dumps(dates or [], ensure_ascii=False),
                    json.dumps(people or [], ensure_ascii=False),
                    json.dumps(organizations or [], ensure_ascii=False),
                    source_url,
                    status,
                ),
            )
            if cursor.lastrowid:
                document_id = cursor.lastrowid
            else:
                document_id = connection.execute(
                    "SELECT id FROM documents WHERE source_path = ?",
                    (str(source_path),),
                ).fetchone()[0]

            connection.execute("DELETE FROM embeddings WHERE chunk_id IN (SELECT id FROM chunks WHERE document_id = ?)", (document_id,))
            connection.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
            connection.executemany(
                """
                INSERT INTO chunks (document_id, chunk_index, content)
                VALUES (?, ?, ?)
                """,
                [(document_id, index, chunk) for index, chunk in enumerate(chunks)],
            )
        return document_id


def get_document(database_path: Path, source_path: Path) -> Optional[DocumentRecord]:
    initialize_database(database_path)
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            """
            SELECT id, source_path, file_hash, title, summary, tags, category, authors, dates, people, organizations, source_url, status
            FROM documents
            WHERE source_path = ?
            """,
            (str(source_path),),
        ).fetchone()
    if row is None:
        return None
    return _document_from_row(row)


def get_document_by_id(database_path: Path, document_id: int) -> Optional[DocumentRecord]:
    initialize_database(database_path)
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            """
            SELECT id, source_path, file_hash, title, summary, tags, category, authors, dates, people, organizations, source_url, status
            FROM documents
            WHERE id = ?
            """,
            (document_id,),
        ).fetchone()
    if row is None:
        return None
    return _document_from_row(row)


def count_chunks(database_path: Path, document_id: int) -> int:
    initialize_database(database_path)
    with closing(sqlite3.connect(database_path)) as connection:
        return connection.execute(
            "SELECT COUNT(*) FROM chunks WHERE document_id = ?",
            (document_id,),
        ).fetchone()[0]


def list_chunks(database_path: Path, document_id: int) -> List[ChunkRecord]:
    initialize_database(database_path)
    with closing(sqlite3.connect(database_path)) as connection:
        rows = connection.execute(
            """
            SELECT id, document_id, chunk_index, content
            FROM chunks
            WHERE document_id = ?
            ORDER BY chunk_index ASC
            """,
            (document_id,),
        ).fetchall()
    return [ChunkRecord(id=row[0], document_id=row[1], chunk_index=row[2], content=row[3]) for row in rows]


def update_document_metadata(
    database_path: Path,
    document_id: int,
    title: str,
    summary: str,
    tags: List[str],
    category: str,
) -> bool:
    initialize_database(database_path)
    normalized_tags = [tag.strip() for tag in tags if tag.strip()]
    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            cursor = connection.execute(
                """
                UPDATE documents
                SET title = ?, summary = ?, tags = ?, category = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (title.strip(), summary.strip(), json.dumps(normalized_tags, ensure_ascii=False), category.strip(), document_id),
            )
        return cursor.rowcount > 0


def delete_document(database_path: Path, document_id: int) -> bool:
    initialize_database(database_path)
    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            connection.execute("PRAGMA foreign_keys = ON")
            cursor = connection.execute("DELETE FROM documents WHERE id = ?", (document_id,))
        return cursor.rowcount > 0


def upsert_chunk_embeddings(database_path: Path, chunk_embeddings: List[tuple], model: str) -> None:
    initialize_database(database_path)
    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            connection.executemany(
                """
                INSERT INTO embeddings (chunk_id, model, vector)
                VALUES (?, ?, ?)
                ON CONFLICT(chunk_id) DO UPDATE SET
                    model = excluded.model,
                    vector = excluded.vector,
                    created_at = CURRENT_TIMESTAMP
                """,
                [
                    (chunk_id, model, json.dumps(vector))
                    for chunk_id, vector in chunk_embeddings
                ],
            )


def count_embeddings(database_path: Path) -> int:
    initialize_database(database_path)
    with closing(sqlite3.connect(database_path)) as connection:
        return connection.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]


def search_documents(database_path: Path, query: str, limit: int = 5) -> List[SearchRecord]:
    initialize_database(database_path)
    normalized_query = query.strip().lower()
    if not normalized_query:
        return []

    like_query = f"%{normalized_query}%"
    with closing(sqlite3.connect(database_path)) as connection:
        rows = connection.execute(
            """
            SELECT
                d.id,
                d.source_path,
                d.file_hash,
                d.title,
                d.summary,
                d.tags,
                d.category,
                d.authors,
                d.dates,
                d.people,
                d.organizations,
                d.source_url,
                c.chunk_index,
                c.content,
                (
                    CASE WHEN lower(COALESCE(d.title, '')) LIKE ? THEN 5 ELSE 0 END +
                    CASE WHEN lower(COALESCE(d.tags, '')) LIKE ? THEN 4 ELSE 0 END +
                    CASE WHEN lower(COALESCE(d.category, '')) LIKE ? THEN 3 ELSE 0 END +
                    CASE WHEN lower(COALESCE(d.summary, '')) LIKE ? THEN 2 ELSE 0 END +
                    CASE WHEN lower(COALESCE(c.content, '')) LIKE ? THEN 1 ELSE 0 END
                ) AS score
            FROM documents d
            JOIN chunks c ON c.document_id = d.id
            WHERE
                lower(COALESCE(d.title, '')) LIKE ? OR
                lower(COALESCE(d.tags, '')) LIKE ? OR
                lower(COALESCE(d.category, '')) LIKE ? OR
                lower(COALESCE(d.summary, '')) LIKE ? OR
                lower(COALESCE(c.content, '')) LIKE ?
            ORDER BY score DESC, d.updated_at DESC, c.chunk_index ASC
            LIMIT ?
            """,
            (
                like_query,
                like_query,
                like_query,
                like_query,
                like_query,
                like_query,
                like_query,
                like_query,
                like_query,
                like_query,
                limit,
            ),
        ).fetchall()

    return [_search_from_row(row, score=row[14]) for row in rows]


def search_documents_advanced(
    database_path: Path,
    query: str,
    limit: int = 5,
    category: str = "",
    tag: str = "",
    person: str = "",
    date_from: str = "",
    date_to: str = "",
) -> List[SearchRecord]:
    records = search_documents(database_path, query, limit=max(limit * 5, 50))
    return apply_search_filters(
        records,
        category=category,
        tag=tag,
        person=person,
        date_from=date_from,
        date_to=date_to,
    )[:limit]


def search_embeddings(database_path: Path, query_embedding: List[float], limit: int = 5) -> List[SearchRecord]:
    initialize_database(database_path)
    if not query_embedding:
        return []

    with closing(sqlite3.connect(database_path)) as connection:
        rows = connection.execute(
            """
            SELECT
                d.id,
                d.source_path,
                d.file_hash,
                d.title,
                d.summary,
                d.tags,
                d.category,
                d.authors,
                d.dates,
                d.people,
                d.organizations,
                d.source_url,
                c.chunk_index,
                c.content,
                e.vector
            FROM embeddings e
            JOIN chunks c ON c.id = e.chunk_id
            JOIN documents d ON d.id = c.document_id
            """
        ).fetchall()

    scored_records = []
    for row in rows:
        try:
            vector = json.loads(row[14] or "[]")
        except json.JSONDecodeError:
            continue
        score = cosine_similarity(query_embedding, vector)
        scored_records.append(_search_from_row(row, score=score))

    return sorted(scored_records, key=lambda record: record.score, reverse=True)[:limit]


def apply_search_filters(
    records: List[SearchRecord],
    category: str = "",
    tag: str = "",
    person: str = "",
    date_from: str = "",
    date_to: str = "",
) -> List[SearchRecord]:
    normalized_category = category.strip().lower()
    normalized_tag = tag.strip().lower()
    normalized_person = person.strip().lower()
    filtered = []
    for record in records:
        if normalized_category and normalized_category not in (record.category or "").lower():
            continue
        if normalized_tag and not any(normalized_tag in item.lower() for item in record.tags):
            continue
        if normalized_person:
            people_values = [item.lower() for item in (record.people or [])]
            if not any(normalized_person in item for item in people_values):
                continue
        if date_from or date_to:
            if not matches_date_range(record.dates, date_from=date_from, date_to=date_to):
                continue
        filtered.append(record)
    return filtered


def matches_date_range(dates: List[str], date_from: str = "", date_to: str = "") -> bool:
    if not dates:
        return False
    normalized_dates = sorted(normalize_date_value(item) for item in dates if normalize_date_value(item))
    if not normalized_dates:
        return False
    start = normalize_date_value(date_from)
    end = normalize_date_value(date_to)
    for value in normalized_dates:
        if start and value < start:
            continue
        if end and value > end:
            continue
        return True
    return False


def normalize_date_value(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    normalized = (
        value.replace("年", "-")
        .replace("月", "-")
        .replace("日", "")
        .replace("/", "-")
        .replace(".", "-")
    )
    parts = [part for part in normalized.split("-") if part]
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return ""
    year, month, day = parts
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def list_documents(database_path: Path, limit: int = 20) -> List[DocumentRecord]:
    initialize_database(database_path)
    with closing(sqlite3.connect(database_path)) as connection:
        rows = connection.execute(
            """
            SELECT id, source_path, file_hash, title, summary, tags, category, authors, dates, people, organizations, source_url, status
            FROM documents
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [_document_from_row(row) for row in rows]


def create_chat_session(database_path: Path, title: str) -> int:
    initialize_database(database_path)
    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            cursor = connection.execute(
                """
                INSERT INTO chat_sessions (title, updated_at)
                VALUES (?, CURRENT_TIMESTAMP)
                """,
                (title.strip() or "新对话",),
            )
        return cursor.lastrowid


def rename_chat_session(database_path: Path, session_id: int, title: str) -> bool:
    initialize_database(database_path)
    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            cursor = connection.execute(
                """
                UPDATE chat_sessions
                SET title = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (title.strip() or "新对话", session_id),
            )
        return cursor.rowcount > 0


def delete_chat_session(database_path: Path, session_id: int) -> bool:
    initialize_database(database_path)
    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            cursor = connection.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
        return cursor.rowcount > 0


def get_chat_session(database_path: Path, session_id: int) -> Optional[ChatSessionRecord]:
    initialize_database(database_path)
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            """
            SELECT id, title, created_at, updated_at
            FROM chat_sessions
            WHERE id = ?
            """,
            (session_id,),
        ).fetchone()
    if row is None:
        return None
    return ChatSessionRecord(id=row[0], title=row[1], created_at=row[2], updated_at=row[3])


def list_chat_sessions(database_path: Path, limit: int = 20) -> List[ChatSessionRecord]:
    initialize_database(database_path)
    with closing(sqlite3.connect(database_path)) as connection:
        rows = connection.execute(
            """
            SELECT id, title, created_at, updated_at
            FROM chat_sessions
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [ChatSessionRecord(id=row[0], title=row[1], created_at=row[2], updated_at=row[3]) for row in rows]


def create_or_update_chat_session(database_path: Path, session_id: Optional[int], title: str) -> int:
    if session_id:
        existing = get_chat_session(database_path, session_id)
        if existing:
            if existing.title in {"新对话", "Untitled"}:
                rename_chat_session(database_path, session_id, title)
            return session_id
    return create_chat_session(database_path, title)


def add_chat_message(
    database_path: Path,
    session_id: int,
    role: str,
    content: str,
    sources: Optional[List[str]] = None,
    style: str = "",
) -> int:
    initialize_database(database_path)
    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            cursor = connection.execute(
                """
                INSERT INTO chat_messages (session_id, role, content, sources, style)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    role,
                    content,
                    json.dumps(sources or [], ensure_ascii=False),
                    style,
                ),
            )
            connection.execute(
                "UPDATE chat_sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (session_id,),
            )
        return cursor.lastrowid


def list_chat_messages(database_path: Path, session_id: int, limit: int = 100) -> List[ChatMessageRecord]:
    initialize_database(database_path)
    with closing(sqlite3.connect(database_path)) as connection:
        rows = connection.execute(
            """
            SELECT id, session_id, role, content, sources, style, created_at
            FROM chat_messages
            WHERE session_id = ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()
    return [
        ChatMessageRecord(
            id=row[0],
            session_id=row[1],
            role=row[2],
            content=row[3],
            sources=json.loads(row[4] or "[]"),
            style=row[5] or "",
            created_at=row[6],
        )
        for row in rows
    ]


def get_latest_assistant_message(database_path: Path, session_id: int) -> Optional[ChatMessageRecord]:
    initialize_database(database_path)
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            """
            SELECT id, session_id, role, content, sources, style, created_at
            FROM chat_messages
            WHERE session_id = ? AND role = 'assistant'
            ORDER BY id DESC
            LIMIT 1
            """,
            (session_id,),
        ).fetchone()
    if row is None:
        return None
    return ChatMessageRecord(
        id=row[0],
        session_id=row[1],
        role=row[2],
        content=row[3],
        sources=json.loads(row[4] or "[]"),
        style=row[5] or "",
        created_at=row[6],
    )


def _document_from_row(row) -> DocumentRecord:
    return DocumentRecord(
        id=row[0],
        source_path=row[1],
        file_hash=row[2] or "",
        title=row[3] or "",
        summary=row[4] or "",
        tags=json.loads(row[5] or "[]"),
        category=row[6] or "",
        authors=json.loads(row[7] or "[]"),
        dates=json.loads(row[8] or "[]"),
        people=json.loads(row[9] or "[]"),
        organizations=json.loads(row[10] or "[]"),
        source_url=row[11] or "",
        status=row[12] or "",
    )


def _search_from_row(row, score: float) -> SearchRecord:
    return SearchRecord(
        document_id=row[0],
        source_path=row[1],
        title=row[3] or "",
        summary=row[4] or "",
        tags=json.loads(row[5] or "[]"),
        category=row[6] or "",
        authors=json.loads(row[7] or "[]"),
        dates=json.loads(row[8] or "[]"),
        people=json.loads(row[9] or "[]"),
        organizations=json.loads(row[10] or "[]"),
        source_url=row[11] or "",
        chunk_index=row[12],
        content=row[13] or "",
        score=float(score or 0),
    )


def get_dashboard_stats(database_path: Path, recent_limit: int = 5) -> dict:
    initialize_database(database_path)
    with closing(sqlite3.connect(database_path)) as connection:
        document_count = connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        chunk_count = connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        embedding_count = connection.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
        tag_rows = connection.execute("SELECT tags FROM documents").fetchall()
        recent_rows = connection.execute(
            """
            SELECT id, source_path, file_hash, title, summary, tags, category, authors, dates, people, organizations, source_url, status
            FROM documents
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (recent_limit,),
        ).fetchall()

    tags = set()
    for row in tag_rows:
        try:
            tags.update(json.loads(row[0] or "[]"))
        except json.JSONDecodeError:
            continue

    return {
        "document_count": document_count,
        "chunk_count": chunk_count,
        "embedding_count": embedding_count,
        "tag_count": len(tags),
        "recent_documents": [_document_from_row(row) for row in recent_rows],
    }


def list_document_overviews(database_path: Path, limit: int = 100) -> List[dict]:
    initialize_database(database_path)
    with closing(sqlite3.connect(database_path)) as connection:
        rows = connection.execute(
            """
            SELECT
                d.id,
                d.source_path,
                d.file_hash,
                d.title,
                d.summary,
                d.tags,
                d.category,
                d.authors,
                d.dates,
                d.people,
                d.organizations,
                d.source_url,
                d.status,
                d.updated_at,
                COUNT(DISTINCT c.id) AS chunk_count,
                COUNT(DISTINCT e.id) AS embedding_count
            FROM documents d
            LEFT JOIN chunks c ON c.document_id = d.id
            LEFT JOIN embeddings e ON e.chunk_id = c.id
            GROUP BY d.id
            ORDER BY d.updated_at DESC, d.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [
        {
            "id": row[0],
            "source_path": row[1],
            "file_hash": row[2] or "",
            "title": row[3] or "",
            "summary": row[4] or "",
            "tags": json.loads(row[5] or "[]"),
            "category": row[6] or "",
            "authors": json.loads(row[7] or "[]"),
            "dates": json.loads(row[8] or "[]"),
            "people": json.loads(row[9] or "[]"),
            "organizations": json.loads(row[10] or "[]"),
            "source_url": row[11] or "",
            "status": row[12] or "",
            "updated_at": row[13] or "",
            "chunk_count": row[14],
            "embedding_count": row[15],
        }
        for row in rows
    ]


def list_similar_documents(database_path: Path, document_id: int, limit: int = 5) -> List[dict]:
    target = get_document_by_id(database_path, document_id)
    if target is None:
        return []
    documents = list_document_overviews(database_path, limit=500)
    scored = []
    for document in documents:
        if document["id"] == document_id:
            continue
        score = similarity_score(target, document)
        if score <= 0:
            continue
        enriched = dict(document)
        enriched["similarity_score"] = score
        scored.append(enriched)
    scored.sort(key=lambda item: (-item["similarity_score"], item["title"], item["id"]))
    return scored[:limit]


def similarity_score(target: DocumentRecord, candidate: dict) -> int:
    score = 0
    candidate_category = candidate.get("category") or ""
    if target.category and candidate_category and target.category == candidate_category:
        score += 4

    target_tags = set(target.tags)
    candidate_tags = set(candidate.get("tags") or [])
    score += len(target_tags & candidate_tags) * 3

    target_tokens = extract_similarity_tokens(f"{target.title} {target.summary}")
    candidate_tokens = extract_similarity_tokens(f"{candidate.get('title', '')} {candidate.get('summary', '')}")
    score += min(4, len(target_tokens & candidate_tokens))
    return score


def extract_similarity_tokens(text: str) -> set[str]:
    return {
        token
        for token in json.loads(json.dumps(re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}|[\u4e00-\u9fff]{2,}", text.lower())))
        if token
    }


def ensure_document_columns(database_path: Path) -> None:
    with closing(sqlite3.connect(database_path)) as connection:
        rows = connection.execute("PRAGMA table_info(documents)").fetchall()
        column_names = {row[1] for row in rows}
        additions = {
            "file_hash": "TEXT",
            "authors": "TEXT",
            "dates": "TEXT",
            "people": "TEXT",
            "organizations": "TEXT",
            "source_url": "TEXT",
        }
        with connection:
            for column_name, column_type in additions.items():
                if column_name in column_names:
                    continue
                connection.execute(f"ALTER TABLE documents ADD COLUMN {column_name} {column_type}")
                column_names.add(column_name)


def compute_file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_document_by_hash(database_path: Path, file_hash: str) -> Optional[DocumentRecord]:
    initialize_database(database_path)
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            """
            SELECT id, source_path, file_hash, title, summary, tags, category, authors, dates, people, organizations, source_url, status
            FROM documents
            WHERE file_hash = ?
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (file_hash,),
        ).fetchone()
    if row is None:
        return None
    return _document_from_row(row)


def list_potential_duplicates(database_path: Path, document_id: int, limit: int = 5) -> List[dict]:
    target = get_document_by_id(database_path, document_id)
    if target is None:
        return []
    documents = list_document_overviews(database_path, limit=500)
    scored = []
    target_title_tokens = extract_similarity_tokens(target.title)
    target_tokens = extract_similarity_tokens(f"{target.title} {target.summary}")
    for document in documents:
        if document["id"] == document_id:
            continue
        similarity = similarity_score(target, document)
        candidate_title_tokens = extract_similarity_tokens(document.get("title", ""))
        candidate_tokens = extract_similarity_tokens(f"{document.get('title', '')} {document.get('summary', '')}")
        title_overlap = len(target_title_tokens & candidate_title_tokens)
        token_overlap = len(target_tokens & candidate_tokens)
        if similarity >= 8 or title_overlap >= 2 or token_overlap >= 4:
            enriched = dict(document)
            enriched["similarity_score"] = similarity
            enriched["duplicate_signal"] = min(100, similarity * 10 + token_overlap * 5 + title_overlap * 10)
            scored.append(enriched)
    scored.sort(key=lambda item: (-item["duplicate_signal"], -item["similarity_score"], item["title"], item["id"]))
    return scored[:limit]


def get_document_growth_stats(database_path: Path, days: int = 30) -> List[dict]:
    """获取文档增长趋势统计，按日期分组。"""
    initialize_database(database_path)
    with closing(sqlite3.connect(database_path)) as connection:
        rows = connection.execute(
            """
            SELECT
                date(created_at) as doc_date,
                COUNT(*) as doc_count
            FROM documents
            WHERE created_at >= date('now', '-' || ? || ' days')
            GROUP BY doc_date
            ORDER BY doc_date
            """,
            (days,),
        ).fetchall()
    return [
        {
            "date": row[0],
            "count": row[1],
        }
        for row in rows
    ]


def add_search_history(database_path: Path, query: str, mode: str, result_count: int) -> int:
    """添加一条搜索历史记录，返回记录的 id。"""
    initialize_database(database_path)
    with closing(sqlite3.connect(database_path)) as connection:
        cursor = connection.execute(
            """
            INSERT INTO search_history (query, mode, result_count)
            VALUES (?, ?, ?)
            """,
            (query, mode, result_count),
        )
        connection.commit()
        return cursor.lastrowid


def list_search_history(database_path: Path, limit: int = 20) -> List[dict]:
    """列出最近的搜索历史记录。"""
    initialize_database(database_path)
    with closing(sqlite3.connect(database_path)) as connection:
        rows = connection.execute(
            """
            SELECT id, query, mode, result_count, created_at
            FROM search_history
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "id": row[0],
            "query": row[1],
            "mode": row[2],
            "result_count": row[3],
            "created_at": row[4],
        }
        for row in rows
    ]
