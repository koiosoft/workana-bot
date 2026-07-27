# MCP Module: codebase-memory

## Prerequisite
- Verify `cbm_search_graph` exists in available tools. If missing, skip this entire module silently.

## Prioritization Rules
1. Always prefer `cbm_search_graph` over `grep` for finding symbols.
2. Use `cbm_trace_call_path` to resolve dependencies.
3. Fallback to `grep`/`read_file` only if graph returns no results.