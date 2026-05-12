from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from app.tools.citation_tool import format_source
from app.tools.openai_client import OpenAIClient, OpenAIClientError
from app.tools.embedding_tool import EmbeddingTool
from app.tools.search_tool import SearchResult, SearchTool


@dataclass(frozen=True)
class Citation:
    source: str
    title: str
    snippet: str
    chunk_index: int


@dataclass(frozen=True)
class Answer:
    question: str
    text: str
    sources: List[str]
    confidence: str
    mode: str = "extractive"
    style: str = "balanced"
    citations: List[Citation] = field(default_factory=list)


def build_snippet(content: str, max_length: int = 220) -> str:
    normalized = " ".join(content.split())
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 1].rstrip() + "…"


def build_rag_input(question: str, results: List[SearchResult], history: Optional[List[dict]] = None, style: str = "balanced") -> str:
    sections = [f"用户问题：{question}", "", "可用知识库片段："]
    if history:
        sections = [f"回答风格：{style}", "", "最近对话："]
        for item in history[-6:]:
            role = "用户" if item.get("role") == "user" else "助手"
            sections.append(f"{role}：{item.get('content', '')}")
        sections.extend(["", f"当前问题：{question}", "", "可用知识库片段："])
    for index, result in enumerate(results, start=1):
        source = format_source(result.source_path, result.chunk_index)
        sections.append(f"[{index}] 标题：{result.title}")
        sections.append(f"来源：{source}")
        sections.append(f"分类：{result.category or 'uncategorized'}")
        sections.append(f"标签：{', '.join(result.tags) if result.tags else '无'}")
        sections.append(f"内容：{result.content}")
        sections.append("")
    return "\n".join(sections).strip()


RAG_INSTRUCTIONS = """你是个人 AI 知识管家的问答 Agent。请只基于提供的知识库片段回答用户问题。
要求：
1. 用中文回答，除非用户问题明确要求其他语言。
2. 先给出简洁结论，再列出依据。
3. 每条关键结论都要引用来源，来源格式必须使用片段中的“来源”字段。
4. 如果资料不足，请明确说“不足以确认”，不要编造。
5. 最后给出 1-3 个可执行的下一步建议。"""

GENERAL_INSTRUCTIONS = """你是个人 AI 知识管家的通用问答 Agent。
要求：
1. 用中文回答，除非用户问题明确要求其他语言。
2. 先明确说明当前没有在知识库中检索到直接相关内容，下面的回答基于通用模型知识。
3. 回答要尽量有帮助，但不要伪造“知识库来源”或引用不存在的材料。
4. 如果问题存在时效性、不确定性或需要外部事实校验，要明确提示用户。
5. 最后给出 1-3 个建议，说明可以补充哪些资料到知识库以获得更可靠的回答。"""

STYLE_HINTS = {
    "concise": "回答尽量简洁，先结论后 2-4 个要点。",
    "balanced": "回答兼顾简洁与解释，适合一般问答。",
    "detailed": "回答更详细，适当展开背景、依据和差异点。",
    "report": "以小报告形式组织回答，包含结论、依据、建议三个部分。",
}


