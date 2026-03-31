import pytest
from pyflayer.models.events import (
    BlockBrokenEvent,
    ChatEvent,
    CollectCompletedEvent,
    DeathEvent,
    GoalFailedEvent,
    GoalReachedEvent,
    HealthChangedEvent,
    KickedEvent,
    SpawnEvent,
    WhisperEvent,
)
from pyflayer.models.vec3 import Vec3


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


class TestWhisperEvent:
    def test_creation(self) -> None:
        event = WhisperEvent(sender="Alex", message="secret", timestamp=2000.0)
        assert event.sender == "Alex"
        assert event.message == "secret"


class TestHealthChangedEvent:
    def test_creation(self) -> None:
        event = HealthChangedEvent(health=15.0, food=18.0, saturation=5.0)
        assert event.health == 15.0
        assert event.food == 18.0
        assert event.saturation == 5.0


class TestDeathEvent:
    def test_with_reason(self) -> None:
        event = DeathEvent(reason="fell from a high place")
        assert event.reason == "fell from a high place"

    def test_without_reason(self) -> None:
        event = DeathEvent(reason=None)
        assert event.reason is None


class TestKickedEvent:
    def test_creation(self) -> None:
        event = KickedEvent(reason="banned", logged_in=True)
        assert event.reason == "banned"
        assert event.logged_in is True


class TestGoalReachedEvent:
    def test_creation(self) -> None:
        pos = Vec3(100.0, 64.0, 200.0)
        event = GoalReachedEvent(position=pos)
        assert event.position == pos


class TestGoalFailedEvent:
    def test_creation(self) -> None:
        event = GoalFailedEvent(reason="no path")
        assert event.reason == "no path"


class TestBlockBrokenEvent:
    def test_creation(self) -> None:
        pos = Vec3(10.0, 64.0, 10.0)
        event = BlockBrokenEvent(block_name="oak_log", position=pos)
        assert event.block_name == "oak_log"
        assert event.position == pos


class TestCollectCompletedEvent:
    def test_creation(self) -> None:
        event = CollectCompletedEvent(item_name="oak_log", count=5)
        assert event.item_name == "oak_log"
        assert event.count == 5
