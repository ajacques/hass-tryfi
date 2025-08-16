from custom_components.tryfi.pytryfi import FiPet, FiDevice
from unittest.mock import Mock
from .utils import mock_response, GRAPHQL_FIXTURE_PET_ALL_INFO

import pytest
import requests


@pytest.fixture
def mock_session() -> requests.Session:
    """Create a mock session."""
    session = Mock()
    session.post = Mock()
    session.get = Mock()
    return session


def test_load_location(mock_session: requests.Session):
    response = mock_response(200)
    response.json.return_value = GRAPHQL_FIXTURE_PET_ALL_INFO
    mock_session.get.return_value = response

    pet = FiPet("pet-id")
    pet._device = FiDevice("device-id")
    pet.updateAllDetails(mock_session)

    assert pet.currLatitude == -40
    assert pet.currLongitude == 16


def test_get_sleep(mock_session: requests.Session):
    response = mock_response(200)
    response.json.return_value = GRAPHQL_FIXTURE_PET_ALL_INFO
    mock_session.get.return_value = response

    pet = FiPet("pet-id")
    pet._device = FiDevice("device-id")
    pet.updateAllDetails(mock_session)

    assert pet.dailySleep == 60
    assert pet.dailyNap == 30

def test