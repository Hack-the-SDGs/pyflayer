"""Tests for internal bridge event dataclasses."""

import pytest

from pyflayer._bridge._events import (
    _DigDoneEvent,
    _EquipDoneEvent,
    _LookAtDoneEvent,
    _PlaceDoneEvent,
)


class TestDigDoneEvent:
    def test_success(self) -> None:
        event = _DigDoneEvent()
        assert event.error is None

    def test_error(self) -> None:
        event = _DigDoneEvent(error="cannot dig")
        assert event.error == "cannot dig"

    def test_frozen(self) -> None:
        event = _DigDoneEvent()
        with pytest.raises(AttributeError):
            event.error = "x"  # type: ignore[misc]


class TestPlaceDoneEvent:
    def test_success(self) -> None:
        assert _PlaceDoneEvent().error is None

    def test_error(self) -> None:
        assert _PlaceDoneEvent(error="no space").error == "no space"


class TestEquipDoneEvent:
    def test_success(self) -> None:
        assert _EquipDoneEvent().error is None

    def test_error(self) -> None:
        assert _EquipDoneEvent(error="item gone").error == "item gone"


class TestLookAtDoneEvent:
    def test_success(self) -> None:
        assert _LookAtDoneEvent().error is None

    def test_error(self) -> None:
        assert _LookAtDoneEvent(error="failed").error == "failed"
