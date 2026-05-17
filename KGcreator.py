import argparse
import os
from pathlib import Path
from typing import Any

from src.config import AppConfig
from src.kg_extract import KGExtractor
from src.llm_factory import LLMFactory
from src.neo4j_writer import Neo4jWriter
from src.source_reader import TextSourceReader
from src.visualize import KGVisualizer


def build_csv(results: Any, output_path: Path) -> None:
    """Save extracted triples to a CSV file.

    Args:
        results: DataFrame containing extracted triples.
        output_path: Target CSV file path.

    Returns:
        None.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(output_path, index=False, encoding="utf-8-sig")


def write_neo4j_results(
    results: Any,
    uri: str,
    user: str,
    password: str,
    database: str | None = None,
    writer_cls: Any = Neo4jWriter,
) -> int:
    """Write extracted knowledge graph triples into Neo4j.

    Args:
        results: DataFrame containing ``subject``, ``predicate`` and ``object`` columns.
        uri: Neo4j connection URI, for example ``bolt://localhost:7687``.
        user: Neo4j user name.
        password: Neo4j password.
        database: Optional Neo4j database name. ``None`` uses the server default.
        writer_cls: Writer class or factory used to create a Neo4j writer.

    Returns:
        Number of valid triples written into Neo4j.
    """
    writer = writer_cls(uri=uri, user=user, password=password, database=database)
    try:
        writer.create_constraints()
        return writer.write_dataframe(results)
    finally:
        writer.close()


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser.

    Args:
        None.

    Returns:
        Configured ``argparse.ArgumentParser`` instance.
    """
    parser = argparse.ArgumentParser(
        description="Knowledge graph extraction and visualization pipeline"
    )
    parser.add_argument("--source", required=True, help="Path to the input .txt file")
    parser.add_argument("--model", default="openai_gpt4o", help="LLM model alias from config")
    parser.add_argument("--csv", default="kg_triples.csv", help="Output CSV file path")
    parser.add_argument("--html", default="kg_graph.html", help="Output HTML visualization file path")
    parser.add_argument("--chunk-size", type=int, default=1200, help="Chunk size for text splitting")
    parser.add_argument("--chunk-overlap", type=int, default=120, help="Chunk overlap size for text splitting")
    parser.add_argument(
        "--write-neo4j",
        action="store_true",
        help="Write extracted triples into a Neo4j database",
    )
    parser.add_argument(
        "--neo4j-uri",
        default=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        help="Neo4j connection URI",
    )
    parser.add_argument(
        "--neo4j-user",
        default=os.getenv("NEO4J_USER", "neo4j"),
        help="Neo4j user name",
    )
    parser.add_argument(
        "--neo4j-password",
        default=os.getenv("NEO4J_PASSWORD"),
        help="Neo4j password. Defaults to NEO4J_PASSWORD environment variable",
    )
    parser.add_argument(
        "--neo4j-database",
        default=os.getenv("NEO4J_DATABASE"),
        help="Neo4j database name. Defaults to the server default database",
    )
    return parser


def main() -> None:
    """Run the full knowledge graph extraction pipeline.

    Args:
        None.

    Returns:
        None.
    """
    parser = build_parser()
    args = parser.parse_args()

    config = AppConfig()
    llm_config = config.get_llm_config(args.model)
    llm = LLMFactory(llm_config).build()
    print("LLM model loaded:", args.model)
    print(
        "Loading source:",
        args.source,
        f"chunk_size={args.chunk_size}",
        f"chunk_overlap={args.chunk_overlap}",
    )

    reader = TextSourceReader(chunk_size=args.chunk_size, chunk_overlap=args.chunk_overlap)
    chunks = reader.load_and_chunk(Path(args.source))

    print(f"Loaded {len(chunks)} text chunks. Extracting triples...")
    extractor = KGExtractor(llm=llm, prompt_template=config.prompt_template)
    extraction_results = extractor.extract(chunks)

    if extraction_results.empty:
        print("No triples extracted. Please check the input text and model config.")
        return

    output_csv_path = Path(args.csv)
    build_csv(extraction_results, output_csv_path)
    print(f"Saved triples CSV: {output_csv_path}")

    visualizer = KGVisualizer()
    visualizer.build_network(extraction_results)
    output_html_path = Path(args.html)
    visualizer.save(output_html_path)
    print(f"Saved knowledge graph HTML: {output_html_path}")

    if args.write_neo4j:
        if not args.neo4j_password:
            raise ValueError(
                "Neo4j password is required. Use --neo4j-password or set NEO4J_PASSWORD."
            )
        written = write_neo4j_results(
            results=extraction_results,
            uri=args.neo4j_uri,
            user=args.neo4j_user,
            password=args.neo4j_password,
            database=args.neo4j_database,
        )
        print(f"Wrote {written} triples into Neo4j.")


if __name__ == "__main__":
    main()
