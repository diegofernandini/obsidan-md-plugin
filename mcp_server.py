#!/usr/bin/env python3
"""
MI-AI MCP Server — expose chat and blueprint pipelines to MCP clients (Cursor, etc.).

Transport: stdio (JSON-RPC). Do not print to stdout; use stderr for diagnostics.

Outputs are written into the *calling agent's project* (MCP roots / project_root /
MI_AI_PROJECT_ROOT), not into this MI-AI repository.
"""
from __future__ import annotations

import logging
import os
import sys
from typing import List, Optional

# Ensure project root is on sys.path when launched as an absolute script path
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from mcp.server.fastmcp import Context, FastMCP

from src.agent_manager import AgentManager
from src.data_ingestor import DataIngestor
from src import pipeline_runners as runners
from src.output_writer import attach_output

# Logging must go to stderr so stdio JSON-RPC stays clean
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("mi-ai-mcp")

MODEL_NAME = os.environ.get("MI_AI_MODEL", "llama3.1")

mcp = FastMCP(
    "mi-ai",
    instructions=(
        "MI-AI Knowledge System: multi-agent research pipelines over a local Obsidian vault "
        "and web sources (Ollama). Pick an explicit tool for the pipeline you need — "
        "run_roadmap, run_synergy, run_explore, run_organize, or run_chat. "
        "Call list_pipelines first if unsure which blueprint fits. "
        "Reports are written into the calling agent's project (pass project_root, or rely on "
        "MCP workspace roots / MI_AI_PROJECT_ROOT). Do not expect files in the MI-AI repo."
    ),
)

_agent_manager: Optional[AgentManager] = None
_ingestor: Optional[DataIngestor] = None


def _get_agent_manager() -> AgentManager:
    global _agent_manager
    if _agent_manager is None:
        logger.info("Initializing AgentManager with model=%s", MODEL_NAME)
        _agent_manager = AgentManager(model_name=MODEL_NAME)
    return _agent_manager


def _get_ingestor() -> DataIngestor:
    global _ingestor
    if _ingestor is None:
        logger.info("Initializing DataIngestor")
        _ingestor = DataIngestor()
    return _ingestor


def _stderr_log(msg: str) -> None:
    logger.info("%s", msg)


async def _mcp_root_uris(ctx: Optional[Context]) -> List[str]:
    """Ask the MCP client for workspace roots (caller project paths)."""
    if ctx is None:
        return []
    try:
        result = await ctx.session.list_roots()
        uris: List[str] = []
        for root in getattr(result, "roots", None) or []:
            uri = getattr(root, "uri", None)
            if uri is not None:
                uris.append(str(uri))
        if uris:
            logger.info("MCP roots from client: %s", uris)
        return uris
    except Exception as e:
        logger.warning("Could not list MCP roots: %s", e)
        return []


def _finalize(
    result: dict,
    *,
    title: str,
    project_root: Optional[str],
    output_dir: Optional[str],
    mcp_root_uris: List[str],
) -> dict:
    return attach_output(
        result,
        title=title,
        project_root=project_root,
        output_dir=output_dir,
        mcp_root_uris=mcp_root_uris or None,
    )


# --- Resources ----------------------------------------------------------------

@mcp.resource("mi-ai://pipelines")
def resource_pipelines() -> str:
    """Catalog of chat modes and blueprint tools with when-to-use guidance."""
    return runners.pipelines_markdown()


@mcp.resource("mi-ai://health")
def resource_health() -> str:
    """Health snapshot: configured model and LLM readiness."""
    am = _get_agent_manager()
    ready = am.llm is not None
    vault = runners.resolve_vault_path()
    project = os.environ.get("MI_AI_PROJECT_ROOT") or os.environ.get("MI_AI_OUTPUT_DIR")
    return (
        f"status: {'ok' if ready else 'degraded'}\n"
        f"model: {MODEL_NAME}\n"
        f"llm_ready: {ready}\n"
        f"default_vault: {vault or '(not set)'}\n"
        f"default_project: {project or '(use MCP roots or project_root arg)'}\n"
    )


# --- Tools --------------------------------------------------------------------

@mcp.tool()
def list_pipelines() -> dict:
    """List available MI-AI chat modes, agent roles, and blueprint pipelines.

    Use this before choosing a tool when the user has not named a specific blueprint.
    Each blueprint has its own tool (run_roadmap, run_synergy, run_explore, run_organize).
    Reports from run_* tools are written into the calling agent's project, not this repo.
    """
    return runners.PIPELINES_CATALOG


@mcp.tool()
async def health_check(ctx: Context) -> dict:
    """Check whether the MI-AI MCP server and Ollama LLM are ready."""
    am = _get_agent_manager()
    ready = am.llm is not None
    roots = await _mcp_root_uris(ctx)
    return {
        "status": "ok" if ready else "degraded",
        "model": MODEL_NAME,
        "llm_ready": ready,
        "default_vault": runners.resolve_vault_path(),
        "mcp_roots": roots,
        "project_root_env": os.environ.get("MI_AI_PROJECT_ROOT"),
        "output_dir_env": os.environ.get("MI_AI_OUTPUT_DIR"),
        "message": (
            "Ollama LLM initialized."
            if ready
            else "LLM not initialized. Ensure Ollama is running and the model is pulled."
        ),
    }


