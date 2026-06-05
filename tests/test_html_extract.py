from spiderpilot.runner.html_extract import extract_by_css_selector, extract_by_xpath


def test_extract_by_css_selector_id():
    assert extract_by_css_selector('<h1 id="title">Example</h1>', '#title') == 'Example'


def test_extract_by_css_selector_data_attr():
    assert extract_by_css_selector('<span data-testid="price">123</span>', 'span[data-testid="price"]') == '123'


def test_extract_by_xpath_id():
    assert extract_by_xpath('<h1 id="title">Example</h1>', "//*[@id='title']") == 'Example'


def test_extract_by_xpath_data_attr():
    assert extract_by_xpath('<span data-testid="price">123</span>', "//span[@data-testid='price']") == '123'
