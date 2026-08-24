"""
Non-streaming runners for MI-AI chat and blueprint pipelines.
Used by the MCP server (and available for shared reuse with FastAPI).
"""
from __future__ import annotations

import os
from typing import Any, Callable, Dict, List, Optional

from src.agent_manager import AgentManager
from src.blueprint_engine import BlueprintEngine
from src.data_ingestor import DataIngestor

LogFn = Callable[[str], None]


def _noop_log(_msg: str) -> None:
    pass


def resolve_vault_path(vault_path: Optional[str] = None) -> Optional[str]:
    """Prefer explicit vault_path, else MI_AI_VAULT_PATH env."""
    if vault_path:
        return vault_path
    env_path = os.environ.get("MI_AI_VAULT_PATH")
    return env_path if env_path else None


def ensure_vault_indexed(
    ingestor: DataIngestor,
    vault_path: Optional[str],
    log: LogFn = _noop_log,
) -> List[str]:
    """Index the vault if needed. Returns log messages."""
    logs: List[str] = []
    if not vault_path:
        return logs
    if ingestor.vectorstore is not None:
        return logs

    msg = "Construyendo Segunda Memoria (Indexando Vault por primera vez)..."
    logs.append(msg)
    log(msg)
    try:
        texts = ingestor.load_local_data(vault_path)
        if texts:
            ingestor.index_data(texts, "VAULT", "vault_index")
            ok = "Vault indexado correctamente."
            logs.append(ok)
            log(ok)
        else:
            warn = "No se encontraron documentos válidos en el Vault."
            logs.append(warn)
            log(warn)
    except Exception as e:
        err = f"Error al indexar el Vault: {e}"
        logs.append(err)
        log(err)
    return logs


def _retrieve_local_context(ingestor: DataIngestor, message: str) -> str:
    if ingestor.vectorstore is None:
        return ""
    retriever = ingestor.get_retriever()
    docs = retriever.invoke(message)
    context_blocks = []
    for d in docs:
        source_file = d.metadata.get("source", "Nota Local Desconocida")
        basename = str(source_file).split("/")[-1]
        if basename.endswith(".md"):
            basename = basename[:-3]
        context_blocks.append(f"--- ARCHIVO ORIGEN: {basename} ---\n{d.page_content}")
    return "\n\n".join(context_blocks)


def _local_system_prompt(agent_role: str) -> str:
    system_prompt = (
        "Eres un asistente de inteligencia de mercado experto. SIEMPRE debes citar tus fuentes "
        "usando el formato [[Nombre de la Nota]] para archivos locales y [Título](URL) para enlaces web. "
        "Al final de tu respuesta, incluye siempre una sección de '## Bibliografía'."
    )
    if "Detective" in agent_role:
        system_prompt = (
            "Tu enfoque es forense. No interpretas; extraes datos puros y citas SIEMPRE "
            "el origen usando [[Wikilinks]]. Incluye bibliografía final."
        )
    elif "Editor" in agent_role:
        system_prompt = (
            "Tu función es dar cohesión y narrativa. Estructuras reportes profesionales e "
            "incluyes SIEMPRE una sección de '## Bibliografía' al final detallando las fuentes."
        )
    return system_prompt


