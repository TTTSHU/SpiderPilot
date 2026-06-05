# SpiderPilot

> AI-powered field-driven reverse crawling framework.  
> 字段样例驱动的 AI 自动逆向爬虫框架。

SpiderPilot 是一个面向 AI 快速开发的爬虫生成框架。用户只需要提供多个样例 URL、目标字段以及字段对应的样例值，SpiderPilot 会自动探测页面、分析接口、定位字段来源、生成抽取计划，并产出可运行、可维护、可验证的爬虫代码。

## 核心理念

传统爬虫开发通常需要人工完成：

```text
分析页面 → 找接口 → 写 selector/json path → 编写 Spider → 调试 → 修复
```

SpiderPilot 希望把这个流程变成：

```text
输入 URL + 字段样例 → 自动逆向 → 自动生成爬虫 → 自动运行校验 → 自动修复
```

也就是：

```text
From examples to spiders.
```

## 通用架构设计

SpiderPilot 不绑定某个行业。跨境电商中的商品详情、店铺增量、类目增量只是 `ecommerce` 行业模板。

核心抽象包括：

- `Entity Model`：业务实体，例如 product、article、job、house、post
- `Page Type`：页面类型，例如 detail、list、search、profile、feed、api
- `Spider Role`：爬虫职责，例如 detail_collector、list_discoverer、search_discoverer
- `Crawl Graph`：多个 Spider 之间的任务流转关系
- `Task Message`：Spider 之间传递的通用任务消息

行业能力通过模板扩展：

```text
generic
ecommerce
news
jobs
real_estate
social_media
```

详细设计见：[`docs/generic_architecture.md`](docs/generic_architecture.md)


## 核心工作流

SpiderPilot 的完整工作流分为 8 步：

```text
1. Spec 输入
2. AntiBot Precheck 反爬预检
3. Probe 页面探测
4. Reverse 自动逆向
5. Extraction Plan 抽取计划
6. Codegen 代码生成
7. Run / Validate 运行校验
8. Repair 自动修复
```

详细设计见：[`docs/workflow.md`](docs/workflow.md)

## 主要功能

### 1. 多 URL 样例输入

支持用户提供多个页面样例，用于交叉验证字段位置，提高解析准确率。

```yaml
samples:
  - url: "https://example.com/product/1001"
    expected:
      title:
        equals: "Apple iPhone 15 128GB Black"
      price:
        equals: "3999.00"
      shop_name:
        equals: "SuperStore"

  - url: "https://example.com/product/1002"
    expected:
      title:
        equals: "Samsung Galaxy S24 256GB"
      price:
        equals: "4599.00"
      shop_name:
        equals: "MobileWorld"
```

### 2. 字段样例驱动的自动逆向

根据用户给定的字段样例值，自动在以下数据源中反向查找字段来源：

- 原始 HTML
- 渲染后 DOM
- Network API 响应
- JSON-LD
- `__NEXT_DATA__`
- `window.__INITIAL_STATE__`
- XHR / Fetch 请求
- 页面内嵌 JSON

### 3. 自动生成 Extraction Plan

SpiderPilot 会把逆向结果固化为结构化抽取计划：

```yaml
fields:
  title:
    source: json
    path: "$.data.product.title"
    confidence: 0.98

  price:
    source: json
    path: "$.data.offer.price.amount"
    normalize: parse_decimal
    confidence: 0.96
```

### 4. 自动生成 Scrapy Spider

根据 Extraction Plan 自动生成可运行的 Scrapy 爬虫代码。

支持方向：

- API Spider
- HTML Spider
- CloakBrowser 辅助探测
- JSONPath 字段提取
- CSS / XPath 字段提取
- 字段标准化处理

### 5. 自动运行与校验

生成爬虫后自动执行，并校验：

- 必填字段是否为空
- 字段类型是否正确
- 价格是否可转数字
- URL 是否合法
- 列表字段是否命中样例
- 多 URL 样例命中率是否达标

### 6. 自动修复闭环

当字段为空或解析失败时，SpiderPilot 会根据：

- 运行日志
- 页面 artifacts
- 当前抽取计划
- 字段校验报告

自动尝试修复 selector、json path 或请求逻辑。

### 7. Anti-Bot Precheck 反爬预检

SpiderPilot 在页面探测后会优先判断目标是否存在反爬：

- 先用无 Cookie 请求建立基线
- 判断页面是否正常返回业务内容
- 如果异常，分析状态码、跳转链、Set-Cookie、响应关键词和关键脚本
- 识别 DataDome、Cloudflare、Akamai、Kasada、PerimeterX、瑞数、字节系签名等常见特征
- 输出结构化 AntiBot Report
- 再决定后续走纯 HTTP、Cookie 生成、JS 签名还原、浏览器探测或人工登录态

详细设计见：[`docs/anti_bot_precheck.md`](docs/anti_bot_precheck.md)

## 推荐工作流

```text
1. 用户创建 Spec
2. SpiderPilot 探测页面
3. 捕获 HTML / DOM / Network / API 响应
4. 根据字段样例值自动反查字段来源
5. 多样本交叉验证稳定路径
6. 生成 Extraction Plan
7. 生成 Scrapy Spider
8. 运行爬虫并输出结果
9. 校验字段命中率
10. 失败后自动修复
```

## 计划目录结构

