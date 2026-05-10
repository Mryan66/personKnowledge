import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.config import Settings
from app.ingest.pipeline import ingest_file
from app.memory.database import get_document_by_id, list_chunks, list_document_overviews
from app.web.knowledge import (
    build_snippet,
    format_character_hint,
    normalize_preview_mode,
    render_document_preview,
    render_chunk_items,
    render_category_filters,
    render_document_detail_panel,
    render_document_rows,
    render_document_status,
    render_embedding_status,
    render_knowledge,
    render_metadata_facts,
    render_message_panel,
    render_preview_toolbar,
    render_similar_documents,
    render_tag_cloud,
)


class KnowledgeWebTests(unittest.TestCase):
    def test_list_document_overviews_includes_counts(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            note = root / "note.md"
            note.write_text("# Knowledge 页面\n\nAgent 知识库浏览。", encoding="utf-8")
            ingest_file(note, database_path)

            overviews = list_document_overviews(database_path)

        self.assertEqual(len(overviews), 1)
        self.assertEqual(overviews[0]["title"], "Knowledge 页面")
        self.assertEqual(overviews[0]["chunk_count"], 1)
        self.assertEqual(overviews[0]["embedding_count"], 0)

    def test_render_document_rows_empty_state(self):
        html = render_document_rows([])

        self.assertIn("暂无入库文档", html)

    def test_render_document_rows_include_detail_link(self):
        html = render_document_rows(
            [
                {
                    "id": 3,
                    "title": "测试文档",
                    "source_path": "/tmp/test.md",
                    "category": "notes",
                    "tags": ["rag"],
                    "summary": "摘要",
                    "chunk_count": 1,
                    "embedding_count": 0,
                    "status": "ingested",
                    "updated_at": "2026-05-06",
                }
            ]
        )

        self.assertIn('/knowledge?document_id=3#document-detail-panel', html)
        self.assertIn('data-detail-link="1"', html)
        self.assertIn('name="selected_document_id"', html)

    def test_render_document_status(self):
        self.assertIn("status-ok", render_document_status({"status": "ingested"}))
        self.assertIn("duplicate", render_document_status({"status": "duplicate"}))
        self.assertIn("similar", render_document_status({"status": "similar"}))

    def test_render_metadata_facts(self):
        document = get_document_by_id_for_test(
            authors=["张三"],
            dates=["2026-05-10"],
            people=["李四"],
            organizations=["OpenAI"],
            source_url="https://example.com",
        )

        html = render_metadata_facts(document)

        self.assertIn("张三", html)
        self.assertIn("2026-05-10", html)
        self.assertIn("李四", html)
        self.assertIn("OpenAI", html)
        self.assertIn("https://example.com", html)

    def test_render_embedding_status(self):
        self.assertIn("status-ok", render_embedding_status(2, 2))
        self.assertIn("status-warn", render_embedding_status(2, 0))

    def test_render_category_and_tag_cloud(self):
        documents = [
            {"category": "rag", "tags": ["rag", "agent"]},
            {"category": "rag", "tags": ["rag"]},
        ]

        self.assertIn("rag", render_category_filters(documents))
        self.assertIn("agent", render_tag_cloud(documents))

    def test_build_snippet_truncates(self):
        self.assertEqual(build_snippet("a" * 20, max_length=10), "aaaaaaaaa…")

    def test_render_message_panel(self):
        html = render_message_panel("已更新")

        self.assertIn("已更新", html)

    def test_render_document_detail_panel(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            note = root / "note.md"
            note.write_text("# 知识详情\n\n用于查看 chunk。", encoding="utf-8")
            result = ingest_file(note, database_path)
            document = get_document_by_id(database_path, result.document_id)
            chunks = list_chunks(database_path, result.document_id)

            html = render_document_detail_panel(document, chunks, [], "<p>preview</p>", "rendered", None)

        self.assertIn("文档详情", html)
        self.assertIn("文档预览", html)
        self.assertIn("preview", html)
        self.assertIn("渲染预览", html)
        self.assertIn("Chunk #0", html)
        self.assertIn("保存元数据", html)
        self.assertIn("重新导入", html)
        self.assertIn("删除文档", html)
        self.assertIn('id="document-detail-panel"', html)

    def test_render_document_detail_panel_includes_structured_metadata(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            note = root / "note.md"
            note.write_text(
                "# 知识详情\n\n作者：张三\n日期：2026-05-10\n人物：李四\n公司：OpenAI\n链接：https://example.com\n",
                encoding="utf-8",
            )
            result = ingest_file(note, database_path)
            document = get_document_by_id(database_path, result.document_id)
            chunks = list_chunks(database_path, result.document_id)

            html = render_document_detail_panel(document, chunks, [], "<p>preview</p>", "rendered", None)

        self.assertIn("张三", html)
        self.assertIn("2026-05-10", html)
        self.assertIn("李四", html)
        self.assertIn("OpenAI", html)
        self.assertIn("https://example.com", html)


def get_document_by_id_for_test(
    authors=None,
    dates=None,
    people=None,
    organizations=None,
    source_url="",
):
    class FakeDocument:
        pass

    document = FakeDocument()
    document.id = 1
    document.source_path = "/tmp/test.md"
    document.title = "测试"
    document.summary = "摘要"
    document.tags = ["rag"]
    document.category = "notes"
    document.status = "ingested"
    document.authors = authors or []
    document.dates = dates or []
    document.people = people or []
    document.organizations = organizations or []
    document.source_url = source_url
    return document

    def test_render_chunk_items_empty_state(self):
        html = render_chunk_items([])

        self.assertIn("暂无 chunk", html)

    def test_render_similar_documents(self):
        html = render_similar_documents(
            [
                {
                    "id": 2,
                    "title": "相似文档",
                    "summary": "相关摘要",
                    "category": "rag",
                    "similarity_score": 8,
                }
            ]
        )

        self.assertIn("相似文档", html)
        self.assertIn("score 8", html)

    def test_render_document_preview_for_markdown(self):
        html = render_document_preview(
            Path("note.md"),
            "# 标题\n\n正文段落\n\n- 第一项\n- 第二项\n\n```python\nprint('hi')\n```",
        )

        self.assertIn("<h2>标题</h2>", html)
        self.assertIn("<p>正文段落</p>", html)
        self.assertIn("<li>第一项</li>", html)
        self.assertIn("print", html)

    def test_render_preview_toolbar(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            note = root / "note.md"
            note.write_text("# Fixture\n\npreview", encoding="utf-8")
            result = ingest_file(note, database_path)
            document = get_document_by_id(database_path, result.document_id)

            html = render_preview_toolbar(document, "raw")

        self.assertIn("原始文本", html)
        self.assertIn("preview=raw", html)
        self.assertIn("preview=rendered", html)
        self.assertIn(".md", html)

    def test_normalize_preview_mode(self):
        self.assertEqual(normalize_preview_mode("raw"), "raw")
        self.assertEqual(normalize_preview_mode("weird"), "rendered")

    def test_format_character_hint(self):
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "note.md"
            path.write_text("hello", encoding="utf-8")

            hint = format_character_hint(path)

        self.assertIn("B", hint)

    def test_render_document_detail_panel_includes_similar_documents(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            first = root / "first.md"
            second = root / "second.md"
            first.write_text("# RAG 一\n\nAgent memory 总结。", encoding="utf-8")
            second.write_text("# RAG 二\n\nAgent memory 实践。", encoding="utf-8")
            first_result = ingest_file(first, database_path)
            second_result = ingest_file(second, database_path)
            document = get_document_by_id(database_path, first_result.document_id)
            chunks = list_chunks(database_path, first_result.document_id)

            html = render_document_detail_panel(
                document,
                chunks,
                [{"id": second_result.document_id, "title": "RAG 二", "summary": "Agent memory 实践。", "category": "agent", "similarity_score": 6}],
                "<p>preview</p>",
                "rendered",
                None,
            )

        self.assertIn("相似文档", html)
        self.assertIn("score 6", html)

    def test_render_knowledge_page_includes_documents(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            note = root / "note.md"
            note.write_text("# 知识库测试\n\n用于页面渲染。", encoding="utf-8")
            ingest_file(note, database_path)
            template_path = root / "knowledge.html"
            template_path.write_text(
                "{{ app_name }} {{ document_count }} {{ chunk_count }} {{ embedding_count }} {{ tag_count }} "
                "{{ limit }} {{ document_rows }} {{ category_filters }} {{ tag_cloud }} {{ message_panel }} {{ document_detail_panel }}",
                encoding="utf-8",
            )
            settings = Settings(workspace_dir=root, database_path=database_path)
            document = get_document_by_id(database_path, 1)
            chunks = list_chunks(database_path, 1)

            html = render_knowledge(
                settings,
                template_path,
                selected_document=document,
                chunks=chunks,
                similar_documents=[{"id": 2, "title": "相似", "summary": "摘要", "category": "rag", "similarity_score": 5}],
                preview_html="<p>preview</p>",
                preview_mode="raw",
                selected_chunk=0,
                message="done",
            )

        self.assertIn("Personal AI Knowledge Butler", html)
        self.assertIn("知识库测试", html)
        self.assertIn("0/1", html)
        self.assertIn("done", html)
        self.assertIn("文档详情", html)
        self.assertIn("文档预览", html)
        self.assertIn("相似文档", html)
        self.assertIn("原始文本", html)
        self.assertIn("chunk-card-active", html)


if __name__ == "__main__":
    unittest.main()
