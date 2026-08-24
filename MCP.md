# MI-AI MCP Server

Expose MI-AI chat and blueprint pipelines to MCP clients (Cursor, Claude Desktop, and other agents) over **stdio**.

Each blueprint is a **separate tool**. The connected agent picks a tool by name (or you ask for it explicitly). There is no hidden auto-router inside one mega-tool.

## Where reports are written

Pipeline outputs are written into the **calling agent's project**, not into this MI-AI repository.

Resolution order for the write target:

1. Tool arg `output_dir` (exact folder)
2. Tool arg `project_root` → `{project_root}/MI-AI Reports/`
3. Env `MI_AI_OUTPUT_DIR`
4. Env `MI_AI_PROJECT_ROOT` → `{MI_AI_PROJECT_ROOT}/MI-AI Reports/`
5. MCP client workspace **roots** (from `roots/list`) → `{root}/MI-AI Reports/`

Each `run_*` result includes `output_path` / `output.written` so the caller can open the file.

## Prerequisites

- Python 3.10+
- Project dependencies: `./venv/bin/pip install -r requirements.txt` (pins `mcp[cli]<2` for FastMCP)
- Ollama running with the configured model (default `llama3.1`)

## Environment

| Variable | Default | Purpose |
|---|---|---|
| `MI_AI_MODEL` | `llama3.1` | Ollama model name for agents |
| `MI_AI_VAULT_PATH` | _(empty)_ | Default Obsidian vault path when tools omit `vault_path` |
| `MI_AI_PROJECT_ROOT` | _(empty)_ | Fallback caller project root for report writes |
| `MI_AI_OUTPUT_DIR` | _(empty)_ | Exact folder for reports (overrides subdir layout) |
| `MI_AI_OUTPUT_SUBDIR` | `MI-AI Reports` | Subfolder under project root |

## Tools

| Tool | When to use |
|---|---|
| `list_pipelines` | Catalog of modes, roles, and blueprints |
| `health_check` | Model / Ollama readiness + visible MCP roots |
| `run_chat` | Chat modes: `local`, `web`, `hybrid` (not a blueprint) |
| `run_roadmap` | Blueprint: deep single-topic research roadmap |
| `run_synergy` | Blueprint: synergy matrix across **2+** topics |
| `run_explore` | Blueprint: literature / concept relation exploration |
| `run_organize` | Blueprint: incremental vault organization |

Common write args on every `run_*` tool: `project_root`, `output_dir`.

### Resources

- `mi-ai://pipelines` — markdown catalog
- `mi-ai://health` — health snapshot

## Cursor setup

Add to your Cursor MCP config (e.g. `~/.cursor/mcp.json` or project `.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "mi-ai": {
      "command": "/absolute/path/to/obsidan-md-plugin/venv/bin/python",
      "args": ["/absolute/path/to/obsidan-md-plugin/mcp_server.py"],
      "env": {
        "MI_AI_MODEL": "llama3.1",
        "MI_AI_VAULT_PATH": "/absolute/path/to/your/vault",
        "MI_AI_PROJECT_ROOT": "/absolute/path/to/calling/agent/project"
      }
    }
  }
}
```

Prefer the project `venv` interpreter so the `mcp` package and LangChain deps resolve correctly.

Set `MI_AI_PROJECT_ROOT` to the workspace that should receive reports when the client does not expose MCP roots (or pass `project_root` on each tool call).

Restart Cursor (or reload MCP servers) after saving.

## Example prompts for the connected agent

- “List MI-AI pipelines.” → `list_pipelines`
- “Run the **roadmap** blueprint on mobile accessibility impact; write into this project.” → `run_roadmap` with `project_root` = workspace
- “Run **synergy** on accessibility and financial inclusion.” → `run_synergy`
- “Local vault chat as Detective: summarize notes about X.” → `run_chat` with `mode=local`

## Manual smoke test

```bash
# From the project root (use the project venv)
./venv/bin/python -c "from mcp_server import list_pipelines; print(list_pipelines())"

# Verify report write goes to a caller project path (not this repo's reports/)
./venv/bin/python -c "
from src.output_writer import write_pipeline_report
import tempfile, os
d = tempfile.mkdtemp()
r = write_pipeline_report(title='TEST', report='hello', project_root=d, pipeline='test')
print(r)
assert r['written'] and r['output_path'].startswith(d)
"
```

Or use the MCP Inspector:

```bash
./venv/bin/mcp dev mcp_server.py
```

## Notes

- Tools block until the pipeline finishes and return `{ report, transcript?, logs, pipeline, output_path?, output }`.
- FastAPI (`server.py`) remains for the Obsidian plugin; the MCP process imports `AgentManager` / `BlueprintEngine` directly (no HTTP loopback).
- Do not write diagnostics to stdout while the MCP server is running (stdio is the protocol). Logs go to stderr.
