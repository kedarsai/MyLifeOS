# Next Steps (Friday, February 20, 2026)

## 1) Enable Live LLM Mode
- Add `OPENAI_API_KEY` in `.env`.
- Optional: set `OPENAI_BASE_URL` only if using a compatible proxy/gateway.
- Run smoke flow end-to-end:
  - Capture -> Process Inbox
  - Chat thread -> Reply -> Distill
  - Generate weekly review
- Confirm prompt runs in `/runs` show model + success + parse status.

## 2) Prompt Quality Pass
- Refine prompt YAMLs in `Vault/config/prompts/` for:
  - better goal/project assignment during ingest
  - better actionable coaching in chat replies
  - tighter weekly recommendations
- Keep outputs schema-safe and short.

## 3) UI Modernization Pass (Focused)
- Improve layout density and visual rhythm on:
  - `/dashboard`
  - `/tasks`
  - `/projects`
  - `/chat`
- Keep navigation compact (avoid adding many new sidebar links).
- Preserve responsive behavior for mobile.

## 4) Task/Project UX Improvements
- Add quick task creation in `/tasks`.
- Add clear goal/project badges in task cards.
- Add bulk actions (complete/assign project) for selected tasks.

## 5) Reliability + Guardrails
- Add more tests for:
  - `/api/chat/threads/{thread_id}/reply`
  - fallback behavior when OpenAI is unavailable
  - project assignment from ingest tags (`project:<id>`)
- Re-run full suite: `uv run pytest -q`.

## 6) Release Readiness
- Final cleanup pass on docs (`README.md`, `status.md`).
- Verify app startup command and default port behavior.
- Optional: package a quick "demo script" checklist for daily use.
