from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from src.a2a.protocol import A2AMessage, AgentCard, A2APerformative

class BaseA2AAgent(ABC):
    """
    Abstract base class for all A2A Protocol Agents.
    Whether running locally (Ollama), via REST API, or over MCP, all agents
    must implement the `process_message` envelope handler.
    """
    def __init__(self, card: AgentCard):
        self.card = card

    @abstractmethod
    async def process_message(self, message: A2AMessage) -> A2AMessage:
        """
        Process an incoming A2AMessage envelope and return an A2AMessage response envelope.
        """
        pass

    def create_reply(
        self, 
        request: A2AMessage, 
        performative: A2APerformative, 
        payload: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> A2AMessage:
        """
        Helper utility to build a valid A2AMessage reply correlated to an incoming request.
        """
        reply_metadata = {"reply_to": request.message_id}
        if metadata:
            reply_metadata.update(metadata)

        return A2AMessage(
            session_id=request.session_id,
            sender_id=self.card.agent_id,
            receiver_id=request.sender_id,
            performative=performative,
            action=f"{request.action}_response",
            payload=payload,
            metadata=reply_metadata
        )
