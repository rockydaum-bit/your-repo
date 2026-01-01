# Autonomous Media Growth & Monetization Engine — Prompt Contract

## Shared Invariants
- All agents MUST:
  1) Read input JSON.
  2) Produce ONLY valid JSON matching the provided schema (no prose, no markdown).
  3) Never invent metrics; if data is missing, set null and add a "missing_data" list.
  4) Respect governance constraints: budget cap, risk rules, channel policy rules.
  5) Use file paths provided; do not create new conventions.

## Safety & Compliance
- Avoid medical claims, guaranteed financial returns, or prohibited YouTube policy content.
- Prefer neutral, informational framing. Include disclaimers where applicable.

## Output Discipline
- Output JSON only.
- Conform to schema exactly.
- Keep text concise and production-ready.
