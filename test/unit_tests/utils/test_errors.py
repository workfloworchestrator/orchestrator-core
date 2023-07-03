from http import HTTPStatus

from orchestrator.utils.errors import ApiException, ProcessFailureError, error_state_to_dict


class RESTResponse:  # From openapi-generator generated clients
    def __init__(self, status, reason, data, headers):
        self.status = status
        self.reason = reason
        self.data = data
        self.headers = headers

    def getheaders(self):
        """Return a dictionary of the response headers."""
        return self.headers


def test_error_state_to_dict():
    e = Exception("bla")
    assert error_state_to_dict(e) == {
        "class": "Exception",
        "error": "bla",
        "traceback": "Exception: bla\n",
    }

    e = ApiException(status=HTTPStatus.NOT_FOUND, reason="Not Found")
    assert error_state_to_dict(e) == {
        "body": None,
        "class": "ApiException",
        "error": "Not Found",
        "headers": "",
        "status_code": HTTPStatus.NOT_FOUND,
        "traceback": "ApiException: (404)\n" "Reason: Not Found\n" "\n",
    }

    e = ApiException(
        http_resp=RESTResponse(HTTPStatus.NOT_FOUND, "Not Found", "Body", {"Header": "value", "Content-type": "bogus"})
    )
    assert error_state_to_dict(e) == {
        "body": "Body",
        "class": "ApiException",
        "error": "Not Found",
        "headers": "Header: value\nContent-type: bogus",
        "status_code": HTTPStatus.NOT_FOUND,
        "traceback": "ApiException: (404)\nReason: Not Found\nHTTP response headers: {'Header': 'value', 'Content-type': 'bogus'}\nHTTP response body: Body\n\n",
    }

    e = ProcessFailureError(message="Something went wrong", details={"foo": "bar"})
    assert error_state_to_dict(e) == {
        "class": "ProcessFailureError",
        "details": {"foo": "bar"},
        "error": "Something went wrong",
        "traceback": "ProcessFailureError: ('Something went wrong', {'foo': 'bar'})\n",
    }
