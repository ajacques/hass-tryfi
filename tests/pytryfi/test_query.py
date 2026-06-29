from __future__ import annotations

from unittest.mock import Mock

import pytest
import responses
import requests
import json

from custom_components.tryfi.pytryfi.exceptions import RemoteApiError
from custom_components.tryfi.pytryfi.common.query import query, updatePetWeight
from tests.pytryfi.utils import mock_graphql, mock_response


@responses.activate
def test_query_error_handling():
    """When tryfi.com returns a non-200 response, the error gets bubbled up"""
    mock_graphql(query="test-query", status=500, response=None)

    # Test execute with HTTP error

    with pytest.raises(BaseException):
        query(requests.Session(), "test-query")


@responses.activate
def test_handle_empty_response():
    """Empty responses are treated as errors"""
    responses.add(
        method=responses.GET,
        url="https://api.tryfi.com/graphql?query=test-query",
        status=200,
        body="",
    )

    with pytest.raises(BaseException) as exc_info:
        query(requests.Session(), "test-query")

    assert "Empty response" in str(exc_info.value)


def test_query_json_parsing():
    """Test query JSON parsing error handling."""
    session = Mock()
    response = mock_response(200)
    response.text = "valid"
    response.json.side_effect = json.JSONDecodeError("Invalid JSON", "doc", 0)
    session.get.return_value = response

    with pytest.raises(RemoteApiError) as exc_info:
        query(session, "test query")

    assert "Invalid JSON response" in str(exc_info.value)


@responses.activate
def test_query_graphql_errors():
    """Test query GraphQL error handling."""
    responses.add(
        responses.GET,
        url="https://api.tryfi.com/graphql?query=test+query",
        status=200,
        json={"errors": [{"message": "GraphQL Error: Invalid query"}]},
    )
    with pytest.raises(RemoteApiError) as exc_info:
        query(requests.Session(), "test query")

    assert "GraphQL error" in str(exc_info.value)
    assert "Invalid query" in str(exc_info.value)


@responses.activate
def test_update_pet_weight():
    """Test updatePetWeight sends mutation and returns updated weight."""
    responses.add(
        method=responses.POST,
        url="https://api.tryfi.com/graphql",
        status=200,
        json={"data": {"updatePet": {"__typename": "BasePet", "weight": 15.5}}},
    )

    result = updatePetWeight(requests.Session(), "pet-123", 15.5)
    assert result == 15.5

    body = json.loads(responses.calls[0].request.body)
    assert body["variables"]["input"]["id"] == "pet-123"
    assert body["variables"]["input"]["weight"] == 15.5
    assert "UpdatePetInput" in body["query"]
