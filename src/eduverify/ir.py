"""Typed intermediate representation. Every element may carry a source span for provenance."""
from __future__ import annotations
from typing import Annotated, Literal, Optional, Union
from pydantic import BaseModel, Field, TypeAdapter


class Fact(BaseModel):
    text: str
    source_span: Optional[str] = None  # verbatim quote from the source material


class Series(BaseModel):
    name: str
    values: list[float]
    source_span: Optional[str] = None


class ChartIR(BaseModel):
    kind: Literal["chart"] = "chart"
    chart_type: Literal["bar", "line", "pie", "scatter"] = "bar"
    title: str
    categories: list[str] = Field(default_factory=list)  # x labels / pie slices
    series: list[Series]
    x_label: str = ""
    y_label: str = ""
    unit: str = ""
    percent: bool = False  # pie/values are percentages that should sum to ~100


class Node(BaseModel):
    id: str
    label: str
    source_span: Optional[str] = None


class Edge(BaseModel):
    src: str
    dst: str
    label: str = ""
    source_span: Optional[str] = None


class DiagramIR(BaseModel):
    kind: Literal["diagram"] = "diagram"
    title: str
    nodes: list[Node]
    edges: list[Edge]
    direction: Literal["TB", "LR"] = "TB"


class Section(BaseModel):
    heading: str
    facts: list[Fact]


class InfographicIR(BaseModel):
    kind: Literal["infographic"] = "infographic"
    title: str
    sections: list[Section]


VisualIR = Annotated[Union[ChartIR, DiagramIR, InfographicIR], Field(discriminator="kind")]
_adapter = TypeAdapter(VisualIR)


def load_ir(data: Union[str, dict]) -> Union[ChartIR, DiagramIR, InfographicIR]:
    return _adapter.validate_json(data) if isinstance(data, str) else _adapter.validate_python(data)


def ir_json_schema() -> dict:
    return _adapter.json_schema()
