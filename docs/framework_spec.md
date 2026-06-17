# Python 爬虫框架开发规范 v1.0

## 1. 设计目标

本规范定义了一个标准化的 Python 爬虫框架接口，使得 AI 可以按固定契约生成爬虫代码。框架基于 Scrapy，增加 TLS 指纹、代理轮换、多步链路、字段声明等能力。

```
AI 生成代码 → 继承 BaseSpider → 实现指定方法 → 直接运行
```

## 2. 基类：BaseSpider

所有 AI 生成的爬虫必须继承 `BaseSpider`，并实现以下方法：

```python
class BaseSpider(RedisSpider):
    """
    标准化爬虫基类。
    AI 生成子类时必须实现：
      - field_spec    : 字段声明（类属性）
      - build_request : 构建初始请求
      - parse         : 解析响应 → 提取字段 → yield item
    """
    
    # ── 子类必须定义的类属性 ──
    name: str                    # 爬虫名称
    field_spec: dict             # 字段声明（见第3节）
    
    # ── 子类可选覆盖的类属性 ──
    download_method: str = "curl_cffi"  # curl_cffi | requests | scrapy_default
    tls_fingerprint: str = "chrome120"  # TLS 指纹版本
    proxy_enabled: bool = True          # 是否启用代理
    proxy_list_file: str = "ips.txt"    # 代理文件路径
    max_retries: int = 3                # 每个请求最大重试次数
    
    # ── 子类必须实现的方法 ──
    def make_request_from_data(self, data: bytes) -> Request | None:
        """
        从 Redis 队列消费任务数据，构建初始请求。
        
        Args:
            data: Redis 队列中的原始字节数据（通常是 JSON 编码的 URL 或参数）
        
        Returns:
            scrapy.Request 对象，或 None（跳过无效数据）
        
        Example:
            payload = json.loads(data.decode())
            return scrapy.Request(
                url=payload["url"],
                callback=self.parse,
                meta={"product_id": payload.get("id")}
            )
        """
        raise NotImplementedError
    
    # ── 子类必须实现的方法 ──
    def parse(self, response: Response) -> Generator[dict, None, None]:
        """
        解析响应，提取字段，yield item。
        
        Args:
            response: Scrapy Response 对象
        
        Yields:
            dict: 提取的数据 item，格式为 {field_name: value}
        
        Example:
            data = response.json()
            item = {}
            item["title"] = json_path(data, "$.data.product.title")
            item["price"] = json_path(data, "$.data.product.price")
            yield item
        """
        raise NotImplementedError
```

## 3. 字段声明：field_spec

```python
field_spec = {
    "field_name": {
        "type": str,           # str | int | float | list | dict
        "required": bool,      # 是否必填
        "source": str,         # json_response | html_selector | html_xpath | json_doc
        "path": str,           # JSONPath ($.data.title) 或 CSS (.title) 或 XPath (//h1)
        "normalize": str,      # 可选: strip | int | float | parse_price | parse_date
        "fallback": Any,       # 可选: 提取失败时的默认值
    }
}
```

## 4. 下载器接口

```python
class DownloaderInterface:
    """
    所有下载器必须实现的接口。
    框架提供两种内置实现：CurlCffiDownloader 和 RequestsDownloader。
    """
    
    @staticmethod
    def get(url: str, headers: dict = None, proxy: str = None, **kwargs) -> Response:
        """GET 请求"""
        pass
    
    @staticmethod
    def post(url: str, json: dict = None, data: str = None, 
             headers: dict = None, proxy: str = None, **kwargs) -> Response:
        """POST 请求"""
        pass
    
    @staticmethod
    def graphql(url: str, query: str, variables: dict = None,
                headers: dict = None, proxy: str = None, **kwargs) -> Response:
        """GraphQL 请求"""
        pass


class CurlCffiDownloader(DownloaderInterface):
    """基于 curl_cffi 的下载器，支持 TLS 指纹伪装"""
    
    impersonate: str = "chrome120"  # chrome120 | chrome110 | safari15_5 | edge101
    
    def __init__(self, proxy_list: list[str] = None):
        self.session = curl_requests.Session(impersonate=self.impersonate, verify=False)
        self.proxy_list = proxy_list or []
    
    def _get_proxy(self) -> dict | None:
        if not self.proxy_list:
            return None
        proxy = random.choice(self.proxy_list)
        return {"http": proxy, "https": proxy}
```

## 5. 解析器接口

