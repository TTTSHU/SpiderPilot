from spiderpilot.platform.initializer import init_platform


def test_init_platform_creates_workspace(tmp_path):
    platform_dir = init_platform("demo", domain="example.com", template="news", workspace=tmp_path)
    assert (platform_dir / "platform.yaml").exists()
    assert (platform_dir / "spider_plan.yaml").exists()
    assert (platform_dir / "specs").is_dir()
    assert (platform_dir / "artifacts").is_dir()
