from pathlib import Path

from spiderpilot.spec import load_spec


def test_example_specs_load():
    paths = [
        Path("examples/ecommerce/product_detail.yaml"),
        Path("examples/news/article_detail.yaml"),
        Path("examples/jobs/job_detail.yaml"),
        Path("examples/real_estate/listing_detail.yaml"),
        Path("examples/social_media/post_detail.yaml"),
    ]
    for path in paths:
        spec = load_spec(path)
        assert spec.samples
        assert spec.fields
