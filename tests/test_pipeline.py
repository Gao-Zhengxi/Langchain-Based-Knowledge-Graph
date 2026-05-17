from __future__ import annotations

import json
import unittest
from pathlib import Path

import pandas as pd

from KGcreator import build_csv
from src.config import LLMConfig
from src.kg_extract import KGExtractor
from src.llm_factory import LLMFactory
from src.source_reader import TextSourceReader
from src.visualize import KGVisualizer


class PipelineTest(unittest.TestCase):
    """Regression tests for the knowledge graph demo pipeline."""

    def test_prompt_template_allows_json_braces(self) -> None:
        """The prompt JSON example must not break text substitution."""
        raw = json.dumps(
            {
                "triples": [
                    {"subject": "A", "predicate": "rel", "object": "B"},
                ]
            }
        )
        extractor = KGExtractor(
            llm=lambda _: raw,
            prompt_template='text:{text}\nformat:{"triples":[]}',
        )

        records = extractor.extract(["hello"]).to_dict("records")

        self.assertEqual(records[0]["subject"], "A")
        self.assertEqual(records[0]["predicate"], "rel")
        self.assertEqual(records[0]["object"], "B")

    def test_long_text_chunks_do_not_exceed_chunk_size(self) -> None:
        """Long paragraphs should be split with the configured overlap."""
        chunks = TextSourceReader(chunk_size=10, chunk_overlap=2).split_chunks(
            "abcdefghijABCDEFGHIJ"
        )

        self.assertEqual(chunks, ["abcdefghij", "ijABCDEFGH", "GHIJ"])
        self.assertTrue(all(len(chunk) <= 10 for chunk in chunks))

    def test_build_csv_creates_parent_directory(self) -> None:
        """CSV output should work when the target directory does not exist."""
        output_path = Path("test_outputs") / "nested" / "triples.csv"
        build_csv(
            pd.DataFrame(
                [{"source": "s", "subject": "A", "predicate": "rel", "object": "B"}]
            ),
            output_path,
        )

        self.assertTrue(output_path.exists())

    def test_visualizer_writes_html_without_notebook_show(self) -> None:
        """Visualization should write an HTML file directly."""
        dataframe = pd.DataFrame(
            [{"source": "s", "subject": "A", "predicate": "rel", "object": "B"}]
        )

        output_path = Path("test_outputs") / "graph.html"
        visualizer = KGVisualizer()
        visualizer.build_network(dataframe)
        visualizer.save(output_path)

        self.assertGreater(output_path.stat().st_size, 0)

    def test_openai_chat_alias_builds_chat_model(self) -> None:
        """gpt-style OpenAI models should use ChatOpenAI."""
        config = LLMConfig(
            name="test",
            provider="openai",
            model_name="gpt-4o-mini",
            model_kwargs={"api_key": "test-key"},
        )

        self.assertEqual(type(LLMFactory(config).build()).__name__, "ChatOpenAI")


if __name__ == "__main__":
    unittest.main()
