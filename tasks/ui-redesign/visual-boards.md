# 关键页面视觉稿说明

## 页面范围

- Dashboard 首页
- Knowledge 列表页
- Knowledge 详情页
- Settings 页

## 桌面端视觉说明

### 1. Dashboard

- 左侧为轻玻璃感导航栏，视觉重量降低
- 主 Hero 使用天蓝色渐变高光和柔和光斑
- 四张统计卡片带有微装饰角标，数值更突出
- 最近导入与当前状态采用双栏布局，增强信息分层

### 2. Knowledge 列表页

- Hero 保持与 Dashboard 一致的视觉语言
- 分类与标签云使用柔和 pill 组件
- 表格包裹在圆角容器中，表头统一轻蓝灰背景
- 批量操作按钮位于表格上方，优先级清晰

### 3. Knowledge 详情页

- 文档详情与编辑区采用双列卡片布局
- 文档预览区作为主要阅读焦点，位于详情区之后
- 预览工具栏支持：
  - 渲染预览
  - 原始文本
  - 源文件信息展示
- Chunk 明细和相似文档延续同一视觉系统

### 4. Settings

- 采用双栏信息卡片展示路径和 OpenAI 配置
- 表单区强调输入焦点和操作可读性
- 支持环境变量区采用深色 code pill，形成视觉对比

## 移动端视觉说明

### 通用规则

- 侧栏折叠为顶部内容块
- Hero 改为单列
- 按钮改为全宽
- 列表和卡片统一单列流式布局

### 1. Dashboard 移动端

- 统计卡片从四列改为单列
- 最近导入与当前状态上下堆叠

### 2. Knowledge 列表页移动端

- 批量操作按钮全宽
- 表格仍可横向滚动，但内容区留白更紧凑

### 3. Knowledge 详情页移动端

- 元数据卡片和编辑卡片上下排列
- 预览工具栏换行显示
- 相似文档改为单列卡片

### 4. Settings 移动端

- 路径和配置卡片上下排列
- 表单字段保持 100% 宽度

## 截图导出计划

建议截图尺寸：

- 桌面端：`1440 x 1600~2200`
- 移动端：`390 x 1600~2200`

建议文件名：

- `dashboard-desktop.png`
- `dashboard-mobile.png`
- `knowledge-list-desktop.png`
- `knowledge-list-mobile.png`
- `knowledge-detail-desktop.png`
- `knowledge-detail-mobile.png`
- `settings-desktop.png`
- `settings-mobile.png`

## 当前说明

视觉稿图片本应输出到：

- `tasks/ui-redesign/`

但本次无头 Chrome 截图命令未获得授权，因此这里只先保留页面视觉说明与导出计划。

