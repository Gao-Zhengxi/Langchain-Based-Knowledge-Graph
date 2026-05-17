from __future__ import annotations

import json
from typing import Any, List

import pandas as pd

from src.models import KGTriple


class KGExtractor:
    """Extract knowledge graph triples from text chunks using an LLM."""

    def __init__(self, llm: Any, prompt_template: str) -> None:
        """Initialize with a generic LLM client and a prompt template string.

        The LLM client can be one of multiple types (langchain LLM, a deepseek
        client, or any callable). This class adapts at runtime to call the
        provided client.

        Args:
            llm: LLM client instance returned from `LLMFactory.build()`.
            prompt_template: Template string containing `{text}` placeholder.
        """
        self._llm = llm
        self._prompt_template = prompt_template

    def _call_llm(self, prompt: str) -> str:
        """Call the provided LLM in a best-effort, compatibility-oriented way.

        Tries several common interfaces in order:
        - `invoke(messages)` (DeepSeek / chat models)
        - `__call__(prompt)` (callable LLMs)
        - `generate([prompt])` / `complete(prompt)`

        Returns the textual response (empty string on failure).
        """
        # DeepSeek-like: invoke(messages)
        try:
            if hasattr(self._llm, "invoke"):
                # DeepSeek expects messages like [(role, text)]
                messages = [("human", prompt)]
                resp = self._llm.invoke(messages)
                # resp may be an object with `.text` or `.content` or be a string
                if hasattr(resp, "text"):
                    return str(resp.text)
                if hasattr(resp, "content"):
                    return str(resp.content)
                return str(resp)
        except Exception:
            pass

        # Callable LLMs: llm(prompt)
        try:
            if callable(self._llm):
                out = self._llm(prompt)
                if isinstance(out, str):
                    return out
                # some APIs return objects
                if hasattr(out, "text"):
                    return str(out.text)
                return str(out)
        except Exception:
            pass

        # Fallbacks: check for generate/complete
        try:
            if hasattr(self._llm, "generate"):
                gen = self._llm.generate([prompt])
                # try to extract text from returned structure
                if hasattr(gen, "generations"):
                    gens = gen.generations
                    if gens and gens[0]:
                        return str(gens[0][0].text)
                return str(gen)
        except Exception:
            pass

        try:
            if hasattr(self._llm, "complete"):
                comp = self._llm.complete(prompt)
                if isinstance(comp, str):
                    return comp
                if hasattr(comp, "text"):
                    return str(comp.text)
                return str(comp)
        except Exception:
            pass

        return ""

    def extract(self, chunks: List[str]) -> pd.DataFrame:
        """Extract triples from a list of text chunks and return a dataframe."""

        records = []

        for chunk in chunks:
            prompt = self._prompt_template.replace("{text}", chunk)
            raw = self._call_llm(prompt)
            triples = self._parse_output(raw)
            for triple in triples:
                records.append(
                    {
                        "source": chunk,
                        "subject": triple.subject,
                        "predicate": triple.predicate,
                        "object": triple.object,
                    }
                )

        return pd.DataFrame(records)

    def _parse_output(self, raw_text: str) -> List[KGTriple]:
        """Parse LLM output into a list of KGTriple objects."""
        raw_text = raw_text.strip()
        json_text = self._extract_json(raw_text)
        if not json_text:
            return []

        try:
            payload = json.loads(json_text)
        except json.JSONDecodeError:
            payload = self._repair_json(json_text)

        triples = []
        for item in payload.get("triples", []):
            if not isinstance(item, dict):
                continue
            triples.append(
                KGTriple(
                    subject=str(item.get("subject", "")).strip(),
                    predicate=str(item.get("predicate", "")).strip(),
                    object=str(item.get("object", "")).strip(),
                )
            )

        return [triple for triple in triples if triple.subject and triple.predicate and triple.object]

    def _extract_json(self, raw_text: str) -> str:
        """Extract JSON payload from LLM text output."""
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return raw_text[start : end + 1]
        return raw_text

    def _repair_json(self, raw_text: str) -> dict:
        """Attempt basic repairs on malformed JSON text."""
        sanitized = raw_text.replace("\n", " ").replace("\"\"", "\"")
        try:
            return json.loads(sanitized)
        except json.JSONDecodeError:
            return {"triples": []}
