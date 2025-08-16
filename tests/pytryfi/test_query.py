from __future__ import annotations

from unittest.mock import Mock

import pytest
import requests
import json

from custom_components.tryfi.pytryfi.exceptions import RemoteApiError
from custom_components.tryfi.pytryfi.common.query import query
from .utils import mock_session, mock_response


def test_query_error_handling():
    """When tryfi.com returns a non-200 response, the error gets bubbled up"""

    session = Mock()

    # Test execute with HTTP error
    response = mock_response(500)
    session.get.return_value = response

    with pytest.raises(BaseException):
        query(session, "test-query")


def test_handle_empty_response(mock_session: requests.Session):
    """Empty responses are treated as errors"""
    response = Mock()
    response.text = ""
    response.raise_for_status.return_value = None
    mock_session.get.return_value = response

    with pytest.raises(BaseException) as exc_info:
        query(mock_session, "test-query")

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


def test_query_graphql_errors():
    """Test query GraphQL error handling."""
    session = Mock()
    response = mock_response(200)
    response.text = "valid"
    response.json.return_value = {
        "errors": [{"message": "GraphQL Error: Invalid query"}]
    }
    session.get.return_value = response

    with pytest.raises(RemoteApiError) as exc_info:
        query(session, "test query")

    assert "GraphQL error" in str(exc_info.value)
    assert "Invalid query" in str(exc_info.value)
