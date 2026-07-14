# My Second Brain

[English →](README.md) · **简体中文**

My Second Brain 是一款本地优先的知识应用。它能将 PDF、笔记、Word 和
PowerPoint 文件、图像以及网页转换为一个相互连接、可搜索且与
Obsidian 兼容的 Markdown Wiki。

它不会让有用的上下文停留在用完即丢的模型对话中，而是在磁盘上构建一层
持久的知识：包括原始源文件、相互链接的概念页、来源追溯信息、按知识范围生成的
概览，以及操作日志。你可以编译新材料、浏览和搜索内容、提出由 Wiki 内容支持的
问题、审查其结构，还可以选择在持久化对话中求解课程习题。

> **本地优先不等于完全离线。** 你的知识库目录和生成的页面会保留在本机上。
> AI 驱动的操作会把该操作所需的源材料或上下文发送给你配置的 OpenAI 或
> Anthropic 模型服务提供方。

如需了解完整用法、配置、删除行为、隐私指南和故障排除，请查看
[用户手册](USER_MANUAL.zh-CN.md)。

## 应用提供的能力

- **持久的 Markdown 知识** —— YAML frontmatter、`[[wikilinks]]` 和 LaTeX
  数学公式即使离开本应用也依然可读。
- **感知来源的编译** —— 每次导入都会创建或更新概念页，并保留指向来源页和
  原始材料的追溯信息。
- **层级化的知识范围** —— 你可以在整个知识库目录中工作，也可以将 **Search**、
  **Ask**、**Review** 和 **Add source** 限定到某个分支或课程。
- **有知识库依据的回答** —— 回答会引用 Wiki 页面；如果引用的页面不存在，系统会
  显示警告，而不会默默接受该引用。
- **混合检索** —— 默认使用本地 BM25 关键词搜索；可选的 LanceDB 向量可增加
  语义搜索能力。
- **可检查的指令** —— 每个知识范围都可以覆盖编译、回答、审查和 **Solver** 所使用的
  `prompt`（提示词）、`purpose`（用途说明）和 `schema`（结构规范）。
- **Web 和 CLI 工作流** —— 日常工作可以使用浏览器；初始设置、脚本化、保存回答和
  维护则可以使用 `llmwiki`。

## 快速开始

### 要求

- Python 3.11 或更高版本
- Git
- 用于 AI 驱动功能的 OpenAI 或 Anthropic API 密钥

运行本应用不需要 Node.js。只有修改前端时才需要它。

### 启动仓库中附带的示例知识库目录

本仓库已包含一个有内容的 example-course 示例知识库目录。克隆仓库、安装包，然后从仓库
根目录启动：

```bash
git clone https://github.com/EricWcr7/My-Second-Brain-by-YFW.git
cd My-Second-Brain-by-YFW
python3 -m venv .venv
source .venv/bin/activate
python -m pip install ".[web]"
llmwiki set-key openai YOUR_OPENAI_API_KEY
llmwiki
```

在 Windows PowerShell 中，使用已安装的 Python 3.11+ 创建并激活环境：

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install ".[web]"
llmwiki set-key openai YOUR_OPENAI_API_KEY
llmwiki
```

将 `YOUR_OPENAI_API_KEY` 替换为真实密钥；不要提交该密钥。如果设置了
`XDG_CONFIG_HOME`，密钥会存储在知识库目录之外的
`$XDG_CONFIG_HOME/llmwiki/.env`；否则存储在 `~/.config/llmwiki/.env`。
把密钥直接作为命令行参数传入可能会将其留在 shell 历史记录中；如有需要，请使用
shell 提供的受保护密钥输入或临时环境变量流程。如果想改用 Anthropic 作为主应用的
模型服务，请参阅 [中文用户手册](USER_MANUAL.zh-CN.md)。

服务器会打开 `http://127.0.0.1:8000`。在 Welcome 页面上选择 **Enter workspace**（进入工作区）。
使用 `Ctrl+C` 停止服务器。

如果只想浏览附带的 Wiki、运行关键词 **Search**，或使用结构 **Review**，可以省略密钥命令。

