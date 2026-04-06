"""Tests for internal bridge event dataclasses."""

import pytest

from minethon._bridge._events import (
    DigDoneEvent,
    EquipDoneEvent,
    LookAtDoneEvent,
    PlaceDoneEvent,
)


class TestDigDoneEvent:
    def test_success(self) -> None:
        event = DigDoneEvent()
        assert event.error is None

    def test_error(self) -> None:
        event = DigDoneEvent(error="cannot dig")
        assert event.error == "cannot dig"

    def test_frozen(self) -> None:
        event = DigDoneEvent()
        with pytest.raises(AttributeError):
            event.error = "x"  # type: ignore[misc]


class TestPlaceDoneEvent:
    def test_success(self) -> None:
        assert PlaceDoneEvent().error is None

    def test_error(self) -> None:
        assert PlaceDoneEvent(error="no space").error == "no space"


class TestEquipDoneEvent:
    def test_success(self) -> None:
        assert EquipDoneEvent().error is None

    def test_error(self) -> None:
        assert EquipDoneEvent(error="item gone").error == "item gone"


class TestLookAtDoneEvent:
    def test_success(self) -> None:
        assert LookAtDoneEvent().error is None

    def test_error(self) -> None:
        assert LookAtDoneEvent(error="failed").error == "failed"
