# 知识图谱构建 Demo

这个项目实现了一个面向对象风格的知识图谱抽取与可视化流程：从非结构化 `.txt` 文本中读取内容，调用 LLM 抽取实体关系三元组，解析为结构化数据，保存为 CSV，并使用 PyVis 生成可交互的 HTML 知识图谱。

## 功能流程

```text
非结构化文本
  -> 文本读取与切片
  -> LLMFactory 选择模型
  -> Prompt 构造
  -> LLM 抽取三元组
  -> JSON / Pydantic 解析
  -> 保存 CSV
  -> PyVis 可视化
```

## 项目结构

```text
.
├── main.py                 # CLI 入口，串联完整流程
├── pyproject.toml          # 项目依赖配置
├── src/
│   ├── config.py           # LLM 配置与 prompt 模板
│   ├── llm_factory.py      # 根据配置创建 LangChain LLM 实例
│   ├── source_reader.py    # 读取 .txt 文件并切片
│   ├── kg_extract.py       # 调用 LLM 并解析三元组
│   ├── models.py           # Pydantic 数据模型
│   └── visualize.py        # 生成 PyVis HTML 知识图谱
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

如果不用 `uv`，也可以在虚拟环境中按 `pyproject.toml` 安装依赖。核心依赖包括：

- `langchain`
- `langchain-openai`
- `langchain-deepseek`
- `pydantic`
- `pydantic-settings`
- `pandas`
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

也可以用系统环境变量持久保存：

```powershell
setx OPENAI_API_KEY "your_openai_api_key"
setx DEEPSEEK_API_KEY "your_deepseek_api_key"
```

## 支持的模型配置

模型别名在 `src/config.py` 中维护，当前内置：

- `openai_gpt4o`：默认配置，使用 `gpt-4o-mini`
- `openai_text_davinci`：OpenAI completion 模型配置
- `deepseek_chat`：DeepSeek chat 模型配置

新增模型时，优先在 `AppConfig.llm_configs` 中增加新的 `LLMConfig`，如果是新 provider，再到 `src/llm_factory.py` 增加对应构建逻辑。

## 运行

确保输入文件是非空 `.txt` 文件，例如 `txt/test1.txt`。

使用默认 OpenAI 配置：

```powershell
.\.venv\Scripts\python.exe main.py `
  --source txt\test1.txt `
  --model openai_gpt4o `
  --csv output\triples.csv `
  --html output\graph.html
```

使用 DeepSeek：

```powershell
.\.venv\Scripts\python.exe main.py `
  --source txt\test1.txt `
  --model deepseek_chat `
  --csv output\triples.csv `
  --html output\graph.html
```

可选参数：

- `--source`：输入 `.txt` 文件路径，必填
- `--model`：模型配置别名，默认 `openai_gpt4o`
- `--csv`：三元组 CSV 输出路径，默认 `kg_triples.csv`
- `--html`：知识图谱 HTML 输出路径，默认 `kg_graph.html`
- `--chunk-size`：文本切片最大字符数，默认 `1200`
- `--chunk-overlap`：相邻切片重叠字符数，默认 `120`

运行成功后会生成：

- CSV：包含 `source`、`subject`、`predicate`、`object` 字段
- HTML：可用浏览器打开查看的交互式知识图谱

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

如果模型输出包含额外说明，`KGExtractor` 会尝试截取首尾 `{}` 之间的 JSON 内容；如果 JSON 无法解析，则该片段不会产生三元组。
