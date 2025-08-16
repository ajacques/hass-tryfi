from unittest.mock import AsyncMock, Mock, patch

import pytest
import requests
import responses
from custom_components.tryfi.pytryfi import PyTryFi
from tests.pytryfi.utils import mock_response


def test_pet_with_no_collar(mock_session: requests.Session):
    # TODO: Get a real requests mocking library. Make this not shit
    responses.add(
        responses.GET,
        "https://api.tryfi.com/test",
        status=200,
        body={}
    )
    response = mock_response(200)
    response.json.return_value = {
        'userId': 'userid',
        'sessionId': 'sessionid',
        'data': {
            'currentUser': {
                'userHouseholds': [
                    {
                        'household': {
                            'bases': [],
                            'pets': [
                                {
                                    '__typename': 'Pet', 
                                    'id': 'testpetwithnodevice',
                                    'chip': None,
                                    'name': 'Yolo',
                                    'device': None
                                }
                            ]
                        }
                    }
                ]
            }
        }
    }
    mock_session.post.return_value = response
    mock_session.get.return_value = response

    tryfi = PyTryFi(session=mock_session)
    
    assert tryfi.pets == []
