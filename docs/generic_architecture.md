# Generic Architecture

SpiderPilot 的核心目标是做一个通用的 AI 自动逆向采集框架，而不是只服务某个行业。

跨境电商中的“商品详情、店铺增量、类目增量”只是一个行业模板示例。SpiderPilot Core 不应该写死 product、shop、category，而应该抽象为更通用的模型。

## 核心抽象

### 1. Entity Model

Entity 表示采集系统中的业务实体。

不同领域的 Entity 示例：

| 领域 | Entity |
|---|---|
| 电商 | product, shop, category, review |
| 新闻 | article, author, channel, tag |
| 招聘 | job, company, recruiter |
| 房产 | house, community, agent |
| 社媒 | post, user, comment, topic |

通用定义：

```yaml
entities:
  article:
    description: 文章
    fields:
      title:
        type: string
        required: true
      published_at:
        type: datetime
        required: false
```

### 2. Page Type

PageType 表示页面类型，不绑定行业。

常见 PageType：

```text
detail
list
search
profile
feed
api
sitemap
```

示例映射：

| 行业 | 页面 | PageType |
|---|---|---|
| 电商 | 商品详情页 | detail |
| 电商 | 类目商品页 | list |
| 新闻 | 文章页 | detail |
| 新闻 | 频道页 | list |
| 招聘 | 职位页 | detail |
| 招聘 | 搜索页 | search |

### 3. Spider Role

SpiderRole 表示爬虫职责，不使用行业词。

通用角色：

```text
detail_collector
list_discoverer
search_discoverer
profile_collector
feed_collector
relationship_discoverer
incremental_discoverer
```

示例：

```yaml
spiders:
  article_detail:
    role: detail_collector
    page_type: detail
    entity: article

  channel_listing:
    role: list_discoverer
    page_type: list
    input_entity: channel
    output_entity: article
```

### 4. Crawl Graph

CrawlGraph 描述多个 Spider 之间的任务流转关系。

SpiderPilot 不假设某个 Spider 必须连接到某个固定 Spider，而是通过图定义：

```yaml
crawl_graph:
  nodes:
    - id: channel_listing
      role: list_discoverer
      input_entity: channel
      output_entity: article

    - id: article_detail
      role: detail_collector
      input_entity: article
      output_entity: article_detail

  edges:
    - from: channel_listing
      to: article_detail
      via: discovered_url
```

### 5. Task Message

Spider 之间通过通用任务消息通信，不写死 product/shop/category。

```json
{
  "platform": "example_news",
  "task": "article_detail",
  "entity_type": "article",
  "entity_id": "123",
  "url": "https://example.com/article/123",
  "source": {
    "task": "channel_listing",
    "entity_type": "channel",
    "url": "https://example.com/news"
  },
  "context": {},
  "priority": 5,
  "created_at": "2026-06-05T12:00:00+08:00"
}
```

## 行业模板

SpiderPilot Core 保持通用，行业能力通过 Domain Templates 提供。

内置模板规划：

```text
generic
ecommerce
news
jobs
real_estate
social_media
```

使用方式：

```bash
spiderpilot platform init allegro --template ecommerce
spiderpilot platform init bbc --template news
spiderpilot platform init jobsite --template jobs
```

## Ecommerce Template 示例

跨境电商模板可以定义：

```yaml
entities:
  product:
  shop:
  category:
  review:

spiders:
  product_detail:
    role: detail_collector
    entity: product

  category_listing:
    role: list_discoverer
    input_entity: category
    output_entity: product
    pushes_to:
      - product_detail

  shop_listing:
    role: list_discoverer
    input_entity: shop
    output_entity: product
    pushes_to:
      - product_detail
```

但这些不是 SpiderPilot Core 的固定概念，只是 ecommerce 模板提供的默认规划。

## 通用流程

```text
Platform Init
  ↓
Domain Template Load
  ↓
Entity Model + Crawl Graph
  ↓
AntiBot Precheck
  ↓
Probe Engine
  ↓
Reverse Engine
  ↓
Field Locator
  ↓
Extraction Plan
  ↓
Code Generator
  ↓
Runner / Validator / Repair
```

## 设计原则

1. Core 不写死任何行业实体。
2. 行业模板只提供默认 Entity、SpiderRole、CrawlGraph。
3. 用户可以修改或新增自己的 Entity 和 CrawlGraph。
4. Spider 之间通过通用 Task Message 通信。
5. 队列命名使用 task_name，而不是 product/shop/category 等固定词。
6. 代码生成器根据 role + page_type + extraction_plan 生成 Spider。
