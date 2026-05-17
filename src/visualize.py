from __future__ import annotations

from pathlib import Path

import pandas as pd
from pyvis.network import Network


class KGVisualizer:
    """Build and save an interactive knowledge graph visualization."""

    def __init__(self, width: str = "100%", height: str = "750px") -> None:
        self.network = Network(
            height=height,
            width=width,
            bgcolor="#ffffff",
            font_color="#000000",
            cdn_resources="in_line",
        )
        self.network.barnes_hut()

    def build_network(self, dataframe: pd.DataFrame) -> None:
        """Build the network graph from extracted triple records."""
        for _, row in dataframe.drop_duplicates(subset=["subject", "predicate", "object"]).iterrows():
            subject = str(row["subject"])
            object_ = str(row["object"])
            predicate = str(row["predicate"])

            self.network.add_node(subject, label=subject, title=subject, color="#6FB1FC")
            self.network.add_node(object_, label=object_, title=object_, color="#FB7E81")
            self.network.add_edge(subject, object_, title=predicate, label=predicate)

    def save(self, output_path: Path, notebook: bool = False) -> None:
        """Save the visualization to an HTML file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        html = self.network.generate_html(notebook=notebook)
        output_path.write_text(html, encoding="utf-8")
