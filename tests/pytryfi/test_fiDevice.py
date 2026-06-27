"""Tests for FiDevice.setConnectedTo — especially null name handling."""

from __future__ import annotations

from custom_components.tryfi.pytryfi.fiDevice import FiDevice


def _make_device() -> FiDevice:
    """Create a bare FiDevice for testing setConnectedTo."""
    return FiDevice("test-device-id")


def test_connected_to_user_both_names():
    """ConnectedToUser with both firstName and lastName present."""
    dev = _make_device()
    result = dev.setConnectedTo({
        "__typename": "ConnectedToUser",
        "date": "2026-06-26T00:00:00.000Z",
        "user": {
            "id": "user123",
            "firstName": "John",
            "lastName": "Smith",
        },
    })
    assert result == "John Smith"
    assert dev.connectionSignalStrength is None


def test_connected_to_user_null_last_name():
    """ConnectedToUser where lastName is None (the bug we fixed).

    The TryFi API sometimes returns the account email as firstName
    with lastName=null.  The old code did ``firstName + " " + lastName``
    which raised TypeError when lastName was None.
    """
    dev = _make_device()
    result = dev.setConnectedTo({
        "__typename": "ConnectedToUser",
        "date": "2026-06-26T00:00:00.000Z",
        "user": {
            "id": "user456",
            "firstName": "user@example.com",
            "lastName": None,
        },
    })
    assert result == "user@example.com"
    assert dev.connectionSignalStrength is None


def test_connected_to_user_null_first_name():
    """ConnectedToUser where firstName is None."""
    dev = _make_device()
    result = dev.setConnectedTo({
        "__typename": "ConnectedToUser",
        "date": "2026-06-26T00:00:00.000Z",
        "user": {
            "id": "user789",
            "firstName": None,
            "lastName": "Smith",
        },
    })
    assert result == "Smith"


def test_connected_to_user_both_null():
    """ConnectedToUser where both names are None."""
    dev = _make_device()
    result = dev.setConnectedTo({
        "__typename": "ConnectedToUser",
        "date": "2026-06-26T00:00:00.000Z",
        "user": {
            "id": "user000",
            "firstName": None,
            "lastName": None,
        },
    })
    assert result == ""


def test_connected_to_user_missing_keys():
    """ConnectedToUser where firstName and lastName keys are absent."""
    dev = _make_device()
    result = dev.setConnectedTo({
        "__typename": "ConnectedToUser",
        "date": "2026-06-26T00:00:00.000Z",
        "user": {
            "id": "user111",
        },
    })
    assert result == ""


def test_connected_to_cellular():
    """ConnectedToCellular sets signal strength and returns 'Cellular'."""
    dev = _make_device()
    result = dev.setConnectedTo({
        "__typename": "ConnectedToCellular",
        "date": "2026-06-26T00:00:00.000Z",
        "signalStrengthPercent": 75,
    })
    assert result == "Cellular"
    assert dev.connectionSignalStrength == 75


def test_connected_to_base():
    """ConnectedToBase returns base ID string."""
    dev = _make_device()
    result = dev.setConnectedTo({
        "__typename": "ConnectedToBase",
        "date": "2026-06-26T00:00:00.000Z",
        "chargingBase": {
            "__typename": "ChargingBase",
            "id": "FB33A514868",
        },
    })
    assert result == "Base ID - FB33A514868"
    assert dev.connectionSignalStrength is None


def test_connected_to_unknown_type():
    """Unknown connection type returns None."""
    dev = _make_device()
    result = dev.setConnectedTo({
        "__typename": "SomeNewType",
        "date": "2026-06-26T00:00:00.000Z",
    })
    assert result is None
    assert dev.connectionSignalStrength is None