```python
class ParserInterface:
    """
    所有解析器必须实现的接口。
    框架提供：JsonParser, HtmlParser, GraphQLParser。
    """
    
    @staticmethod
    def extract(response: Response, field_spec: dict) -> dict:
        """
        根据 field_spec 从响应中提取字段。
        
        Args:
            response: Scrapy Response
            field_spec: 字段声明
        
        Returns:
            dict: {field_name: value}
        """
        pass


class JsonParser:
    """JSON 响应解析器"""
    
    @staticmethod
    def extract(response: Response, field_spec: dict) -> dict:
        data = response.json()
        item = {}
        for name, spec in field_spec.items():
            if spec["source"] != "json_response":
                continue
            value = resolve_json_path(data, spec["path"])
            item[name] = normalize(value, spec.get("normalize"))
        return item

class HtmlParser:
    """HTML 解析器，支持 CSS 选择器和 XPath"""
    
    @staticmethod
    def css(response: Response, selector: str) -> str:
        return response.css(selector).get(default="")
    
    @staticmethod
    def xpath(response: Response, xpath: str) -> str:
        return response.xpath(xpath).get(default="")
```

## 6. 多步链路模式

爬虫分为两种模式，AI 生成代码时根据 Spec 选择：

### 模式 A：单步爬虫（页面 → 解析 → 入库）
```
请求页面 → parse → 提取字段 → yield item
```
适用：页面本身包含所有字段（HTML/内嵌 JSON/JSON-LD）

### 模式 B：多步链路爬虫（请求 A → 请求 B → 合并 → 入库）
```
请求 A → parse_A → 提取部分字段 → 构建请求 B
     → parse_B → 提取部分字段 → 合并 → yield item
```
适用：需要先请求列表再请求详情、需要先拿 token 再拿数据

### 模式 C：链式变体爬虫（主请求 → N 个变体请求 → 聚合）
```
请求主数据 → 解析变体列表 → 对每个变体串行请求 N 个接口 → 聚合 yield
```
适用：empik 类多变体、多接口拼接

多步链路的声明方式：

```python
class MySpider(BaseSpider):
    # 声明链路
    chain = [
        {"name": "variants",    "url": GRAPHQL_URL, "method": "POST", "query": QUERY_VARIANTS},
        {"name": "static_info", "url": GRAPHQL_URL, "method": "POST", "query": QUERY_STATIC},
        {"name": "offers",      "url": GRAPHQL_URL, "method": "POST", "query": QUERY_OFFERS},
        {"name": "best_offer",  "url": GRAPHQL_URL, "method": "POST", "query": QUERY_BEST},
    ]
    
    current_step: int = 0  # 当前链路位置（框架自动推进）
```

## 7. 队列接口

```python
class QueueInterface:
    """
    任务队列抽象。
    内置实现：RedisQueue, MemoryQueue。
    """
    
    def push(self, task: TaskMessage) -> None:
        """推送任务到队列"""
        pass
    
    def pop(self) -> TaskMessage | None:
        """从队列取出任务"""
        pass


@dataclass
class TaskMessage:
    """标准化任务消息"""
    platform: str           # 平台名，如 "empik"
    task: str               # 任务类型，如 "product_detail"
    entity_type: str        # 实体类型，如 "product"
    url: str                # 目标 URL
    entity_id: str = None   # 可选的实体 ID
    context: dict = None    # 附加上下文参数
```

## 8. 存储接口

```python
class StorageInterface:
    """
    数据存储抽象。
    内置实现：MongoDBPipeline, JSONFilePipeline。
    """
    
    def save(self, item: dict) -> None:
        pass


class MongoDBPipeline(StorageInterface):
    def __init__(self, uri: str, db: str, collection: str):
        self.client = pymongo.MongoClient(uri)
        self.collection = self.client[db][collection]
    
    def save(self, item: dict):
        item["_id"] = item.get("_id") or hashlib.md5(
            json.dumps(item, sort_keys=True).encode()
        ).hexdigest()
        self.collection.update_one({"_id": item["_id"]}, {"$set": item}, upsert=True)
```

## 9. 辅助函数

框架提供以下内置辅助函数，AI 无需重复生成：

