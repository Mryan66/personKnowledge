from pathlib import Path
from typing import List, Optional

from app.memory.database import list_chunks, upsert_chunk_embeddings
from app.tools.openai_client import OpenAIClient


class EmbeddingTool:
    def __init__(self, client: OpenAIClient, model: str):
        self.client = client
        self.model = model

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        return self.client.create_embeddings(texts, model=self.model)

    def embed_document_chunks(self, database_path: Path, document_id: int) -> int:
        chunks = list_chunks(database_path, document_id)
        vectors = self.embed_texts([chunk.content for chunk in chunks])
        upsert_chunk_embeddings(
            database_path,
            [(chunk.id, vector) for chunk, vector in zip(chunks, vectors)],
            model=self.model,
        )
        return len(vectors)
