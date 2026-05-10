# 项目开发 Checklist

## P0 核心能力

- [x] 实现 `OrganizerAgent`，替换硬编码占位逻辑
- [x] 在导入流程中接入 `OrganizerAgent`
- [x] 保留无 API Key 时的启发式 fallback
- [x] 为文档增加标题/摘要/标签/分类编辑能力
- [x] 增加文档详情页
- [x] 增加 chunk 明细展示
- [x] 增加删除文档能力
- [x] 增加重新导入能力
- [x] 为扫描件 PDF 增加 OCR fallback
- [x] 实现真正的 Hybrid Search
- [x] 增加结果去重与归一化排序
- [x] 增加 Rerank

## P1 检索与问答

- [x] 增加相似文档功能
- [x] 增加 Ask 结果保存为笔记
- [x] 增加多轮问答
- [x] 增加对话历史
- [ ] 增加标签/分类/时间过滤
- [x] 增加搜索历史

## P2 复盘与自动化

- [x] 支持周报
- [x] 支持月报
- [ ] 支持自动定时 Review
- [ ] 支持 Review 对比
- [x] 增加 Dashboard 趋势图
- [ ] 增加导入统计
- [ ] 增加待办提取
- [ ] 增加过期知识提醒
- [ ] 增加 Token 成本统计
- [ ] 增加成本上限控制

## P3 产品完成度

- [ ] 增加 Inbox 拖拽上传
- [ ] 增加文件夹监听
- [ ] 增加网页剪藏
- [ ] 增加导入历史
- [x] 更新 Settings 页面文案，移除已实现但仍显示"预留"的描述

## 数据层建议

- [x] `chat_sessions` 表（已存在）
- [x] `chat_messages` 表（已存在）
- [ ] `search_history` 表（待新增）
- [ ] `review_runs` 表（待新增）
- [ ] `openai_usage_logs` 表（待新增）

## 测试补齐

- [ ] 为 `OrganizerAgent` 增加测试
- [ ] 为 Knowledge 编辑能力增加测试
- [ ] 为删除/重新导入增加测试
- [ ] 为 Hybrid Search 增加测试
- [ ] 为多轮问答增加测试
- [ ] 为自动 Review 增加测试
