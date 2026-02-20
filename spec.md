
Below is a **V2 Product Spec** for your local “Life OS” assistant (FastAPI + HTMX, runs on your PC), plus a **practical action plan** broken into buildable tasks with clear acceptance criteria.

---

# V2 Product Spec — Personal Assistant (Local-First, Goal-Driven)

## 0) Product vision

A personal system that:

* **Captures anything** (thoughts, activity, meals, sleep, ideas, goals, chats)
* **Never loses originality** (raw preserved forever)
* **Continuously structures + summarizes**
* Turns insights into **action items** (todos + improvements)
* Shows **goal dashboards**: progress, patterns, what’s good/bad, what to do next
* Works locally on your PC, with **transparent prompts** (configurable)

---

## 1) Principles

1. **Raw is sacred**: never overwrite the original input.
2. **Structured is queryable**: extract facts into typed fields.
3. **Summaries are compact**: a 1–2 line top summary + bullets.
4. **Insights must become actions**: chat shouldn’t be the final product.
5. **Auditable AI**: every LLM run is logged with prompt version + inputs/outputs.
6. **Local-first**: all data is stored locally; DB can be rebuilt from markdown vault.

---

## 2) Scope of V2

### In scope

* Markdown vault as source of truth (Obsidian-friendly)
* SQLite as index + analytics layer (FTS search, dashboards, tasks)
* Goal dashboards (weight loss etc.)
* Structured logging: activity, sleep, food, weight
* Insights & improvements with reminders
* Chat interface saved + distilled outcomes
* Missing-data followups (“You didn’t log yesterday’s sleep”)

### Out of scope (V3+)

* Cloud sync across devices
* Multi-user
* Complex nutrition macro calculations (unless you log them)
* Wearables integrations (Apple Health import) — optional later

---

## 3) Key user flows

### Flow A — Quick capture (default)

1. User pastes text (messy allowed)
2. App saves **raw entry** immediately (Inbox)
3. User clicks **Process Inbox** or auto-process (config)
4. App writes:

   * summary + details bullets
   * extracted observations (steps, sleep, meals, etc.)
   * tags + goal links
   * derived todos if any

### Flow B — Goal setup (weight loss)

1. Create goal: name, timeframe, rules, tracked metrics
2. Assign default metrics: weight, steps, sleep, workouts, food notes
3. Goal dashboard shows:

   * progress cards + trends
   * patterns (sleep/food vs performance)
   * improvements + next actions

### Flow C — Review & improve

1. Dashboard highlights: “You slept 12h 3 times this week”
2. You open **Goal Chat**
3. Discuss; assistant asks targeted questions if data missing
4. Outcome saved as:

   * Insight
   * Improvement item
   * Todos + reminders

### Flow D — Missing data recovery

1. If days missing, app prompts:

   * “Log sleep for Feb 18?”
   * “Log food for Feb 17?”
2. Quick check-in form fills structured log fast

---

## 4) Information Architecture (Pages)

### Global

* **Dashboard** (Today)
* **Inbox**
* **Timeline**
* **Goals**
* **Search**
* **Prompts (Config)**
* **Runs (Audit log)**

### Dashboard (Today)

Cards:

* Today’s Todos
* Missing Logs (last N days)
* Active Goals quick status
* “Key insight this week” (optional)

### Inbox

* Entries awaiting processing
* Batch process

### Timeline

* Filter by date range, type, tag, goal

### Goals

* Goals list
* Goal detail page (dashboard + chat + insights + improvements)

### Search

* Keyword search (FTS)
* Facets: type, tags, goal, date range

### Prompts (Config)

* List prompt templates (YAML)
* View/edit prompt text, model settings, schemas
* Version tag per prompt

### Runs

* Every LLM call: timestamp, prompt id/version, model, input refs, output JSON, validation status

---

## 5) Storage Design (Hybrid)

## 5.1 Markdown vault (Source of Truth)

