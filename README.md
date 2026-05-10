# Personal AI Knowledge Butler

一个本地优先的个人 AI 知识管家，用于整理、检索、复盘和调用个人知识。

## 功能特性

- ✅ **智能文档整理**：基于 LLM 的自动标题、摘要、标签、分类生成
- ✅ **混合检索**：关键词 + 向量检索 + 重排序（向量检索需配置 API Key）
- ✅ **RAG 问答**：基于个人知识库的智能问答
- ✅ **多轮对话**：支持会话记忆和历史对话
- ✅ **知识复盘**：每日/每周/每月复盘生成
- ✅ **Web UI**：美观的本地 Web 界面
- ✅ **文档管理**：编辑、删除、重新导入、相似文档发现、快速过滤
- ✅ **问答沉淀**：支持将高质量问答保存为笔记
- ✅ **搜索历史**：记录搜索历史，一键重搜
- ✅ **知识增长**：可视化文档增长趋势
- ✅ **OCR 支持**：扫描件 PDF 导入（需手动安装依赖）
- ✅ **火山引擎**：默认适配火山编码计划 API

## 当前项目状态

项目已完成个人知识库 MVP 主链路，当前已支持：

- ✅ 本地文件扫描与导入
- ✅ Markdown / TXT / PDF 文本解析
- ✅ 摘要、标签、分类生成
- ✅ SQLite 元数据存储
- ✅ 文档切块与 Embedding
- ✅ 关键词检索、向量检索、Hybrid Search
- ✅ 基于知识库的 RAG 问答
- ✅ 多轮对话与问答沉淀
- ✅ 每日 / 每周 / 每月复盘
- ✅ Web UI 知识管理与设置页面

当前仍未完成或能力较薄弱的部分包括：

- ⚠️ 更多文档格式与外部来源接入
- ⚠️ 自动归档、去重合并、标签治理
- ⚠️ 双链、知识图谱、主题地图
- ⚠️ Todo 提取、提醒系统、任务集成
- ⚠️ 写作风格学习与高级写作辅助
- ⚠️ 桌面端、隐私审计、成本统计、错误恢复

更完整的逐模块完成度检查请参考：

- `tasks/project-feature-status.md`

## 快速开始

### 安装依赖

```bash
pip install -e .
```

### 初始化工作区

```bash
python3 -m app.cli init
```

### 导入文档

将文件放入 `inbox/` 文件夹，然后：

```bash
python3 -m app.cli scan
python3 -m app.cli ingest
```

或直接指定文件：

```bash
python3 -m app.cli ingest path/to/document.md
```

### 检索

```bash
python3 -m app.cli search "关键词"
python3 -m app.cli search "语义检索" --mode vector
```

### 问答

```bash
python3 -m app.cli ask "我有哪些关于 AI 的笔记？"
```

### 复盘

```bash
python3 -m app.cli review --limit 20
```

### 启动 Web UI

```bash
python3 -m app.cli web
```

默认地址：`http://127.0.0.1:8765`

## 配置 OpenAI / 火山引擎 API

### 方式一：环境变量

```bash
export OPENAI_API_KEY="your-api-key"
```

### 方式二：`.env` 文件

在项目根目录创建 `.env` 文件：

```env
OPENAI_API_KEY="your-api-key"
```

### 方式三：Web UI Settings 页面

启动 Web UI 后在 Settings 页面配置，支持 macOS Keychain 安全存储。

### 可选配置

```env
OPENAI_MODEL="doubao-seed-2.0-code"
OPENAI_BASE_URL="https://ark.cn-beijing.volces.com/api/v3"
OPENAI_EMBEDDING_MODEL="doubao-embedding-2.0-text-16k"
OPENAI_TIMEOUT_SECONDS="60"
KB_ENABLE_OCR="false"
```

## OCR 支持（可选）

要启用扫描件 PDF 解析，需要安装额外依赖：

```bash
pip install pytesseract pdf2image pillow
# 并安装系统级 Tesseract OCR 引擎
# macOS: brew install tesseract-lang
# Linux: apt install tesseract-ocr
# Windows: https://github.com/UB-Mannheim/tesseract/wiki
```

然后在 Settings 页面勾选"启用 OCR"。

## 项目结构

```
personKnowledge/
├── inbox/                    # 待处理文件入口
├── knowledge/                # 整理后的知识库
│   ├── reviews/              # 复盘文档
│   └── topics/               # 问答沉淀的笔记
├── data/                     # SQLite 元数据和向量索引
├── app/
│   ├── agents/               # OrganizerAgent, QueryAgent, ReviewAgent
│   ├── ingest/               # 文件扫描与导入流程
│   ├── memory/               # 数据库操作
│   ├── tools/                # OpenAI, embedding, search, etc.
│   ├── web/                  # Web UI 路由和渲染
│   └── ui/                  # HTML 模板和 CSS
└── tests/                   # 测试
```

## 开发路线图

- ✅ MVP 主流程完成
- ✅ OrganizerAgent 实现
- ✅ Knowledge 页面详情和编辑
- ✅ Hybrid Search + Rerank
- ✅ 周报/月报支持
- ✅ 搜索历史和知识增长可视化
- ✅ 火山引擎 API 适配
- ✅ OCR 框架实现
- ⏳ 自动定时复盘
- ⏳ 成本统计与上限控制
- ⏳ 趋势分析与知识运营

详细开发任务请参考 `tasks/` 文件夹。
