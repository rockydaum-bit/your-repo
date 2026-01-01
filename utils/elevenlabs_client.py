from __future__ import annotations

import os
import time
import json
import requests
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class ElevenLabsResult:
    voice_id: str
    model_id: str
    outputs: list[str]  # file paths written

class ElevenLabsClient:
    """
    Minimal, stable REST client for ElevenLabs TTS convert endpoint.

    Endpoint (per docs): POST /v1/text-to-speech/{voice_id}
    Auth header: xi-api-key
    """
    def __init__(self, api_key: str, base_url: str = "https://api.elevenlabs.io") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }

    def synthesize_to_file(
        self,
        *,
        text: str,
        voice_id: str,
        output_path: str,
        model_id: str = "eleven_multilingual_v2",
        output_format: str = "mp3_44100_128",
        voice_settings: dict[str, Any] | None = None,
        max_retries: int = 5,
        timeout_sec: int = 120,
    ) -> str:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        url = f"{self.base_url}/v1/text-to-speech/{voice_id}"
        params = {"output_format": output_format}

        payload: dict[str, Any] = {
            "text": text,
            "model_id": model_id,
        }
        if voice_settings:
            payload["voice_settings"] = voice_settings

        last_err: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.post(
                    url,
                    headers=self._headers(),
                    params=params,
                    data=json.dumps(payload).encode("utf-8"),
                    timeout=timeout_sec,
                )

                if resp.status_code == 200:
                    with open(output_path, "wb") as f:
                        f.write(resp.content)
                    return output_path

                # Retry on rate limits / transient
                if resp.status_code in (408, 429, 500, 502, 503, 504):
                    wait = min(2 ** attempt, 30)
                    time.sleep(wait)
                    continue

                # Non-retryable
                raise RuntimeError(f"ElevenLabs error {resp.status_code}: {resp.text[:500]}")

            except Exception as e:
                last_err = e
                wait = min(2 ** attempt, 30)
                time.sleep(wait)

        raise RuntimeError(f"ElevenLabs synth failed after retries: {last_err}")

    def synthesize_chunks(
        self,
        *,
        chunks: list[dict[str, Any]],
        voice_id: str,
        out_dir: str,
        model_id: str,
        output_format: str,
        voice_settings: dict[str, Any],
    ) -> ElevenLabsResult:
        os.makedirs(out_dir, exist_ok=True)
        outputs: list[str] = []

        for c in chunks:
            chunk_id = c.get("chunk_id", "chunk")
            text = c["text"]
            out_path = os.path.join(out_dir, f"{chunk_id}.mp3")
            outputs.append(
                self.synthesize_to_file(
                    text=text,
                    voice_id=voice_id,
                    output_path=out_path,
                    model_id=model_id,
                    output_format=output_format,
                    voice_settings=voice_settings,
                )
            )

        return ElevenLabsResult(voice_id=voice_id, model_id=model_id, outputs=outputs)