Folder layout (<=3 levels):

```
Vault/
  entries/2026/2026-02/
  goals/
  chats/
  reviews/
  config/prompts/
```

### File naming

`YYYY-MM-DD_HH-mm_<type>_<slug>.md`

### Entry template (canonical)

```md
---
id: <uuid>
created: 2026-02-19T18:05:00+04:00
type: activity|sleep|food|thought|idea|todo|goal|note|chat
status: inbox|processed|archived
goals: [weight-loss]
tags: [walking, steps]
summary: "Walk: 10,000 steps in 50 min at Electra Park."
---

## Details
- ...

## Actions
- [ ] ...

## Context (Raw)
<original raw text exactly as typed>

## AI (optional)
Prompt: ingest_extract@v3
RunId: <uuid>
```

### Goal note template

`Vault/goals/<goal_id>_<slug>.md`:

* rules
* tracked metrics
* review cadence

### Review notes

Weekly review is a markdown note stored in `Vault/reviews/`.

---

## 5.2 SQLite (Derived index + analytics)

SQLite is **rebuildable** from vault.

### Tables (suggested V2 schema)

#### `entries_index`

* id (uuid, PK)
* path (text)
* created_at (text)
* type (text)
* status (text)
* summary (text)
* raw_text (text)
* details_md (text)
* tags_json (text)
* goals_json (text)
* updated_at (text)
* content_hash (text) (detect external edits)

#### Observations (typed facts)

* `obs_activity`: entry_id, steps, duration_min, distance_km, location, calories, pace, notes
* `obs_sleep`: entry_id, sleep_start, sleep_end, duration_min, quality, notes
* `obs_food`: entry_id, meal_type, items_json, notes
* `obs_weight`: entry_id, weight_kg

#### Goals

* `goals`: goal_id, name, start_date, end_date, rules_md, metrics_json, status
* `goal_links`: goal_id, entry_id, link_type (e.g., “related”, “evidence”)

#### Tasks & improvements

* `tasks`: task_id, source_entry_id, goal_id, title, due_date, priority, status, created_at, updated_at
* `improvements`: improvement_id, goal_id, title, rationale, status, created_at, updated_at, last_nudged_at
* `insights`: insight_id, goal_id, title, evidence_json, created_at

#### Chat

* `chat_threads`: thread_id, goal_id, created_at, title
* `chat_messages`: message_id, thread_id, role, content, created_at

#### Prompt registry + runs

* `prompt_templates`: prompt_id, name, version, provider, model, params_json, system_text, user_text, schema_json
* `prompt_runs`: run_id, prompt_id, prompt_version, created_at, input_refs_json, output_json, parse_ok, error_text

#### Search

* FTS5 virtual table: `fts_entries(summary, raw_text, details_md, tags, goals)` with triggers to keep it synced.

---

## 6) LLM System (transparent + configurable)

## 6.1 Provider abstraction

* Provider = `openai` (primary) and optional `ollama` later
* Config defines default models per task:

  * ingestion/extraction (cheap)
  * weekly review (high quality)
  * chat reasoning (high quality)

## 6.2 Prompt registry (files + DB)

Prompt YAML files in `Vault/config/prompts/*.yaml` are loaded into DB on startup/reload.

Example prompt config (YAML):

```yaml
id: ingest_extract
version: v3
provider: openai
model: gpt-5-mini
params:
  temperature: 0.2
schema: schemas/ingest_extract.json
system: |
  You are a personal life-OS assistant. Preserve the user's meaning. Extract facts precisely.
user: |
  Raw entry:
  {{raw_text}}

  Goal context:
  {{goal_context}}

  Return JSON that matches the schema.
```

## 6.3 Structured output contracts (schemas)

Key schemas:

* `ingest_extract.json`
* `goal_chat_response.json`
* `distill_outcomes.json`
* `weekly_goal_review.json`

**Rule:** if model output fails schema validation:

