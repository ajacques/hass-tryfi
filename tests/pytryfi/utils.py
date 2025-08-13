from unittest.mock import Mock

import pytest

def mock_response(status_code: int) -> Mock:
    response = Mock()
    response.status_code = status_code
    if 200 <= status_code <= 299:
        response.raise_for_status.return_value = None
        response.ok.return_value = True
    else:
        response.raise_for_status.side_effect = Exception(
            f"Fake HTTP Status: {status_code}"
        )
        response.ok.return_value = False
    return response

@pytest.fixture
def mock_session():
    """Create a mock session."""
    session = Mock()
    session.post = Mock()
    session.get = Mock()
    return session

GRAPHQL_FIXTURE_PET_ALL_INFO = {
    'data': {
        'pet': {
            'device': {
                "__typename": "Device",
                "id": "DEVICEID",
                "moduleId": "DEVICEID",
                "info": {
                    "batteryPercent": 92,
                    "buildId": "4.16.61-d8fcd9279-fc3_f3-prod",
                },
                "operationParams": {
                    "__typename": "OperationParams",
                    "mode": "NORMAL",
                    "ledEnabled": None,
                    "ledOffAt": None
                },
                "ledColor": {
                    "__typename": "LedColor",
                    "ledColorCode": 8,
                    "hexCode": "ffffff",
                    "name": "White"
                },
                "lastConnectionState": {
                    "__typename": "ConnectedToBase",
                    "date": "2025-06-17T01:25:41.705Z",
                    "chargingBase": {
                      "__typename": "ChargingBase",
                      "id": "FB33A514868"
                    }
                },
                "nextLocationUpdateExpectedBy": "2025-06-17T01:32:35.504Z",
            },
            "ongoingActivity": {
                "__typename": "OngoingRest",
                "areaName": "FooArea",
                "lastReportTimestamp": "2025-06-17T01:30:00.000Z",
                "position": {
                    "latitude": -40,
                    "longitude": 16,
                },
                "start": "2025-06-17T01:00:00.000Z"
            },
            "dailyStepStat": {
                "stepGoal": 5000,
                "totalSteps": 4000,
                "totalDistance": 54
            },
            "weeklyStepStat": {

            },
            "monthlyStepStat": {

            },
            "dailySleepStat": {
                "restSummaries": [
                    {
                        "data": {
                            "sleepAmounts": [
                                { "type": "SLEEP", "duration": 60 },
                                { "type": "NAP", "duration": 30 }
                            ]
                        }
                    }
                ]
            },
            "monthlySleepStat": {
                "restSummaries": [
                    {
                        "data": {
                            
                        }
                    }
                ]
            }
        }
    }
}
