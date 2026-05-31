import requests

from src.dataprep.canard_speed_cameras import CanardSpeedCameraSource


class _StubResponse:
    def __init__(self, *, text: str, content_type: str = "application/json", status_code: int = 200):
        self.text = text
        self.status_code = status_code
        self.headers = {"content-type": content_type}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")


class _StubSession:
    def __init__(self, responses):
        self._responses = responses

    def get(self, url, timeout, headers):
        response = self._responses[url]
        if isinstance(response, Exception):
            raise response
        return response


def test_canard_source_parses_geojson_without_fallback(tmp_path):
    geojson = """{
      "type": "FeatureCollection",
      "features": [
        {
          "id": "cam-1",
          "geometry": {"type": "Point", "coordinates": [21.0122, 52.2297]},
          "properties": {"road": "A"}
        }
      ]
    }"""
    session = _StubSession({"https://example.com/cameras.json": _StubResponse(text=geojson)})
    source = CanardSpeedCameraSource(
        endpoints=("https://example.com/cameras.json",),
        fallback_path=tmp_path / "unused.json",
        session=session,
    )

    result = source.load_points()

    assert result.used_fallback is False
    assert result.source_url == "https://example.com/cameras.json"
    assert len(result.points) == 1
    assert result.points[0].latitude == 52.2297
    assert result.points[0].longitude == 21.0122


def test_canard_source_uses_fallback_when_remote_unavailable(tmp_path):
    fallback = tmp_path / "fallback.json"
    fallback.write_text(
        '[{"id":"fallback-1","latitude":51.1079,"longitude":17.0385,"road_name":"Wrocław (demo)"}]',
        encoding="utf-8",
    )
    session = _StubSession({"https://example.com/down": requests.ConnectionError("network down")})
    source = CanardSpeedCameraSource(
        endpoints=("https://example.com/down",),
        fallback_path=fallback,
        session=session,
    )

    result = source.load_points()

    assert result.used_fallback is True
    assert result.source_url is None
    assert len(result.points) == 1
    assert result.points[0].source == "local_fallback"


def test_canard_source_parses_html_coordinate_pattern(tmp_path):
    html = '<script>const points=[{"lat":52.1,"lng":21.1}]</script>'
    session = _StubSession({"https://example.com/page": _StubResponse(text=html, content_type="text/html")})
    source = CanardSpeedCameraSource(
        endpoints=("https://example.com/page",),
        fallback_path=tmp_path / "unused.json",
        session=session,
    )

    result = source.load_points()

    assert result.used_fallback is False
    assert len(result.points) == 1
    assert result.points[0].latitude == 52.1
    assert result.points[0].longitude == 21.1