def run_chat(
    agent_manager: AgentManager,
    ingestor: DataIngestor,
    message: str,
    mode: str = "local",
    agent_role: str = "Detective / Agente Extractor",
    vault_path: Optional[str] = None,
    active_note_content: Optional[str] = None,
    log: LogFn = _noop_log,
) -> Dict[str, Any]:
    """
    Run chat pipeline (local / web / hybrid) and return a structured result.
    Mirrors server.py /chat branching without SSE.
    """
    logs: List[str] = []
    vault_path = resolve_vault_path(vault_path)
    mode = (mode or "local").lower().strip()

    def _log(msg: str) -> None:
        logs.append(msg)
        log(msg)

    try:
        if mode == "local":
            context = ""
            if vault_path:
                logs.extend(ensure_vault_indexed(ingestor, vault_path, log=_log))
                try:
                    context = _retrieve_local_context(ingestor, message)
                except Exception as e:
                    _log(f"Error recuperando contexto: {e}")

            if active_note_content:
                context += f"\n\n--- NOTA ACTIVA (Para Contexto/Edición) ---\n{active_note_content}"

            _log("Analizando el contexto local...")
            system_prompt = _local_system_prompt(agent_role)
            report = agent_manager._run_agent_task(agent_role, system_prompt, context, message)
            return {
                "pipeline": "chat",
                "mode": mode,
                "agent_role": agent_role,
                "report": report,
                "logs": logs,
                "transcript": None,
                "bibliography": None,
            }

        if mode == "web":
            _log("Generando estrategia de búsqueda global...")
            queries = agent_manager.generate_search_queries(message)

            _log("Consultando fuentes académicas y generales...")
            search_results = ingestor.get_combined_research(queries)

            _log("Seleccionando las fuentes más relevantes...")
            selected_sources = agent_manager.select_best_sources(search_results, message)

            if not selected_sources:
                return {
                    "pipeline": "chat",
                    "mode": mode,
                    "agent_role": agent_role,
                    "report": "El investigador no encontró fuentes suficientemente relevantes para este tema.",
                    "logs": logs,
                    "transcript": None,
                    "bibliography": None,
                }

            research_contents = []
            for source in selected_sources:
                _log(f"Analizando contenido de {source['title']}...")
                research_contents.append(ingestor.scrape_url(source["url"]))

            transcript = None
            if len(research_contents) >= 2:
                _log("Iniciando debate de contraste...")
                debate_result = agent_manager.conduct_contrast_analysis(
                    research_contents[0], research_contents[1], message
                )
                report = debate_result["report"]
                transcript = debate_result["transcript"]
            else:
                _log("Sintetizando hallazgos...")
                report = agent_manager.synthesize_report(research_contents[0], message)

            bibliography = "\n".join(
                [f"- [{s.get('title', 'Fuente Web')}]({s['url']})" for s in selected_sources]
            )
            return {
                "pipeline": "chat",
                "mode": mode,
                "agent_role": agent_role,
                "report": report,
                "logs": logs,
                "transcript": transcript,
                "bibliography": bibliography,
            }

        if mode == "hybrid":
            _log("Validando memoria local (Vault)...")
            local_context = ""
            try:
                logs.extend(ensure_vault_indexed(ingestor, vault_path, log=_log))
                if ingestor.vectorstore is not None:
                    local_context = _retrieve_local_context(ingestor, message)
            except Exception as e:
                _log(f"Error recuperando contexto híbrido: {e}")

            _log("Lanzando investigación web complementaria...")
            queries = agent_manager.generate_search_queries(message)
            search_results = ingestor.get_combined_research(queries)
            selected_web = agent_manager.select_best_sources(search_results, message)

            web_contents = []
            for source in selected_web:
                _log(f"Cruzando información con {source['title']}...")
                web_contents.append(ingestor.scrape_url(source["url"]))

            _log("Agente Híbrido resolviendo conflictos y sintetizando...")
            report = agent_manager.conduct_hybrid_analysis(
                local_context, web_contents, "I", message
            )
            for phrase in (
                "[Fuente interna]",
                "[Fuente externa]",
                "[Fuente Externa]",
                "[Fuente Interna]",
            ):
                report = report.replace(phrase, "")

            bibliography = "\n".join(
                [f"- [{s.get('title', 'Fuente Web')}]({s['url']})" for s in selected_web]
            )
            return {
                "pipeline": "chat",
                "mode": mode,
                "agent_role": agent_role,
                "report": report,
                "logs": logs,
                "transcript": None,
                "bibliography": bibliography,
            }

        return {
            "pipeline": "chat",
            "mode": mode,
            "agent_role": agent_role,
            "report": "Modo de chat no soportado. Usa local, web o hybrid.",
            "logs": logs,
            "transcript": None,
            "bibliography": None,
        }
    except Exception as e:
        _log(f"Error crítico en chat: {e}")
        return {
            "pipeline": "chat",
            "mode": mode,
            "agent_role": agent_role,
            "report": f"Ocurrió un error: {e}",
            "logs": logs,
            "transcript": None,
            "bibliography": None,
            "error": str(e),
        }


def _make_engine(
    agent_manager: AgentManager,
    ingestor: DataIngestor,
    model_name: str,
    log: LogFn,
) -> BlueprintEngine:
    return BlueprintEngine(
        model_name=model_name,
        log_callback=log,
        agent_manager=agent_manager,
        ingestor=ingestor,
    )


def run_roadmap(
    agent_manager: AgentManager,
    ingestor: DataIngestor,
    topic: str,
    vault_path: Optional[str] = None,
    model_name: str = "llama3.1",
    log: LogFn = _noop_log,
) -> Dict[str, Any]:
    logs: List[str] = []

    def _log(msg: str) -> None:
        logs.append(msg)
        log(msg)

    vault_path = resolve_vault_path(vault_path)
    engine = _make_engine(agent_manager, ingestor, model_name, _log)
    result = engine.run_research_roadmap(topic, vault_path)
    return {
        "pipeline": "blueprint/roadmap",
        "topic": topic,
        "report": result.get("report", ""),
        "transcript": result.get("transcript"),
        "logs": logs,
    }


