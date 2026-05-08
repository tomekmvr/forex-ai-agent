from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from src.config.ai_settings import AISettings


@dataclass(frozen=True)
class SupervisorAssessment:
    signal: int
    confidence: float
    reasoning: str
    diagnostics: dict[str, Any]


class OpenAISupervisorClient:
    def __init__(self, settings: AISettings, client: Optional[httpx.Client] = None) -> None:
        if not settings.enabled:
            raise ValueError("OpenAI supervisor client requires an enabled AISettings configuration.")
        self.settings = settings
        self.client = client or httpx.Client(
            base_url="https://api.openai.com/v1",
            timeout=settings.request_timeout_seconds,
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
        )

    def assess(self, *, prompt: str) -> SupervisorAssessment:
        response = self.client.post(
            "/responses",
            json={
                "model": self.settings.openai_model,
                "input": prompt,
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "supervisor_assessment",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "signal": {"type": "integer", "enum": [-1, 0, 1]},
                                "confidence": {"type": "number"},
                                "reasoning": {"type": "string"},
                                "diagnostics": {"type": "object"},
                            },
                            "required": ["signal", "confidence", "reasoning", "diagnostics"],
                            "additionalProperties": False,
                        },
                    }
                },
            },
        )
        response.raise_for_status()
        payload = response.json()
        parsed = self._extract_json(payload)
        return SupervisorAssessment(
            signal=int(parsed["signal"]),
            confidence=max(0.0, min(1.0, float(parsed["confidence"]))),
            reasoning=str(parsed["reasoning"]),
            diagnostics=dict(parsed.get("diagnostics", {})),
        )

    @staticmethod
    def _extract_json(payload: dict[str, Any]) -> dict[str, Any]:
        output = payload.get("output", [])
        for item in output:
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    text = content.get("text", "{}")
                    return json.loads(text)
        raise ValueError("OpenAI response did not include a JSON supervisor assessment.")