```text
SpiderPilot/
├── README.md
├── pyproject.toml
├── .env.example
├── spiderpilot/
│   ├── __init__.py
│   ├── cli.py                    # CLI 入口
│   ├── workflow.py               # 主工作流编排
│   ├── models.py                 # Pydantic 数据模型
│   ├── llm.py                    # LLM 调用封装
│   │
│   ├── core/                     # 通用核心抽象
│   │   ├── __init__.py
│   │   └── models.py             # Entity / PageType / CrawlGraph / TaskMessage
│   │
│   ├── platform/                 # 平台画像与 Spider 矩阵规划
│   │   └── __init__.py
│   │
│   ├── templates/                # 行业模板
│   │   ├── __init__.py
│   │   └── domains/
│   │       ├── generic.yaml
│   │       ├── ecommerce.yaml
│   │       └── news.yaml
│   │
│   ├── antibot/                  # 反爬预检模块
│   │   └── __init__.py
│   │
│   ├── probe/                    # 页面探测模块
│   │   ├── __init__.py
│   │   ├── http_probe.py         # httpx/requests 原始请求
│   │   ├── browser_probe.py      # CloakBrowser 浏览器渲染
│   │   └── network_capture.py    # Network/HAR/API 响应捕获
│   │
│   ├── reverse/                  # 自动逆向模块
│   │   ├── __init__.py
│   │   ├── source_detector.py    # 数据源识别
│   │   ├── field_locator.py      # 字段样例值反查
│   │   ├── json_analyzer.py      # JSONPath 分析
│   │   ├── html_analyzer.py      # CSS/XPath 分析
│   │   └── signature_detector.py # JS 签名/动态参数识别
│   │
│   ├── planner/                  # 抽取计划模块
│   │   ├── __init__.py
│   │   └── extraction_plan.py
│   │
│   ├── generator/                # 代码生成模块
│   │   ├── __init__.py
│   │   ├── scrapy_generator.py
│   │   └── templates/
│   │       ├── api_spider.py.j2
│   │       ├── html_spider.py.j2
│   │       └── test_spider.py.j2
│   │
│   ├── runner/                   # 运行模块
│   │   ├── __init__.py
│   │   └── scrapy_runner.py
│   │
│   ├── validator/                # 校验模块
│   │   ├── __init__.py
│   │   └── result_validator.py
│   │
│   └── repair/                   # 自动修复模块
│       ├── __init__.py
│       └── auto_repair.py
│
├── workspace/
│   ├── specs/                    # 用户输入 Spec
│   ├── artifacts/                # 页面探测产物
│   ├── plans/                    # Extraction Plan
│   ├── generated_spiders/        # 生成的爬虫
│   └── results/                  # 运行结果
│
├── examples/
│   └── product_detail.yaml
└── tests/
```

## CLI 设计草案

```bash
# 初始化任务 Spec
spiderpilot init product_detail

# 根据 Spec 一键创建爬虫
spiderpilot create -f workspace/specs/product_detail.yaml

# 只探测页面，不生成代码
spiderpilot probe -f workspace/specs/product_detail.yaml

# 自动逆向字段来源
spiderpilot reverse -f workspace/specs/product_detail.yaml

# 根据 Extraction Plan 生成代码
spiderpilot generate -p workspace/plans/product_detail.yaml

# 运行生成的爬虫
spiderpilot run product_detail

# 校验结果
spiderpilot validate product_detail
```

## MVP 目标

第一版优先支持：

- 单页面详情页
- 多 URL 样例输入
- 字段样例值反查
- 静态 HTML 分析
- API JSON 分析
- 内嵌 JSON / JSON-LD / `__NEXT_DATA__` 分析
- 生成 Scrapy Spider
- 运行并输出 JSON 结果
- 基础字段校验

暂不优先支持：

- 登录态复杂站点
- 验证码
- 强反爬
- 大规模分布式调度
- 自动部署

## 技术栈

- Python
- Scrapy
- CloakBrowser
- httpx
- parsel / lxml
- Pydantic
- Jinja2
- pytest
- OpenAI API / Local LLM


## CLI 快速示例

```bash
# 查看可用行业模板
spiderpilot template list

# 初始化平台工作区
spiderpilot platform init demo --domain example.com --template ecommerce

# 创建任务
spiderpilot create -f examples/ecommerce/product_detail.yaml

# 一键执行 MVP 工作流
spiderpilot create -f examples/ecommerce/product_detail.yaml --run-all

# 分步调试
spiderpilot antibot -f workspace/specs/product_detail_demo.yaml
spiderpilot probe -f workspace/specs/product_detail_demo.yaml
spiderpilot reverse -f workspace/specs/product_detail_demo.yaml
spiderpilot plan -f workspace/specs/product_detail_demo.yaml
spiderpilot generate -p workspace/plans/product_detail_demo.yaml --kind python
spiderpilot generate -p workspace/plans/product_detail_demo.yaml --kind scrapy
spiderpilot run -f workspace/specs/product_detail_demo.yaml -p workspace/plans/product_detail_demo.yaml --mode artifacts
spiderpilot run -f workspace/specs/product_detail_demo.yaml -p workspace/plans/product_detail_demo.yaml --mode http
spiderpilot validate -f workspace/specs/product_detail_demo.yaml -r workspace/results/product_detail_demo.json
spiderpilot repair-loop -f workspace/specs/product_detail_demo.yaml
```

## 当前状态

当前能力和未完成事项见：[`docs/current_status.md`](docs/current_status.md)

## 项目状态

SpiderPilot 当前处于早期设计与 MVP 开发阶段。
