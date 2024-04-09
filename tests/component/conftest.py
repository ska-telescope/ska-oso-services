import pytest


# See https://developer.skao.int/projects/ska-ser-xray/en/latest/guide/pytest.html
@pytest.hookimpl
def pytest_collection_modifyitems(
    session, config, items
):  # pylint: disable=unused-argument
    for item in items:
        for marker in item.iter_markers(name="xray"):
            test_key = marker.args[0]
            item.user_properties.append(("test_key", test_key))
