from spiderpilot.probe.cloak_cdp import cloak_binary_path


def test_cloak_binary_path_shape():
    path = cloak_binary_path()
    assert path is None or isinstance(path, str)
