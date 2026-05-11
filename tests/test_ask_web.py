import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.agents.query_agent import Answer
from app.config import Settings
from app.memory.database import ChatMessageRecord, ChatSessionRecord
from app.web.ask import (
    render_answer_panel,
    render_ask,
    render_ask_sidebar,
    render_ask_status_badge,
    render_conversation_panel,
    render_prefill_context_panel,
    render_session_history_drawer,
    render_session_history_panel,
)


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
        self.assertIn("回答已生成", html)
        self.assertIn("依据来源", html)
        self.assertIn("查看引用与操作", html)

    def test_render_answer_panel_empty_result_state(self):
        answer = Answer(
            question="没有结果",
            text="我还没有在知识库中找到相关内容。",
            sources=[],
            confidence="none",
            mode="none",
            style="balanced",
        )

        html = render_answer_panel(answer, message="no result", question="没有结果")

        self.assertIn("暂时没有足够相关的信息", html)
        self.assertIn("立即重试", html)

    def test_render_answer_panel_fallback_state_includes_source_only_action(self):
        answer = Answer(
            question="RAG 是什么？",
            text="来源摘要回答",
            sources=["note.md#chunk-0"],
            confidence="low",
            mode="fallback",
            style="balanced",
        )

        html = render_answer_panel(
            answer,
            message="fallback",
            question="RAG 是什么？",
            answer_state="model_error",
            use_llm=True,
            use_embeddings=True,
            model="gpt-test",
            answer_style="balanced",
        )

        self.assertIn("改用来源摘要", html)
        self.assertIn("gpt-test", html)

    def test_render_answer_panel_config_error_guides_to_settings(self):
        answer = Answer(
            question="配置异常",
            text="暂时无法稳定生成 AI 回答。",
            sources=[],
            confidence="none",
            mode="extractive",
            style="balanced",
        )

        html = render_answer_panel(
            answer,
            message="config error",
            question="配置异常",
            answer_state="config_error",
            use_llm=False,
        )

        self.assertIn("检查设置", html)

    def test_render_conversation_panel(self):
        html = render_conversation_panel(
            [
                ChatMessageRecord(1, 1, "user", "什么是 RAG？", [], "concise", "2026-05-06"),
                ChatMessageRecord(2, 1, "assistant", "RAG 是检索增强生成。", ["rag.md#chunk-0"], "concise", "2026-05-06"),
            ]
        )

        self.assertIn("聊天记录", html)
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

        self.assertIn("最近会话", html)
        self.assertIn("Agent 对话", html)
        self.assertIn('active-history', html)

    def test_render_session_history_drawer(self):
        html = render_session_history_drawer(
            [
                ChatSessionRecord(1, "RAG 对话", "2026-05-06", "2026-05-06"),
                ChatSessionRecord(2, "Agent 对话", "2026-05-06", "2026-05-06"),
            ],
            "2",
        )

        self.assertIn("历史会话", html)
        self.assertIn("Agent 对话", html)

    def test_render_ask_status_badge(self):
        badge = render_ask_status_badge(None, "idle")

        self.assertIn("直接提问", badge)

    def test_render_ask_sidebar(self):
        html = render_ask_sidebar(
            sessions=[ChatSessionRecord(2, "Agent 对话", "2026-05-06", "2026-05-06")],
            selected_session_id="2",
            answer=None,
            answer_state="idle",
            prefill_context="当前问题将围绕《Agent 笔记》展开",
            openai_ready=False,
        )

        self.assertEqual("", html)

    def test_render_prefill_context_panel(self):
        html = render_prefill_context_panel("当前问题将围绕《RAG 搜索》展开")

        self.assertIn("已带入搜索上下文", html)
        self.assertIn("RAG 搜索", html)

    def test_render_ask_page_includes_form_state(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            template_path = root / "ask.html"
            template_path.write_text(
                "{{ app_name }} {{ question }} {{ limit }} {{ model }} {{ search_mode_options }} "
                "{{ search_mode_description }} {{ answer_style_options }} {{ session_id }} {{ session_options }} {{ ask_status_badge }} {{ prefill_context_panel }} {{ conversation_panel }} {{ session_history_drawer }} {{ ask_sidebar }} "
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
                prefill_context="当前问题将围绕《Agent 笔记》展开",
            )

        self.assertIn("Personal AI Knowledge Butler", html)
        self.assertIn("Agent", html)
        self.assertIn("2", html)
        self.assertIn("关键词搜索", html)
        self.assertIn("checked", html)
        self.assertIn("未配置", html)
        self.assertIn("extractive", html)
        self.assertIn("详细", html)
        self.assertIn("Agent 对话", html)
        self.assertIn("Agent 笔记", html)
        self.assertIn("来源摘要", html)
        self.assertIn("历史会话", html)


if __name__ == "__main__":
    unittest.main()