def run_synergy(
    agent_manager: AgentManager,
    ingestor: DataIngestor,
    topics: List[str],
    vault_path: Optional[str] = None,
    model_name: str = "llama3.1",
    log: LogFn = _noop_log,
) -> Dict[str, Any]:
    logs: List[str] = []

    def _log(msg: str) -> None:
        logs.append(msg)
        log(msg)

    vault_path = resolve_vault_path(vault_path)
    engine = _make_engine(agent_manager, ingestor, model_name, _log)
    result = engine.run_synergy_matrix(topics, vault_path)
    return {
        "pipeline": "blueprint/synergy",
        "topics": topics,
        "report": result.get("report", ""),
        "transcript": result.get("transcript"),
        "logs": logs,
    }


def run_explore(
    agent_manager: AgentManager,
    ingestor: DataIngestor,
    topics: List[str],
    vault_path: Optional[str] = None,
    model_name: str = "llama3.1",
    log: LogFn = _noop_log,
) -> Dict[str, Any]:
    logs: List[str] = []

    def _log(msg: str) -> None:
        logs.append(msg)
        log(msg)

    vault_path = resolve_vault_path(vault_path)
    engine = _make_engine(agent_manager, ingestor, model_name, _log)
    result = engine.run_literature_relation_exploration(topics, vault_path)
    return {
        "pipeline": "blueprint/explore",
        "topics": topics,
        "report": result.get("report", ""),
        "transcript": result.get("transcript"),
        "logs": logs,
    }


def run_organize(
    agent_manager: AgentManager,
    ingestor: DataIngestor,
    vault_path: Optional[str] = None,
    model_name: str = "llama3.1",
    log: LogFn = _noop_log,
) -> Dict[str, Any]:
    logs: List[str] = []

    def _log(msg: str) -> None:
        logs.append(msg)
        log(msg)

    vault_path = resolve_vault_path(vault_path)
    if not vault_path:
        return {
            "pipeline": "blueprint/organize",
            "report": "vault_path is required (pass argument or set MI_AI_VAULT_PATH).",
            "transcript": None,
            "logs": logs,
            "error": "missing_vault_path",
        }

    engine = _make_engine(agent_manager, ingestor, model_name, _log)
    result = engine.run_batch_organize(vault_path)
    return {
        "pipeline": "blueprint/organize",
        "vault_path": vault_path,
        "report": result.get("report", ""),
        "transcript": result.get("transcript"),
        "logs": logs,
    }


PIPELINES_CATALOG = {
    "chat_modes": [
        {
            "id": "local",
            "name": "Local RAG",
            "description": "Answer from Obsidian vault notes via vector retrieval.",
            "tool": "run_chat",
            "args": {"mode": "local"},
        },
        {
            "id": "web",
            "name": "Web Research",
            "description": "Autonomous web/academic search with contrast debate.",
            "tool": "run_chat",
            "args": {"mode": "web"},
        },
        {
            "id": "hybrid",
            "name": "Hybrid 360",
            "description": "Combine vault memory with complementary web research.",
            "tool": "run_chat",
            "args": {"mode": "hybrid"},
        },
    ],
    "agent_roles": [
        "Detective / Agente Extractor",
        "Editor / Agente Sintetizador",
        "Crítico / Abogado del Diablo",
        "Visionario / Innovador",
    ],
    "blueprints": [
        {
            "id": "roadmap",
            "tool": "run_roadmap",
            "name": "Research Roadmap",
            "description": (
                "Deep single-topic blueprint: state of the art → critical gaps → visionary ideas. "
                "Use for one research theme."
            ),
        },
        {
            "id": "synergy",
            "tool": "run_synergy",
            "name": "Synergy Matrix",
            "description": (
                "Cross-analyze multiple topics for intersections and joint opportunities. "
                "Pass 2+ topics."
            ),
        },
        {
            "id": "explore",
            "tool": "run_explore",
            "name": "Literature Relation Exploration",
            "description": (
                "Explore literary/conceptual relations across multiple concepts from research sources."
            ),
        },
        {
            "id": "organize",
            "tool": "run_organize",
            "name": "Vault Organize",
            "description": "Incremental frontmatter/organization pass over vault notes.",
        },
    ],
}


def pipelines_markdown() -> str:
    lines = [
        "# MI-AI Pipelines",
        "",
        "Call a specific tool to run that pipeline. The connected agent should choose by tool name.",
        "Reports are written into the **calling agent's project** (`project_root` / MCP roots / `MI_AI_PROJECT_ROOT` → `MI-AI Reports/`), not the MI-AI repo.",
        "",
        "## Chat (`run_chat`)",
        "",
    ]
    for m in PIPELINES_CATALOG["chat_modes"]:
        lines.append(f"- **{m['id']}**: {m['description']}")
    lines.extend(["", "## Agent roles (local chat)", ""])
    for role in PIPELINES_CATALOG["agent_roles"]:
        lines.append(f"- `{role}`")
    lines.extend(["", "## Blueprints", ""])
    for b in PIPELINES_CATALOG["blueprints"]:
        lines.append(f"- **`{b['tool']}`** ({b['name']}): {b['description']}")
    lines.append("")
    return "\n".join(lines)
