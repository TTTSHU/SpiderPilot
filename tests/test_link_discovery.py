from pathlib import Path

from spiderpilot.discovery import run_discovery
from spiderpilot.reverse.link_discovery import discover_links
from spiderpilot.workflow import create_task


def test_discover_links_relative():
    links = discover_links('<a class="product" href="/p/1">Product 1</a>', 'https://e.test/cat')
    assert links[0].url == 'https://e.test/p/1'
    assert links[0].selector == 'a.product'


def test_run_discovery_messages(tmp_path):
    spec = tmp_path / 'spec.yaml'
    spec.write_text('''
version: 1
name: listing_demo
samples:
  - id: s1
    url: "https://e.test/list"
    expected:
      marker:
        contains: ["Product"]
fields:
  marker:
    type: string
''', encoding='utf-8')
    created = create_task(spec, workspace=tmp_path)
    root = tmp_path / 'artifacts' / 'listing_demo' / 's1'
    root.joinpath('raw.html').write_text('<a class="product" href="/p/1">Product 1</a>', encoding='utf-8')
    report = run_discovery(created['workspace'].spec_path, workspace=tmp_path, target_task='product_detail', entity_type='product', include=['/p/'])
    assert report['messages_total'] == 1
    assert report['messages'][0]['task'] == 'product_detail'
