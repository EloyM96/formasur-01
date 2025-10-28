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


def test_rest_client_raises_when_disabled():
    client = MoodleRESTClient(
        base_url="https://moodle.example",
        token="abc123",
        enabled=False,
        http_client=DummyHTTPClient([]),
    )

    with pytest.raises(MoodleAPIError):
        client.fetch_courses()


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