@mcp.tool()
async def run_chat(
    message: str,
    ctx: Context,
    mode: str = "local",
    agent_role: str = "Detective / Agente Extractor",
    vault_path: Optional[str] = None,
    active_note_content: Optional[str] = None,
    project_root: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> dict:
    """Run a MI-AI chat pipeline (not a blueprint).

    Modes:
    - local: RAG over the Obsidian vault
    - web: autonomous web/academic research with contrast debate
    - hybrid: vault + web synthesis

    Writes the report into the calling agent's project (project_root, MCP roots,
    or MI_AI_PROJECT_ROOT → MI-AI Reports/). Returns report plus output_path.
    """
    roots = await _mcp_root_uris(ctx)
    result = runners.run_chat(
        agent_manager=_get_agent_manager(),
        ingestor=_get_ingestor(),
        message=message,
        mode=mode,
        agent_role=agent_role,
        vault_path=vault_path,
        active_note_content=active_note_content,
        log=_stderr_log,
    )
    return _finalize(
        result,
        title=f"CHAT_{mode}_{message[:30]}",
        project_root=project_root,
        output_dir=output_dir,
        mcp_root_uris=roots,
    )


@mcp.tool()
async def run_roadmap(
    topic: str,
    ctx: Context,
    vault_path: Optional[str] = None,
    project_root: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> dict:
    """Blueprint: Research Roadmap for a SINGLE topic.

    Sequence: state of the art → critical gap analysis → visionary ideas.
    Writes the report into the calling agent's project. Returns report, transcript,
    logs, and output_path.
    """
    roots = await _mcp_root_uris(ctx)
    result = runners.run_roadmap(
        agent_manager=_get_agent_manager(),
        ingestor=_get_ingestor(),
        topic=topic,
        vault_path=vault_path,
        model_name=MODEL_NAME,
        log=_stderr_log,
    )
    return _finalize(
        result,
        title=f"ROADMAP_{topic[:40]}",
        project_root=project_root,
        output_dir=output_dir,
        mcp_root_uris=roots,
    )


@mcp.tool()
async def run_synergy(
    topics: List[str],
    ctx: Context,
    vault_path: Optional[str] = None,
    project_root: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> dict:
    """Blueprint: Synergy Matrix across MULTIPLE topics.

    Cross-analyzes topics for intersections and joint opportunities.
    Pass at least two topic strings. Writes into the calling agent's project.
    """
    if not topics or len(topics) < 2:
        return {
            "pipeline": "blueprint/synergy",
            "error": "Provide at least two topics.",
            "report": "",
            "transcript": None,
            "logs": [],
            "topics": topics or [],
            "output": {"written": False, "message": "Not run — need 2+ topics."},
        }
    roots = await _mcp_root_uris(ctx)
    result = runners.run_synergy(
        agent_manager=_get_agent_manager(),
        ingestor=_get_ingestor(),
        topics=topics,
        vault_path=vault_path,
        model_name=MODEL_NAME,
        log=_stderr_log,
    )
    combined = " + ".join(topics)[:40]
    return _finalize(
        result,
        title=f"SYNERGY_{combined}",
        project_root=project_root,
        output_dir=output_dir,
        mcp_root_uris=roots,
    )


@mcp.tool()
async def run_explore(
    topics: List[str],
    ctx: Context,
    vault_path: Optional[str] = None,
    project_root: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> dict:
    """Blueprint: Literature Relation Exploration across concepts.

    Writes the report into the calling agent's project. Returns report, transcript,
    logs, and output_path.
    """
    if not topics:
        return {
            "pipeline": "blueprint/explore",
            "error": "Provide at least one topic/concept.",
            "report": "",
            "transcript": None,
            "logs": [],
            "topics": [],
            "output": {"written": False, "message": "Not run — need topics."},
        }
    roots = await _mcp_root_uris(ctx)
    result = runners.run_explore(
        agent_manager=_get_agent_manager(),
        ingestor=_get_ingestor(),
        topics=topics,
        vault_path=vault_path,
        model_name=MODEL_NAME,
        log=_stderr_log,
    )
    combined = " + ".join(topics)[:40]
    return _finalize(
        result,
        title=f"EXPLORE_{combined}",
        project_root=project_root,
        output_dir=output_dir,
        mcp_root_uris=roots,
    )


@mcp.tool()
async def run_organize(
    ctx: Context,
    vault_path: Optional[str] = None,
    project_root: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> dict:
    """Blueprint: incremental organization of an Obsidian vault (frontmatter, structure).

    Requires vault_path or MI_AI_VAULT_PATH. Writes the summary report into the
    calling agent's project (separate from vault edits).
    """
    roots = await _mcp_root_uris(ctx)
    result = runners.run_organize(
        agent_manager=_get_agent_manager(),
        ingestor=_get_ingestor(),
        vault_path=vault_path,
        model_name=MODEL_NAME,
        log=_stderr_log,
    )
    return _finalize(
        result,
        title="ORGANIZE_vault",
        project_root=project_root,
        output_dir=output_dir,
        mcp_root_uris=roots,
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
