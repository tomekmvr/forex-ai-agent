from __future__ import annotations

import csv
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


@dataclass(frozen=True)
class SpeedCameraPoint:
    point_id: str
    latitude: float
    longitude: float
    road_name: str | None = None
    source: str = "unknown"


@dataclass(frozen=True)
class SpeedCameraLoadResult:
    points: list[SpeedCameraPoint]
    source_url: str | None
    used_fallback: bool
    status_message: str


class CanardSpeedCameraSource:
    """Best-effort loader for CANARD speed-camera coordinates with local fallback."""

    DEFAULT_ENDPOINTS = (
        "https://www.canard.gitd.gov.pl/cms/web/guest/mapa-stacjonarnych-urzadzen-rejestrujacych",
    )

    def __init__(
        self,
        *,
        endpoints: tuple[str, ...] | None = None,
        fallback_path: Path | None = None,
        timeout_seconds: float = 10.0,
        session: requests.Session | None = None,
    ) -> None:
        self.endpoints = endpoints or self.DEFAULT_ENDPOINTS
        self.fallback_path = fallback_path or Path(__file__).resolve().parent / "data" / "canard_speed_cameras_fallback.json"
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()

    def load_points(self) -> SpeedCameraLoadResult:
        errors: list[str] = []

        for endpoint in self.endpoints:
            try:
                response = self.session.get(
                    endpoint,
                    timeout=self.timeout_seconds,
                    headers={"User-Agent": "forex-ai-agent-canard-prototype/1.0"},
                )
                response.raise_for_status()
            except requests.RequestException as exc:
                errors.append(f"{endpoint}: {exc}")
                continue

            parsed = self._parse_payload(response.text, response.headers.get("content-type", ""), endpoint)
            if parsed:
                return SpeedCameraLoadResult(
                    points=parsed,
                    source_url=endpoint,
                    used_fallback=False,
                    status_message=f"Loaded {len(parsed)} speed-camera points from CANARD endpoint.",
                )
            errors.append(f"{endpoint}: payload parsed but no coordinates were found")

        fallback_points = self._load_fallback_points()
        fallback_message = (
            "CANARD endpoint unavailable or unparseable; using local fallback dataset."
            if fallback_points
            else "CANARD endpoint unavailable and fallback dataset could not be loaded."
        )
        if errors:
            fallback_message = f"{fallback_message} Errors: {'; '.join(errors)}"

        return SpeedCameraLoadResult(
            points=fallback_points,
            source_url=None,
            used_fallback=True,
            status_message=fallback_message,
        )

    def _parse_payload(self, payload: str, content_type: str, source: str) -> list[SpeedCameraPoint]:
        json_points = self._parse_json_payload(payload, source)
        if json_points:
            return json_points

        csv_points = self._parse_csv_payload(payload, content_type, source)
        if csv_points:
            return csv_points

        return self._parse_html_payload(payload, source)

    def _parse_json_payload(self, payload: str, source: str) -> list[SpeedCameraPoint]:
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return []
        return self._deduplicate(self._extract_points_from_json(data, source=source))

    def _parse_csv_payload(self, payload: str, content_type: str, source: str) -> list[SpeedCameraPoint]:
        lines = [line.strip() for line in payload.splitlines() if line.strip()]
        if not lines:
            return []
        looks_like_csv = "csv" in content_type.lower() or ("," in lines[0] and "lat" in lines[0].lower())
        if not looks_like_csv:
            return []

        reader = csv.DictReader(lines)
        points: list[SpeedCameraPoint] = []
        for row in reader:
            latitude, longitude = self._extract_lat_lon(row)
            if latitude is None or longitude is None:
                continue
            points.append(
                self._build_point(
                    node=row,
                    latitude=latitude,
                    longitude=longitude,
                    source=source,
                    fallback_prefix="csv",
                    fallback_index=len(points),
                )
            )
        return self._deduplicate(points)

    def _parse_html_payload(self, payload: str, source: str) -> list[SpeedCameraPoint]:
        points: list[SpeedCameraPoint] = []
        patterns = (
            r'"lat"\s*:\s*(-?\d+\.\d+)[^\n\r]*?"(?:lon|lng|longitude)"\s*:\s*(-?\d+\.\d+)',
            r"data-lat\s*=\s*['\"](-?\d+\.\d+)['\"][^>]*data-(?:lon|lng)\s*=\s*['\"](-?\d+\.\d+)['\"]",
        )
        for pattern in patterns:
            for index, match in enumerate(re.finditer(pattern, payload, flags=re.IGNORECASE)):
                latitude = float(match.group(1))
                longitude = float(match.group(2))
                points.append(
                    self._build_point(
                        node={},
                        latitude=latitude,
                        longitude=longitude,
                        source=source,
                        fallback_prefix="html",
                        fallback_index=index,
                    )
                )
        return self._deduplicate(points)

    def _extract_points_from_json(self, node: Any, *, source: str) -> list[SpeedCameraPoint]:
        points: list[SpeedCameraPoint] = []

        if isinstance(node, dict):
            geometry = node.get("geometry")
            if isinstance(geometry, dict) and geometry.get("type") == "Point":
                coordinates = geometry.get("coordinates")
                if isinstance(coordinates, list) and len(coordinates) >= 2:
                    longitude = self._as_float(coordinates[0])
                    latitude = self._as_float(coordinates[1])
                    if latitude is not None and longitude is not None:
                        points.append(
                            self._build_point(
                                node=node,
                                latitude=latitude,
                                longitude=longitude,
                                source=source,
                                fallback_prefix="point",
                                fallback_index=len(points),
                            )
                        )

            latitude, longitude = self._extract_lat_lon(node)
            if latitude is not None and longitude is not None:
                points.append(
                    self._build_point(
                        node=node,
                        latitude=latitude,
                        longitude=longitude,
                        source=source,
                        fallback_prefix="point",
                        fallback_index=len(points),
                    )
                )

            for value in node.values():
                points.extend(self._extract_points_from_json(value, source=source))

        elif isinstance(node, list):
            for item in node:
                points.extend(self._extract_points_from_json(item, source=source))

        return points

    def _load_fallback_points(self) -> list[SpeedCameraPoint]:
        try:
            payload = self.fallback_path.read_text(encoding="utf-8")
            data = json.loads(payload)
        except (OSError, json.JSONDecodeError):
            return []

        if not isinstance(data, list):
            return []

        points: list[SpeedCameraPoint] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            latitude, longitude = self._extract_lat_lon(item)
            if latitude is None or longitude is None:
                continue
            points.append(
                self._build_point(
                    node=item,
                    latitude=latitude,
                    longitude=longitude,
                    source="local_fallback",
                    fallback_prefix="fallback",
                    fallback_index=len(points),
                )
            )
        return self._deduplicate(points)

    def _build_point(
        self,
        *,
        node: dict[str, Any],
        latitude: float,
        longitude: float,
        source: str,
        fallback_prefix: str,
        fallback_index: int,
    ) -> SpeedCameraPoint:
        point_id = node.get("id") or node.get("name")
        if not point_id:
            point_id = f"{fallback_prefix}-{fallback_index}-{latitude:.6f}-{longitude:.6f}"

        road_name = node.get("road") or node.get("street") or node.get("road_name")
        return SpeedCameraPoint(
            point_id=str(point_id),
            latitude=latitude,
            longitude=longitude,
            road_name=str(road_name) if road_name else None,
            source=source,
        )

    @staticmethod
    def _deduplicate(points: list[SpeedCameraPoint]) -> list[SpeedCameraPoint]:
        unique: dict[tuple[float, float], SpeedCameraPoint] = {}
        for point in points:
            key = (round(point.latitude, 6), round(point.longitude, 6))
            unique[key] = point
        return list(unique.values())

    @staticmethod
    def _extract_lat_lon(node: dict[str, Any]) -> tuple[float | None, float | None]:
        latitude = None
        longitude = None

        for key in ("lat", "latitude", "y"):
            if key in node:
                latitude = CanardSpeedCameraSource._as_float(node.get(key))
                break

        for key in ("lon", "lng", "longitude", "x"):
            if key in node:
                longitude = CanardSpeedCameraSource._as_float(node.get(key))
                break

        return latitude, longitude

    @staticmethod
    def _as_float(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


def build_canard_speed_camera_source_from_env() -> CanardSpeedCameraSource:
    urls_env = os.getenv("FOREX_AGENT_CANARD_URLS", "").strip()
    endpoints = tuple(url.strip() for url in urls_env.split(",") if url.strip())

    fallback_env = os.getenv("FOREX_AGENT_CANARD_FALLBACK_FILE", "").strip()
    fallback_path = Path(fallback_env) if fallback_env else None

    return CanardSpeedCameraSource(endpoints=endpoints or None, fallback_path=fallback_path)