class QueryAgent:
    def __init__(
        self,
        database_path: Path,
        default_limit: int = 3,
        openai_client: Optional[OpenAIClient] = None,
        use_llm: bool = False,
        embedding_tool: Optional[EmbeddingTool] = None,
        search_mode: str = "auto",
        answer_style: str = "balanced",
    ):
        self.search_tool = SearchTool(database_path, embedding_tool=embedding_tool)
        self.default_limit = default_limit
        self.openai_client = openai_client
        self.use_llm = use_llm
        self.search_mode = search_mode
        self.answer_style = answer_style

    def answer(self, question: str, limit: Optional[int] = None, history: Optional[List[dict]] = None) -> Answer:
        result_limit = limit or self.default_limit
        results = self.search_tool.search(question, limit=result_limit, mode=self.search_mode)
        if not results:
            if self.use_llm and self.openai_client:
                try:
                    return self._generate_general_answer(question, history=history)
                except OpenAIClientError as error:
                    return Answer(
                        question=question,
                        text=(
                            "我还没有在知识库中找到相关内容。"
                            f"同时，通用 AI 回答生成失败：{error}。可以先导入更多资料，或换一个关键词提问。"
                        ),
                        sources=[],
                        confidence="none",
                        mode="none",
                        style=self.answer_style,
                    )
            return Answer(
                question=question,
                text="我还没有在知识库中找到相关内容。可以先导入更多资料，或换一个关键词提问。",
                sources=[],
                confidence="none",
                mode="none",
                style=self.answer_style,
            )

        if self.use_llm and self.openai_client:
            try:
                return self._generate_rag_answer(question, results, history=history)
            except OpenAIClientError as error:
                fallback = self._generate_extractive_answer(question, results)
                return Answer(
                    question=question,
                    text=f"OpenAI RAG 生成失败，已回退到来源型回答。错误：{error}\n\n{fallback.text}",
                    sources=fallback.sources,
                    confidence=fallback.confidence,
                    mode="fallback",
                    style=self.answer_style,
                    citations=fallback.citations,
                )

        return self._generate_extractive_answer(question, results)

    def stream_answer(
        self,
        question: str,
        on_delta: Callable[[Answer], None],
        limit: Optional[int] = None,
        history: Optional[List[dict]] = None,
    ) -> Answer:
        result_limit = limit or self.default_limit
        results = self.search_tool.search(question, limit=result_limit, mode=self.search_mode)
        if not results:
            if self.use_llm and self.openai_client:
                try:
                    return self._stream_general_answer(question, on_delta=on_delta, history=history)
                except OpenAIClientError as error:
                    return Answer(
                        question=question,
                        text=(
                            "我还没有在知识库中找到相关内容。"
                            f"同时，通用 AI 回答生成失败：{error}。可以先导入更多资料，或换一个关键词提问。"
                        ),
                        sources=[],
                        confidence="none",
                        mode="none",
                        style=self.answer_style,
                    )
            return Answer(
                question=question,
                text="我还没有在知识库中找到相关内容。可以先导入更多资料，或换一个关键词提问。",
                sources=[],
                confidence="none",
                mode="none",
                style=self.answer_style,
            )

        if self.use_llm and self.openai_client:
            try:
                return self._stream_rag_answer(question, results, on_delta=on_delta, history=history)
            except OpenAIClientError as error:
                fallback = self._generate_extractive_answer(question, results)
                return Answer(
                    question=question,
                    text=f"OpenAI RAG 生成失败，已回退到来源型回答。错误：{error}\n\n{fallback.text}",
                    sources=fallback.sources,
                    confidence=fallback.confidence,
                    mode="fallback",
                    style=self.answer_style,
                    citations=fallback.citations,
                )

        return self._generate_extractive_answer(question, results)

    def _generate_rag_answer(self, question: str, results: List[SearchResult], history: Optional[List[dict]] = None) -> Answer:
        response = self.openai_client.generate_text(
            instructions=build_rag_instructions(self.answer_style),
            input_text=build_rag_input(question, results, history=history, style=self.answer_style),
        )
        return Answer(
            question=question,
            text=response.text,
            sources=self._collect_sources(results),
            confidence=self._estimate_confidence(results),
            mode="rag",
            style=self.answer_style,
            citations=self._build_citations(results),
        )

    def _stream_rag_answer(
        self,
        question: str,
        results: List[SearchResult],
        on_delta: Callable[[Answer], None],
        history: Optional[List[dict]] = None,
    ) -> Answer:
        chunks = []
        citations = self._build_citations(results)
        for delta in self.openai_client.generate_text_stream(
            instructions=build_rag_instructions(self.answer_style),
            input_text=build_rag_input(question, results, history=history, style=self.answer_style),
        ):
            chunks.append(delta)
            on_delta(
                Answer(
                    question=question,
                    text="".join(chunks),
                    sources=self._collect_sources(results),
                    confidence=self._estimate_confidence(results),
                    mode="rag",
                    style=self.answer_style,
                    citations=[],
                )
            )
        return Answer(
            question=question,
            text="".join(chunks),
            sources=self._collect_sources(results),
            confidence=self._estimate_confidence(results),
            mode="rag",
            style=self.answer_style,
            citations=citations,
        )

    def _generate_general_answer(self, question: str, history: Optional[List[dict]] = None) -> Answer:
        response = self.openai_client.generate_text(
            instructions=build_general_instructions(self.answer_style),
            input_text=build_general_input(question, history=history, style=self.answer_style),
        )
        return Answer(
            question=question,
            text=response.text,
            sources=[],
            confidence="low",
            mode="general",
            style=self.answer_style,
        )

    def _stream_general_answer(
        self,
        question: str,
        on_delta: Callable[[Answer], None],
        history: Optional[List[dict]] = None,
    ) -> Answer:
        chunks = []
        for delta in self.openai_client.generate_text_stream(
            instructions=build_general_instructions(self.answer_style),
            input_text=build_general_input(question, history=history, style=self.answer_style),
        ):
            chunks.append(delta)
            on_delta(
                Answer(
                    question=question,
                    text="".join(chunks),
                    sources=[],
                    confidence="low",
                    mode="general",
                    style=self.answer_style,
                )
            )
        return Answer(
            question=question,
            text="".join(chunks),
            sources=[],
            confidence="low",
            mode="general",
            style=self.answer_style,
        )

    def _generate_extractive_answer(self, question: str, results: List[SearchResult]) -> Answer:
        lines = build_extractive_lines(results, self.answer_style)

        return Answer(
            question=question,
            text="\n".join(lines),
            sources=self._collect_sources(results),
            confidence=self._estimate_confidence(results),
            mode="extractive",
            style=self.answer_style,
            citations=self._build_citations(results),
        )

    def _collect_sources(self, results: List[SearchResult]) -> List[str]:
        return [format_source(result.source_path, result.chunk_index) for result in results]

    def _estimate_confidence(self, results: List[SearchResult]) -> str:
        if not results:
            return "none"
        top_score = results[0].score
        if top_score >= 10:
            return "high"
        if top_score >= 5:
            return "medium"
        return "low"

    def _build_citations(self, results: List[SearchResult]) -> List[Citation]:
        citations = []
        for result in results:
            citations.append(
                Citation(
                    source=format_source(result.source_path, result.chunk_index),
                    title=result.title,
                    snippet=build_snippet(result.content, max_length=260),
                    chunk_index=result.chunk_index,
                )
            )
        return citations


