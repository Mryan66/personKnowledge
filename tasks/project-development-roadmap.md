# 项目开发任务拆解

## 1. 目标

基于当前代码现状，将项目从"已具备 MVP 主链路"推进到"可持续使用的个人知识系统"。

## 2. 当前状态

项目核心功能已基本完成：
- ✅ OrganizerAgent 已实现（LLM 整理 + 规则 fallback）
- ✅ Knowledge 页面已支持详情、编辑、删除、重新导入、相似文档
- ✅ Ask 页面已支持多轮问答、会话历史、保存笔记
- ✅ 基础的关键词和向量检索已实现

## 3. 总体开发原则

1. 先补知识质量，再补检索体验，最后补自动化运营
2. 优先复用现有架构，保持 SQLite 单体架构
3. 每个阶段都要带最小测试闭环

## 4. 迭代路线图

### 阶段一：核心体验增强

#### 任务 1：实现 OCR 支持（P0）

**目标**：让扫描件 PDF 也能进入导入链路

**建议实现策略**：
- 抽象 PDF 解析策略接口
- 文本层 PDF 继续走 `pypdf`
- 扫描件或空文本时走 OCR fallback
- OCR 做成可选配置，依赖可按需安装

**验收标准**：
- 扫描件 PDF 可被识别并导入
- 支持在 Settings 页面配置 OCR 选项
- 有清晰的错误提示

**相关文件**：
- `app/ingest/parser.py`
- `app/config.py`
- `app/ui/templates/settings.html`

#### 任务 2：实现真正的 Hybrid Search（P0）

**目标**：融合关键词检索与向量检索结果

**建议实现**：
- `SearchTool.search()` 在 `auto` 模式下同时拉取 keyword/vector 结果
- 做简单归一化与合并去重
- 后续再加 rerank

**验收标准**：
- 检索结果来源不再只有单一路径
- 结果质量优于现有单路检索

**相关文件**：
- `app/tools/search_tool.py`
- `app/memory/database.py`
- `tests/test_search.py`

#### 任务 3：增加 Rerank（P0）

**目标**：对 hybrid 结果做二次重排序

**建议实现**：
- 第一阶段先做规则 rerank（基于标签、分类匹配度）
- 第二阶段可考虑轻量 rerank 模型

**验收标准**：
- 排名前几条结果更稳定
- 相同 query 的相关性主观体验提升

### 阶段二：自动化与运营

#### 任务 4：周报/月报支持（P1）

**目标**：在现有每日 Review 基础上扩展周期报表

**建议实现**：
- 复用 `ReviewAgent`
- 参数化周期粒度（day/week/month）
- Review 页面增加周期选择器

#### 任务 5：自动定时 Review（P1）

**目标**：支持每天/每周自动生成复盘

**建议实现**：
- 从 CLI 定时触发考虑
- 提供简单的 cron 配置说明
- 后续可考虑 Web 管理入口

#### 任务 6：搜索历史（P1）

**目标**：支持保存和查看历史搜索

**建议实现**：
- 新增 `search_history` 表
- Search 页面展示最近搜索

#### 任务 7：Dashboard 趋势统计（P1）

**目标**：展示知识增长趋势、导入统计等

**建议实现**：
- 新增按日期聚合统计
- Dashboard 增加趋势卡片（简单文字版即可）

### 阶段三：成本与高级运营

#### 任务 8：成本统计与上限控制（P2）

**目标**：记录 OpenAI 调用量与估算成本，提供简单限额控制

**建议实现**：
- 在 `openai_client.py` 增加统计记录
- 新增 `openai_usage_logs` 表
- Settings 页面增加成本统计和上限设置

#### 任务 9：待办提取（P2）

**目标**：从文档或 review 中提取 Todo

**建议实现**：
- 先规则法提取，再逐步引入 Agent
- Review 页面展示提取的待办

#### 任务 10：过期知识提醒（P2）

**目标**：标记长期未复习或可能过期的知识

**建议实现**：
- Dashboard 增加"需要复习"提示
- 基于最后访问时间判断

## 5. 推荐开发顺序

### Sprint 1
- OCR 基础支持
- Hybrid Search
- Rerank

### Sprint 2
- 搜索历史
- 周报/月报
- Dashboard 趋势统计

### Sprint 3
- 自动定时 Review
- 成本统计和上限控制
- 待办提取与过期提醒

## 6. 最小测试建议

每阶段至少补三类测试：
- 单元测试：核心函数和数据库操作
- 集成测试：导入、检索、问答主流程
- Web 渲染测试：页面按钮和输出状态

## 7. 配套文档

参考同目录下文件：
- `tasks/project-architecture-overview.md`
- `tasks/project-architecture-mermaid.md`
- `tasks/project-module-status-matrix.md`