### 创建干净的个人知识库目录

从克隆的仓库安装 `llmwiki` 后，初始化另一个目录：

```bash
llmwiki init ~/my-second-brain
cd ~/my-second-brain
llmwiki
```

`llmwiki init` 具有幂等性：它会创建缺失的知识库目录文件，不会覆盖现有内容。
新的空白知识库目录包含受保护的 `Academic` 知识范围，但不包含示例课程，也不会启用
**Solver**。

### 开始使用后的前五分钟

1. 选择 **Enter workspace**（进入工作区）。
2. 如需操作整个知识库目录，保持 `General` 知识范围；也可以打开
   **Scope → Manage scopes**（知识范围 → 管理知识范围）来创建或选择更窄的范围。
3. 选择 **Add source**（添加源材料），选择一个或多个文件，或输入 URL，确认目标范围后
   执行编译。
4. 使用 **Workspace** 输入框或 **Search**（`Cmd/Ctrl+K`）打开生成的概念页和来源页。
5. 打开 **Ask**（提问）以获取综合回答，或打开 **Review**（审查）来检查来源追溯信息和
   链接。

## 可选的语义搜索

从克隆的仓库安装 `search` 扩展依赖：

```bash
python -m pip install ".[web,search]"
```

然后在知识库目录内部重建向量：

```bash
llmwiki reindex
```

语义搜索还需要嵌入模型密钥，或一个与 OpenAI 兼容的本地端点。如果没有它，或者没有安装
`search` 扩展依赖，应用将回退到 BM25 关键词搜索。

## 知识范围模型

一个知识范围可以看到其自身分区以及所有后代分区中的页面。因此，`General` 可以看到整个
知识库目录；而一门课程只能看到该课程的内容。

```text
General
├── Academic
│   └── example-course
├── Research
└── Personal
```

知识范围用于组织检索；它们不是用户账户或安全边界。本应用面向单用户设计，没有身份验证层。

## 知识库目录布局

| 路径 | 用途 |
| --- | --- |
| `raw/` | 已导入文件和图像资源的本地副本 |
| `wiki/` | 生成的概念页、来源页、概览、索引、日志、用途说明和结构规范 |
| `.llmwiki/` | 知识库目录配置、导入状态、标准化缓存、可选向量、提示词覆盖和 **Solver** 会话 |

Wiki 仍然是纯 Markdown，因此可以用 Git、文本编辑器或 Obsidian 检查。
[中文用户手册](USER_MANUAL.zh-CN.md)说明了应打开哪个目录以及
应备份哪些内容。

## 命令行入口

```text
llmwiki init       Create or complete a vault
llmwiki ingest     Compile one file or URL
llmwiki query      Ask from the terminal; optionally save the answer
llmwiki search     Search concept pages
llmwiki lint       Run structural or deep review
llmwiki overview   Regenerate an overview
llmwiki reindex    Rebuild semantic vectors
llmwiki set-key    Store or inspect provider keys
llmwiki             Launch the web app
```

有关选项和示例，请参阅 [中文用户手册中的 CLI 参考](USER_MANUAL.zh-CN.md)。

## 开发

安装测试依赖并运行 Python 测试套件：

```bash
python -m pip install ".[dev]"
make test
make eval
```

如需进行前端开发：

```bash
make web-install
make dev
```

`make dev` 会在端口 8000 上运行 FastAPI，并在端口 5173 上运行 Vite。修改前端源码后，
运行 `make web-build` 以重新构建 `llmwiki/web/static/` 下已提交的生产资源。

## 起源与许可证

本项目实现并扩展了
[Andrej Karpathy 的 LLM Wiki 模式](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)：
不可变的源材料、由 LLM 维护的 Markdown Wiki、指令/结构规范层，以及
导入/查询/审查工作流。本实现还增加了层级化知识范围、分支特定指令、混合检索、
浏览器体验、模型服务提供方支持、持久化 **Solver** 会话和自动依据校验。

本项目采用 [MIT 许可证](LICENSE) 发布。
