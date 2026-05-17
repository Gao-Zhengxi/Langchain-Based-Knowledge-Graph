import argparse
from pathlib import Path

from src.config import AppConfig
from src.kg_extract import KGExtractor
from src.llm_factory import LLMFactory
from src.source_reader import TextSourceReader
from src.visualize import KGVisualizer


def build_csv(results, output_path: Path) -> None:
    """Save extracted triples to a CSV file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(output_path, index=False, encoding="utf-8-sig")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Knowledge graph extraction and visualization pipeline"
    )
    parser.add_argument("--source", required=True, help="Path to the input .txt file")
    parser.add_argument("--model", default="openai_gpt4o", help="LLM model alias from config")
    parser.add_argument("--csv", default="kg_triples.csv", help="Output CSV file path")
    parser.add_argument("--html", default="kg_graph.html", help="Output HTML visualization file path")
    parser.add_argument("--chunk-size", type=int, default=1200, help="Chunk size for text splitting")
    parser.add_argument("--chunk-overlap", type=int, default=120, help="Chunk overlap size for text splitting")
    args = parser.parse_args()

    config = AppConfig()
    llm_config = config.get_llm_config(args.model)
    llm = LLMFactory(llm_config).build()
    print("LLM 模型已加载：", args.model)
    print(f"加载文档中，路径：{args.source}，chunk_size={args.chunk_size}，chunk_overlap={args.chunk_overlap}")
    reader = TextSourceReader(chunk_size=args.chunk_size, chunk_overlap=args.chunk_overlap)
    chunks = reader.load_and_chunk(Path(args.source))

    print(f"文档已加载并分块，得到 {len(chunks)} 个文本块。开始提取三元组...")
    extractor = KGExtractor(llm=llm, prompt_template=config.prompt_template)
    extraction_results = extractor.extract(chunks)

    if extraction_results.empty:
        print("未提取到任何三元组，请检查输入文本与模型配置。")
        return

    output_csv_path = Path(args.csv)
    build_csv(extraction_results, output_csv_path)
    print(f"已保存三元组 CSV：{output_csv_path}")

    visualizer = KGVisualizer()
    visualizer.build_network(extraction_results)
    output_html_path = Path(args.html)
    visualizer.save(output_html_path)
    print(f"已保存知识图谱可视化：{output_html_path}")


if __name__ == "__main__":
    main()
