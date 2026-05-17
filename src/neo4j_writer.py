from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any, Optional


class Neo4jWriter:
    """Write extracted knowledge graph triples into a Neo4j database.

    The class is responsible only for persistence into Neo4j. It accepts plain
    mappings or dataframe records, so callers do not need to depend on Neo4j
    details outside this module.

    Args:
        uri: Neo4j connection URI, for example ``bolt://localhost:7687``.
        user: Neo4j user name.
        password: Neo4j password.
        database: Optional Neo4j database name. ``None`` uses the server default.
        driver: Optional prebuilt Neo4j driver. Useful for tests or shared drivers.
        node_label: Label used for entity nodes.
        relationship_type: Relationship type used for all stored triples. The
            original predicate is stored as a relationship property.
        batch_size: Number of triples written per transaction.
    """

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
        driver: Optional[Any] = None,
        node_label: str = "Entity",
        relationship_type: str = "RELATED_TO",
        batch_size: int = 1000,
    ) -> None:
        self._driver = driver or self._create_driver(
            uri=uri,
            user=user,
            password=password,
        )
        self._database = database
        self._node_label = self._validate_identifier(node_label, "node_label")
        self._relationship_type = self._validate_identifier(
            relationship_type, "relationship_type"
        )
        self._batch_size = self._validate_batch_size(batch_size)

    def close(self) -> None:
        """Close the underlying Neo4j driver.

        Args:
            None.

        Returns:
            None.
        """
        self._driver.close()

    def create_constraints(self) -> None:
        """Create the uniqueness constraint used by entity node upserts.

        The constraint keeps one node per entity name for this writer's label.

        Args:
            None.

        Returns:
            None.
        """
        query = (
            f"CREATE CONSTRAINT {self._node_label.lower()}_name_unique IF NOT EXISTS "
            f"FOR (n:{self._node_label}) REQUIRE n.name IS UNIQUE"
        )
        self._run(query)

    def write_triples(self, triples: Iterable[Mapping[str, Any]]) -> int:
        """Write triples into Neo4j.

        Each item must contain ``subject``, ``predicate`` and ``object``. The
        optional ``source`` field is stored on the relationship.

        Args:
            triples: Iterable of mapping records, usually produced by
                ``DataFrame.to_dict("records")``.

        Returns:
            Number of valid triples written.
        """
        rows = [row for row in (self._normalize_triple(item) for item in triples) if row]
        if not rows:
            return 0

        query = self._build_write_query()
        written = 0
        for batch in self._iter_batches(rows):
            self._run(query, rows=batch)
            written += len(batch)
        return written

    def write_dataframe(self, dataframe: Any) -> int:
        """Write triples from a pandas-like dataframe into Neo4j.

        The dataframe must provide ``to_dict("records")`` and contain the
        columns ``subject``, ``predicate`` and ``object``. ``source`` is optional.

        Args:
            dataframe: Pandas dataframe or compatible object.

        Returns:
            Number of valid triples written.
        """
        records = dataframe.to_dict("records")
        return self.write_triples(records)

    def clear_graph(self) -> None:
        """Delete nodes and relationships managed by this writer's node label.

        This is intended for local demos or tests. It deletes every node with
        ``node_label`` and all relationships attached to those nodes.

        Args:
            None.

        Returns:
            None.
        """
        query = f"MATCH (n:{self._node_label}) DETACH DELETE n"
        self._run(query)

    def _create_driver(
        self, uri: Optional[str], user: Optional[str], password: Optional[str]
    ) -> Any:
        """Create a Neo4j driver from connection parameters."""
        if not uri or not user or not password:
            raise ValueError(
                "uri, user and password are required when driver is not provided"
            )

        try:
            from neo4j import GraphDatabase
        except ImportError as exc:
            raise ImportError("Please install the neo4j package to use Neo4jWriter.") from exc

        return GraphDatabase.driver(uri, auth=(user, password))

    def _build_write_query(self) -> str:
        """Build the Cypher upsert query used for triple persistence."""
        return f"""
        UNWIND $rows AS row
        MERGE (subject:{self._node_label} {{name: row.subject}})
        MERGE (object:{self._node_label} {{name: row.object}})
        MERGE (subject)-[relation:{self._relationship_type} {{predicate: row.predicate}}]->(object)
        SET relation.sources =
            CASE
                WHEN row.source = "" THEN coalesce(relation.sources, [])
                WHEN row.source IN coalesce(relation.sources, []) THEN relation.sources
                ELSE coalesce(relation.sources, []) + [row.source]
            END
        """

    def _run(self, query: str, **parameters: Any) -> None:
        """Run one Cypher statement in the configured database."""
        session_kwargs = {}
        if self._database:
            session_kwargs["database"] = self._database

        with self._driver.session(**session_kwargs) as session:
            result = session.run(query, **parameters)
            if hasattr(result, "consume"):
                result.consume()

    def _normalize_triple(self, item: Mapping[str, Any]) -> Optional[dict[str, str]]:
        """Validate and normalize one triple record."""
        subject = self._clean_value(item.get("subject"))
        predicate = self._clean_value(item.get("predicate"))
        obj = self._clean_value(item.get("object"))
        source = self._clean_value(item.get("source"))

        if not subject or not predicate or not obj:
            return None

        return {
            "subject": subject,
            "predicate": predicate,
            "object": obj,
            "source": source,
        }

    def _iter_batches(self, rows: list[dict[str, str]]) -> Iterable[list[dict[str, str]]]:
        """Yield rows in fixed-size batches."""
        for start in range(0, len(rows), self._batch_size):
            yield rows[start : start + self._batch_size]

    def _clean_value(self, value: Any) -> str:
        """Convert a field value to a trimmed string."""
        if value is None:
            return ""
        return str(value).strip()

    def _validate_identifier(self, value: str, field_name: str) -> str:
        """Validate a Cypher label or relationship type identifier."""
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
            raise ValueError(f"{field_name} must be a valid Cypher identifier")
        return value

    def _validate_batch_size(self, batch_size: int) -> int:
        """Validate the configured batch size."""
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than 0")
        return batch_size
