from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

from app.memory.database import SearchRecord, apply_search_filters, search_documents, search_documents_advanced, search_embeddings
from app.tools.embedding_tool import EmbeddingTool
from app.tools.openai_client import OpenAIClientError


@dataclass(frozen=True)
class SearchResult:
    source_path: str
    title: str
    summary: str
    content: str
    tags: List[str]
    category: str
    chunk_index: int
    score: float
    mode: str = "keyword"


class SearchTool:
    def __init__(self, database_path: Path, embedding_tool: Optional[EmbeddingTool] = None):
        self.database_path = database_path
        self.embedding_tool = embedding_tool

    def search(
        self,
        query: str,
        limit: int = 5,
        mode: str = "auto",
        filters: Optional[Dict[str, str]] = None,
    ) -> List[SearchResult]:
        filters = filters or {}
        if mode == "keyword":
            records = search_documents_advanced(self.database_path, query, limit=limit, **self._normalize_filters(filters))
            return [self._map_record(record, mode="keyword") for record in records]

        if mode == "vector" and self.embedding_tool:
            try:
                query_embedding = self.embedding_tool.embed_texts([query])[0]
                vector_records = search_embeddings(self.database_path, query_embedding, limit=max(limit * 5, 50))
                vector_records = apply_search_filters(vector_records, **self._normalize_filters(filters))[:limit]
                return [self._map_record(record, mode="vector") for record in vector_records]
            except (OpenAIClientError, IndexError, ValueError):
                return []

        # Auto mode: Hybrid Search
        keyword_records = []
        vector_records = []

        # Get keyword results
        try:
            keyword_records = search_documents_advanced(
                self.database_path,
                query,
                limit=max(limit * 2, 20),
                **self._normalize_filters(filters),
            )
        except Exception:
            pass

        # Get vector results if available
        if self.embedding_tool:
            try:
                query_embedding = self.embedding_tool.embed_texts([query])[0]
                vector_records = search_embeddings(self.database_path, query_embedding, limit=max(limit * 5, 50))
                vector_records = apply_search_filters(vector_records, **self._normalize_filters(filters))[: max(limit * 2, 20)]
            except (OpenAIClientError, IndexError, ValueError):
                pass

        # Merge and rerank
        merged = self._merge_and_rerank(query, keyword_records, vector_records)
        return merged[:limit]

    def _merge_and_rerank(
        self,
        query: str,
        keyword_records: List[SearchRecord],
        vector_records: List[SearchRecord],
    ) -> List[SearchResult]:
        # Normalize scores to 0-1 range
        all_records: List[SearchRecord] = []
        seen_chunks: Set[str] = set()

        # Add vector results first (higher weight)
        for record in vector_records:
            chunk_key = f"{record.document_id}:{record.chunk_index}"
            if chunk_key not in seen_chunks:
                seen_chunks.add(chunk_key)
                all_records.append(record)

        # Add keyword results, skipping duplicates
        for record in keyword_records:
            chunk_key = f"{record.document_id}:{record.chunk_index}"
            if chunk_key not in seen_chunks:
                seen_chunks.add(chunk_key)
                all_records.append(record)

        # Rerank with simple heuristic
        reranked = []
        query_lower = query.lower()

        for record in all_records:
            score = record.score

            # Boost if query appears in title
            title_lower = (record.title or "").lower()
            if query_lower in title_lower:
                score += 0.3

            # Boost if query appears in tags
            for tag in record.tags:
                if query_lower in tag.lower():
                    score += 0.2

            # Boost if category matches query
            category_lower = (record.category or "").lower()
            if query_lower in category_lower:
                score += 0.15

            # Check which source this record came from
            is_vector = any(v.document_id == record.document_id and v.chunk_index == record.chunk_index for v in vector_records)
            mode = "vector" if is_vector else "keyword"

            reranked.append((score, record, mode))

        # Sort by score descending
        reranked.sort(key=lambda x: x[0], reverse=True)

        # Map to SearchResult
        results = []
        for score, record, mode in reranked:
            results.append(self._map_record(record, mode=mode, override_score=score))

        return results

    def _normalize_filters(self, filters: Dict[str, str]) -> Dict[str, str]:
        return {
            "category": (filters.get("category") or "").strip(),
            "tag": (filters.get("tag") or "").strip(),
            "person": (filters.get("person") or "").strip(),
            "date_from": (filters.get("date_from") or "").strip(),
            "date_to": (filters.get("date_to") or "").strip(),
        }

    def _map_record(self, record, mode: str, override_score: Optional[float] = None) -> SearchResult:
        return SearchResult(
            source_path=record.source_path,
            title=record.title,
            summary=record.summary,
            content=record.content,
            tags=record.tags,
            category=record.category,
            chunk_index=record.chunk_index,
            score=override_score if override_score is not None else record.score,
            mode=mode,
        )
