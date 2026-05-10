import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.ingest.pipeline import ingest_file
from app.memory.database import count_embeddings, search_embeddings
from app.tools.embedding_tool import EmbeddingTool
from app.tools.search_tool import SearchTool
from app.tools.vector_tool import cosine_similarity


class FakeEmbeddingClient:
    def __init__(self, vectors_by_text=None):
        self.vectors_by_text = vectors_by_text or {}

    def create_embeddings(self, inputs, model):
        return [self.vectors_by_text.get(text, self.vectors_by_text.get("__query__", [1.0, 0.0])) for text in inputs]


class VectorSearchTests(unittest.TestCase):
    def test_cosine_similarity_scores_vectors(self):
        self.assertAlmostEqual(cosine_similarity([1.0, 0.0], [1.0, 0.0]), 1.0)
        self.assertAlmostEqual(cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0)
        self.assertEqual(cosine_similarity([1.0], [1.0, 2.0]), 0.0)

    def test_ingest_file_can_store_embeddings(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            note = root / "note.md"
            note.write_text("# 向量检索\n\nEmbedding 可以支持语义搜索。", encoding="utf-8")
            embedding_tool = EmbeddingTool(FakeEmbeddingClient(), model="fake-embedding")

            result = ingest_file(note, database_path, embedding_tool=embedding_tool)

            self.assertEqual(result.embedding_count, 1)
            self.assertEqual(count_embeddings(database_path), 1)

    def test_search_embeddings_orders_by_similarity(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            first = root / "first.md"
            second = root / "second.md"
            first.write_text("# 苹果\n\n水果和果园。", encoding="utf-8")
            second.write_text("# 汽车\n\n发动机和轮胎。", encoding="utf-8")
            vectors = {
                "# 苹果\n\n水果和果园。": [1.0, 0.0],
                "# 汽车\n\n发动机和轮胎。": [0.0, 1.0],
            }
            embedding_tool = EmbeddingTool(FakeEmbeddingClient(vectors), model="fake-embedding")
            ingest_file(first, database_path, embedding_tool=embedding_tool)
            ingest_file(second, database_path, embedding_tool=embedding_tool)

            results = search_embeddings(database_path, [0.9, 0.1], limit=2)

            self.assertEqual(results[0].title, "苹果")
            self.assertGreater(results[0].score, results[1].score)

    def test_search_tool_uses_vector_mode_when_embedding_tool_exists(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            note = root / "note.md"
            note.write_text("# 语义搜索\n\nEmbedding 检索。", encoding="utf-8")
            vectors = {"# 语义搜索\n\nEmbedding 检索。": [1.0, 0.0], "__query__": [1.0, 0.0]}
            embedding_tool = EmbeddingTool(FakeEmbeddingClient(vectors), model="fake-embedding")
            ingest_file(note, database_path, embedding_tool=embedding_tool)

            results = SearchTool(database_path, embedding_tool=embedding_tool).search("含义相近的问题", mode="vector")

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].mode, "vector")


if __name__ == "__main__":
    unittest.main()