```python
# JSON 路径解析
json_path(data, "$.data.product.title")      → data["data"]["product"]["title"]
json_path(data, "$.items[0].name")           → data["items"][0]["name"]
json_path(data, "$.data.*.name")             → 通配符支持

# 字段标准化
normalize("  hello  ", "strip")              → "hello"
normalize("39.99", "parse_price")            → 39.99
normalize("12345", "int")                    → 12345
normalize("2024-01-15", "parse_date")        → datetime(2024,1,15)

# 签名工具
sign_params(params: dict, secret: str)       → 签名字符串
build_query_string(params: dict)             → URL query string

# 安全工具
safe_get(dict, *keys)                        → 安全嵌套取值，为 None 不抛异常
extract_number("39.99 zł")                  → 39.99
md5("hello")                                → "5d41402abc4b..."
```

## 10. 完整示例：AI 生成的 Empik 爬虫

```python
class EmpikProductSpider(BaseSpider):
    name = "empik_product"
    download_method = "curl_cffi"
    tls_fingerprint = "chrome120"
    proxy_enabled = True
    
    field_spec = {
        "title":        {"type": str, "source": "json_response", "path": "$.data.getProduct.baseInformation.name", "required": True, "normalize": "strip"},
        "price":        {"type": float, "source": "json_response", "path": "$.data.getProduct.bestOffer.originalPrice", "required": True, "normalize": "parse_price"},
        "rating_score": {"type": float, "source": "json_response", "path": "$.data.getProduct.baseInformation.rating.score"},
        "rating_count": {"type": int, "source": "json_response", "path": "$.data.getProduct.baseInformation.rating.count", "normalize": "int"},
        "description":  {"type": str, "source": "json_response", "path": "$.data.getProduct.descriptionData.cleanDescription"},
        "shop_name":    {"type": str, "source": "json_response", "path": "$.data.getOffersForProduct[0].shop.name"},
    }
    
    # 多步链路声明
    chain = [
        {"name": "variants",     "url": "https://www.empik.com/gateway/api/graphql/products", 
         "method": "POST", "body_template": "getVariants"},
        {"name": "static_info",  "url": "https://www.empik.com/gateway/api/graphql/products", 
         "method": "POST", "body_template": "getProductStaticInfo"},
    ]
    
    def build_request(self, product_id: str) -> Request:
        """AI 只需实现这一步：把 product_id 转成首次请求"""
        body = {
            "operationName": "getVariants",
            "variables": {"productId": product_id},
            "query": self.QUERY_VARIANTS,
        }
        return scrapy.Request(
            url="https://www.empik.com/gateway/api/graphql/products",
            method="POST",
            body=json.dumps(body),
            headers={"content-type": "application/json"},
            callback=self.parse,
            meta={"stage": 0, "product_id": product_id}
        )
```

## 11. AI 生成代码的输入格式

AI 接收以下 Extraction Plan（YAML），输出符合本规范的爬虫代码：

```yaml
# Extraction Plan — 本规范的输入格式
name: empik_product
platform: empik
spider_mode: chain              # single | chain | variant_chain
tls_fingerprint: chrome120
proxy_required: true

source:
  type: json_response
  sample_urls:
    - https://www.empik.com/xxx

fields:
  title:
    source: json_response
    path: "$.data.getProduct.baseInformation.name"
    type: str
    required: true
    normalize: strip
  price:
    source: json_response
    path: "$.data.getProduct.bestOffer.originalPrice"
    type: float
    required: true
    normalize: parse_price

chain:
  - name: variants
    url: https://www.empik.com/gateway/api/graphql/products
    method: POST
    body_template: getVariants
  - name: static_info
    url: https://www.empik.com/gateway/api/graphql/products
    method: POST
    body_template: getProductStaticInfo
```

## 12. 目录结构

```
spider_framework/
├── base_spider.py          # BaseSpider 基类
├── downloader/
│   ├── __init__.py
│   ├── interface.py        # DownloaderInterface
│   ├── curl_cffi.py        # CurlCffiDownloader
│   └── requests.py         # RequestsDownloader
├── parser/
│   ├── __init__.py
│   ├── interface.py        # ParserInterface
│   ├── json_parser.py      # JsonParser
│   └── html_parser.py      # HtmlParser
├── pipeline/
│   ├── __init__.py
│   ├── interface.py        # StorageInterface
│   └── mongodb.py          # MongoDBPipeline
├── queue/
│   ├── __init__.py
│   ├── interface.py        # QueueInterface
│   └── redis_queue.py      # RedisQueue
├── helpers.py              # json_path, normalize, sign_params, ...
├── models.py               # TaskMessage, ExtractionPlan, ...
└── generated/              # AI 生成的爬虫放这里
    ├── empik_product.py
    └── allegro_product.py
```
