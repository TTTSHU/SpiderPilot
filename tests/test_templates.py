from spiderpilot.templates.loader import list_templates, load_template


def test_list_templates_contains_defaults():
    templates = list_templates()
    assert "generic" in templates
    assert "ecommerce" in templates
    assert "news" in templates


def test_load_ecommerce_template():
    data = load_template("ecommerce")
    assert data["name"] == "ecommerce"
    assert "product" in data["entities"]
    assert "crawl_graph" in data
