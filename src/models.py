from __future__ import annotations

from pydantic import BaseModel, Field
from typing import List


class KGTriple(BaseModel):
    subject: str = Field(..., description="三元组主体")
    predicate: str = Field(..., description="三元组关系")
    object: str = Field(..., description="三元组客体")


class KGExtractionResult(BaseModel):
    source: str = Field(..., description="原始文本块")
    triples: List[KGTriple] = Field(default_factory=list, description="提取的三元组列表")