* store run with `parse_ok=false`
* keep entry as inbox
* show “retry” with last error

---

## 7) Analytics & Patterns (how it works)

Split into two layers:

### Layer 1: Deterministic metrics (Python)

* steps/day, moving averages
* weight trend slope (7/30)
* streaks (logging + activity)
* anomalies (z-score / threshold)
* correlations (simple: activity vs sleep, sleep vs weight change)

### Layer 2: Narrative + coaching (LLM)

Feed computed metrics + a few representative entries → produce:

* “What’s going well”
* “What’s not”
* “Patterns emerging”
* “Next best actions (2–5)”

Outputs are stored as:

* goal insight(s)
* improvement item(s)
* todo(s)

---

## 8) Reminders & nudges

### Types

* Missing logs reminder (daily check)
* Ignored improvement reminder (e.g., not acted for 7 days)
* Goal review reminder (weekly)

### Implementation (local)

* Use a local scheduler (e.g., APScheduler) + in-app banners
* Optional OS notifications later

### Nudge policy

* Gentle → persistent if repeated misses
* Always actionable (one-click “log now”)

---

## 9) “Never lose originality” guarantee

* Raw stays in `## Context (Raw)` section unchanged
* Every processing run:

  * appends or updates structured sections **without editing raw**
  * logs prompt run id and version
* Optional “entry versions” later if you want full diff history

---

# V2 Action Plan — Practical Tasks

Below is an execution-ready backlog. Each task has a crisp output and acceptance criteria.

---

## Epic 0 — Project scaffolding

**0.1** Create repo + local runtime

* FastAPI + Jinja templates + HTMX
* Config file for `vault_path`, `db_path`, `timezone`

✅ Accept: app runs locally, shows home page.

**0.2** Basic UI layout

* Sidebar nav + top bar
* Consistent card component

✅ Accept: navigation between placeholder pages.

---

## Epic 1 — Storage foundation (Vault + DB)

**1.1** Vault manager

* Create vault folders if missing
* File naming + slug generator
* Atomic writes (write temp → rename)

✅ Accept: creating an entry writes a correct `.md` file.

**1.2** Markdown parser/writer

* YAML frontmatter parse/serialize
* Extract sections: Details, Actions, Raw

✅ Accept: read→write roundtrip preserves raw exactly.

**1.3** SQLite schema + migrations

* Create tables listed above
* Add FTS5 table + triggers or sync logic

✅ Accept: DB initializes cleanly; can insert + query entries.

**1.4** Indexer (rebuild DB from vault)

* Scan vault, parse frontmatter + sections
* Upsert into `entries_index`
* Compute content_hash

✅ Accept: delete DB → rebuild → all notes appear in timeline.

---

## Epic 2 — Capture + Inbox + Timeline

**2.1** Capture form

* Single textbox + optional type selector
* Batch mode: split multiple entries by blank lines or `Type|Text`

✅ Accept: one paste can create multiple entries.

**2.2** Inbox page

* List unprocessed entries
* Bulk select → process

✅ Accept: entries show status, created date, short preview.

**2.3** Timeline page

* Date filters + type + tag + goal filters
* Pagination

✅ Accept: fast filtering without scanning vault each time.

---

## Epic 3 — Search (fast)

**3.1** Keyword search (FTS5)

* Search box → results list with snippets
* Facets: type, tags, goals

✅ Accept: results returned in <1s for large vault.

---

## Epic 4 — Prompt Registry + LLM Run Logging

**4.1** Prompt loader

* Load YAML prompt files into DB
* “Reload prompts” button

✅ Accept: editing YAML changes behavior after reload.

**4.2** Run logger

* Save every run: prompt id/version, inputs refs, output, parse_ok

✅ Accept: Runs page shows history, errors, and outputs.

**4.3** Schema validation

* Pydantic validation against expected JSON schema
* Fail safe: no destructive writes on invalid output

✅ Accept: invalid output leaves entry in inbox + shows error.

