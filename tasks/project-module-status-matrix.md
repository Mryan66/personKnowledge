# 模块状态矩阵

| 模块域 | 代表文件/目录 | 状态 | 说明 |
|------|----------------|------|------|
| CLI 入口 | `app/cli.py` | ✅ 已完成 | 命令入口清晰，覆盖核心操作 |
| 配置中心 | `app/config.py` | ✅ 已完成 | 支持环境变量、`.env`、Keychain |
| Inbox 扫描 | `app/ingest/scanner.py` | ✅ 已完成 | 支持目录递归扫描 |
| 文档解析 | `app/ingest/parser.py` | ⚠️ 半完成 | PDF 仅支持文本层，不支持 OCR |
| 切块 | `app/ingest/chunker.py` | ✅ 已完成 | 固定窗口切块可用 |
| 摘要/标签/分类 | `app/agents/organizer_agent.py` | ✅ 已完成 | LLM 驱动的智能整理，带 fallback |
| 导入编排 | `app/ingest/pipeline.py` | ✅ 已完成 | 主流程已闭环，已集成 OrganizerAgent |
| SQLite 存储 | `app/memory/database.py` | ✅ 已完成 | schema、查询、统计、写入都已具备 |
| Embedding 生成 | `app/tools/embedding_tool.py` | ✅ 已完成 | 已支持文档 chunk 向量化 |
| OpenAI 接入 | `app/tools/openai_client.py` | ✅ 已完成 | Responses 与 Embeddings 可调用 |
| 关键词检索 | `app/tools/search_tool.py` | ✅ 已完成 | 基础检索已可用 |
| 向量检索 | `app/tools/search_tool.py` + `vector_tool.py` | ⚠️ 半完成 | 可用，但无 Hybrid Search 和 rerank |
| OrganizerAgent | `app/agents/organizer_agent.py` | ✅ 已完成 | 完整实现，带 LLM 和规则 fallback |
| QueryAgent | `app/agents/query_agent.py` | ✅ 已完成 | 支持多轮问答和会话记忆 |
| ReviewAgent | `app/agents/review_agent.py` | ⚠️ 半完成 | 日报可用，周报/月报/周期化缺失 |
| Dashboard | `app/web/dashboard.py` | ⚠️ 半完成 | 基础统计可用，趋势卡片未实现 |
| Inbox 页面 | `app/web/inbox.py` | ⚠️ 半完成 | 可导入，但无监听/OCR/历史 |
| Search 页面 | `app/web/search.py` | ⚠️ 半完成 | 可检索，但无高级过滤与历史 |
| Ask 页面 | `app/web/ask.py` | ✅ 已完成 | 可问答，支持多轮、历史、保存笔记 |
| Review 页面 | `app/web/review.py` | ⚠️ 半完成 | 可生成和浏览，但无自动化 |
| Knowledge 页面 | `app/web/knowledge.py` | ✅ 已完成 | 可浏览、详情、编辑、删除、重新导入、相似文档 |
| Settings 页面 | `app/web/settings.py` | ⚠️ 半完成 | 配置可保存，但治理能力不足 |
| 前端模板 | `app/ui/templates/` | ✅ 已完成 | 页面完整，大部分功能已可用 |
| 自动化任务 | 全局 | ❌ 未开发 | 无定时 ingest/review/提醒 |
| 成本治理 | 全局 | ❌ 未开发 | 无 token 统计和成本上限 |
| OCR 能力 | 全局 | ❌ 未开发 | 扫描件 PDF 无法处理 |
| 知识运营能力 | 全局 | ⚠️ 半完成 | 无过期提醒、待办提取、趋势分析 |

## 优先级建议

### P0
- **OCR** - 扫描件 PDF 支持
- **Hybrid Search + Rerank** - 提升检索质量

### P1
- **周报/月报** - 扩展复盘周期
- **自动定时 Review** - 自动化运营
- **搜索历史** - 用户体验优化

### P2
- **成本统计与上限** - 成本治理
- **趋势统计** - Dashboard 增强
- **待办提取** - 知识运营增强
