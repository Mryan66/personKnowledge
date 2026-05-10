from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional

from app.memory.database import DocumentRecord, list_documents


@dataclass(frozen=True)
class ReviewReport:
    title: str
    body: str
    path: Optional[Path] = None


def render_review_markdown(title: str, documents: List[DocumentRecord]) -> str:
    lines = [f"# {title}", ""]
    lines.append("## 总览")
    lines.append(f"- 新增/最近更新文档：{len(documents)} 篇")

    tag_counter = Counter(tag for document in documents for tag in document.tags)
    category_counter = Counter(document.category for document in documents if document.category)
    top_tags = ", ".join(tag for tag, _ in tag_counter.most_common(8)) or "暂无"
    top_categories = ", ".join(category for category, _ in category_counter.most_common(5)) or "暂无"
    lines.append(f"- 高频标签：{top_tags}")
    lines.append(f"- 主要分类：{top_categories}")
    lines.append("")

    lines.append("## 文档摘要")
    if not documents:
        lines.append("- 暂无已入库文档。")
    for document in documents:
        tag_text = ", ".join(document.tags) if document.tags else "暂无标签"
        lines.append(f"- **{document.title or 'Untitled'}**")
        lines.append(f"  - 分类：{document.category or 'uncategorized'}")
        lines.append(f"  - 标签：{tag_text}")
        lines.append(f"  - 摘要：{document.summary or '暂无摘要'}")
        lines.append(f"  - 来源：{document.source_path}")
    lines.append("")

    lines.append("## 建议行动")
    if documents:
        lines.append("- 选择 1-2 篇高价值文档补充更详细的个人理解。")
        lines.append("- 检查高频标签是否需要合并或重命名。")
        lines.append("- 对重要主题使用 `ask` 追问并沉淀结论。")
    else:
        lines.append("- 先把 Markdown 或 TXT 文件放入 `inbox/`，再运行 `ingest`。")
    lines.append("")
    return "\n".join(lines)


class ReviewAgent:
    def __init__(self, database_path: Path, reviews_dir: Path):
        self.database_path = database_path
        self.reviews_dir = reviews_dir

    def generate_daily_review(
        self,
        target_date: Optional[date] = None,
        limit: int = 20,
        write_file: bool = True,
    ) -> ReviewReport:
        review_date = target_date or date.today()
        title = f"Daily Review - {review_date.isoformat()}"
        documents = list_documents(self.database_path, limit=limit)
        body = render_review_markdown(title, documents)
        path = None
        if write_file:
            self.reviews_dir.mkdir(parents=True, exist_ok=True)
            path = self.reviews_dir / f"{review_date.isoformat()}-daily-review.md"
            path.write_text(body, encoding="utf-8")
        return ReviewReport(title=title, body=body, path=path)

    def generate_weekly_review(
        self,
        target_date: Optional[date] = None,
        limit: int = 50,
        write_file: bool = True,
    ) -> ReviewReport:
        review_date = target_date or date.today()
        start_of_week = review_date - timedelta(days=review_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        title = f"Weekly Review - {start_of_week.isoformat()} to {end_of_week.isoformat()}"
        documents = list_documents(self.database_path, limit=limit)
        body = render_review_markdown(title, documents)
        path = None
        if write_file:
            self.reviews_dir.mkdir(parents=True, exist_ok=True)
            path = self.reviews_dir / f"{review_date.isoformat()}-weekly-review.md"
            path.write_text(body, encoding="utf-8")
        return ReviewReport(title=title, body=body, path=path)

    def generate_monthly_review(
        self,
        target_date: Optional[date] = None,
        limit: int = 100,
        write_file: bool = True,
    ) -> ReviewReport:
        review_date = target_date or date.today()
        month_name = review_date.strftime("%Y-%m")
        title = f"Monthly Review - {month_name}"
        documents = list_documents(self.database_path, limit=limit)
        body = render_review_markdown(title, documents)
        path = None
        if write_file:
            self.reviews_dir.mkdir(parents=True, exist_ok=True)
            path = self.reviews_dir / f"{review_date.isoformat()}-monthly-review.md"
            path.write_text(body, encoding="utf-8")
        return ReviewReport(title=title, body=body, path=path)
