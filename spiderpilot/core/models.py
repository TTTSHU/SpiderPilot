"""Core generic models for SpiderPilot.

These models intentionally avoid domain-specific names such as product/shop/category.
Domain templates map industry concepts onto these generic primitives.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


PageType = Literal["detail", "list", "search", "profile", "feed", "api", "sitemap"]
SpiderRole = Literal[
    "detail_collector",
    "list_discoverer",
    "search_discoverer",
    "profile_collector",
    "feed_collector",
    "relationship_discoverer",
    "incremental_discoverer",
]


class EntityField(BaseModel):
    type: str = "string"
    required: bool = False
    description: str | None = None


class EntityModel(BaseModel):
    name: str
    description: str | None = None
    fields: dict[str, EntityField] = Field(default_factory=dict)


class CrawlNode(BaseModel):
    id: str
    role: SpiderRole
    page_type: PageType | None = None
    input_entity: str | None = None
    output_entity: str | None = None


class CrawlEdge(BaseModel):
    from_node: str = Field(alias="from")
    to_node: str = Field(alias="to")
    via: str = "discovered_url"

    model_config = {"populate_by_name": True}


class CrawlGraph(BaseModel):
    nodes: list[CrawlNode] = Field(default_factory=list)
    edges: list[CrawlEdge] = Field(default_factory=list)


class TaskSource(BaseModel):
    task: str | None = None
    entity_type: str | None = None
    url: str | None = None


class TaskMessage(BaseModel):
    platform: str
    task: str
    entity_type: str
    entity_id: str | None = None
    url: str
    source: TaskSource | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    priority: int = 5
    created_at: datetime = Field(default_factory=datetime.now)
