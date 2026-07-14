# My Second Brain — 用户手册

[English →](USER_MANUAL.md)

本手册介绍如何使用和管理 My Second Brain。[README](README.zh-CN.md) 负责项目介绍和快速启动；本指南则完整讲解浏览器工作流、CLI、配置、存储、隐私和故障排除。

产品名称是 **My Second Brain**，Python 包和命令行程序名为 `llmwiki`。界面中可见的英文标签会以 `代码样式` 保留，并配上自然的中文说明，方便你在应用中准确对应。

## 目录

1. [应用的工作原理](#应用的工作原理)
2. [启动应用并进入工作区](#启动应用并进入工作区)
3. [理解和管理范围](#理解和管理范围)
4. [添加并编译来源](#添加并编译来源)
5. [使用 Workspace 和 Search](#使用-workspace-和-search)
6. [阅读页面和概览](#阅读页面和概览)
7. [提问](#提问)
8. [检查 Wiki 健康状况](#检查-wiki-健康状况)
9. [删除页面和范围](#删除页面和范围)
10. [自定义 Scope settings](#自定义-scope-settings)
11. [使用 Solver](#使用-solver)
12. [提供商密钥和模型](#提供商密钥和模型)
13. [配置参考](#配置参考)
14. [命令行参考](#命令行参考)
15. [存储备份和 Obsidian](#存储备份和-obsidian)
16. [隐私和安全](#隐私和安全)
17. [故障排除](#故障排除)
18. [当前限制](#当前限制)

## 应用的工作原理

My Second Brain 会把来源材料编译成一个持久化的 Markdown 知识库。基本流程如下：

```text
文件或 URL
    ↓ 规范化并分析
原始材料 + 生成的来源页面
    ↓ 提取并合并概念
相互链接的概念页面
    ↓ 在当前范围内检索
Search、Ask、Review、概览和 Solver
```

### 知识库目录

任何包含 `.llmwiki/` 的目录都是一个 **知识库目录（vault）**。运行 `llmwiki init` 即可创建。所有命令都会从当前目录开始向上查找这个标记，因此你可以在知识库根目录或其任意子目录中运行命令。

知识库主要分为三层：

| 层 | 用途 | 通常由谁管理 |
| --- | --- | --- |
| `raw/` | 已导入文件和图像的本地副本 | 你提供材料；应用管理保存的副本 |
| `wiki/` | 生成的概念、来源页面、概览、索引和日志 | 应用及其配置的 LLM |
| `.llmwiki/` | 配置、导入状态、缓存、向量、覆盖设置和 Solver 会话 | 应用 |

概念页面和来源页面使用 YAML frontmatter、标准 Markdown、`[[wikilinks]]`，以及 `$...$` 或 `$$...$$` 形式的 LaTeX 数学公式。你可以手动编辑，但之后再次编译时，生成内容可能被合并或替换。更推荐修改原始来源、编译指导或 `Scope settings`（范围设置），然后重新编译。

### 来源追踪与依据

每个生成的概念页面都应在 `sources:` 元数据中列出一个或多个来源页面的 slug。来源页面会指向保存的原始副本或来源 URL。`Ask` 和 `Solver` 的回答使用 `[[slug]]` 引用；应用会检查每个被引用的 slug 是否存在，并在不存在时发出警告。

这项检查验证的是 **存在性**，而不是被引用页面在逻辑上是否支持回答中的每一项主张。如果这一差别很重要，请阅读被引用页面及其来源。

### 本地优先，但并非完全离线

知识库会保存在你的机器上，但由 AI 驱动的操作仍会把选定内容发送给已配置的提供商：

- `Add source`（添加来源）会发送规范化后的来源内容，用于分析和生成。图像及扫描版/文本稀疏的 PDF 会先发送原始文件字节，以进行视觉转录。
- `Ask`（提问）会发送问题、检索到的 Wiki 页面和任何临时附件；图像或扫描版 PDF 附件也可能发送原始字节用于视觉处理。
- 深度 `Review`（检查）和概览重新生成会发送相关 Wiki 内容。
- 语义搜索会把页面分块和查询发送到 embeddings 端点。
- `Solver` 会发送对话、最新检索到的课程页面和附件。

浏览、本地标题/slug 匹配、BM25 关键词搜索和结构性 `Review` 无需 API 密钥也能工作。

## 启动应用并进入工作区

请先按照 [README 快速开始](README.zh-CN.md#快速开始) 完成安装，然后在知识库目录或其子目录中运行：

```bash
llmwiki
```

服务器会绑定到 `127.0.0.1:8000`，打开浏览器并显示 `Welcome`（欢迎页）。选择 `Enter workspace`（进入工作区）即可打开主应用。品牌链接会返回 Welcome 页面，但不会重置当前范围。

如需修改启动行为，可使用隐藏的 `serve` 别名：

```bash
llmwiki serve --port 8080 --no-open
llmwiki serve --host 127.0.0.1 --port 8080
```

除非你确实希望可信网络中的其他机器访问该应用，否则不要使用 `--host 0.0.0.0`。Web API 没有身份验证，并且包含写入和删除操作。

### 主界面

桌面端导航栏包含：

- `Workspace`（工作区）—— 当前范围内的搜索、页面列表和常用操作。
- `Ask`（提问）—— 基于 Wiki 的单轮问答，可附加临时文件。
- `Solver`（解题器）—— 持久化的课程问题多轮会话；仅在配置后显示。
- `Review`（检查）—— 结构检查和可选的 LLM 检查。
- `Add source`（添加来源）—— 编译文件或 URL。
- `Search`（搜索）—— 打开命令面板。

页眉会显示当前 `Scope`（范围）、面包屑、`AI ready`（AI 已就绪）或 `Local only`（仅本地）状态，以及浅色/深色主题控件。选择 Scope 控件会打开：

- `Overview`（概览）
- `Regenerate overview`（重新生成概览）
- `Scope settings`（范围设置）
- `Manage scopes`（管理范围）

当前范围和主题会保存在浏览器本地存储中。在窄屏上，主导航会移到底部，侧栏则以抽屉形式打开。

### 键盘快捷键

| 快捷键 | 操作 |
| --- | --- |
| `Cmd+K` / `Ctrl+K` | 在应用中的任何位置打开 `Search` |
| `/` | 未编辑其他字段时，聚焦 `Workspace` 搜索框 |
| `Enter` | 打开第一个搜索结果或操作 |
| `Esc` | 清空/关闭 `Search`，或关闭移动端抽屉 |
| `Cmd+Enter` / `Ctrl+Enter` | 提交 `Solver` 消息 |

## 理解和管理范围

范围（scope）是面向用户的组织单位；在磁盘上，它以斜杠分隔的 **section path** 保存，例如 `academic/example-course`。

可见性遵循前缀规则：

```text
General                    可看到所有页面
academic                   可看到所有学术课程中的页面
academic/example-course          只看到 example-course 中的页面
research                   可看到 research 及其所有子范围
```

范围是组织和检索边界，不是账户或权限边界。

### 选择现有范围

1. 打开 `Scope → Manage scopes`（范围 → 管理范围），或使用 `Workspace` 中的 `Manage scopes` 操作。
2. 在列表中选择一个范围名称。
3. 面板会关闭，`Workspace` 会在该范围内重新加载。

打开概念页面或来源页面，也会把当前范围切换到该页面所属的 section。应用会记住这一选择，供下次浏览器访问使用。需要跨整个知识库搜索或提问时，请在 Manage scopes 中选择 `General`。

### 创建范围

1. 打开 `Manage scopes`（管理范围）。
2. 在 `Create a scope`（创建范围）下输入 `Name`（名称）。
3. 选择 `Parent`（父级）。
4. 选择 `Create scope`（创建范围）。

若要创建 Research 或 Personal 这样的顶级分支，请把 `General` 设为父级；若要创建课程，请把 `Academic` 设为父级。当前 UI 中 Academic 课程是叶节点，不能再添加子范围；非 Academic 分支可以嵌套。

名称会保留 Unicode 字符和字母大小写。连续的空格或标点会在 section path 中转换为连字符。重复名称的检查不区分大小写。

**`Add source` 只会列出现有范围。** 请先创建目标范围；编译时不能直接输入一个新名称来创建范围。

`General` 和初始化时创建的 `Academic` 范围受保护，不能删除。新知识库只包含 Academic，不包含课程、课程内容或 Solver 配置。

## 添加并编译来源

在导航栏中选择 `Add source`（添加来源），或选择 `Workspace` 中同名的操作。

### 编译文件或 URL

1. 选择 `File`（文件）或 `URL` 标签页。
2. 对于文件，可拖放一个或多个项目，或选择 `choose files`（选择文件）；对于网页，请粘贴 HTTP 或 HTTPS URL。
3. 可选填 `Compilation guidance`（编译指导），例如“保留证明步骤”或“聚焦第 3 章”。同一批次中的所有项目都会使用相同指导。
4. 仔细检查 `Scope`（范围）和 `Destination`（目标位置）。
5. 选择 `Compile into _scope_`（编译到指定范围）。

多个项目会顺序处理，以免瞬间发出大量昂贵的模型请求。每一行最终会显示以下四种结果之一：

- **成功** —— 来源页面以及任何生成或更新的概念页面已写入。
- **跳过** —— 相同且完整的内容已存在于该范围中。
- **警告** —— 核心 Wiki 写入成功，但向量索引或概览刷新等后续步骤失败。
- **失败** —— 该项目未编译；其他已选项目仍会继续处理。

### 支持的来源类型

| 输入 | 扩展名或形式 | 加载行为和注意事项 |
| --- | --- | --- |
| Markdown / 文本 | `.md`、`.markdown`、`.txt` | 直接作为文本读取 |
| PDF | `.pdf` | 使用 PyMuPDF 提取文本；文本稀疏或扫描版 PDF 会切换到提供商视觉能力 |
| Word | `.docx` | 提取段落、标题和表格单元格；嵌入媒体不会作为单独的视觉输入 |
| PowerPoint | `.pptx` | 按幻灯片提取文本框；没有文字的图表或图像可能被遗漏 |
| 图像 | `.png`、`.jpg`、`.jpeg`、`.gif`、`.webp`、`.bmp`、`.tiff` | 使用提供商视觉能力；存储在 `raw/assets/` 下 |
| 网页 | `http://` 或 `https://` URL | 获取并清理可读正文；付费墙和客户端渲染页面可能失败 |

非图像本地文件会复制到 `raw/sources/`。如果同名文件已存在但字节不同，应用会在名称后添加八字符校验和后缀。URL 在来源追踪中仍保留为 URL，其规范化内容会缓存在 `.llmwiki/` 下。

### 重复检测和重新编译

重复检测使用文件/内容校验和与目标范围的组合。只有当上次导入并编译所生成的来源页面和所有概念页面仍然存在时，未更改的来源才会被跳过。即使下载文件被重命名，只要字节完全相同，仍会被识别为重复内容。

重新编译的方法：

- 在 Web 应用中，提供非空的 Compilation guidance，或先删除一个生成页面。
- 在 CLI 中使用 `llmwiki ingest SOURCE --force`。
- 使用 CLI 选项 `--vision` 强制对 PDF 进行视觉转录。

### 大型来源和提交行为

大于 `ingest_segment_max_tokens` 的来源会被划分为确定性的分段。每个分段都执行分析和生成阶段，其草稿会合并到同一条来源记录中。只有所有分段都成功后，概念页面和来源页面才会提交，因此编译中途发生模型错误不会部分改写 Wiki。不过，原始副本和规范化缓存此时可能已经创建。

主写入完成后，向量索引和概览重新生成会以尽力而为的方式执行。它们失败时会显示警告，但不会回滚新页面。请根据情况运行 `llmwiki reindex` 或使用 `Regenerate overview` 重试。

## 使用 Workspace 和 Search

`Workspace` 是当前范围的命令工作台。查询为空时，它会显示常用操作以及简短的概念和来源列表。输入文字后，会立即按标题/slug 过滤，并从后端请求排序后的概念结果。

操作组包含：

- `Add source`
- `Ask`
- `Review scope`（检查范围）
- `Refresh overview`（刷新概览）
- `Manage scopes`

选择 `Search` 或按 `Cmd/Ctrl+K`，会在命令面板中打开同一组范围内结果和操作。这个快捷键在整个应用中都可用，但结果仍受当前范围约束。

### 关键词与语义排序

后端搜索始终会针对概念标题和页面正文建立 BM25 关键词排序。满足以下四项要求时，它会通过 Reciprocal Rank Fusion 将关键词排序与语义向量融合：

1. `hybrid_search = true`。
2. 已安装 `[search]` extra。
3. 已配置 embeddings 密钥或 OpenAI 兼容端点。
4. 当前 `embed_model` 已有向量索引。

如果任何向量组件不可用，`Search` 会静默返回关键词结果。以后安装向量支持后，请运行：

```bash
llmwiki reindex
```

Search 会对概念页面进行语义排序。来源页面仍可通过 Workspace 的本地标题/slug 匹配出现。

如果结果看起来不完整，请先检查当前 `Scope`。选择父级范围或 `General` 来扩大检索范围。

## 阅读页面和概览

概念页面和来源页面会渲染为 Markdown，支持 KaTeX 数学公式和可点击的 `[[wikilinks]]`。面包屑显示当前 section。打开页面会更新当前范围；选择有效的 wikilink 会打开对应页面。

如果 wikilink 指向不存在的 slug，应用会把它标记为缺失并显示提示，而不是静默跳转。

### 概览

每个范围都有叙述性概览。打开 `Scope → Overview`（范围 → 概览）即可阅读。使用 Scope 菜单中的 `Regenerate overview` 或 Workspace 中的 `Refresh overview`，可以重写当前范围的概览。

编译来源后，应用会自动尝试刷新目标范围及其所有祖先范围，一直到 General。手动重新生成只针对当前范围，并且需要主提供商密钥。如果 General 概览为空，可以回退显示 `wiki/index.md` 中生成的目录。

删除页面或范围后，应用不会自动重写所有仍然存在的父级概览。如果摘要仍提到已删除内容，请重新生成受影响的父级概览。

## 提问

`Ask` 会根据当前范围生成一次单轮回答。

1. 打开 `Ask` 前，先选择所需范围。
2. 输入问题，或选择一个示例提示。
3. 可选使用 `Attach files`（附加文件）提供一次性上下文。
4. 选择 `Ask the model`（询问模型）。

应用会在当前范围内检索概念页面，将其装入配置的上下文预算，并连同问题一起发送给主提供商。如果 `rerank = true`，应用会额外调用一次模型，对更大的候选集重新排序，然后再构建最终上下文。

Ask 只接受上传文件，不接受 URL 附件；它支持与 Add source 相同的文件类型和加载器。文件会转换成临时上下文，不会复制到 `raw/`、写入 Wiki，或在请求结束后保留，但其中的内容仍会发送给提供商。

回答会显示：

- 渲染后的 Markdown 和数学公式；
- 模型引用且确实存在的 Wiki slug 所组成的 `References`（参考资料）列表；以及
- 对不存在的被引用 slug 的警告。

Web 应用不会保存 Ask 回答。如果某个回答应成为 `wiki/queries/` 下的文件，请使用 `llmwiki query --save`。

## 检查 Wiki 健康状况

打开 `Review`（检查）并选择 `Run checks`（运行检查）。结构性 Review 不需要 API 密钥，会报告：

- 没有 `sources:` 来源追踪的概念页面；
- 没有对应来源页面的来源追踪条目；
- 悬空的 `[[wikilinks]]`；以及
- 没有入站链接的孤立概念。

启用 `deep review (uses API)`（深度检查，使用 API）后，会额外执行一次 LLM 检查。它可能报告矛盾、缺失概念、不清晰或过时的材料、缺失的交叉引用、待调查问题、建议来源和数据缺口。

深度 Review 不会搜索网页，也不会修改页面。其结果只是供你评估的编辑建议。

## 删除页面和范围

删除操作是永久性的。请先备份重要材料。

### 删除单个概念页面

打开页面并选择垃圾桶图标。确认后，应用会删除概念页面及其向量条目。其来源账本仍然保留，但页面缺失会使该来源可以重新编译。

### 删除单个来源页面

打开来源页面并选择垃圾桶图标。应用会删除来源页面、对应的导入记录、规范化缓存以及由其拥有的原始文件。它还会从同一范围内概念的来源追踪中移除该来源，并删除任何因此不再有来源的概念。

其他位置的 wikilink 不会被重写；`Review` 会报告这些新出现的悬空链接。

### 删除范围

1. 打开 `Scope → Manage scopes`。
2. 选择未受保护范围旁的垃圾桶图标。
3. 准确输入界面显示的范围标签。
4. 确认 `Delete scope`（删除范围）。

这会删除后代概念/来源页面、匹配的账本记录和缓存/原始文件、概览、指令覆盖设置及向量条目。`General` 和 `Academic` 无法删除。

Solver 会话单独存放在 `.llmwiki/solver/` 下，不属于范围删除的一部分；请同时在 Solver 中删除不再需要的会话。如果删除了配置给 Solver 的范围，请清空或修改 `solver_section` 并重启；删除范围不会自动更新该设置。

## 自定义 Scope settings

打开 `Scope → Scope settings`（范围 → 范围设置），可编辑当前范围的 LLM 指令。可用卡片包括：

- `Purpose`（用途）
- `Schema`（模式）
- `Ingest · analysis`（导入 · 分析）
- `Ingest · generation`（导入 · 生成）
- `Answer · Ask`（回答 · 提问）
- `Solver · problem sets`（Solver · 习题集）
- `Lint · deep review`（Lint · 深度检查）

`General` 是共享的 `Baseline`（基线）。其他每个范围的卡片会显示为：

- `Inherited`（继承）—— 使用 General 基线；或
- `Override`（覆盖）—— 使用专门为该范围保存的文本。

继承机制有意保持浅层。如果范围没有自己的覆盖设置，它会直接回退到 General，而不会继承父分支。

卡片控件的行为如下：

- `Save`（保存）会存储编辑器中的当前文本。
- `Undo`（撤销）会把编辑器恢复到上次保存的文本；它只丢弃未保存的更改。
- `Copy`（复制）会把编辑器文本放入剪贴板。
- `Reset to general`（重置为 General）会删除该范围的覆盖设置并恢复 General 基线。
- `Also apply each Save to`（每次保存时也应用到）会把同一组件写入所有选中的范围。

编辑 General 基线会影响仍继承该组件的所有范围。Prompt 更改可能显著改变生成页面和回答，因此请一次只编辑一个组件，并用小型来源或简短问题进行测试。

## 使用 Solver

`Solver` 是持久化的多轮习题集聊天，固定在一个已配置范围内。它仅提供浏览器工作流。

### 启用 Solver

在 `.llmwiki/config.toml` 中设置一个非空 section path，然后重启服务器：

```toml
[settings]
solver_section = "academic/example-course"
```

新知识库中该设置为空，因此 Solver 默认隐藏。示例 checkout 已为 `academic/example-course` 启用它。

### 开始并使用会话

1. 打开 `Solver`。
2. 选择 `New session model`（新会话模型）。当相应密钥可用时，当前代码提供 `GPT-5.6 Sol` 和 `Claude Fable 5`。
3. 选择 `New session`（新建会话）。模型选择会锁定在该会话中。
4. 输入 `Problem or follow-up`（题目或追问）。
5. 可选附加 PDF 或图像。
6. 选择 `Solve`（解题），或按 `Cmd/Ctrl+Enter`。

每轮都会从 `solver_section` 检索最新概念页面，发送完整对话，并生成一份完整的 Markdown 解答。真实引用会显示在 References 中；缺失 slug 会触发与 Ask 相同的警告。当提供商返回相关内容时，折叠面板中会显示 `Reasoning summary`（推理摘要）。它不是原始思维链；某些成功响应不会包含摘要。

### 附件和持久化

Solver 接受 `.pdf`、`.png`、`.jpg`、`.jpeg`、`.gif` 和 `.webp`，每个文件最大 30 MB。附件不会导入并编译到 Wiki，但会随会话一起保存，并在后续轮次中作为对话历史重新发送。因此，包含大型附件的长会话可能较慢且费用较高。

会话会跨重启持久化保存在 `.llmwiki/solver/` 下。删除会话会移除其对话记录和附件。如果提供商调用失败，本次尝试不会追加到会话，新上传的文件也会被删除。

两个可选模型都会使用各自配置的最高推理强度。模型是否可用取决于你的提供商账户；仓库默认值不保证你拥有访问权限。

## 提供商密钥和模型

主提供商控制 `Add source`、`Ask`、深度 `Review` 和概览生成。在 `.llmwiki/config.toml` 中设置：

```toml
[settings]
provider = "openai"      # or "anthropic"
```

存储相应密钥：

```bash
llmwiki set-key openai YOUR_OPENAI_API_KEY
llmwiki set-key anthropic YOUR_ANTHROPIC_API_KEY
llmwiki set-key --show
```

`--show` 会遮蔽已存值。密钥以明文写入 `${XDG_CONFIG_HOME:-~/.config}/llmwiki/.env`；在 POSIX 系统上请求文件模式 `0600`，且绝不会写入知识库配置。Windows 不会以相同方式执行 Unix 所有权位。启动时，已存值会覆盖同名的 shell 环境变量。如果导出的密钥看似正确但身份验证仍失败，请检查已存密钥。更改密钥后请重启服务器。

未指定模型设置时，当前代码默认使用：

| 提供商 | 编译/回答默认模型 | 次级/低成本默认模型 |
| --- | --- | --- |
| OpenAI | `gpt-5.6-sol` | `gpt-5.6-sol` |
| Anthropic | `claude-opus-4-8` | `claude-haiku-4-5` |

如果账户无法访问默认模型，请覆盖 `compile_model`。对于 OpenAI，替代模型必须支持应用所用的 Responses API 推理参数，包括 `reasoning.effort = "high"`；当前配置指导要求 GPT-5.5+ 推理模型。`cheap_model` 预留给低成本操作，当前并非每条路径都会使用。

Solver 模型选择独立于主 `provider`：GPT 使用 `OPENAI_API_KEY`，Claude 使用 `ANTHROPIC_API_KEY`。若要同时提供两种选择，请设置两个密钥。

Embeddings 同样独立。语义搜索始终使用由 `embed_base_url`、`embed_api_key_env` 和 `embed_model` 配置的 OpenAI 兼容 embeddings 端点。Anthropic 密钥可以让 Ask 就绪，而语义搜索仍处于仅关键词模式。

## 配置参考

编辑 `.llmwiki/config.toml` 中的 `[settings]`，然后重启 Web 服务器。以下默认值描述的是新初始化的知识库；示例 checkout 覆盖了其中一部分。

| 设置 | 默认值 | 作用 |
| --- | --- | --- |
| `provider` | `"openai"` | 主聊天/编译提供商：`openai` 或 `anthropic` |
| `compile_model` | 提供商默认值 | 用于编译、Ask、深度 Review 和概览的模型 |
| `cheap_model` | 提供商默认值 | 预留的低成本模型设置 |
| `default_section` | `""` | 省略 `--section` 时的 CLI 导入目标，以及未指定范围的已保存查询所用的元数据 section；空值表示 General |
| `search_top_k` | `8` | 回答或 Solver 轮次保留的概念页面数 |
| `context_token_budget` | `60000` | Ask 和深度 Review 的近似上下文上限 |
| `hybrid_search` | `true` | 在 BM25 之外启用尽力而为的语义路径 |
| `embed_base_url` | 未设置 | OpenAI 兼容 embeddings 基础 URL；未设置时使用 OpenAI |
| `embed_api_key_env` | `"OPENAI_API_KEY"` | embeddings 身份验证读取的环境变量 |
| `embed_model` | `"text-embedding-3-small"` | 所有范围共用的单一 embedding 模型 |
| `vector_top_n` | `40` | 页面聚合/融合前考虑的向量分块数 |
| `rrf_k` | `60` | Reciprocal Rank Fusion 常数 |
| `rerank` | `false` | 在选择 Ask 上下文前增加一次 LLM 相关性排序 |
| `rerank_candidates` | `20` | 重新排序时使用的较大候选池 |
| `chunk_max_chars` | `1500` | 页面 section 为 embeddings 分块前允许的最大字符数 |
| `ingest_segment_max_tokens` | `60000` | 每个编译分段的近似最大来源大小 |
| `pdf_vision_min_chars_per_page` | `100` | 提取文本密度低于该值的 PDF 会使用视觉能力 |
| `request_timeout` | `300.0` | 普通操作的提供商超时秒数 |
| `ingest_request_timeout` | `3600.0` | Add source / ingest 期间每个请求的超时秒数 |
| `max_retries` | `2` | SDK 对瞬时提供商故障的重试次数 |
| `solver_section` | `""` | 固定 Solver 范围；空值会禁用 Solver |
| `solver_reasoning_effort` | `"xhigh"` | 没有锁定目录模型的旧会话所用推理强度 |
| `solver_request_timeout` | `600.0` | 每轮 Solver 的超时秒数 |

更改 `embed_model` 或稍后安装 `[search]` 后，请运行 `llmwiki reindex`。启用 `rerank` 会增加延迟，并为每次 Ask 或 Solver 轮次额外调用一次模型；如果重新排序失败，则使用正常检索顺序。

## 命令行参考

CLI 和 Web 应用共享相同的核心流水线，但功能并不完全相同。

| 命令 | 用途和重要选项 |
| --- | --- |
| `llmwiki` | 启动 Web 应用 |
| `llmwiki init [PATH]` | 创建缺失的知识库目录和种子文件，不覆盖现有内容 |
| `llmwiki ingest SOURCE` | 编译一个文件或 URL；支持 `--section`、`--vision` 和 `--force` |
| `llmwiki query QUESTION` | 在终端中提问；支持 `--section`、`--save` 和 `--format prose\|table\|slides` |
| `llmwiki search QUERY` | 搜索概念页面；支持 `--section` 和 `--top-k` |
| `llmwiki lint` | 结构性 Review；可添加 `--deep` 和/或 `--section` |
| `llmwiki overview` | 重新生成 General 或指定 `--section` 的概览 |
| `llmwiki reindex` | 建立/更新语义向量；`--force` 会重新嵌入未更改页面 |
| `llmwiki set-key` | 存储提供商密钥；`--show` 列出遮蔽后的已存密钥 |
| `llmwiki serve` | 使用 `--host`、`--port` 和 `--no-open` 控制启动行为 |

示例：

```bash
llmwiki ingest lecture.pdf --section academic/example-course
llmwiki ingest scan.pdf --section academic/example-course --vision --force
llmwiki query "Compare open and closed sets" --section academic/example-course --save --format table
llmwiki query "Summarize the course" --save --format slides
llmwiki search "boundary points" --section academic/example-course --top-k 5
llmwiki lint --section academic/example-course --deep
llmwiki overview --section academic/example-course
llmwiki reindex --force
```

保存的查询会写入 `wiki/queries/`。目前，它们不会出现在 Web 页面列表或生成的 `wiki/index.md` 中。以 `slides` 格式保存时，会写入带有 `marp: true` 的 Marp 风格 Markdown。

`llmwiki lint` 只有在发现 error 时才以状态码 1 退出；仅有 warning 和 info 项时仍返回状态码 0。

## 存储备份和 Obsidian

### 完整目录结构

| 路径 | 内容 |
| --- | --- |
| `raw/sources/` | 复制的非图像文件 |
| `raw/assets/` | 已导入的图像文件 |
| `wiki/concepts/<section>/` | 生成的概念页面 |
| `wiki/sources/<section>/` | 生成的来源/来源追踪页面 |
| `wiki/queries/` | 通过 `--save` 保存的 CLI 回答 |
| `wiki/overview.md` | General 概览 |
| `wiki/overviews/<section>.md` | 各范围的概览 |
| `wiki/index.md` | 重新生成的概念/来源目录 |
| `wiki/log.md` | 仅追加的操作日志 |
| `wiki/purpose.md`、`wiki/schema.md` | General 指令基线 |
| `.llmwiki/config.toml` | 知识库设置，绝不存放 API 密钥 |
| `.llmwiki/state.json` | 导入校验和与来源追踪账本 |
| `.llmwiki/normalized/` | 规范化 Markdown 缓存 |
| `.llmwiki/lancedb/` | 可选向量索引 |
| `.llmwiki/prompts/` | 可编辑的 General 操作 prompt |
| `.llmwiki/sections/` | 各范围的指令覆盖设置 |
| `.llmwiki/solver/` | Solver 对话记录和附件 |
| `~/.config/llmwiki/.env` | 知识库之外持久化保存的 API 密钥 |

### 备份和恢复

应用没有内置的导出、备份、恢复或同步命令。如需完整备份，请停止服务器并复制整个知识库目录。这样可保留原始文件、生成页面、配置、状态、覆盖设置和 Solver 会话。全局密钥文件位于知识库之外，通常应重新创建，而不是复制。

单独复制 `wiki/` 可以得到便于携带的阅读版本，但不包含原始来源文件、导入状态、设置和 Solver 会话。`.llmwiki/lancedb/` 可以通过 `llmwiki reindex` 重新生成；若要精确续接工作，其他状态可能很重要。

### 与 Obsidian 配合使用

在 Obsidian 中打开 **知识库根目录**。生成页面位于 `wiki/` 下，而图像来源页面可能链接到该目录之外的 `raw/assets/`。Obsidian 可直接识别这些 Markdown 和 wikilink。无需修改文件即可使用图谱和反向链接视图；Marp 幻灯片和 Dataview 查询则需要各自对应的 Obsidian 插件。

请把 `wiki/index.md`、`wiki/log.md` 和生成的概览视为由应用管理。手动更改可能被覆盖，或与导入账本不一致。

## 隐私和安全

- 切勿把 API 密钥放入 `.llmwiki/config.toml`、文档、Git、截图或 issue 报告。
- `llmwiki set-key` 会把密钥存储在知识库之外，并在 POSIX 系统上请求 `0600` 文件模式，但其值仍以明文保存在磁盘上。Windows 不会以相同方式执行 Unix 所有权位。
- 直接把明文密钥作为命令行参数传入，可能使其保留在 shell 历史中。如果你的 shell 会记录命令，请优先使用受保护的密钥提示或临时环境变量。
- 编译敏感材料前，请检查提供商的数据处理政策。
- Solver 对话记录和附件会持久化保存在 `.llmwiki/solver/` 下。
- 新初始化的知识库不会全面忽略 Git 中的 Solver 和向量状态。提交包含私人材料的知识库前，请检查 `git status` 和忽略规则。
- `raw/` 和 `wiki/` 按设计也可能包含敏感来源文本。
- 除非你已经添加合适的外部访问控制层，否则请保持默认 loopback 主机。范围不提供授权功能。

## 故障排除

| 症状 | 检查事项 |
| --- | --- |
| `command not found: llmwiki` | 激活安装该软件包的虚拟环境。 |
| “No llmwiki vault found” | 运行 `llmwiki init PATH`，然后在该目录或其后代目录中工作。 |
| Web UI 依赖错误 | 在仓库根目录运行 `python -m pip install ".[web]"`。 |
| 应用显示 `Local only` | 设置与 `provider` 匹配的密钥，重启服务器，并查看 `llmwiki set-key --show`。 |
| 导出的密钥正确但仍失败 | 已存密钥会覆盖 shell 值；请更新或检查已存密钥。 |
| `model_not_found`、权限或访问错误 | 把 `compile_model` 设为可访问且兼容的模型。OpenAI 覆盖模型必须支持应用的 Responses API 推理参数。 |
| 不支持的文件类型 | 使用准确的受支持扩展名或 HTTP(S) URL。只有在文件格式确实匹配时才重命名。 |
| 来源显示 `skipped` | 该内容在此范围中已完整存在。添加指导、删除生成页面，或使用 CLI `--force`。 |
| 扫描版 PDF 不完整 | 使用 CLI `--vision` 重试，或提高 `pdf_vision_min_chars_per_page`。 |
| `Add source` 很慢或超时 | 大型/视觉来源可能需要多次调用。请重试、拆分扫描文件，或调整 `ingest_request_timeout`。 |
| 没有语义结果 | 安装 `[search]`、配置 embeddings 密钥/端点，然后运行 `llmwiki reindex`。关键词搜索仍应可用。 |
| `Search` 或 `Ask` 找不到预期页面 | 先检查 Scope；切换到父级范围或 General。 |
| 导入并编译完成但显示向量/概览警告 | 页面已经提交。运行 `llmwiki reindex`，或单独重新生成概览。 |
| `Solver` 未显示 | 设置 `solver_section` 并重启。新知识库默认禁用它。 |
| Solver 模型被禁用 | 存储该模型旁标明的环境密钥；现有会话无法切换模型。 |
| Solver 拒绝上传 | 使用 PDF 或受支持的图像，并确保每个文件不超过 30 MB。 |
| 端口 8000 被占用 | 运行 `llmwiki serve --port 8080 --no-open`。 |
| 可编辑安装后出现 `ModuleNotFoundError: llmwiki` | 正常重新安装：`python -m pip install --force-reinstall --no-deps .`。 |
| 开发 checkout 中前端路由返回 404 | 运行 `make web-install` 和 `make web-build`，然后重启。 |

提供商错误会直接呈现，但不会显示原始应用 traceback。失败的 Ask 或 Solver 调用不会静默切换提供商。

## 当前限制

- 应用为单用户设计，没有内置身份验证或授权。
- 没有内置的知识库归档导入、批量目录导入、导出、备份、恢复或同步工作流。
- Web 与 CLI 功能不同：强制重新导入/视觉转写、保存/格式化回答和重新索引控制偏向 CLI；范围管理、Scope settings 和 Solver 偏向浏览器。
- 引用验证只检查 Wiki slug 是否存在，不检查主张是否由该页面蕴含。
- 页面导航以 slug 为基础。不同范围或页面类型中相同的 slug 可能产生歧义，因此请优先使用不同的概念/来源名称。
- DOCX/PPTX 加载器侧重可提取文本；只有视觉内容时，可能需要单独导入图像或 PDF。
- URL 提取可能因身份验证墙、付费墙、反机器人措施，或内容只在客户端渲染后出现而失败。
- `Add source` 和 `Ask` 不强制执行专用的应用级上传大小限制；实际限制仍来自内存、超时和提供商 payload 规则。
- 当上游来源发生变化时，生成的知识可能过时。请重新编译已更改材料，并定期运行 `Review`。