def build_rag_instructions(answer_style: str) -> str:
    hint = STYLE_HINTS.get(answer_style, STYLE_HINTS["balanced"])
    return f"{RAG_INSTRUCTIONS}\n补充风格要求：{hint}"


def build_general_instructions(answer_style: str) -> str:
    hint = STYLE_HINTS.get(answer_style, STYLE_HINTS["balanced"])
    return f"{GENERAL_INSTRUCTIONS}\n补充风格要求：{hint}"


def build_general_input(question: str, history: Optional[List[dict]] = None, style: str = "balanced") -> str:
    sections = [f"回答风格：{style}"]
    if history:
        sections.extend(["", "最近对话："])
        for item in history[-6:]:
            role = "用户" if item.get("role") == "user" else "助手"
            sections.append(f"{role}：{item.get('content', '')}")
    sections.extend(
        [
            "",
            "知识库检索结果：未命中",
            "要求：先说明知识库里没找到直接相关内容，再基于通用能力回答。",
            f"当前问题：{question}",
        ]
    )
    return "\n".join(sections).strip()


def build_extractive_lines(results: List[SearchResult], answer_style: str) -> List[str]:
    if answer_style == "concise":
        lines = ["根据当前知识库，最相关的内容如下："]
    elif answer_style == "report":
        lines = ["## 结论", "以下内容最相关。", "", "## 依据"]
    elif answer_style == "detailed":
        lines = ["根据当前知识库，找到以下相关内容，并补充核心依据："]
    else:
        lines = ["根据当前知识库，找到以下相关内容："]

    for index, result in enumerate(results, start=1):
        source = format_source(result.source_path, result.chunk_index)
        snippet = build_snippet(result.content, max_length=300 if answer_style == "detailed" else 220)
        lines.append(f"{index}. {result.title}：{snippet}")
        lines.append(f"   来源：{source}")
        if answer_style in {"detailed", "report"}:
            lines.append(f"   分类：{result.category or 'uncategorized'}；标签：{', '.join(result.tags) if result.tags else '无'}")
    if answer_style == "report":
        lines.extend(["", "## 建议", "- 继续追问某一主题并沉淀为笔记。"])
    return lines
