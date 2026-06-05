# SpiderPilot Workflow

SpiderPilot 的核心流程分为 8 步：

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

这 8 步既可以通过一个命令串起来：

```bash
spiderpilot create -f examples/product_detail.yaml
```

也可以拆开调试：

```bash
spiderpilot spec check -f examples/product_detail.yaml
spiderpilot antibot -f examples/product_detail.yaml
spiderpilot probe -f examples/product_detail.yaml
spiderpilot reverse -f examples/product_detail.yaml
spiderpilot generate -p workspace/plans/product_detail_demo.yaml
spiderpilot run product_detail_demo
spiderpilot validate product_detail_demo
spiderpilot repair product_detail_demo
```

## 1. Spec 输入

用户提供一个结构化任务文件，描述：

- 任务名称
- 页面类型
- 多个样例 URL
- 每个 URL 对应的字段样例值
- 目标字段定义

示例：

```yaml
version: 1
name: product_detail_demo
target_type: detail

samples:
  - id: sample_1
    url: "https://example.com/product/1001"
    expected:
      title:
        equals: "Apple iPhone 15 128GB Black"
      price:
        equals: "3999.00"

  - id: sample_2
    url: "https://example.com/product/1002"
    expected:
      title:
        equals: "Samsung Galaxy S24 256GB"
      price:
        equals: "4599.00"

fields:
  title:
    type: string
    required: true
  price:
    type: decimal
    required: true
```

目标：

```text
把自然语言需求转成可校验、可复用、可版本管理的 Spec。
```

输出：

```text
workspace/specs/{task_name}.yaml
```

---

## 2. AntiBot Precheck 反爬预检

拿到 URL 后，SpiderPilot 不会立刻解析页面，而是先判断目标是否能正常访问。

流程：

```text
无 Cookie 请求 URL
  ↓
记录 status_code / headers / set-cookie / body / redirect_chain
  ↓
判断是否正常返回业务内容
  ↓
如果异常，识别反爬特征
```

重点判断：

- 是否返回 `403 / 412 / 429 / 503`
- 是否跳转 challenge 页面
- 是否出现 `captcha / challenge / blocked / access denied`
- 是否 Set-Cookie 中出现反爬特征
- 是否命中 DataDome、Cloudflare、Akamai、Kasada、PerimeterX、瑞数、字节系签名等特征

输出示例：

```yaml
anti_bot:
  status: detected
  vendor: datadome
  confidence: 0.91
  baseline_status: 403
  requires_cookie: true
  requires_js_challenge: true
```

目标：

```text
先判断目标属于纯 HTTP、Cookie Challenge、JS 签名、浏览器环境绑定、登录态还是人工挑战。
```

详细设计见：[`anti_bot_precheck.md`](anti_bot_precheck.md)

---

## 3. Probe 页面探测

通过 HTTP 和 CloakBrowser 探测页面，保存可复现分析证据。

探测产物：

```text
workspace/artifacts/{task_name}/
├── sample_1/
│   ├── raw.html
│   ├── headers.json
│   ├── cookies.json
│   ├── network.har
│   ├── rendered.html
│   ├── screenshot.png
│   └── responses/
└── sample_2/
    ├── raw.html
    ├── headers.json
    ├── cookies.json
    ├── network.har
    ├── rendered.html
    ├── screenshot.png
    └── responses/
```

探测内容：

- 原始 HTML
- 渲染后 DOM
- 请求头 / 响应头
- Set-Cookie
- Network / HAR
- API 响应样本
- 页面截图
- localStorage / sessionStorage，必要时

目标：

```text
让 AI 和程序都基于 artifacts 分析，而不是凭空猜测页面结构。
```

---

## 4. Reverse 自动逆向

这是 SpiderPilot 的核心步骤。

输入：

- 用户 expected 字段样例
- raw.html
- rendered.html
- network responses
- 内嵌 JSON
- cookies
- headers

核心动作：

```text
在所有 artifacts 中反查字段样例值。
```

例如用户给：

