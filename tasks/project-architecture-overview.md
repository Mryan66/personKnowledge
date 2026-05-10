# 项目架构与模块梳理

## 1. 项目定位

该项目是一个本地优先的个人 AI 知识管家，当前采用 Python 单体应用架构。

## 2. 当前完成度

项目核心功能已基本完成，处于可用状态：
- ✅ MVP 主流程闭环
- ✅ OrganizerAgent 已实现
- ✅ Knowledge 编辑/详情/删除已实现
- ✅ Ask 多轮对话/历史/保存笔记已实现
- ✅ 基础关键词和向量检索已实现

## 3. 目录分层

| 层级 | 目录/文件 | 作用 |
|------|-----------|------|
| 入口层 | `app/cli.py` | CLI 命令入口，串联 init / scan / ingest / search / ask / review / web |
| 配置层 | `app/config.py` | 读取 `.env`、环境变量、工作区路径与 OpenAI 配置 |
| 导入层 | `app/ingest/` | 扫描、解析、切块、摘要、标签、分类、导入流程 |
| 存储层 | `app/memory/database.py` | SQLite 元数据、chunk、embedding、chat 会话持久化 |
| 工具层 | `app/tools/` | OpenAI、embedding、search、vector、file、secret store 等 |
| Agent 层 | `app/agents/` | OrganizerAgent、QueryAgent、ReviewAgent |
| Web 层 | `app/web/` | 路由处理与页面渲染 |
| UI 层 | `app/ui/` | HTML 模板与 CSS |
| 数据目录 | `inbox/` `knowledge/` `data/` | 输入文件、知识产物、数据库和向量数据 |
| 测试层 | `tests/` | 覆盖导入、检索、Agent、Web 页面等基础行为 |

## 4. 当前核心架构

### 4.1 主体模块

- `app/ingest/scanner.py` - 扫描支持的导入文件
- `app/ingest/parser.py` - 文本和 PDF 解析（PDF 仅支持文本层）
- `app/ingest/chunker.py` - 固定窗口切块
- `app/agents/organizer_agent.py` - LLM 驱动的文档智能整理
- `app/ingest/pipeline.py` - 完整导入流程编排
- `app/memory/database.py` - 数据库操作（文档、chunk、embedding、chat 会话）
- `app/tools/openai_client.py` - OpenAI API 调用
- `app/tools/search_tool.py` - 关键词/向量检索统一封装
- `app/agents/query_agent.py` - 来源型回答和 RAG 回答（支持多轮）
- `app/agents/review_agent.py` - 每日复盘生成
- `app/web/server.py` - HTTP 服务器和路由

### 4.2 数据库 Schema

已实现的表：
- `documents` - 文档元数据
- `chunks` - 文档分块
- `embeddings` - 向量 embedding
- `chat_sessions` - 对话会话
- `chat_messages` - 对话消息

## 5. 已完成模块

所有核心功能已完成：
- 工作区初始化
- Inbox 文件扫描和导入
- `.md` / `.txt` / `.pdf` 解析
- SQLite 完整存储
- 关键词检索和向量检索
- OpenAI embedding 和 RAG 问答
- 多轮对话和会话历史
- 每日复盘
- Knowledge 文档管理（详情/编辑/删除/重新导入/相似文档）
- Ask 问答结果保存为笔记
- Dashboard / Inbox / Search / Ask / Review / Knowledge / Settings 完整 Web UI
- OpenAI 配置管理和 macOS Keychain 存储

## 6. 半完成/待完成模块

### 6.1 后端待优化

| 模块 | 当前情况 | 缺口 |
|------|---------|------|
| PDF 解析 | 仅支持文本层 | OCR 支持缺失 |
| 检索 | 向量/关键词二选一 | Hybrid Search + Rerank |
| 复盘 | 仅支持日报 | 周报/月报/自动定时 |
| Dashboard | 基础统计 | 趋势统计 |
| 成本 | 无统计 | Token 用量和成本上限 |

### 6.2 数据库待新增表

- `search_history` - 搜索历史
- `review_runs` - 复盘运行记录
- `openai_usage_logs` - OpenAI 调用日志

## 7. 推荐开发优先级

### P0 - 核心体验
1. OCR 支持
2. Hybrid Search + Rerank

### P1 - 体验优化
1. 搜索历史
2. 周报/月报
3. Dashboard 趋势统计

### P2 - 自动化运营
1. 自动定时 Review
2. 成本统计和上限控制
3. 待办提取和过期知识提醒

## 8. 配套图表

参考同目录下文件：
- `tasks/project-architecture-mermaid.md`
- `tasks/project-module-status-matrix.md`
