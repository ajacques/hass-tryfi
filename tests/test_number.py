"""Test TryFi number platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

from homeassistant.core import HomeAssistant

from custom_components.tryfi.number import TryFiPetWeightNumber


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = Mock()
    coordinator.data = Mock()
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


@pytest.fixture
def mock_pet_with_stats():
    """Create a mock pet with statistics."""
    pet = Mock()
    pet.petId = "test_pet_123"
    pet.name = "Fido"
    pet.photoLink = "https://example.com/photo.jpg"
    pet.activityType = "REST"
    pet.currPlaceName = "Home"
    pet.currPlaceAddress = "123 Main St"
    pet.device = Mock()
    pet.device.batteryPercent = 75
    pet.device.isCharging = False
    pet.device.connectedTo = "Cellular"
    pet.device.connectionState = "ConnectedToCellular"
    pet.dailySteps = 5000
    pet.weeklyTotalDistance = 17500
    pet.monthlySleep = 864000
    return pet


async def test_weight_number(
    hass: HomeAssistant,
    mock_coordinator,
    mock_pet_with_stats,
) -> None:
    """Test TryFi weight number entity."""
    mock_coordinator.data.getPet.return_value = mock_pet_with_stats

    sensor = TryFiPetWeightNumber(mock_coordinator, mock_pet_with_stats)

    assert sensor.native_unit_of_measurement == "kg"


async def test_async_set_native_value(
    hass: HomeAssistant,
    mock_coordinator,
    mock_pet_with_stats,
) -> None:
    """Test async_set_native_value calls the API and refreshes coordinator."""
    mock_coordinator.data.getPet.return_value = mock_pet_with_stats
    mock_pet_with_stats.setWeight.return_value = True

    entity = TryFiPetWeightNumber(mock_coordinator, mock_pet_with_stats)
    entity.hass = hass

    await entity.async_set_native_value(15.5)

    mock_pet_with_stats.setWeight.assert_called_once_with(
        mock_coordinator.data.session, 15.5
    )
    mock_coordinator.async_request_refresh.assert_awaited_once()


async def test_async_set_native_value_no_pet(
    hass: HomeAssistant,
    mock_coordinator,
    mock_pet_with_stats,
) -> None:
    """Test async_set_native_value when pet is not available."""
    mock_coordinator.data.getPet.return_value = None

    entity = TryFiPetWeightNumber(mock_coordinator, mock_pet_with_stats)
    entity.hass = hass

    await entity.async_set_native_value(15.5)

    mock_coordinator.async_request_refresh.assert_not_awaited()


async def test_async_set_native_value_api_error(
    hass: HomeAssistant,
    mock_coordinator,
    mock_pet_with_stats,
) -> None:
    """Test async_set_native_value raises HomeAssistantError when API call fails."""
    from homeassistant.exceptions import HomeAssistantError

    mock_coordinator.data.getPet.return_value = mock_pet_with_stats
    mock_pet_with_stats.setWeight.side_effect = ConnectionError("API error")

    entity = TryFiPetWeightNumber(mock_coordinator, mock_pet_with_stats)
    entity.hass = hass

    with pytest.raises(HomeAssistantError, match="Failed to set weight for Fido"):
        await entity.async_set_native_value(15.5)

    mock_coordinator.async_request_refresh.assert_not_awaited()
