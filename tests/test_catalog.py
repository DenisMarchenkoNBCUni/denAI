"""Tests for catalog namespacing and dispatch parsing."""


def test_namespace_prefix_parsing() -> None:
    full_name = "github__list_pull_requests"
    server_key, _, tool_name = full_name.partition("__")
    assert server_key == "github"
    assert tool_name == "list_pull_requests"


def test_namespace_with_double_underscore_in_tool() -> None:
    full_name = "alexandria__search__docs"
    server_key, _, tool_name = full_name.partition("__")
    assert server_key == "alexandria"
    assert tool_name == "search__docs"