---

## Epic 5 — Ingestion/Extraction pipeline

**5.1** Process single entry

* Build LLM context (goal rules if linked, last N relevant logs)
* Call LLM → parse JSON → update markdown sections + DB tables

✅ Accept: entry becomes “processed” with summary/details/tags extracted.

**5.2** Observation extraction mapping

* Map extracted facts into obs tables:

  * activity (steps/duration/location)
  * sleep
  * food
  * weight

✅ Accept: activity entry populates obs_activity and reflects on goal charts.

**5.3** Batch processing

* Process inbox sequentially with progress feedback

✅ Accept: process 50 entries reliably; failures don’t stop entire batch.

---

## Epic 6 — Goals (CRUD + dashboard v1)

**6.1** Goals CRUD

* Create/edit goal: name, timeframe, rules, metrics tracked
* Link entries to goals (auto + manual)

✅ Accept: goal shows linked entries and tracked metrics.

**6.2** Goal dashboard v1 (deterministic metrics)
Cards:

* Steps avg (7 days), streak
* Weight trend (if logged)
* Sleep avg (if logged)
* Logging completeness

✅ Accept: metrics update instantly after processing new entries.

---

## Epic 7 — Todos + Improvements

**7.1** Task extraction + checkbox sync

* From LLM “actions” → tasks table
* From markdown `- [ ]` checkboxes → tasks table sync

✅ Accept: checking a box updates task status.

**7.2** Today page

* Due today / overdue / next actions
* Quick complete

✅ Accept: your daily actions are visible without opening notes.

**7.3** Improvements module

* Create from LLM distilled outcomes
* Track status + last nudged

✅ Accept: improvements appear in goal dashboard.

---

## Epic 8 — Chat inside goals + distilled outcomes

**8.1** Chat thread UI

* Chat per goal (thread list + messages)
* Save messages to DB + optional markdown transcript in `Vault/chats/`

✅ Accept: chat is persisted and searchable.

**8.2** Context builder for chat

* Pull: goal rules + last 7/30 day metrics + recent entries relevant

✅ Accept: chat answers reference your data, not generic advice.

**8.3** Distill outcomes

* Button: “Convert to Insight/Improvement/Todos”
* Runs a distillation prompt and saves results

✅ Accept: after chat, you get actionable items on dashboard.

---

## Epic 9 — Missing data capture + reminders

**9.1** Missing logs detector

* For active goals, detect gaps (sleep/food/activity) by date

✅ Accept: dashboard shows “missing for Feb 18”.

**9.2** Quick check-in forms

* Sleep check-in, Food check-in, Activity check-in templates

✅ Accept: fill missing day in <30 seconds.

**9.3** Scheduler (optional in V2)

* Daily reminder + weekly review reminder (in-app banner first)

✅ Accept: reminders appear; can snooze/disable.

---

## Epic 10 — Weekly Review (goal-level coaching)

**10.1** Weekly metrics aggregator

* Compute deterministic summary

✅ Accept: produces a structured “weekly snapshot” object.

**10.2** LLM weekly review writer

* Generate “What’s good/bad/patterns/next actions”
* Save as `Vault/reviews/` markdown + DB row for display

✅ Accept: goal dashboard shows last review and recommended actions.

---

# Deliverable checklist for V2 (definition of done)

* ✅ Vault is source of truth, DB rebuild works
* ✅ Capture → process → structured facts stored
* ✅ Goal dashboards show progress + logging completeness
* ✅ Todos are actionable and visible on Today page
* ✅ Chat exists and outcomes become improvements/todos
* ✅ Prompts are editable and every run is auditable

---

If you want, I’ll produce the **exact JSON schemas** for:

* `ingest_extract`
* `goal_chat_response`
* `distill_outcomes`
* `weekly_goal_review`

…and a minimal **SQLite DDL** + the canonical **markdown template renderer** rules (so your processing never corrupts raw text).
