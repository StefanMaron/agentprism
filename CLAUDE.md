# agentprism — contributor guide

## Architecture

agentprism is an MCP stdio server. Each Claude Code session that loads it gets one `agentprism` process. That process:

1. Speaks MCP JSON-RPC over stdin/stdout with the host (Claude Code)
2. Spawns external coding-agent CLIs as subprocesses per `agent_spawn`/`agent_run` call
3. Runs a lightweight HTTP API on a random free port for the dashboard
4. Writes a lockfile to `~/.agentprism/{pid}.json` so the standalone dashboard can discover it

```
Host (Claude Code)  ←──MCP stdio──►  agentprism server
                                            │
                                     SessionRegistry
                                            │
                          ┌─────────────────┼──────────────────┐
                          ▼                 ▼                  ▼
                    CopilotAdapter   GeminiAdapter       OllamaAdapter
                    (subprocess)     (subprocess)        (HTTP REST)
```

## Adding a provider

1. Create `agentprism/adapters/<name>.py` — subclass `AgentAdapter` from `base.py`
2. Implement: `models()`, `check_available()`, `spawn()`, `send()`, `status()`, `wait()`, `kill()`
3. Register in `session.py`: add to `PROVIDERS` dict
4. Add env var for binary path following the `AGENTPRISM_<NAME>_BIN` pattern
5. Update README provider tables

### AgentAdapter contract

```python
class AgentAdapter:
    provider: str                        # registry key, e.g. "copilot"

    @classmethod
    def models(cls) -> list[dict]: ...   # [{"id": "...", "multiplier": "1x", "note": "..."}]

    @classmethod
    def check_available(cls) -> ProviderStatus: ...

    async def spawn(self, task, cwd, model=None, mode=None) -> str:  # session_id
    async def send(self, session_id, message) -> str:                # non-blocking, returns immediately
    async def status(self, session_id) -> str:                       # working|idle|done|error
    async def wait(self, session_id, timeout=None) -> str:           # blocks, returns accumulated output
    async def kill(self, session_id) -> None:
```

`send()` must be non-blocking — return a short confirmation string immediately and let the turn drain in the background. The host calls `agent_wait` or `agent_status` to observe progress.

### Subprocess pattern

All CLI adapters use `asyncio.create_subprocess_exec`:

```python
proc = await asyncio.create_subprocess_exec(
    *argv,
    stdin=asyncio.subprocess.DEVNULL,   # CRITICAL: never inherit MCP's stdin
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
    cwd=cwd,
)
```

**`stdin=DEVNULL` is required** — inheriting the parent's stdin would corrupt the MCP JSON-RPC channel. Exception: Gemini CLI requires `stdin=PIPE` and a single `b"\n"` write to unblock its startup prompt.

### Quota detection

Call `detect_quota_error(text, provider, model)` from `base.py` after collecting output. It scans for `"429"`, `"quota"`, `"rate limit"`, etc. and raises `QuotaExceededError` with structured fields. `tools.py` catches this and returns a `{"error": "quota_exceeded", ...}` JSON dict instead of crashing.

## Key files

| File | Purpose |
|------|---------|
| `agentprism/server.py` | MCP server entrypoint, registers tools, handles sampling push notifications |
| `agentprism/tools.py` | Tool JSON schemas + `ToolDispatcher` (all `_tool_*` handlers) |
| `agentprism/session.py` | `SessionRegistry`, `PROVIDERS` dict, `git_delta()` |
| `agentprism/adapters/base.py` | `AgentAdapter` ABC, `ProviderStatus`, `QuotaExceededError`, `detect_quota_error` |
| `agentprism/dashboard.py` | Per-instance HTTP API + SSE streaming (`/api/sessions`, `/api/sessions/{id}/stream`) |
| `agentprism/standalone_dashboard.py` | Fan-out dashboard that discovers all instances via `~/.agentprism/*.json` lockfiles |

## git_delta

`git_delta(cwd, base_sha)` is called after `agent_wait` and `agent_status` to return:
- `new_commits` — list of commits made since spawn
- `working_tree_changes` — current `git status --short` output

This means callers never need to run git commands themselves after waiting on a session.

## Dashboard SSE

The per-instance dashboard streams session output via Server-Sent Events at `/api/sessions/{id}/stream`. The standalone dashboard proxies these from the correct instance. Watch buttons use `data-sid`/`data-provider`/`data-task` HTML attributes + a single event listener — inline `onclick` with task text breaks when task contains quotes.

## Development

```bash
pip install -e ".[dev]"
ruff check .
pytest
```

Publish to PyPI:
```bash
python -m build
twine upload dist/*
```
