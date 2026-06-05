from spiderpilot.templates.loader import list_templates, load_template


def test_domain_templates_include_planned_domains():
    templates = set(list_templates())
    assert {"generic", "ecommerce", "news", "jobs", "real_estate", "social_media"}.issubset(templates)


def test_domain_templates_have_crawl_graph():
    for name in ["ecommerce", "news", "jobs", "real_estate", "social_media"]:
        data = load_template(name)
        assert data["entities"]
        assert data["crawl_graph"]["nodes"]
