from pathlib import Path
from spiderpilot.generator.codegen import _class_name
from spiderpilot.runner.local_runner import _extract_mvp_value
from spiderpilot.validator.result_validator import _matches_expected
from spiderpilot.spec import ExpectedValue
from spiderpilot.repair.auto_repair import _suggest_action


def test_class_name():
    assert _class_name("product_detail_demo") == "ProductDetailDemoSpider"


def test_extract_mvp_value():
    assert _extract_mvp_value("hello price 123", {"evidence": {"matched_value": "123"}}) == "123"
    assert _extract_mvp_value("hello sample2", {"evidence": {"matched_value": "sample1", "samples": {"s2": {"matched_value": "sample2"}}}}, sample_id="s2") == "sample2"
    assert _extract_mvp_value("hello", {"evidence": {"matched_value": "123"}}) is None


def test_matches_expected():
    assert _matches_expected("abc", ExpectedValue(equals="abc"))
    assert _matches_expected("abcdef", ExpectedValue(contains=["abc", "def"]))


def test_suggest_action():
    assert "required" in _suggest_action({"reason": "required_empty"})["action"]


def test_extract_json_doc_path_value():
    html = '<script type="application/ld+json">{"name":"Example Product"}</script>'
    assert _extract_mvp_value(html, {"evidence": {"path": "json_doc:0:$.name"}}) == "Example Product"


def test_extract_json_response_path_value(tmp_path):
    responses = tmp_path / "responses"
    responses.mkdir()
    (responses / "api.json").write_text("{\"data\":{\"price\":\"123\"}}", encoding="utf-8")
    assert _extract_mvp_value("", {"evidence": {"path": "json_response:api.json:$.data.price"}}, sample_dir=tmp_path) == "123"


def test_generated_extractor_executes_json_response(tmp_path):
    import importlib.util
    import yaml
    from spiderpilot.generator.codegen import generate_spider

    plan = {
        "name": "demo_json",
        "fields": {
            "price": {
                "evidence": {
                    "path": "json_response:api.json:$.data.price",
                    "matched_value": "123",
                }
            }
        },
    }
    plan_path = tmp_path / "plan.yaml"
    plan_path.write_text(yaml.safe_dump(plan), encoding="utf-8")
    result = generate_spider(plan_path, workspace=tmp_path)
    responses = tmp_path / "sample" / "responses"
    responses.mkdir(parents=True)
    (responses / "api.json").write_text("{\"data\":{\"price\":\"123\"}}", encoding="utf-8")

    spec = importlib.util.spec_from_file_location("generated_demo", result["path"])
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    extractor = module.DemoJsonSpider()
    assert extractor.parse_text("", sample_dir=tmp_path / "sample")["price"] == "123"


def test_generate_scrapy_spider_contains_json_path(tmp_path):
    import yaml
    from spiderpilot.generator.codegen import generate_spider
    plan = {
        "name": "demo_api",
        "fields": {
            "price": {"evidence": {"path": "json_response:api.json:$.data.price", "matched_value": "123"}}
        },
    }
    plan_path = tmp_path / "plan.yaml"
    plan_path.write_text(yaml.safe_dump(plan), encoding="utf-8")
    result = generate_spider(plan_path, workspace=tmp_path, kind="scrapy")
    code = Path(result["path"]).read_text(encoding="utf-8")
    assert "class DemoApiSpider(scrapy.Spider)" in code
    assert "self.get_json_path(data, '$.data.price')" in code


def test_extract_html_selector_path_value():
    assert _extract_mvp_value('<h1 id="title">Example</h1>', {"evidence": {"source": "html_selector", "path": "#title"}}) == "Example"
    assert _extract_mvp_value('<span data-testid="price">123</span>', {"evidence": {"source": "html_xpath", "path": "//span[@data-testid=\'price\']"}}) == "123"


def test_generate_scrapy_spider_contains_css_xpath(tmp_path):
    import yaml
    from spiderpilot.generator.codegen import generate_spider
    plan = {
        "name": "demo_html",
        "fields": {
            "title": {"source": "html_selector", "evidence": {"path": "#title", "matched_value": "Example"}},
            "price": {"source": "html_xpath", "evidence": {"path": "//span[@data-testid=\'price\']", "matched_value": "123"}},
        },
    }
    plan_path = tmp_path / "plan.yaml"
    plan_path.write_text(yaml.safe_dump(plan), encoding="utf-8")
    result = generate_spider(plan_path, workspace=tmp_path, kind="scrapy")
    code = Path(result["path"]).read_text(encoding="utf-8")
    assert "response.css('#title').get()" in code
    assert "response.xpath" in code


def test_generate_scrapy_spider_signature_note(tmp_path):
    import yaml
    from spiderpilot.generator.codegen import generate_spider
    plan = {"name": "demo_sig", "signature": {"required": True, "signer": "signer_stub.js", "verify_report": "verify.yaml"}, "fields": {}}
    plan_path = tmp_path / "plan.yaml"
    plan_path.write_text(yaml.safe_dump(plan), encoding="utf-8")
    result = generate_spider(plan_path, workspace=tmp_path, kind="scrapy")
    code = Path(result["path"]).read_text(encoding="utf-8")
    assert "Signature signer: signer_stub.js" in code
    assert "TODO: call signer" in code
