# Current Status

SpiderPilot 当前已经打通 8 步 MVP 主链路：

```text
Spec → AntiBot → Probe → Reverse → Plan → Codegen → Run/Validate → Repair
```

## 已完成能力

- CLI 基础命令
- `create --run-all` 一键工作流
- Spec YAML 加载与校验
- AntiBot HTTP 预检
- AntiBot Strategy 报告
- HTTP Probe artifacts
- JSON response 自动保存到 `responses/response_0.json`
- Probe index
- Embedded JSON / JSON-LD / `__NEXT_DATA__` 反查
- `responses/*.json` 反查
- source-aware Extraction Plan
- dependency-light Python extractor codegen
- Scrapy JSON spider codegen MVP
- artifacts runner
- HTTP runner
- Validate 报告
- Repair loop MVP
- TaskMessage 序列化
- Memory queue / Redis List queue abstraction
- domain templates: generic, ecommerce, news, jobs, real_estate, social_media
- mock HTTP JSON E2E 测试

- CloakBrowser real CDP/Network capture MVP
- HTTP vs CloakBrowser probe diff
- CSS selector inference
- XPath inference
- URL pattern inference
- Link discovery and TaskMessage output
- `create --run-all --with-cloak` workflow
## 仍未完成/高级能力

- rendered.html / screenshot / cookies / storage 实采
- API URL pattern 推断
- 分页/listing 自动发现
- JS 签名定位与还原
- 自动 Repair 修改 plan 并重跑
- 完整 Scrapy settings/items/pipelines/redis queue 生成
- Redis Stream ACK/retry/priority

## 当前推荐下一步

1. 接入 CloakBrowser CDP/HAR 抓包能力。
2. 给 Reverse 增加 CSS/XPath selector 推导。
3. 给 Codegen 生成更完整 Scrapy project artifacts。
