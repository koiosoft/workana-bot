# Task 5

## Task
Create the RequirementAnalysesRepository in app/database/requirement_analyses_repository.py with insert and get_latest_by_project_id methods (no sequential versioning). [ASSET: ./assets/TASK005_spec.md]

> **MANDATORY — Prepare:** Read EVERY file referenced by `[ASSET: ...]` markers in this file BEFORE starting the task. Asset paths are relative to THIS file's directory (e.g. `./assets/TASKXXX_spec.md` → the `assets/` folder next to this file). Do not begin implementation until you have read them.

## Status
Completed

## Justification
### What was built

- `app/database/requirement_analyses_repository.py` — `RequirementAnalysesRepository`
  bound to the `requirement_analyses` collection, exposing exactly two public data
  operations plus index management:
  - `async insert(document) -> str` — validates and persists the Etapa 1 accumulated
    JSON (`project_id`, `link_hash`, `analysis` as the full nested object with
    `maturity_score` / `maturity_reason` / `entities` / `gaps` / `branch`,
    `maturity_threshold_used` as int, `model_used` as str, `created_at` as a real
    BSON date), returns the new `_id` as a string.
  - `async get_latest_by_project_id(project_id) -> dict | None` — `find_one` filtered
    by `project_id`, `sort=[("created_at", DESCENDING)]`; stringifies `_id`.
  - `async ensure_indexes()` — declares `(project_id ASC, created_at DESC)` named
    `project_id_created_at_desc` and `(link_hash ASC)` named `link_hash_asc`, guarded
    by the `_indexes_ready` flag used by every sibling repository.
- `app/database/__init__.py` — re-exported `RequirementAnalysesRepository` alongside
  `ProjectsRepository` so callers import it from `app.database` (2 lines; no behaviour
  change to existing exports).
- `tests/unit/database/test_requirement_analyses_repository.py` — 22 unit tests
  (UNIT014 coverage): index declarations, absence of any `version_number` index or
  sort key, persisted document shape, nested analysis verbatim, `created_at` default
  vs explicit, threshold coercion/rejection, invalid-payload rejection with no write,
  unknown-field dropping, and a fake-store round trip proving the highest
  `created_at` wins.

### Why this design (technical justification)

- **No sequential versioning (§6.1 "Sin versionado secuencial").** Unlike
  `ProposalVersionsRepository`, which reads the previous `version_number` and
  increments it inside `insert_version`, this repository never reads before writing
  and never stores a counter. That removes a read-modify-write race (two concurrent
  `/procesar` runs could compute the same next version) and keeps `insert` a single
  atomic `insert_one`. "Latest" is therefore derived at read time purely from
  `created_at DESC`, which is what ACK017 requires; `version_number` appears nowhere
  in the module except in a regression test asserting it is absent, and in the
  unknown-field-drop test that proves even a caller-supplied one is not persisted.
- **Index choice follows the access pattern, not the entity.** Only two queries
  exist: "newest analysis for project X" and lookups by `link_hash` (the scraping/
  Telegram layer identifies projects by `link_hash` before/without the Mongo `_id`,
  exactly like `proposal_versions`). The compound `(project_id, created_at DESC)`
  index makes the ordering an index seek rather than scan-then-sort, so
  `get_latest_by_project_id` stays O(log n) regardless of history size. A
  single-field `project_id` index was deliberately NOT added: the compound index
  already serves any `project_id`-prefixed query, so a second one would only add
  write cost. Index names mirror `proposal_versions` (`*_asc`,
  `project_id_..._desc`) so ops tooling sees one convention.
- **`created_at` is stored as a datetime, not an ISO string.** §6.1 says "ISODate",
  i.e. the BSON date type, and `proposal_versions.insert_version` already stores
  `datetime.now(timezone.utc)`. Sorting on a real date is correct and indexable;
  sorting on an ISO-8601 string only happens to work when offsets are identical,
  and local-time strings would order silently wrong. UTC-aware by default, and an
  explicitly supplied `datetime` is honoured so a retry can reuse a timestamp.
- **Validation raises instead of logging-and-ignoring.** `insert` rejects a
  non-empty-but-malformed envelope with `ValueError` naming the offending field
  (missing `project_id` / `link_hash` / `analysis`, empty `analysis`, blank
  `model_used`, non-int `maturity_threshold_used`, non-datetime `created_at`). The
  Stage 1 record is the audit trail behind the branch decision (TASK017 needs
  `maturity_threshold_used` to prove which threshold was in force); persisting a
  partial document would make that review impossible after the fact, so failing loud
  at the boundary is cheaper than discovering a hole later. This mirrors the
  `ValueError` guard already at the top of `insert_version`.
- **`analysis` is stored verbatim as a plain dict.** The Pydantic gatekeeper
  (`app.models.analysis.RequirementAnalysis`, TASK003) already ran in the adapter
  before this call, and §6.1 wants the *accumulated* JSON kept as written so the
  merged Stage 1 + Stage 2 + Stage 3 payload stays comparable across stages
  (INT003/UNIT020). Re-validating here would couple the persistence layer to the LLM
  contract and would silently reshape numbers via validators; the repository
  therefore constrains only its own envelope fields and passes the subdocument
  through untouched. Unknown top-level extras are dropped rather than rejected so a
  caller passing the whole pipeline context cannot leak Stage 2/3 payloads into the
  Stage 1 collection.
- **Dynamic `collection` property + lazy `ensure_indexes`.** Identical to
  `ProjectsRepository`, `ProposalVersionsRepository` and `ProcessSemaphore`: the
  singleton connection in `app/database/mongo.py` may not exist at construction
  time, so nothing touches the driver in `__init__`. This also means importing the
  module has no I/O side effect — important because `app/database/__init__.py` now
  imports it eagerly.
- **Scope discipline (ACK020).** No router, endpoint, port, model or adapter was
  touched; nothing calls this repository yet. Callers arrive in TASK016 (Telegram
  handler persistence). `insert` returning the `_id` string matches
  `insert_version`'s contract so the handler can log/reference it consistently.

### Verification

- `python3 -m pytest tests/unit/database/test_requirement_analyses_repository.py -q`
  → 22 passed.
- `python3 -m pytest tests/unit -q` → 379 passed (no regressions from the
  `app/database/__init__.py` export).
- Collection access is dynamic (`get_database()["requirement_analyses"]`): no
  `create_collection` and no `$jsonSchema` validator, matching `projects`,
  `proposal_versions` and `process_semaphore`. Schema enforcement stays in the Pydantic
  models plus this module's `_normalise`, so a future field change needs no Atlas-side
  `collMod`.
- `python3 -m pytest tests/integration -q` → 70 passed, 1 failed:
  `test_proposals.py::TestRefineProposalLive::test_refine_endpoint_live_llm`. This is
  a pre-existing live-LLM flake unrelated to TASK005 — the run shows the remote
  OpenRouter model emitting a misspelled key (`refinement_justamination` /
  `refinement_justison`, varying per run) so `refinement_justification` arrives empty.
  Confirmed pre-existing by re-running that single test against the committed
  (`git show HEAD:`) version of the file: it fails identically, and my changes touch
  no code path it exercises.
- Live smoke test against the configured Atlas cluster (throwaway `project_id`,
  deleted afterwards): two inserts with different `created_at`,
  `get_latest_by_project_id` returned the newer document (score 9 over 4), and
  `index_information()` confirmed `project_id_created_at_desc = [(project_id, 1),
  (created_at, -1)]` and `link_hash_asc = [(link_hash, 1)]` were actually created.