```yaml
price:
  equals: "3999.00"
```

SpiderPilot 会寻找：

- 哪个 API 响应包含 `3999.00`
- 哪个 JSONPath 命中该字段
- 哪个 HTML selector 命中该字段
- 哪个内嵌 JSON 命中该字段
- 多个 URL 是否在同一路径上稳定命中

候选来源优先级：

```text
API JSON
  >
内嵌 JSON / __NEXT_DATA__ / JSON-LD
  >
静态 HTML
  >
渲染 DOM
```

输出候选路径：

```yaml
candidates:
  title:
    - source: api
      path: "$.data.product.title"
      samples_matched: 2
      confidence: 0.98

  price:
    - source: api
      path: "$.data.offer.price.amount"
      samples_matched: 2
      confidence: 0.96
```

目标：

```text
根据字段样例值反向定位稳定数据源，而不是人工写 selector/json path。
```

---

## 5. Extraction Plan 抽取计划

Reverse 之后，不直接生成代码，而是先生成结构化抽取计划。

示例：

```yaml
version: 1
name: product_detail_demo

source:
  type: api
  method: GET
  url_pattern: "https://example.com/api/product/{product_id}"
  confidence: 0.96

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

输出：

```text
workspace/plans/{task_name}.yaml
```

目标：

```text
把 AI 逆向结果固化为可审查、可测试、可代码生成、可修复的中间产物。
```

---

## 6. Codegen 代码生成

根据 Extraction Plan 生成可运行爬虫。

输入：

```text
workspace/plans/{task_name}.yaml
```

输出：

```text
workspace/generated_spiders/{task_name}.py
```

生成类型：

- API Spider
- HTML Spider
- CloakBrowser-assisted Spider

优先级：

```text
API Spider > HTML Spider > CloakBrowser-assisted Spider
```

目标：

```text
生成可维护的 Scrapy Spider，而不是一次性脚本。
```

---

## 7. Run / Validate 运行校验

生成 Spider 后立即运行，并校验输出结果。

运行输出：

```text
workspace/results/{task_name}.json
```

校验内容：

- 必填字段是否非空
- 字段类型是否正确
- 字段值是否匹配 expected
- 多样本命中率是否达标
- 价格是否可转 decimal
- URL 是否合法
- 列表字段是否包含 expected contains

校验报告：

```yaml
validation:
  ok: true
  samples_total: 2
  samples_passed: 2
  field_hit_rate: 1.0
```

目标：

```text
不只生成代码，还要证明代码能跑、字段能命中。
```

---

## 8. Repair 自动修复

如果校验失败，SpiderPilot 进入自动修复循环。

失败示例：

```yaml
validation:
  ok: false
  errors:
    - field: price
      reason: empty
      current_path: "$.data.offer.price.amount"
```

Repair 会重新分析：

- 当前 path 为什么取不到
- API 响应结构是否变化
- 字段是否在另一个 response
- 是否应该改用 HTML selector
- 是否需要 Cookie
- 是否需要签名参数
- 是否命中反爬

修复对象：

- Extraction Plan
- selector
- json path
- request headers
- request URL
- signature module，后续支持

修复循环：

```text
repair plan
  ↓
generate code
  ↓
run
  ↓
validate
  ↓
最多重试 3 次
```

目标：

```text
让 SpiderPilot 形成生成、运行、验证、修复的闭环。
```

---

## MVP 开发顺序

建议按以下顺序落地：

```text
MVP-1: Spec 模型 + create 命令骨架
MVP-2: HTTP AntiBot Precheck
MVP-3: HTTP Probe
MVP-4: 字段样例值反查
MVP-5: Extraction Plan 生成
MVP-6: 简单 Scrapy Spider 生成
MVP-7: Run / Validate
MVP-8: Repair 闭环
```

## 最终目标

```text
用户输入少量 URL + 字段样例值，SpiderPilot 自动完成：
反爬预检、页面探测、字段反查、接口定位、抽取计划生成、代码生成、运行校验和自动修复。
```
