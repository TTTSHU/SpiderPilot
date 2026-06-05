"""Core generic models for SpiderPilot.

These lightweight dataclasses avoid domain-specific names such as
product/shop/category. Domain templates map industry concepts onto these
generic primitives.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


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


@dataclass
class EntityField:
    type: str = "string"
    required: bool = False
    description: str | None = None


@dataclass
class EntityModel:
    name: str
    description: str | None = None
    fields: dict[str, EntityField] = field(default_factory=dict)


@dataclass
class CrawlNode:
    id: str
    role: SpiderRole
    page_type: PageType | None = None
    input_entity: str | None = None
    output_entity: str | None = None


@dataclass
class CrawlEdge:
    from_node: str
    to_node: str
    via: str = "discovered_url"


@dataclass
class CrawlGraph:
    nodes: list[CrawlNode] = field(default_factory=list)
    edges: list[CrawlEdge] = field(default_factory=list)


@dataclass
class TaskSource:
    task: str | None = None
    entity_type: str | None = None
    url: str | None = None


@dataclass
class TaskMessage:
    platform: str
    task: str
    entity_type: str
    url: str
    entity_id: str | None = None
    source: TaskSource | None = None
    context: dict[str, Any] = field(default_factory=dict)
    priority: int = 5
    created_at: datetime = field(default_factory=datetime.now)
