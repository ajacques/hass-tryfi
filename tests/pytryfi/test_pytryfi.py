import responses
from custom_components.tryfi.pytryfi import PyTryFi
from custom_components.tryfi.pytryfi.common.query import REQUEST_GET_HOUSEHOLDS
from tests.pytryfi.utils import mock_graphql, mock_login_requests


@responses.activate
def test_pet_with_no_collar():
    mock_login_requests()
    
    mock_graphql(
        query=REQUEST_GET_HOUSEHOLDS,
        status=200,
        response = {
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
    )

    tryfi = PyTryFi()
    
    assert tryfi.pets == []
