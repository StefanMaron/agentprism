# agentmux

**A universal MCP server that exposes coding agents — GitHub Copilot, Claude Code, Codex — as background subagents behind a single, unified tool interface.**

agentmux lets one AI agent orchestrate other AI agents. Drop it into your MCP client (Claude Code, Cursor, Continue, …) and you gain seven tools — `agent_spawn`, `agent_send`, `agent_wait`, `agent_status`, `agent_list`, `agent_kill`, `agent_models` — that drive any supported coding agent through its native protocol. Run several in parallel, hand off tasks between them, or use a cheaper model as a worker for a more expensive planner. agentmux speaks each provider's wire protocol natively (ACP JSON-RPC for Copilot, etc.) — no fragile screen-scraping or pexpect.

## Installation

```bash
# from PyPI (when published)
pip install agentmux

# or from source
git clone https://github.com/StefanMaron/agentmux
cd agentmux
pip install -e .
```

You also need at least one supported coding-agent CLI installed and authenticated:

| Provider     | CLI                                  | Auth                          |
|--------------|--------------------------------------|-------------------------------|
| Copilot      | `copilot` ([install][copilot-cli])   | `copilot` then `/login`       |
| Claude Code  | `claude` ([install][claude-cli])     | `claude` then `/login`        |
| Codex        | `codex` ([install][codex-cli])       | `codex login`                 |

[copilot-cli]: https://docs.github.com/en/copilot/github-copilot-in-the-cli
[claude-cli]:  https://docs.anthropic.com/en/docs/claude-code
[codex-cli]:   https://github.com/openai/codex

## Usage with Claude Code

Register agentmux as an MCP server in Claude Code's `~/.config/claude/settings.json` (or wherever your client looks for MCP servers):

```json
{
  "mcpServers": {
    "agentmux": {
      "command": "agentmux",
      "args": [],
      "env": {
        "AGENTMUX_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

Restart Claude Code. The seven `agent_*` tools will appear. Try:

> Use `agent_spawn` to start a Copilot session in `/tmp/playground` with the task "write a python script that prints prime numbers up to 100", then `agent_wait` for it to finish.

## Tool reference

| Tool            | Args                                                           | Returns                                  |
|-----------------|----------------------------------------------------------------|------------------------------------------|
| `agent_models`  | `provider?`                                                    | model ids + multipliers                  |
| `agent_spawn`   | `task`, `cwd`, `provider`, `model?`, `mode?`                   | `session_id` (non-blocking)              |
| `agent_send`    | `session_id`, `message`                                        | agent reply (blocks until done)          |
| `agent_status`  | `session_id`                                                   | `working` \| `idle` \| `done` \| `error` |
| `agent_wait`    | `session_id`, `timeout_seconds?`                               | accumulated output (blocks)              |
| `agent_list`    | —                                                              | every active session                     |
| `agent_kill`    | `session_id`                                                   | terminates the subprocess                |

## Provider support

| Provider       | Status | Protocol                       |
|----------------|--------|--------------------------------|
| GitHub Copilot | ✓      | ACP JSON-RPC over stdio        |
| Claude Code    | 🔜     | (planned: ACP / `--print`)     |
| Codex          | 🔜     | (planned: stdio JSON)          |

## Architecture

```
┌──────────────────┐                     ┌──────────────────────────────┐
│  MCP client      │  agent_spawn(...)   │      agentmux server         │
│  (Claude Code,   │ ──────────────────► │                              │
│   Cursor, ...)   │  ◄──── result ────  │  ┌────────────────────────┐  │
└──────────────────┘                     │  │   ToolDispatcher       │  │
                                         │  └───────────┬────────────┘  │
                                         │              │               │
                                         │  ┌───────────▼────────────┐  │
                                         │  │   SessionRegistry      │  │
                                         │  │   session_id ► Adapter │  │
                                         │  └───────────┬────────────┘  │
                                         │              │               │
                                         │  ┌───────────▼────────────┐  │
                                         │  │   CopilotAdapter       │  │
                                         │  │   ClaudeCodeAdapter 🔜 │  │
                                         │  │   CodexAdapter      🔜 │  │
                                         │  └───────────┬────────────┘  │
                                         └──────────────┼───────────────┘
                                                        │ stdio JSON-RPC
                                                        ▼
                                          ┌─────────────────────────────┐
                                          │  copilot --acp (subprocess) │
                                          └─────────────────────────────┘
```

Each adapter owns one subprocess and one logical session. A reader coroutine demuxes stdout: replies (with `id`) resolve pending futures, while `session/update` notifications stream into an output buffer that `agent_wait` and `agent_send` drain.

## Configuration

Environment variables:

| Variable                | Default                           | Purpose                                  |
|-------------------------|-----------------------------------|------------------------------------------|
| `AGENTMUX_LOG_LEVEL`    | `INFO`                            | Python logging level (logs go to stderr) |
| `AGENTMUX_COPILOT_BIN`  | `/home/stefan/.local/bin/copilot` | Path to the `copilot` binary             |

## Development

```bash
pip install -e ".[dev]"
ruff check .
pytest
```

## License

MIT
