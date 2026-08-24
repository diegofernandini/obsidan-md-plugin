import uuid
import logging
from typing import Dict, Any, List, Optional
from src.a2a.router import A2AMessageRouter
from src.a2a.protocol import A2AMessage, AgentCard, A2APerformative
from src.a2a.agents.ollama_agent import LocalOllamaA2AAgent
from src.agent_manager import AgentManager

logger = logging.getLogger("a2a-orchestrator")

class A2APipelineOrchestrator:
    """
    Orchestrates multi-agent pipelines (Roadmap, Synergy, Chat) by sending A2A Protocol messages
    across the A2AMessageRouter to registered agents (local or remote).
    """
    def __init__(self, router: Optional[A2AMessageRouter] = None, agent_manager: Optional[AgentManager] = None):
        self.router = router or A2AMessageRouter()
        self.agent_manager = agent_manager or AgentManager()
        self._ensure_default_agents()

    def _ensure_default_agents(self):
        """Registers default local Ollama A2A agents for key capabilities if not present."""
        if not self.router.list_agents():
            # 1. Synthesizer Agent
            synth_card = AgentCard(
                agent_id="agent-synthesizer-local",
                name="Editor Jefe / Sintetizador",
                role="Editor Jefe / Agente Sintetizador",
                description="Toma la información fragmentada y la transforma en un informe ejecutivo fluido.",
                capabilities=["synthesizer", "synthesize_report"]
            )
            self.router.register_agent(LocalOllamaA2AAgent(synth_card, agent_manager=self.agent_manager))

            # 2. Critical Analyst Agent
            critical_card = AgentCard(
                agent_id="agent-critical-local",
                name="Crítico Académico / Abogado del Diablo",
                role="Analista de Brechas y Crítico Académico",
                description="Detecta vacíos, contradicciones y áreas no exploradas.",
                capabilities=["critical_analyst", "critical_gap_analysis"]
            )
            self.router.register_agent(LocalOllamaA2AAgent(critical_card, agent_manager=self.agent_manager))

            # 3. Visionary Agent
            visionary_card = AgentCard(
                agent_id="agent-visionary-local",
                name="Visionario / Arquitecto de Innovación",
                role="Visionario / Arquitecto de Innovación",
                description="Propone hipótesis disruptivas y conexiones inesperadas.",
                capabilities=["visionary", "propose_vision"]
            )
            self.router.register_agent(LocalOllamaA2AAgent(visionary_card, agent_manager=self.agent_manager))

            # 4. Detective / Extractor Agent
            detective_card = AgentCard(
                agent_id="agent-detective-local",
                name="Detective / Extractor de Patrones",
                role="Detective / Agente Extractor de Patrones",
                description="Extrae cifras, datos clave y relaciones cause-efecto de contextos.",
                capabilities=["detective", "extract_information"]
            )
            self.router.register_agent(LocalOllamaA2AAgent(detective_card, agent_manager=self.agent_manager))

    async def run_roadmap_pipeline(self, topic: str, combined_context: str, selected_web: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes the Research Roadmap Blueprint using A2A protocol message exchanges.
        Step 1: State of Art (Synthesizer)
        Step 2: Critical Gaps (Critical Analyst)
        Step 3: Visionary Ideas (Visionary)
        """
        session_id = str(uuid.uuid4())
        logger.info(f"Starting A2A Research Roadmap Pipeline for '{topic}' (session={session_id})")

        # Step 1: Synthesizer Agent
        synth_msg = A2AMessage(
            session_id=session_id,
            sender_id="orchestrator",
            receiver_id="capability:synthesizer",
            performative=A2APerformative.REQUEST,
            action="synthesize_report",
            payload={"topic": topic, "context": combined_context}
        )
        synth_res = await self.router.send_message(synth_msg)
        if synth_res.performative == A2APerformative.FAILURE:
            raise RuntimeError(f"A2A Roadmap Step 1 Failed: {synth_res.payload.get('error')}")
        state_of_the_art = synth_res.payload.get("result", "")

        # Step 2: Critical Analyst Agent
        gap_msg = A2AMessage(
            session_id=session_id,
            sender_id="orchestrator",
            receiver_id="capability:critical_analyst",
            performative=A2APerformative.REQUEST,
            action="critical_gap_analysis",
            payload={"topic": topic, "context": combined_context}
        )
        gap_res = await self.router.send_message(gap_msg)
        if gap_res.performative == A2APerformative.FAILURE:
            raise RuntimeError(f"A2A Roadmap Step 2 Failed: {gap_res.payload.get('error')}")
        gaps = gap_res.payload.get("result", "")

        # Step 3: Visionary Agent
        vision_msg = A2AMessage(
            session_id=session_id,
            sender_id="orchestrator",
            receiver_id="capability:visionary",
            performative=A2APerformative.REQUEST,
            action="propose_vision",
            payload={"topic": topic, "context": combined_context, "gaps": gaps}
        )
        vision_res = await self.router.send_message(vision_msg)
        if vision_res.performative == A2APerformative.FAILURE:
            raise RuntimeError(f"A2A Roadmap Step 3 Failed: {vision_res.payload.get('error')}")
        vision = vision_res.payload.get("result", "")

        # Format final aggregated Markdown report
        bib_sources = selected_web or []
        bib_lines = [f"- [{s.get('title', 'Fuente Web')}]({s['url']})" for s in bib_sources if 'url' in s]
        bib_text = "\n".join(bib_lines) if bib_lines else "- No se requirió bibliografía externa."

        full_report = f"""# ROADMAP DE INVESTIGACIÓN: {topic.upper()}

## 1. ESTADO DEL ARTE Y SÍNTESIS GLOBAL
{state_of_the_art}

## 2. ANÁLISIS CRÍTICO Y BRECHAS DETECTADAS
{gaps}

## 3. LÍNEAS DE INVESTIGACIÓN Y PROPUESTAS VISIONARIAS
{vision}

## 4. BIBLIOGRAFÍA Y FUENTES
{bib_text}

---
*Este reporte fue generado por MI-AI Intelligence usando una orquestación de agentes A2A Protocol.*
"""
        return {
            "session_id": session_id,
            "topic": topic,
            "report": full_report,
            "state_of_the_art": state_of_the_art,
            "gaps": gaps,
            "vision": vision
        }
