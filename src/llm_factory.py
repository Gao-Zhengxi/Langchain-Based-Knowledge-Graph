from __future__ import annotations

from pydantic import SecretStr

from src.config import LLMConfig


class LLMFactory:
    """Create LLM instances for upstream extraction."""

    def __init__(self, config: LLMConfig) -> None:
        """Initialize the factory with one model configuration."""
        self.config = config

    def build(self):
        """Return a LangChain LLM object based on the configured provider."""
        if self.config.provider == "openai":
            return self._build_openai()

        if self.config.provider == "deepseek":
            return self._build_deepseek()

        raise ValueError(f"Unsupported LLM provider: {self.config.provider}")

    def _build_openai(self):
        """Build an OpenAI LangChain model."""
        try:
            from langchain_openai import ChatOpenAI, OpenAI
        except ImportError as exc:
            raise ImportError(
                "Please install langchain-openai and configure OPENAI_API_KEY."
            ) from exc

        llm_class = ChatOpenAI if self._is_openai_chat_model() else OpenAI
        return llm_class(
            model=self.config.model_name,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            **self.config.model_kwargs,
        )

    def _build_deepseek(self):
        """Build a DeepSeek LangChain chat model."""
        try:
            from langchain_deepseek import ChatDeepSeek
        except ImportError as exc:
            raise ImportError(
                "Please install langchain-deepseek and configure DEEPSEEK_API_KEY."
            ) from exc

        kwargs = dict(self.config.model_kwargs)
        if isinstance(kwargs.get("api_key"), str):
            kwargs["api_key"] = SecretStr(kwargs["api_key"])

        return ChatDeepSeek(
            model=self.config.model_name,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            **kwargs,
        )

    def _is_openai_chat_model(self) -> bool:
        """Return whether the OpenAI model should use the chat interface."""
        return self.config.model_name.startswith(("gpt-", "o1", "o3", "o4"))
