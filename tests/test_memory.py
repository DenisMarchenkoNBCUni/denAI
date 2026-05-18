"""Tests for thread memory."""

from denai.slack.memory import ThreadMemory


def test_get_empty() -> None:
    mem = ThreadMemory()
    assert mem.get("C123", "ts123") == []


def test_set_and_get() -> None:
    mem = ThreadMemory()
    messages = [{"role": "user", "content": "hi"}]
    mem.set("C123", "ts123", messages)
    assert mem.get("C123", "ts123") == messages


def test_max_turns_truncation() -> None:
    mem = ThreadMemory(max_turns=3)
    messages = [{"role": "user", "content": str(i)} for i in range(10)]
    mem.set("C1", None, messages)
    result = mem.get("C1", None)
    assert len(result) == 3
    assert result[0]["content"] == "7"


def test_separate_threads() -> None:
    mem = ThreadMemory()
    mem.set("C1", "t1", [{"role": "user", "content": "a"}])
    mem.set("C1", "t2", [{"role": "user", "content": "b"}])
    assert mem.get("C1", "t1")[0]["content"] == "a"
    assert mem.get("C1", "t2")[0]["content"] == "b"
