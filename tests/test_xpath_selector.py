from spiderpilot.reverse.html_selector import infer_xpath_candidates
from spiderpilot.reverse.locator import locate_expected_in_xpath
from spiderpilot.spec import ExpectedValue


def test_infer_xpath_candidates_id():
    html = '<h1 id="title">Example Product</h1>'
    candidates = infer_xpath_candidates(html, "Example Product")
    assert candidates[0]["xpath"] == "//*[@id='title']"


def test_infer_xpath_candidates_class():
    html = '<h1 class="product-title">Example Product</h1>'
    candidates = infer_xpath_candidates(html, "Example Product")
    assert "contains(concat" in candidates[0]["xpath"]


def test_locate_expected_in_xpath():
    html = '<span data-testid="price">3999.00</span>'
    candidates = locate_expected_in_xpath("price", ExpectedValue(equals="3999.00"), "s1", html)
    assert candidates
    assert candidates[0].source == "html_xpath"
    assert candidates[0].path == "//span[@data-testid='price']"
