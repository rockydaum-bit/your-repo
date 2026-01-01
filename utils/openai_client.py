from __future__ import annotations

import json
from openai import OpenAI


class OpenAIJsonClient:
    def __init__(self, api_key: str, model: str) -> None:
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def run_json(
        self, system_prompt: str, user_prompt: str, input_payload: dict
    ) -> dict:
        """
        Forces JSON output by instruction + parsing.
        If the model returns non-JSON, this will raise.
        """
        msg = (
            f"{user_prompt}\n\n"
            f"INPUT_PAYLOAD_JSON:\n{json.dumps(input_payload, ensure_ascii=False)}\n"
            f"\nOUTPUT_RULE: Return ONLY valid JSON."
        )

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": msg},
            ],
            temperature=0.3,
        )

        content = resp.choices[0].message.content or ""
        content = content.strip()

        # strict parse
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"Model did not return valid JSON. Error: {e}\nRaw:\n{content[:2000]}"
            )
