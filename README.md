# 知识图谱构建 Demo

这个项目用于从非结构化 `.txt` 文本中抽取知识图谱三元组，并输出 CSV 和 HTML 可视化结果。项目也支持把抽取结果可选写入 Neo4j 数据库。

## 功能流程

```text
非结构化文本
  -> 文本读取与切分
  -> LLMFactory 选择模型
  -> Prompt 构造
  -> LLM 抽取三元组
  -> JSON / Pydantic 解析
  -> 保存 CSV
  -> 生成 PyVis HTML 可视化
  -> 可选写入 Neo4j
```

## 项目结构

```text
.
├── KGcreator.py            # CLI 入口，串联完整流程
├── pyproject.toml          # 项目依赖配置
├── src/
│   ├── config.py           # LLM 配置和 prompt 模板
│   ├── llm_factory.py      # 根据配置创建 LangChain LLM 实例
│   ├── source_reader.py    # 读取 .txt 文件并切分文本
│   ├── kg_extract.py       # 调用 LLM 并解析三元组
│   ├── models.py           # Pydantic 数据模型
│   ├── visualize.py        # 生成 PyVis HTML 知识图谱
│   └── neo4j_writer.py     # 写入 Neo4j 数据库
├── tests/
│   └── test_pipeline.py    # 核心流程回归测试
└── txt/
    └── test1.txt           # 示例文本文件
```

## 环境准备

项目使用 Python 3.13，并通过 `uv` 管理依赖。

安装依赖：

```powershell
uv sync
```

核心依赖包括：

- `langchain`
- `langchain-openai`
- `langchain-deepseek`
- `neo4j`
- `pandas`
- `pydantic`
- `pydantic-settings`
- `pyvis`

## 配置模型 Key

使用 OpenAI：

```powershell
$env:OPENAI_API_KEY = "your_openai_api_key"
```

使用 DeepSeek：

```powershell
$env:DEEPSEEK_API_KEY = "your_deepseek_api_key"
```

也可以用 `setx` 持久保存到 Windows 用户环境变量：

```powershell
setx OPENAI_API_KEY "your_openai_api_key"
setx DEEPSEEK_API_KEY "your_deepseek_api_key"
```

## 支持的模型配置

模型别名在 `src/config.py` 中维护，当前内置：

- `openai_gpt4o`：默认配置，使用 `gpt-4o-mini`
- `openai_text_davinci`：OpenAI completion 模型配置
- `deepseek_chat`：DeepSeek chat 模型配置

新增模型时，优先在 `AppConfig.llm_configs` 中增加新的 `LLMConfig`。如果是新的 provider，再到 `src/llm_factory.py` 增加对应构建逻辑。

## 运行

确保输入文件是非空 `.txt` 文件，例如 `txt/test1.txt`。

使用默认 OpenAI 配置：

```powershell
uv run python KGcreator.py `
  --source txt\test1.txt `
  --model openai_gpt4o `
  --csv output\triples.csv `
  --html output\graph.html
```

使用 DeepSeek：

```powershell
uv run python KGcreator.py `
  --source txt\test1.txt `
  --model deepseek_chat `
  --csv output\triples.csv `
  --html output\graph.html
```

## 写入 Neo4j

默认情况下，程序只生成 CSV 和 HTML，不会写入 Neo4j。

如果要写入 Neo4j，需要增加 `--write-neo4j`：

```powershell
uv run python KGcreator.py `
  --source txt\test1.txt `
  --model openai_gpt4o `
  --csv output\triples.csv `
  --html output\graph.html `
  --write-neo4j `
  --neo4j-uri bolt://localhost:7687 `
  --neo4j-user neo4j `
  --neo4j-password your_neo4j_password
```

也可以通过环境变量配置 Neo4j：

```powershell
$env:NEO4J_URI = "bolt://localhost:7687"
$env:NEO4J_USER = "neo4j"
$env:NEO4J_PASSWORD = "your_neo4j_password"
$env:NEO4J_DATABASE = "neo4j"
```

然后运行：

```powershell
uv run python KGcreator.py `
  --source txt\test1.txt `
  --write-neo4j
```

Neo4j 写入逻辑在 `src/neo4j_writer.py` 中。写入时会：

- 创建实体唯一约束
- 将 `subject` 和 `object` 合并为 `Entity` 节点
- 用 `RELATED_TO` 关系连接实体
- 将原始 `predicate` 保存为关系属性
- 将来源文本片段保存到关系的 `sources` 列表中

## 参数说明

- `--source`：输入 `.txt` 文件路径，必填
- `--model`：模型配置别名，默认 `openai_gpt4o`
- `--csv`：三元组 CSV 输出路径，默认 `kg_triples.csv`
- `--html`：知识图谱 HTML 输出路径，默认 `kg_graph.html`
- `--chunk-size`：文本切片最大字符数，默认 `1200`
- `--chunk-overlap`：相邻切片重叠字符数，默认 `120`
- `--write-neo4j`：是否把三元组写入 Neo4j，默认不写入
- `--neo4j-uri`：Neo4j 连接地址，默认读取 `NEO4J_URI`，否则使用 `bolt://localhost:7687`
- `--neo4j-user`：Neo4j 用户名，默认读取 `NEO4J_USER`，否则使用 `neo4j`
- `--neo4j-password`：Neo4j 密码，默认读取 `NEO4J_PASSWORD`
- `--neo4j-database`：Neo4j 数据库名，默认读取 `NEO4J_DATABASE`，不填则使用服务器默认数据库

## 输出结果

运行成功后会生成：

- CSV：包含 `source`、`subject`、`predicate`、`object` 字段
- HTML：可用浏览器打开查看的交互式知识图谱
- Neo4j 数据：仅在启用 `--write-neo4j` 时写入

## 输出 JSON 要求

LLM 需要返回如下 JSON 结构，程序会从模型输出中提取并解析 JSON：

```json
{
  "triples": [
    {
      "subject": "实体A",
      "predicate": "关系",
      "object": "实体B"
    }
  ]
}
```

如果模型输出包含额外说明，`KGExtractor` 会尝试截取首尾 `{}` 之间的 JSON 内容。如果 JSON 无法解析，该文本片段不会产生三元组。

## 运行测试

```powershell
uv run python -m unittest discover -s tests
```
