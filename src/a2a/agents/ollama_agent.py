import logging
from typing import Dict, Any, Optional
from src.a2a.base_agent import BaseA2AAgent
from src.a2a.protocol import A2AMessage, AgentCard, A2APerformative
from src.agent_manager import AgentManager

logger = logging.getLogger("a2a-ollama-agent")

class LocalOllamaA2AAgent(BaseA2AAgent):
    """
    Concrete A2A Agent backed by local Ollama LLM execution via AgentManager.
    Exposes specialized capabilities (synthesizer, critical_analyst, visionary, detective).
    """
    def __init__(self, card: AgentCard, agent_manager: Optional[AgentManager] = None, model_name: str = "llama3.2:1b"):
        super().__init__(card)
        self.agent_manager = agent_manager or AgentManager(model_name=model_name)

    async def process_message(self, message: A2AMessage) -> A2AMessage:
        if message.performative != A2APerformative.REQUEST:
            return self.create_reply(
                request=message,
                performative=A2APerformative.FAILURE,
                payload={"error": f"Unsupported performative '{message.performative}'. Expected 'REQUEST'."}
            )

        action = message.action
        payload = message.payload
        topic = payload.get("topic", "")
        context = payload.get("context", "")
        task_text = payload.get("task", "")

        logger.info(f"Agent [{self.card.agent_id}] processing action '{action}' for topic '{topic}'")

        try:
            if action == "synthesize_report":
                result = self.agent_manager.synthesize_report(context, topic)
            elif action == "critical_gap_analysis":
                result = self.agent_manager.perform_critical_gap_analysis(context, topic)
            elif action == "propose_vision":
                gaps = payload.get("gaps", "")
                result = self.agent_manager.propose_visionary_ideas(context, gaps, topic)
            elif action == "extract_information":
                result = self.agent_manager.extract_information(context, topic)
            elif action == "conduct_contrast_analysis":
                content_optimist = payload.get("content_optimista", context)
                content_critical = payload.get("content_escetico", context)
                res_dict = self.agent_manager.conduct_contrast_analysis(content_optimist, content_critical, topic)
                return self.create_reply(
                    request=message,
                    performative=A2APerformative.INFORM,
                    payload={"report": res_dict["report"], "transcript": res_dict["transcript"]}
                )
            else:
                # Default role-based task execution
                system_prompt = payload.get("system_prompt", self.card.description)
                result = self.agent_manager._run_agent_task(self.card.role, system_prompt, context, task_text or topic)

            return self.create_reply(
                request=message,
                performative=A2APerformative.INFORM,
                payload={"result": result, "report": result}
            )
        except Exception as e:
            logger.error(f"Error in A2A Agent [{self.card.agent_id}]: {e}", exc_info=True)
            return self.create_reply(
                request=message,
                performative=A2APerformative.FAILURE,
                payload={"error": str(e)}
            )
