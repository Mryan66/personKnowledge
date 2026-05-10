import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.agents.query_agent import Answer
from app.config import Settings
from app.memory.database import ChatMessageRecord, ChatSessionRecord
from app.web.ask import render_answer_panel, render_ask, render_conversation_panel, render_session_history_panel


class AskWebTests(unittest.TestCase):
    def test_render_answer_panel_empty_before_question(self):
        html = render_answer_panel(None)

        self.assertEqual(html, "")

    def test_render_answer_panel_shows_answer_and_sources(self):
        answer = Answer(
            question="RAG 是什么？",
            text="RAG 是检索增强生成。",
            sources=["note.md#chunk-0"],
            confidence="high",
            mode="rag",
            style="report",
        )

        html = render_answer_panel(answer, message="done", session_id="3")

        self.assertIn("RAG 是检索增强生成", html)
        self.assertIn("note.md#chunk-0", html)
        self.assertIn("high", html)
        self.assertIn("done", html)
        self.assertIn("保存为笔记", html)

    def test_render_conversation_panel(self):
        html = render_conversation_panel(
            [
                ChatMessageRecord(1, 1, "user", "什么是 RAG？", [], "concise", "2026-05-06"),
                ChatMessageRecord(2, 1, "assistant", "RAG 是检索增强生成。", ["rag.md#chunk-0"], "concise", "2026-05-06"),
            ]
        )

        self.assertIn("多轮对话", html)
        self.assertIn("什么是 RAG", html)
        self.assertIn("RAG 是检索增强生成", html)

    def test_render_session_history_panel(self):
        html = render_session_history_panel(
            [
                ChatSessionRecord(1, "RAG 对话", "2026-05-06", "2026-05-06"),
                ChatSessionRecord(2, "Agent 对话", "2026-05-06", "2026-05-06"),
            ],
            "2",
        )

        self.assertIn("对话历史", html)
        self.assertIn("Agent 对话", html)
        self.assertIn('active-history', html)

    def test_render_ask_page_includes_form_state(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            template_path = root / "ask.html"
            template_path.write_text(
                "{{ app_name }} {{ question }} {{ limit }} {{ model }} {{ search_mode_options }} "
                "{{ search_mode_description }} {{ answer_style_options }} {{ session_id }} {{ session_options }} {{ conversation_panel }} {{ session_history_panel }} "
                "{{ use_llm_checked }} {{ use_embeddings_checked }} "
                "{{ openai_status }} {{ openai_status_class }} {{ answer_mode }} {{ answer_confidence }} {{ answer_panel }}",
                encoding="utf-8",
            )
            settings = Settings(workspace_dir=root)
            answer = Answer("Agent", "answer", [], "low", "extractive", style="balanced")

            html = render_ask(
                settings,
                template_path,
                question="Agent",
                search_mode="keyword",
                limit=2,
                use_llm=False,
                use_embeddings=True,
                answer_style="detailed",
                session_id="2",
                sessions=[ChatSessionRecord(2, "Agent 对话", "2026-05-06", "2026-05-06")],
                messages=[ChatMessageRecord(1, 2, "user", "Agent?", [], "detailed", "2026-05-06")],
                answer=answer,
            )

        self.assertIn("Personal AI Knowledge Butler", html)
        self.assertIn("Agent", html)
        self.assertIn("2", html)
        self.assertIn("Keyword", html)
        self.assertIn("checked", html)
        self.assertIn("未配置", html)
        self.assertIn("extractive", html)
        self.assertIn("详细", html)
        self.assertIn("Agent 对话", html)


if __name__ == "__main__":
    unittest.main()
