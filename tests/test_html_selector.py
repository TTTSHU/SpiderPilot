from spiderpilot.reverse.html_selector import infer_css_candidates
from spiderpilot.reverse.locator import locate_expected_in_html_selectors
from spiderpilot.spec import ExpectedValue


def test_infer_css_candidates_id():
    html = '<html><h1 id="title">Example Product</h1></html>'
    candidates = infer_css_candidates(html, "Example Product")
    assert candidates[0]["selector"] == "#title"


def test_infer_css_candidates_data_attr():
    html = '<span data-testid="price">3999.00</span>'
    candidates = infer_css_candidates(html, "3999.00")
    assert candidates[0]["selector"] == 'span[data-testid="price"]'


def test_locate_expected_in_html_selectors():
    html = '<h1 class="product-title">Example Product</h1>'
    candidates = locate_expected_in_html_selectors("title", ExpectedValue(equals="Example Product"), "s1", html)
    assert candidates
    assert candidates[0].source == "html_selector"
    assert candidates[0].path == "h1.product-title"
