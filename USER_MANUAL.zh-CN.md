# My Second Brain by YFW — 用户手册

[English →](USER_MANUAL.md) · **简体中文**

本手册介绍安装、浏览器与 CLI 工作流、配置、存储、隐私和故障排除。Python 发行包名为
`my-second-brain-by-yfw`；导入命名空间、命令和配置目录继续使用 `llmwiki`。

## 目录

1. [安装、初始化和启动](#安装初始化和启动)
2. [应用的工作原理](#应用的工作原理)
3. [使用浏览器界面](#使用浏览器界面)
4. [理解和管理范围](#理解和管理范围)
5. [添加并编译来源](#添加并编译来源)
6. [使用 Workspace 和 Search](#使用-workspace-和-search)
7. [阅读页面、Ask 与概览](#阅读页面ask-与概览)
8. [Review 与删除内容](#review-与删除内容)
9. [自定义范围指令](#自定义范围指令)
10. [模型服务密钥与模型](#模型服务密钥与模型)
11. [配置参考](#配置参考)
12. [命令行参考](#命令行参考)
13. [存储、备份与 Obsidian](#存储备份与-obsidian)
14. [隐私与安全](#隐私与安全)
15. [故障排除与限制](#故障排除与限制)

## 安装、初始化和启动

请使用 Python 3.11 或更高版本。公开版本支持的流程是从克隆的仓库安装，不假定通过包索引
安装。

如果当前环境已经安装了旧发行包 `second-brain-by-yfw`，请先卸载它，再安装更名后的发行包：

```bash
python -m pip uninstall second-brain-by-yfw
```

必须先执行卸载，因为新旧发行包提供相同的 `llmwiki` 包和命令。

macOS 或 Linux：

```bash
git clone https://github.com/EricWcr7/My-Second-Brain-by-YFW.git
cd My-Second-Brain-by-YFW
python3 -m venv .venv
source .venv/bin/activate
python -m pip install ".[web]"
llmwiki init .
llmwiki set-key openai YOUR_OPENAI_API_KEY
llmwiki
```

Windows PowerShell：

```powershell
git clone https://github.com/EricWcr7/My-Second-Brain-by-YFW.git
cd My-Second-Brain-by-YFW
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install ".[web]"
llmwiki init .
llmwiki set-key openai YOUR_OPENAI_API_KEY
llmwiki
```

请替换密钥占位符，并且永远不要提交真实密钥。如果更愿意使用环境变量，请在启动前导出
`OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY`，并跳过 `set-key`。

`llmwiki init .` 具有幂等性：它只创建缺失的目录和种子文件，不会替换已有内容。任何包含
`.llmwiki/` 的目录都是知识库目录。命令会从当前目录向上查找该标记，因此也可以在知识库
目录的子目录中执行。

运行 `llmwiki` 会绑定到 `127.0.0.1:8000`、打开浏览器并显示 Welcome 页面。选择
**Enter workspace**。如需无界面启动或更换端口，请使用：

```bash
llmwiki serve --port 8080 --no-open
```

除非已经添加外部身份验证和授权层，否则请保持回环地址。本应用自身不提供这两项功能。

## 应用的工作原理

应用把来源材料编译为持久的 Markdown 知识库：

```text
文件或 URL
    ↓ 标准化与分析
已存储的来源 + 生成的来源页
    ↓ 提取并合并概念
相互链接的概念页
    ↓ 在当前范围内检索
Search、Ask、Review 和概览
```

### 知识库目录分层

| 分层 | 用途 |
| --- | --- |
| `raw/` | 已导入文件和图像的本地副本 |
| `wiki/` | 概念、来源页、已保存的 CLI 回答、概览、索引和日志 |
| `.llmwiki/` | 设置、导入状态、缓存、可选向量和指令覆盖 |

生成的页面使用 YAML frontmatter、标准 Markdown、`[[wikilinks]]` 和 LaTeX 数学公式。
你可以手动编辑，但后续导入可能合并或替换生成内容。为了得到可重复的结果，应修改来源或
对应指令，然后重新编译。

### 来源追踪与依据

概念页会在 `sources:` 元数据中列出来源页 slug；来源页则指向存储的原始文件或 URL。
Ask 会验证每个被引用的 `[[slug]]`，并在页面不存在时警告。

引用验证只能证明页面存在，不能证明该页面在逻辑上支持每项陈述。准确性要求较高时，应
检查引用页面和原始来源。

### 本地优先，但并非完全离线

知识库目录保存在本机，但配置的模型服务会收到 AI 操作所需的数据：

- Add source 会发送标准化文本用于分析和生成；图像以及文字稀少的扫描 PDF 可能发送原始
  字节用于视觉转录。
- Ask 会发送问题、检索到的 Wiki 页面，以及临时附件中的文本或视觉输入。
- 深度 Review 和概览重新生成会发送相关 Wiki 内容。
- 语义搜索会向嵌入端点发送页面片段和查询。

浏览页面、按标题/slug 匹配、BM25 Search 和结构 Review 不需要模型服务密钥。

## 使用浏览器界面

桌面导航包含：

- **Workspace** —— 按范围搜索、页面列表和常用操作。
- **Ask** —— 一次有 Wiki 依据的提问，可附加临时文件。
- **Review** —— 结构检查以及可选的模型辅助审查。
- **Add source** —— 编译文件或 URL。
- **Search** —— 打开命令面板。

页眉显示当前 **Scope**、面包屑、模型服务就绪状态和主题控件。Scope 菜单可打开概览、
重新生成概览、范围设置和范围管理。当前范围和主题保存在浏览器 local storage 中。在窄屏
设备上，主导航会移到底部，侧栏会变为抽屉。

### 键盘快捷键

| 快捷键 | 操作 |
| --- | --- |
| `Cmd+K` / `Ctrl+K` | 打开 Search |
| `/` | 在其他输入框未激活时聚焦 Workspace 搜索 |
| `Enter` | 打开第一个 Search 结果或操作 |
| `Esc` | 清空或关闭 Search；关闭移动端抽屉 |

## 理解和管理范围

范围在磁盘上保存为斜杠分隔的 section path。可见性遵循前缀规则：

```text
General                         可看到所有页面
academic                        可看到整个学术分支
academic/example-course         只看到该子范围
projects                        可看到该分支及全部后代
```

范围用于组织导航和检索，不是账户或权限边界。

### 选择或创建范围

1. 打开 **Scope → Manage scopes**。
2. 选择已有名称；或者输入新 **Name** 并选择 **Parent**。
3. 添加范围时选择 **Create scope**。

名称会保留 Unicode 和字母大小写，连续空格或标点会在路径中转成连字符；重复检查不区分
大小写。打开页面也会把当前范围切换到该页面的分区。如需扩大到整个知识库目录，请选择
`General`。

`General` 和初始化时创建的 `Academic` 分支受保护，不能删除。当前界面把 `Academic` 的
子范围视为叶节点；其他分支可以继续嵌套。使用 Add source 前要先创建目标范围。

## 添加并编译来源

打开 **Add source**，选择 **File** 或 **URL**，确认目标，然后选择 **Compile**。可选的
Compilation guidance 会应用到该批次的每一项。多个文件会依次处理。

可能的结果包括：

- **Success** —— 已写入来源页和概念页。
- **Skipped** —— 相同且完整的内容已存在于该范围。
- **Warning** —— 核心写入成功，但索引或概览刷新等后续步骤失败。
- **Failure** —— 当前项未编译；后续项继续处理。

### 支持的输入

| 输入 | 扩展名或形式 | 说明 |
| --- | --- | --- |
| Markdown / 文本 | `.md`、`.markdown`、`.txt` | 直接读取 |
| PDF | `.pdf` | 使用 PyMuPDF 提取文本；扫描页或文字稀少页面改用视觉输入 |
| Word | `.docx` | 提取段落、标题和表格单元格文本 |
| PowerPoint | `.pptx` | 按幻灯片提取文本框内容 |
| 图像 | `.png`、`.jpg`、`.jpeg`、`.gif`、`.webp`、`.bmp`、`.tiff` | 使用模型视觉能力；存入 `raw/assets/` |
| 网页 | HTTP 或 HTTPS URL | 提取可读正文；访问限制和仅客户端渲染的页面可能失败 |

非图像文件会复制到 `raw/sources/`。同名但内容不同的文件会获得校验和后缀。URL 会在
来源追踪中保持为 URL，标准化内容缓存到 `.llmwiki/`。

重复检测使用内容和目标范围，并检查先前生成的页面是否仍然存在。如需再次编译，可以添加
非空 guidance、删除一个生成页面，或使用 `llmwiki ingest SOURCE --force`。CLI 的
`--vision` 会强制使用 PDF 视觉转录。

大型来源会按 `ingest_segment_max_tokens` 分段。只有所有分段成功后才提交 Wiki 页面，
但原始副本或标准化缓存可能已经创建。向量和概览更新属于尽力而为的后续步骤；可使用
`llmwiki reindex` 或 **Regenerate overview** 重试。

## 使用 Workspace 和 Search

Workspace 显示当前范围内的操作和页面。输入文字后会立即按标题和 slug 过滤，并向后端请求
排序后的概念结果。**Search** 或 `Cmd/Ctrl+K` 会在命令面板中打开相同的范围内结果。

BM25 关键词排序始终可用。满足以下所有条件时，语义向量也会参与排序：

1. `hybrid_search = true`。
2. 已安装 `[search]` 扩展依赖。
3. 已配置嵌入密钥或兼容端点。
4. 当前 `embed_model` 已有向量索引。

从仓库检出目录安装，并在知识库目录中构建：

```bash
python -m pip install ".[web,search]"
llmwiki reindex
```

任一向量组件不可用时，Search 会返回 BM25 结果。来源页仍可能通过本地标题/slug 匹配
出现。如果缺少预期结果，先扩大当前范围。

## 阅读页面、Ask 与概览

概念页和来源页会渲染 Markdown、KaTeX 数学公式和可点击 wikilink。缺失的 wikilink 会被
标记，而不是静默跳转。

每个范围都有叙述性概览。打开 **Scope → Overview** 阅读，使用
**Regenerate overview** 刷新当前范围。导入会尝试刷新目标范围及其祖先。删除不会重写
所有仍存在的概览，因此父范围仍提到被删除内容时，需要手动重新生成。

### Ask

1. 选择预期范围。
2. 打开 **Ask** 并输入问题。
3. 可选择为本次请求附加文件。
4. 选择 **Ask the model**。

Ask 会检索概念页，把它们压缩到上下文预算内，然后发送给主模型服务。当
`rerank = true` 时，会先增加一次调用来重新排列更大的候选集合。附件使用导入加载器，
但只在本次请求中存在：它们不会复制到 `raw/` 或写入 Wiki，不过内容仍会发送给模型服务。

浏览器不会保存回答。使用 `llmwiki query --save` 可在 `wiki/queries/` 下创建文件。CLI
还支持 `--format prose`、`table` 或 `slides`。

## Review 与删除内容

结构 Review 会报告缺少来源追踪的概念、缺失的来源记录、悬空 wikilink 和没有入站链接的
概念，不需要密钥。**Deep review** 会增加模型调用，用于发现矛盾、缺口、过时内容和后续
建议；它不会浏览网络或修改页面。

删除不可撤销，请先备份重要材料。

- 删除概念页会移除该页面和对应向量。来源账本仍会保留，使该来源可以再次编译。
- 删除来源页会移除来源页、对应导入记录、标准化缓存和由应用管理的原始文件；同时移除同一
  范围内的来源追踪，并删除因此失去全部来源的概念。
- 删除不受保护的范围会移除其后代概念和来源、相关状态/缓存/原始文件、概览、指令覆盖和
  向量。确认时必须准确输入显示的标签。

其他页面中的链接不会被重写。删除后应运行 Review，并重新生成受影响的概览。

## 自定义范围指令

打开 **Scope → Scope settings**，可以检查或编辑六类指令组件：

- **Purpose**
- **Schema**
- **Ingest · analysis**
- **Ingest · generation**
- **Answer · Ask**
- **Lint · deep review**

`General` 是共享基线。其他范围要么有自己的覆盖，要么直接回退到 General；不会从最近的
父范围继承。操作基线位于 `.llmwiki/prompts/`，文档基线位于 `wiki/purpose.md` 和
`wiki/schema.md`，范围覆盖位于 `.llmwiki/sections/`。

**Save** 写入编辑器内容，**Undo** 丢弃未保存编辑，**Copy** 复制文本，
**Reset to general** 删除范围覆盖。多范围 Save 控件会把同一组件写入每个已选范围。提示词
修改可能显著改变生成页面和回答，因此在大范围应用前，应先用一个小来源或问题测试单项修改。

## 模型服务密钥与模型

主模型服务控制导入、Ask、深度 Review 和概览生成。在 `.llmwiki/config.toml` 中选择：

```toml
[settings]
provider = "openai"      # 或 "anthropic"
```

存储或检查密钥：

```bash
llmwiki set-key openai YOUR_OPENAI_API_KEY
llmwiki set-key anthropic YOUR_ANTHROPIC_API_KEY
llmwiki set-key --show
```

持久化密钥以明文保存在 `${XDG_CONFIG_HOME:-~/.config}/llmwiki/.env`，并请求 POSIX
权限模式 `0600`；`--show` 会遮蔽值。持久化值会覆盖从 shell 继承的同名变量。如果希望以
shell 环境为准，就不要存储该密钥。修改密钥后请重启服务器。

省略 `compile_model` 和 `cheap_model` 时，每个模型服务使用项目配置的默认模型。只有在
账户能够访问且模型支持应用所需 API 功能时才应覆盖模型。

嵌入设置独立于主模型服务。语义搜索通过 `embed_base_url`、`embed_api_key_env` 和
`embed_model` 配置的 OpenAI 兼容端点运行。Anthropic 可以支持主工作流，而 Search
仍保持仅 BM25，或使用单独配置的嵌入服务。

## 配置参考

编辑 `.llmwiki/config.toml` 中的 `[settings]`，然后重启服务器。

| 设置 | 默认值 | 作用 |
| --- | --- | --- |
| `provider` | `"openai"` | 主模型服务：OpenAI 或 Anthropic |
| `compile_model` | 模型服务默认值 | 导入、Ask、深度 Review 和概览所用模型 |
| `cheap_model` | 模型服务默认值 | 预留的低成本模型设置 |
| `default_section` | `""` | CLI 导入目标；空值表示 General |
| `search_top_k` | `8` | 回答上下文保留的概念页数量 |
| `context_token_budget` | `60000` | 回答/审查上下文的大致上限 |
| `hybrid_search` | `true` | 在 BM25 之外尽力使用向量 |
| `embed_base_url` | 未设置 | 兼容的嵌入 base URL；未设置时使用 OpenAI |
| `embed_api_key_env` | `"OPENAI_API_KEY"` | 嵌入鉴权读取的环境变量 |
| `embed_model` | `"text-embedding-3-small"` | 全部范围使用的嵌入模型 |
| `vector_top_n` | `40` | 聚合/融合前考虑的向量片段数 |
| `rrf_k` | `60` | Reciprocal Rank Fusion 常数 |
| `rerank` | `false` | 在选择 Ask 上下文前增加模型相关性排序 |
| `rerank_candidates` | `20` | 重新排序时使用的候选池 |
| `chunk_max_chars` | `1500` | 嵌入时进一步分块前的最大字符数 |
| `ingest_segment_max_tokens` | `60000` | 每个导入分段的大致最大来源大小 |
| `pdf_vision_min_chars_per_page` | `100` | 低于此文字密度的 PDF 使用视觉输入 |
| `request_timeout` | `300.0` | 普通模型请求超时秒数 |
| `ingest_request_timeout` | `3600.0` | 导入期间每次请求的超时秒数 |
| `max_retries` | `2` | SDK 对暂时性失败的重试次数 |

更改嵌入模型或安装搜索扩展依赖后，运行 `llmwiki reindex`。启用 rerank 会增加延迟，并让
每次 Ask 多一次模型调用；失败时会回退到原始检索顺序。

## 命令行参考

| 命令 | 用途和重要选项 |
| --- | --- |
| `llmwiki` | 启动浏览器应用 |
| `llmwiki init [PATH]` | 创建缺失目录和种子文件，不覆盖已有内容 |
| `llmwiki ingest SOURCE` | 编译一个文件或 URL；`--section`、`--vision`、`--force` |
| `llmwiki query QUESTION` | 提问；`--section`、`--save`、`--format prose\|table\|slides` |
| `llmwiki search QUERY` | 搜索概念；`--section`、`--top-k` |
| `llmwiki lint` | 结构 Review；可加 `--deep` 和 `--section` |
| `llmwiki overview` | 重新生成 General 或指定 `--section` 的概览 |
| `llmwiki reindex` | 更新语义向量；`--force` 会重新嵌入未变化页面 |
| `llmwiki set-key` | 存储密钥；`--show` 列出已遮蔽的持久化值 |
| `llmwiki serve` | 使用 `--host`、`--port` 和 `--no-open` 控制启动 |

示例：

```bash
llmwiki ingest notes.md --section projects/learning-notes
llmwiki ingest scanned-handout.pdf --section projects/learning-notes --vision --force
llmwiki query "How should I schedule retrieval practice?" --section projects/learning-notes --save --format table
llmwiki search "spaced repetition" --section projects/learning-notes --top-k 5
llmwiki lint --section projects/learning-notes --deep
llmwiki overview --section projects/learning-notes
llmwiki reindex --force
```

已保存的 query 位于 `wiki/queries/`，不会出现在浏览器页面列表或生成的索引中。保存的
`slides` 输出使用 Marp 风格 Markdown。只有发现 error 时，`llmwiki lint` 才会以状态 1
退出。

## 存储、备份与 Obsidian

| 路径 | 内容 |
| --- | --- |
| `raw/sources/` | 已复制的非图像文件 |
| `raw/assets/` | 已导入图像 |
| `wiki/concepts/<section>/` | 生成的概念 |
| `wiki/sources/<section>/` | 来源与追踪页面 |
| `wiki/queries/` | 通过 `--save` 保存的 CLI 回答 |
| `wiki/overview.md` | General 概览 |
| `wiki/overviews/<section>.md` | 范围概览 |
| `wiki/index.md` | 生成的目录 |
| `wiki/log.md` | 只追加的操作日志 |
| `wiki/purpose.md`、`wiki/schema.md` | General 文档基线 |
| `.llmwiki/config.toml` | 知识库设置，绝不保存 API 密钥 |
| `.llmwiki/state.json` | 导入校验和与来源账本 |
| `.llmwiki/normalized/` | 标准化 Markdown 缓存 |
| `.llmwiki/lancedb/` | 可选向量索引 |
| `.llmwiki/prompts/` | 可编辑的 General 操作提示词 |
| `.llmwiki/sections/` | 范围指令覆盖 |
| `~/.config/llmwiki/.env` | 知识库目录外的持久化密钥 |

应用没有内置备份、恢复、导出或同步命令。如需精确备份，请停止服务器并复制整个知识库
目录。向量索引可以重建；原始材料、状态账本、设置和覆盖对于完整继续使用很重要。模型服务
密钥应单独重新配置。

在 Obsidian 中打开**知识库目录根目录**。生成页面位于 `wiki/`，图像链接可以指向
`raw/assets/`。Markdown 和 wikilink 可直接工作；Marp 或 Dataview 内容需要对应插件。
生成的索引、日志和概览应视为由应用管理。

## 隐私与安全

- 不要把密钥写入知识库配置、文档、Git、截图或 issue 报告。
- 在命令行中传入密钥可能把它留在 shell 历史记录中；适合时请使用环境变量或受保护的密钥
  输入流程。
- 即使 POSIX 权限受到限制，持久化密钥在磁盘上仍是明文。
- 导入敏感材料前请审查模型服务的数据处理政策。
- `raw/`、`wiki/` 和覆盖文件可能包含来源文本或指令。在提交任何已初始化的知识库目录前，
  请检查 `git status` 和忽略规则。
- 保持默认回环地址。范围不提供访问控制。

仓库中的 `brain-network.png` 插图由 EricWcr7 创作，并按仓库的
[MIT 许可证](LICENSE)发布。第三方字体和库保留各自条款，详见
[第三方声明](THIRD_PARTY_NOTICES.md)。重新分发或用于商业场景前，应单独审查 PyMuPDF 的
许可条款。

## 故障排除与限制

| 现象 | 检查项 |
| --- | --- |
| `command not found: llmwiki` | 激活安装时使用的虚拟环境。 |
| “No llmwiki vault found” | 运行 `llmwiki init PATH`，然后在该目录或其后代中工作。 |
| Web 依赖错误 | 在仓库检出目录运行 `python -m pip install ".[web]"`。 |
| 应用显示 **Local only** | 设置与 `provider` 匹配的密钥、重启，并检查 `llmwiki set-key --show`。 |
| 导出的密钥似乎被忽略 | 持久化值会覆盖它；更新持久化密钥或删除对应条目。 |
| 模型访问错误 | 选择当前账户可访问且兼容的模型。 |
| 不支持的来源 | 使用列表中的扩展名或 HTTP(S) URL。 |
| 来源被跳过 | 添加 guidance、移除一个生成页面，或使用 CLI `--force`。 |
| 扫描 PDF 内容不完整 | 使用 CLI `--vision` 重试，或调整视觉阈值。 |
| 导入很慢 | 大型或视觉来源可能需要多次调用；拆分来源或调整导入超时。 |
| 没有语义结果 | 安装 `[search]`、配置嵌入，然后运行 `llmwiki reindex`；BM25 仍可用。 |
| Search 或 Ask 缺少页面 | 扩大当前范围。 |
| 导入后出现索引或概览警告 | 核心页面已写入；单独重建索引或重新生成概览。 |
| 端口 8000 被占用 | 运行 `llmwiki serve --port 8080 --no-open`。 |
| 缺少生产前端 | 运行 `make web-install && make web-build`，然后重启。 |

当前限制包括：仅支持单用户且没有内置身份验证；没有批量目录导入、归档导入、备份、恢复、
导出或同步命令；slug 重复时基于 slug 的导航可能有歧义；DOCX 和 PPTX 提取以文本为主；
存在访问限制或依赖客户端渲染时，URL 提取可能失败。生成的知识也可能过时，应重新编译已变化
的来源并定期运行 Review。
