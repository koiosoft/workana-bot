# SDD Sub-agent Surface

## Why?

SDD protocols need to invoke sub-agents (workers, judges, test-runners, reviewers,
doc-updaters) to delegate work. Originally the invocation API was hardcoded in `.md`
files using the legacy syntax (`Agent()`, `get_subagent_result()`, `steer_subagent()`,
`subagent_type`, `prompt`, `run_in_background`) of the `@tintinweb/pi-subagents`
extension.

That caused two problems:

1. **Confused orchestration LLMs** — they tried to call `Agent()` (which is not a tool)
   or used legacy params instead of the real ones, wasting turns re-interpreting.
2. **Changing shell or extension meant rewriting every protocol** — the API was coupled
   to a concrete implementation.

## Solution: Surface YAML + KEYs

Each shell/extension has a YAML file in this directory defining the **invocation surface**:
the use-case KEYs that the protocols reference.

```yaml
# e.g. .sdd/sub-agents/pi/nicobailon-pi-subagents.yaml
use_cases:
  launch: subagent({ agent, task, async, model, thinking })
  resume: subagent({ action: "resume", id, message })
```

When a protocol needs to invoke a sub-agent, it writes:

```markdown
Via use_case: launch
  agent: "sdd-worker"
  task: "Implement TASK001..."
  async: true
```

The LLM looks up `launch` in the YAML, copies the canonical form
`subagent({ agent, task, async, ... })`, and fills the values. **No ambiguity, no
translation.**

## Convention for orchestrator LLMs

1. When you read `use_case: <key>` in a protocol, look up that KEY in the active shell YAML.
2. The YAML gives you the **canonical invocation form**.
3. Fill the parameters with the values the protocol specifies.
4. If a KEY is not present in the YAML, use general judgment.

## How to write a new surface YAML

1. Create the file at `.sdd/sub-agents/<shell>/<name>.yaml`.
2. Define the KEYs the protocol needs. All are optional — define only what your extension
   supports:

```yaml
use_cases:
  # Launch a sub-agent in background.
  # Params: agent, task, async, model, thinking
  launch: <invocation>

  # Resume a "blocked" or "paused" sub-agent (after interrupt/manual).
  # Preserves the sub-agent context/session.
  # Params: id (of the run), message
  resume: <invocation>

  # Redirect a sub-agent in-flight.
  # Params: id, message
  steer: <invocation>

  # Read an async sub-agent result.
  # Params: id
  read_result: <invocation>

  # Wait for an async run to finish, then read result.
  # Params: id
  wait_result: <invocation>

  # Check an in-flight status.
  # Params: id
  check_status: <invocation>
```

Each KEY carries parameter placeholders the protocol will supply.

3. Add your file to the table in the Files section.

## Available files

| Shell | Extension | File |
|---|---|---|
| Pi | nicobailon/pi-subagents | `pi/nicobailon-pi-subagents.yaml` |

## Design principles

- **Deterministic and finite**: the protocol uses ~6 invocation patterns. Everything else the
  LLM resolves by general judgment.
- **KEY forces a lookup**: the LLM cannot ignore the YAML, because the KEY alone is
  meaningless until resolved.
- **Decoupled**: switching shells = switching the YAML. The `.md` protocols never name tools
  or concrete params.
- **Minimal**: the YAML defines only what the protocol needs. It is not an exhaustive
  catalogue of the sub-agent API.
