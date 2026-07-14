# Second Brain by YFW

[English →](README.md) · **简体中文**

Second Brain by YFW 是一款本地优先的知识应用。它把文档、图像和网页转换成相互
连接、可搜索并兼容 Obsidian 的 Markdown Wiki。来源追踪、链接概念、按范围生成的
概览和操作日志都保存在磁盘上，因此离开应用后仍能阅读和使用这些知识。

> **本地优先不等于完全离线。** 知识库目录和生成的页面保留在本机；AI 驱动的
> 操作会把完成该操作所需的来源或上下文发送给你配置的 OpenAI 或 Anthropic
> 模型服务提供方。

浏览器工作流、配置、存储、隐私和故障排除请参阅[用户手册](USER_MANUAL.zh-CN.md)。

## 主要能力

- **持久的 Markdown** —— YAML frontmatter、`[[wikilinks]]` 和 LaTeX 数学公式可在
  文本编辑器或 Obsidian 中继续使用。
- **感知来源的导入** —— 导入会创建来源记录、合并可复用概念，并保留来源追踪。
- **按范围组织知识** —— Search、Ask、Review、概览和导入都可以针对整个知识库目录
  或某个分支执行。
- **有依据的回答** —— 回答会引用 Wiki 页面；不存在的页面引用会被报告。
- **混合检索** —— 本地 BM25 关键词搜索默认可用；可选的 LanceDB 向量可增加语义检索。
- **可检查的指令** —— General 基线和范围级覆盖可控制用途说明、结构规范、导入、Ask
  以及深度 Review 的提示词。
- **浏览器与 CLI 工作流** —— 日常操作使用浏览器；初始化、脚本、保存回答和维护使用
  `llmwiki`。

## 快速开始

### 要求

- Python 3.11 或更高版本
- Git
- 用于 AI 驱动操作的 OpenAI 或 Anthropic API 密钥

只有开发前端时才需要 Node.js。

### macOS 或 Linux

按顺序克隆仓库、创建环境、从检出目录安装、初始化一个已忽略的知识库目录、配置密钥并
启动应用：

```bash
git clone https://github.com/EricWcr7/second-brain-by-yfw.git
cd second-brain-by-yfw
python3 -m venv .venv
source .venv/bin/activate
python -m pip install ".[web]"
llmwiki init .
llmwiki set-key openai YOUR_OPENAI_API_KEY
llmwiki
```

### Windows PowerShell

```powershell
git clone https://github.com/EricWcr7/second-brain-by-yfw.git
cd second-brain-by-yfw
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install ".[web]"
llmwiki init .
llmwiki set-key openai YOUR_OPENAI_API_KEY
llmwiki
```

请把占位符替换为真实密钥，并且不要提交密钥。持久化密钥位于知识库目录之外的
`${XDG_CONFIG_HOME:-~/.config}/llmwiki/.env`。直接在命令行中传入密钥可能会把它留在
shell 历史记录中；如有需要，请改用环境变量或 shell 的受保护密钥流程。Anthropic
配置见[模型服务密钥与模型](USER_MANUAL.zh-CN.md#模型服务密钥与模型)。

服务器会打开 `http://127.0.0.1:8000`。选择 **Enter workspace** 进入工作区，使用
`Ctrl+C` 停止服务器。浏览已有页面、运行 BM25 Search 或结构 Review 不需要密钥。

### 第一次工作流

1. 打开 **Scope → Manage scopes**，创建或选择目标范围。
2. 选择 **Add source**，选择文件或输入 URL，然后执行编译。
3. 使用 **Workspace** 或 **Search**（`Cmd/Ctrl+K`）打开生成的页面。
4. 使用 **Ask** 获取有 Wiki 依据的综合回答。
5. 使用 **Review** 检查来源追踪和链接。

`llmwiki init .` 具有幂等性：它只补齐缺失文件，不会替换已有内容。如果希望仓库检出目录
始终不含数据，可以另建目录：

```bash
mkdir my-vault
cd my-vault
llmwiki init .
llmwiki
```

## 支持的来源

导入管道支持 Markdown、纯文本、PDF、DOCX、PPTX、常见图像格式以及 HTTP(S) 网页。
应用会先在本机提取文本；图像和文字稀少的扫描 PDF 会使用模型服务的视觉输入。因此，
模型服务可能收到文档文本或原始图像/PDF 字节。

## 可选的语义搜索

从仓库检出目录安装搜索扩展依赖，配置嵌入模型密钥或兼容 OpenAI 的端点，然后在知识库
目录中构建向量：

```bash
python -m pip install ".[web,search]"
llmwiki reindex
```

缺少扩展依赖、嵌入密钥或向量索引时，Search 会回退到本地 BM25 排序。

## 范围模型

一个范围可以看到自身分区和所有后代分区。`General` 可以看到整个知识库目录；子范围只能
看到自己的分支。

```text
General
├── Academic
│   └── Example Course
└── Projects
    └── Learning Notes
```

范围用于组织检索，不是账户、权限或安全边界。本应用面向单用户设计，没有身份验证层。

## 知识库目录布局

公开仓库只包含应用代码。运行 `llmwiki init .` 后会创建以下已被 Git 忽略的运行时目录：

| 路径 | 用途 |
| --- | --- |
| `raw/` | 已导入文件和图像资源的本地副本 |
| `wiki/` | 生成的概念页、来源页、概览、索引、日志、用途说明和结构规范 |
| `.llmwiki/` | 配置、导入状态、标准化缓存、可选向量和提示词覆盖 |

如需精确恢复，请备份整个知识库目录。仅备份 `wiki/` 也可得到便于携带的阅读副本。

## 命令行概览

```text
llmwiki init       创建或补齐知识库目录
llmwiki ingest     编译一个文件或 URL
llmwiki query      在终端中提问，并可选择保存回答
llmwiki search     搜索概念页
llmwiki lint       运行结构或深度审查
llmwiki overview   重新生成概览
llmwiki reindex    重建语义向量
llmwiki set-key    存储或检查模型服务密钥
llmwiki            启动 Web 应用
```

选项和示例见[命令行参考](USER_MANUAL.zh-CN.md#命令行参考)。

## 开发

安装开发依赖并运行 Python 测试和依据评估：

```bash
python -m pip install ".[dev]"
make test
make eval
```

开发前端：

```bash
make web-install
make dev
```

`make dev` 会在端口 8000 上运行 FastAPI，并在端口 5173 上运行 Vite。修改前端源码后，
运行 `make web-build`，并提交 `llmwiki/web/static/` 下刷新后的生产构建。

## 起源、插图与许可证

本项目实现并扩展了
[Andrej Karpathy 的 LLM Wiki 模式](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)：
不可变的来源材料、由 LLM 维护的 Markdown Wiki、指令/结构规范层，以及导入、查询和审查
工作流。

仓库中的 `brain-network.png` 插图由 EricWcr7 为本项目创作，并按仓库的
[MIT 许可证](LICENSE)发布。第三方字体和库保留各自的许可证，详见
[第三方声明](THIRD_PARTY_NOTICES.md)。尤其是在重新分发应用或用于商业产品之前，请查看
PyMuPDF 的当前许可条款。
