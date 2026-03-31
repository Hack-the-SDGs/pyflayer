import pytest
from pyflayer.models.events import ChatEvent, SpawnEvent


class TestSpawnEvent:
    def test_creation(self) -> None:
        event = SpawnEvent()
        assert isinstance(event, SpawnEvent)

    def test_frozen(self) -> None:
        event = SpawnEvent()
        with pytest.raises((AttributeError, TypeError)):
            event.x = 1  # type: ignore[attr-defined]


class TestChatEvent:
    def test_creation(self) -> None:
        event = ChatEvent(sender="Steve", message="hello", timestamp=1000.0)
        assert event.sender == "Steve"
        assert event.message == "hello"
        assert event.timestamp == 1000.0

    def test_frozen(self) -> None:
        event = ChatEvent(sender="Steve", message="hello", timestamp=1000.0)
        with pytest.raises(AttributeError):
            event.sender = "Alex"  # type: ignore[misc]
