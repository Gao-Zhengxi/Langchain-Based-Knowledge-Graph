from __future__ import annotations

from pydantic import BaseModel, Field

try:

    from pydantic import BaseSettings  # type: ignore
except Exception:

    try:
        from pydantic_settings import BaseSettings  # type: ignore
    except Exception:
        import warnings

        warnings.warn(
            "pydantic BaseSettings not available. Install 'pydantic-settings' for full functionality."
        )
        from pydantic import BaseModel as BaseSettings  # type: ignore
from typing import Any, Dict


class LLMConfig(BaseModel):
    name: str = Field(..., description="配置别名")
    provider: str = Field("openai", description="模型提供商，例如 openai 或 deepseek")
    model_name: str = Field("gpt-4o-mini", description="模型名称")
    temperature: float = Field(0.0, description="采样温度")
    max_tokens: int = Field(1024, description="最大输出 token 数量")
    model_kwargs: Dict[str, Any] = Field(default_factory=dict, description="传给模型构造函数的额外参数")


class AppConfig(BaseSettings):
    default_model: str = Field("openai_gpt4o", description="默认模型别名")
    llm_configs: Dict[str, LLMConfig] = Field(
        {
            "openai_gpt4o": LLMConfig(
                name="openai_gpt4o",
                provider="openai",
                model_name="gpt-4o-mini",
                temperature=0.0,
                max_tokens=1024,
            ),
            "openai_text_davinci": LLMConfig(
                name="openai_text_davinci",
                provider="openai",
                model_name="text-davinci-003",
                temperature=0.0,
                max_tokens=1024,
            ),
            "deepseek_chat": LLMConfig(
                name="deepseek_chat",
                provider="deepseek",
                model_name="deepseek-chat",
                temperature=0.0,
                max_tokens=1024,
                model_kwargs={},
            ),
        },
        description="可选模型配置映射",
    )
    prompt_template: str = Field(
        """
请根据以下文本提取知识三元组，并输出 JSON 结构。
只需要返回 JSON，不要返回任何额外描述。

文本:
{text}

输出格式:
{
  "triples": [
    {"subject": "...", "predicate": "...", "object": "..."}
  ]
}
""",
        description="LLM 提取三元组的提示模板",
    )

    class Config:
        env_prefix = "KG_"
        extra = "ignore"

    def get_llm_config(self, alias: str) -> LLMConfig:
        """Return a configured LLM config by alias."""
        if alias not in self.llm_configs:
            raise ValueError(f"未找到模型配置：{alias}")
        return self.llm_configs[alias]
