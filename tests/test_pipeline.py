from __future__ import annotations

import json
import unittest
from pathlib import Path

import pandas as pd

from KGcreator import build_csv, build_parser, write_neo4j_results
from src.config import LLMConfig
from src.kg_extract import KGExtractor
from src.llm_factory import LLMFactory
from src.neo4j_writer import Neo4jWriter
from src.source_reader import TextSourceReader
from src.visualize import KGVisualizer


class FakeNeo4jResult:
    """Small Neo4j result double used by writer tests."""

    def consume(self) -> None:
        """Mimic Neo4j result consumption."""


class FakeNeo4jSession:
    """Capture Cypher statements executed through a fake Neo4j session."""

    def __init__(self, calls, session_kwargs) -> None:
        self._calls = calls
        self._session_kwargs = session_kwargs

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def run(self, query, **parameters):
        self._calls.append(
            {
                "query": query,
                "parameters": parameters,
                "session_kwargs": self._session_kwargs,
            }
        )
        return FakeNeo4jResult()


class FakeNeo4jDriver:
    """Capture Neo4j sessions without opening a real database connection."""

    def __init__(self) -> None:
        self.calls = []
        self.closed = False

    def session(self, **kwargs):
        return FakeNeo4jSession(self.calls, kwargs)

    def close(self) -> None:
        self.closed = True


class FakeNeo4jWriter:
    """Capture KGcreator Neo4j write helper calls without a real database."""

    instances = []

    def __init__(self, uri, user, password, database=None) -> None:
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self.constraints_created = False
        self.closed = False
        self.dataframe = None
        FakeNeo4jWriter.instances.append(self)

    def create_constraints(self) -> None:
        self.constraints_created = True

    def write_dataframe(self, dataframe) -> int:
        self.dataframe = dataframe
        return len(dataframe)

    def close(self) -> None:
        self.closed = True


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

    def test_cli_parses_neo4j_write_options(self) -> None:
        """KGcreator CLI should expose optional Neo4j writing settings."""
        args = build_parser().parse_args(
            [
                "--source",
                "txt/test1.txt",
                "--write-neo4j",
                "--neo4j-uri",
                "bolt://example:7687",
                "--neo4j-user",
                "neo4j",
                "--neo4j-password",
                "secret",
                "--neo4j-database",
                "neo4j",
            ]
        )

        self.assertTrue(args.write_neo4j)
        self.assertEqual(args.neo4j_uri, "bolt://example:7687")
        self.assertEqual(args.neo4j_password, "secret")

    def test_write_neo4j_results_uses_writer_interface(self) -> None:
        """KGcreator should write extracted dataframe rows through Neo4jWriter."""
        FakeNeo4jWriter.instances = []
        dataframe = pd.DataFrame(
            [{"source": "s", "subject": "A", "predicate": "rel", "object": "B"}]
        )

        written = write_neo4j_results(
            results=dataframe,
            uri="bolt://localhost:7687",
            user="neo4j",
            password="secret",
            database="neo4j",
            writer_cls=FakeNeo4jWriter,
        )

        writer = FakeNeo4jWriter.instances[0]
        self.assertEqual(written, 1)
        self.assertTrue(writer.constraints_created)
        self.assertTrue(writer.closed)
        self.assertIs(writer.dataframe, dataframe)

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

    def test_neo4j_writer_writes_valid_triples(self) -> None:
        """Neo4jWriter should batch and normalize valid triples."""
        driver = FakeNeo4jDriver()
        writer = Neo4jWriter(driver=driver, database="neo4j", batch_size=1)

        written = writer.write_triples(
            [
                {"source": "s1", "subject": " Alice ", "predicate": "knows", "object": "Bob"},
                {"source": "s2", "subject": "", "predicate": "likes", "object": "Tea"},
            ]
        )

        self.assertEqual(written, 1)
        self.assertEqual(driver.calls[0]["session_kwargs"], {"database": "neo4j"})
        self.assertIn("MERGE (subject:Entity", driver.calls[0]["query"])
        self.assertEqual(
            driver.calls[0]["parameters"]["rows"][0],
            {
                "source": "s1",
                "subject": "Alice",
                "predicate": "knows",
                "object": "Bob",
            },
        )

    def test_neo4j_writer_closes_driver(self) -> None:
        """Neo4jWriter.close should delegate to the underlying driver."""
        driver = FakeNeo4jDriver()
        writer = Neo4jWriter(driver=driver)

        writer.close()

        self.assertTrue(driver.closed)


if __name__ == "__main__":
    unittest.main()
