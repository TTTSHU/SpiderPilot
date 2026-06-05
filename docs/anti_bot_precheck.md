# Anti-Bot Precheck

SpiderPilot 在拿到目标页面后，第一步不是直接生成解析规则，而是先判断页面是否存在反爬、挑战页、Cookie 绑定或动态签名逻辑。

## 核心思路

```text
目标 URL
  ↓
无 Cookie 请求
  ↓
判断是否正常返回
  ↓
如果异常，分析响应状态、跳转链、Set-Cookie 和页面特征
  ↓
识别是否命中常见反爬厂商或自研反爬
  ↓
决定后续策略：纯 HTTP / Cookie 生成 / JS 签名还原 / 浏览器探测 / 暂停人工介入
```

## Step 1: 无 Cookie 基线请求

SpiderPilot 首先使用干净请求访问目标页面：

- 不带用户 Cookie
- 不带浏览器存储状态
- 使用基础 headers
- 记录状态码、响应体、跳转链、Set-Cookie、响应大小、标题和关键脚本

需要记录：

```yaml
baseline:
  url: "https://example.com/product/1001"
  status_code: 200
  final_url: "https://example.com/product/1001"
  redirect_chain: []
  response_size: 183245
  set_cookie_names:
    - datadome
  title: "Example Product"
  looks_like_challenge: false
```

## Step 2: 判断是否正常返回

正常返回通常满足：

- HTTP 状态码为 200
- 页面标题和业务内容正常
- 响应体包含用户样例字段值或业务关键词
- 没有明显 challenge / captcha / blocked / access denied 文案
- 没有异常跳转到验证页面

异常返回包括：

- `403 / 412 / 429 / 503`
- 302 跳转到 challenge 页面
- 响应体极短或只有验证脚本
- 出现验证码、人机验证、访问受限
- 返回内容和浏览器渲染内容明显不同
- 需要特定 Cookie 后才返回业务数据

## Step 3: Cookie 特征识别

如果无 Cookie 请求不能正常返回，SpiderPilot 会分析响应中的 Cookie 特征，判断是否和常见反爬系统匹配。

常见 Cookie / Header / 脚本特征：

| 类型 | 常见特征 |
|---|---|
| DataDome | `datadome` cookie、`ddSession`、`ddOriginalReferrer`、challenge 页面 |
| Cloudflare | `cf_clearance`、`__cf_bm`、`cf_chl_*`、Turnstile |
| Akamai | `_abck`、`bm_sz`、`ak_bmsc`、sensor data |
| PerimeterX | `_px`, `_px3`, `_pxvid`, `px-captcha` |
| Kasada | `x-kpsdk-*`, `kpsdk`, `ct`, `ips.js` |
| Imperva | `incap_ses_*`, `visid_incap_*`, `_incapsula_` |
| Shape/F5 | `TS*`, `Shape`, `f5_cspm`, challenge JS |
| 瑞数 | `412`、`FSSBBIl1UgzbN7N`、`NfBCSins2OywS`、`sdenv` |
| 字节系 | `webmssdk`、`byted_acrawler`、`X-Bogus`、`a_bogus` |

## Step 4: 响应差异对比

SpiderPilot 会至少做两类对比：

```text
A. HTTP 干净请求结果
B. 浏览器探测结果
```

对比内容：

- 状态码是否不同
- 最终 URL 是否不同
- Set-Cookie 是否不同
- HTML 大小是否不同
- 页面标题是否不同
- 是否只有浏览器能拿到业务数据
- 业务字段样例值是否只在浏览器结果中出现

如果浏览器能看到业务数据，而纯 HTTP 不能看到，则继续分析：

```text
是 Cookie 挑战？
是 JS 生成签名？
是接口需要动态 header？
是 TLS/HTTP2 指纹问题？
是必须登录？
```

## Step 5: 反爬分类

SpiderPilot 初步分为几类：

### 1. 无明显反爬

```text
无 Cookie 请求即可返回业务数据
```

策略：

```text
直接进入 Source Detection 和 Field Locator
```

### 2. Cookie Challenge 型

```text
第一次请求返回挑战脚本或 Set-Cookie
第二次带 Cookie 才能访问业务页面
```

策略：

```text
分析 Cookie 生成逻辑
优先还原协议生成过程
必要时使用浏览器作为分析工具
```

### 3. JS 签名型

```text
接口请求需要 sign / token / timestamp / x-* 动态参数
```

策略：

```text
定位签名函数
提取输入参数
还原签名算法
生成 Node/Python 签名模块
```

### 4. 浏览器环境绑定型

```text
请求依赖 navigator、canvas、webgl、screen、timezone、storage 等浏览器环境
```

策略：

```text
对比真实浏览器环境和 Node/jsdom 环境
最小化补环境
生成可复现的签名/请求模块
```

### 5. 登录态/权限型

```text
不登录无法看到目标字段
```

策略：

```text
标记 requires_auth
提示用户提供登录态 Cookie 或状态文件
```

### 6. 验证码/人工挑战型

```text
出现 captcha / slider / turnstile / hcaptcha 等
```

策略：

```text
标记 manual_required
暂停自动生成，等待人工处理或接入合法验证码流程
```

## Step 6: 输出 AntiBot Report

预检结果输出为结构化报告：

```yaml
anti_bot:
  status: detected
  vendor: datadome
  confidence: 0.92
  baseline_status: 403
  browser_status: 200
  requires_cookie: true
  requires_js_challenge: true
  requires_auth: false
  evidence:
    set_cookie:
      - datadome
    response_keywords:
      - "DataDome"
      - "captcha"
    script_keywords:
      - "ddOriginalReferrer"
  recommended_strategy:
    - analyze_cookie_generation
    - capture_browser_network
    - compare_cookie_before_after_challenge
```

## 在整体流程中的位置

```text
Spec 输入
  ↓
AntiBot Precheck
  ↓
Page Probe
  ↓
Source Detection
  ↓
Field Locator
  ↓
Extraction Plan
  ↓
Spider Generator
  ↓
Runner / Validator / Repair
```

## 设计原则

1. 先判断能不能无 Cookie 正常访问。
2. 如果不能，先看 Cookie 和响应特征是否命中常见反爬厂商。
3. 不要一开始就使用浏览器作为最终采集方案。
4. 浏览器优先作为分析工具，用于抓包、对比和定位。
5. 最终采集优先生成纯 HTTP / Scrapy / 签名模块方案。
6. 所有反爬判断必须输出证据，不能只靠猜测。
