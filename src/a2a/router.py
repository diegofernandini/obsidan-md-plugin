import logging
from typing import Dict, List, Optional
from src.a2a.base_agent import BaseA2AAgent
from src.a2a.protocol import A2AMessage, AgentCard, A2APerformative

logger = logging.getLogger("a2a-router")

class A2AMessageRouter:
    """
    Message Router and Capability Bus for the A2A Protocol.
    Handles agent registration, capability-based resolution (e.g. 'capability:critical_analyst'),
    and message dispatching.
    """
    def __init__(self):
        self._registry: Dict[str, BaseA2AAgent] = {}
        self._capability_map: Dict[str, List[str]] = {}

    def register_agent(self, agent: BaseA2AAgent) -> None:
        agent_id = agent.card.agent_id
        self._registry[agent_id] = agent
        
        for cap in agent.card.capabilities:
            if cap not in self._capability_map:
                self._capability_map[cap] = []
            if agent_id not in self._capability_map[cap]:
                self._capability_map[cap].append(agent_id)
                
        logger.info(f"Registered A2A Agent [{agent_id}] with capabilities: {agent.card.capabilities}")

    def list_agents(self) -> List[AgentCard]:
        return [agent.card for agent in self._registry.values()]

    def get_agent_by_id(self, agent_id: str) -> Optional[BaseA2AAgent]:
        return self._registry.get(agent_id)

    async def send_message(self, message: A2AMessage) -> A2AMessage:
        """
        Dispatches an A2AMessage envelope to the target receiver_id or capability route.
        """
        target_id = message.receiver_id
        
        # Capability-based routing if receiver_id is prefixed with "capability:"
        if target_id.startswith("capability:"):
            cap_name = target_id.split("capability:", 1)[1]
            candidates = self._capability_map.get(cap_name, [])
            if not candidates:
                err_msg = f"No registered A2A Agent satisfies capability '{cap_name}'"
                logger.error(err_msg)
                return A2AMessage(
                    session_id=message.session_id,
                    sender_id="a2a-router",
                    receiver_id=message.sender_id,
                    performative=A2APerformative.FAILURE,
                    action=f"{message.action}_failed",
                    payload={"error": err_msg}
                )
            target_id = candidates[0]  # First available agent for capability

        agent = self._registry.get(target_id)
        if not agent:
            err_msg = f"Target A2A Agent '{target_id}' not found in router registry."
            logger.error(err_msg)
            return A2AMessage(
                session_id=message.session_id,
                sender_id="a2a-router",
                receiver_id=message.sender_id,
                performative=A2APerformative.FAILURE,
                action=f"{message.action}_failed",
                payload={"error": err_msg}
            )

        logger.info(f"Routing A2AMessage [{message.message_id}] from '{message.sender_id}' to '{target_id}' (action={message.action})")
        return await agent.process_message(message)
