import pytest

from app.connectors.moodle import MoodleAPIError, MoodleRESTClient, MoodleSOAPClient


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:  # pragma: no cover - used in tests
        return None

    def json(self):  # pragma: no cover - used in tests
        return self._payload

    @property
    def text(self):  # pragma: no cover - used in tests
        return str(self._payload)


class DummyHTTPClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, params=None):
        self.calls.append((url, params))
        return DummyResponse(self.payload)

    def post(self, url, content=None, headers=None):
        self.calls.append((url, content, headers))
        return DummyResponse({"status": "ok"})

    def close(self):  # pragma: no cover - compatibility noop
        return None


def test_rest_client_fetches_courses_with_token(monkeypatch):
    client = MoodleRESTClient(
        base_url="https://moodle.example",
        token="abc123",
        enabled=True,
        http_client=DummyHTTPClient([{"fullname": "Prevención", "enddate": 1_700_000_000}]),
    )

    result = client.fetch_courses()

    assert result[0]["fullname"] == "Prevención"
    assert client._http_client.calls[0][1]["wstoken"] == "abc123"


def test_rest_client_builds_criteria_parameters():
    http_client = DummyHTTPClient([])
    client = MoodleRESTClient(
        base_url="https://moodle.example",
        token="abc123",
        enabled=True,
        http_client=http_client,
    )

    client.fetch_courses(criteria=[{"key": "category", "value": 12}])

    _, params = http_client.calls[0]
    assert params["criteria[0][key]"] == "category"
    assert params["criteria[0][value]"] == 12


def test_rest_client_raises_when_disabled():
    client = MoodleRESTClient(
        base_url="https://moodle.example",
        token="abc123",
        enabled=False,
        http_client=DummyHTTPClient([]),
    )

    with pytest.raises(MoodleAPIError):
        client.fetch_courses()


def test_rest_client_raises_on_exception_payload():
    client = MoodleRESTClient(
        base_url="https://moodle.example",
        token="abc123",
        enabled=True,
        http_client=DummyHTTPClient(
            {"exception": "invalidtoken", "message": "Token incorrecto"}
        ),
    )

    with pytest.raises(MoodleAPIError) as error:
        client.fetch_courses()

    assert "Token incorrecto" in str(error.value)


def test_rest_client_raises_on_unexpected_payload_shape():
    client = MoodleRESTClient(
        base_url="https://moodle.example",
        token="abc123",
        enabled=True,
        http_client=DummyHTTPClient({"status": "ok"}),
    )

    with pytest.raises(MoodleAPIError) as error:
        client.fetch_courses()

    assert "formato inesperado" in str(error.value)


def test_soap_client_builds_envelope_with_token():
    transport = DummyHTTPClient({"status": "ok"})
    client = MoodleSOAPClient(
        wsdl_url="https://moodle.example/wsdl",
        token="abc123",
        enabled=True,
        transport=transport,
    )

    client.call("core_function", some="value")

    url, content, headers = transport.calls[0]
    assert url == "https://moodle.example/wsdl"
    assert "abc123" in content
    assert "core:some" in content
    assert headers["Content-Type"].startswith("text/xml")


def test_soap_client_respects_feature_flag():
    client = MoodleSOAPClient(
        wsdl_url="https://moodle.example/wsdl",
        token="abc123",
        enabled=False,
        transport=DummyHTTPClient({}),
    )

    with pytest.raises(MoodleAPIError):
        client.call("core_function")
