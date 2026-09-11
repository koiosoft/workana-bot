## Core Tooling (Read, Reason, and Write)

The agent MUST follow this cascading fallback chain for all codebase interactions. This maximizes token efficiency while guaranteeing the safety of every modification.

> **jcodemunch via the `mcp` gateway**: `order`, `menu`, `route`, `set_tool_tier`, `announce_model`, `jcodemunch_guide` are exposed by the jcodemunch server and called **through the session-inherited `mcp` tool**, e.g. `mcp({server: "jcodemunch", tool: "order", args: {action: "search_symbols", args: {"query": "..."}}})` or `mcp({search: "menu"})`. Do NOT list them as direct tools in `tools:` — they are reached via the gateway. `cbm_*` tools become direct after `cbm_connect`. **Prefer pi-tools (Tier 1) for surgical searches** — they are always available and cheaper.

### 1. Information Retrieval (Reading & Searching)

To locate code or context, the agent **MUST** apply this cascading fallback chain. **Protocol first**: follow the cascade strictly; heuristic judgment is only a fallback when the protocol does not resolve the query. Never skip the lighter levels without exhausting them first. **Escalation is by SCOPE, not a rigid tier order**: use the lighter/faster levels for targeted and precise lookups; escalate to the heavy level only when the query is abstract/semantic, spans multiple layers, or a lower tier would flood the context with too many/noisy matches.

| Tier | Tool | Purpose & Trigger | Token Cost |
| :--- | :--- | :--- | :--- |
| **1** | **pi-tools** | **Structural & surgical search (cheapest).** Always available, no bootstrap needed. Replacements for classic Unix tools:
| | | - **Reemplazan a grep**: `find_replace` (text/regex search) and `find_references` (trace usages, calls, imports globally).
| | | - **Reemplazan a find**: `find_symbol` (locate files by function/class/struct).
| | | - **Reemplazan a ls**: `file_outline` (list structural content of a file).
| | | - **Reemplazan a cat**: `replace_in_symbol` (read/edit code blocks) and `clipboard` (text fragments).
| | | Cheap while scoped; escalate to Tier 2 for catalog navigation or Tier 3 for architecture. | **Low–Moderate** (only matching lines/names) |
| **2** | **`jcodemunch`** | **Artifact & catalog retrieval via the `mcp` gateway.** Call `mcp({server: "jcodemunch", tool: "order", args: {action: "search_symbols", args: {"query": "..."}}})`, `mcp({..., tool: "order", args: {action: "get_symbol_source", args: {"repo": "...", "symbol_id": "..."}}})`, `mcp({..., tool: "order", args: {action: "get_ranked_context", ...}})`. Index: `mcp({..., tool: "order", args: {action: "index_folder", args: {"path": "."}}})`. Discover actions via `mcp({..., tool: "menu"})`. Requires MCP bootstrap. | **Minimal** (tens–hundreds of tokens) |
| **3** | **`cbm` (CODE_BASE_MEMORY)** | **Heavy context: semantic & architectural.** Use `cbm_search_graph`, `cbm_trace_path`, `cbm_get_architecture` / `cbm_get_graph_schema`, `cbm_search_code`. Trigger: abstract query, flow across multiple layers, or when pi-tools flood the context. Requires MCP bootstrap. | **High** (injects broad indexed fragment) |
| **4** | **`read_file` (`read`)** | **Absolute last resort.** Full raw file content for holistic context. | **High** (full file) |

**Rule:** to find "where `authenticate` is", try **pi-tools** (`find_symbol`, `find_references`, `find_replace`) (Tier 1) first; **if Tier 1 does not fully resolve the query, escalate to Tier 2 jcodemunch** — it returns cross-references and signatures pi-tools cannot. Escalate to **`cbm`** (Tier 3) only for abstract/architectural questions. Save `read_file` for last.

**Escalation triggers — Tier 1 → Tier 2 (jcodemunch) when:**
- `find_references` returns empty or partial, but you know the symbol is used elsewhere.
- You need cross-references, signatures, summaries, or ranked results beyond a bare name match.
- The query is semantic (concept → code) rather than exact-name.
- `find_symbol`/`find_replace` resolve the name but not the relationships/impact.
In those cases call `mcp({server: "jcodemunch", tool: "order", args: {action: "search_symbols", args: {"query": "..."}}})` or `mcp({..., tool: "order", args: {action: "get_ranked_context", ...}})` BEFORE falling to Tier 3/4.

**JCodeMunch Usage (via the `mcp` gateway):** `mcp({server: "jcodemunch", tool: "order", args: {action: "...", args: {...}}})`, `mcp({server: "jcodemunch", tool: "menu"})`, `mcp({server: "jcodemunch", tool: "route", args: {task: "..."}})`. These are reached through the `mcp` tool, NOT listed as direct tools in `tools:`.

### 2. Safe Execution (Writing & Editing)

Once the retrieval phase identifies the target file(s):

- **DO NOT** use generic `replace` or `write` operations.
- **ALWAYS** use the `pi` agent's native `edit` tool (fully backed by `pi-hashline-edit`).
- This ensures every operation is anchored by `LINE#HASH`, guaranteeing atomic updates and preventing silent overwrites of concurrent changes.
- **CRITICAL anti-pattern — NEVER dump/near-rewrite the whole file inside a single `edit` call.** Only replace (or insert/delete) the **specific minimal set of lines** you are changing. One `edit` call = one small, targeted change anchored by its hashes. Restating large bodies of unchanged code: (1) wastes output tokens and frequently trips the model's output-token ceiling (colgados con `stopReason: "length"`), and (2) risks silently corrupting the file if a token is omitted. Prefer many small `edit` calls over one giant one, and use `replace_text` for exact single-occurrence substitutions.
- If `plan_refactoring` is needed, dispatch via `mcp({server: "jcodemunch", tool: "order", args: {action: "plan_refactoring", args: {...}}})` and apply the resulting `{old_text, new_text}` patches through the hashline-backed `edit` tool, again as minimal targeted edits.

### 3. General Workflow for a Task

1. **Explore** with pi-tools (`find_symbol`, `find_references`, `find_replace`, `file_outline`) (Tier 1) to locate the artifact/symbol.
2. **Navigate catalog** with jcodemunch (Tier 2) via the `mcp` gateway: `mcp({server: "jcodemunch", tool: "order", args: {action: "search_symbols", args: {"query": "..."}}})`, `mcp({server: "jcodemunch", tool: "menu"})`.
3. **Analyze impact/architecture** with `cbm` (Tier 3) when the task still needs relationships, algorithms, or cross-layer flow.
4. **Execute** the change using the native `edit` tool (`pi-hashline-edit`) for surgical safety.
5. **Verify** by re-querying jcodemunch via `mcp` (`mcp({server: "jcodemunch", tool: "order", args: {action: "get_symbol_source", args: {"repo": "...", "symbol_id": "..."}}})`) to confirm the symbol was updated.

**Note:** `pi-hashline-edit` is the engine for Tiers 1/4 (pi-tools/`read`) and the native `edit` tool. It is not a standalone tier.