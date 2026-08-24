from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import uuid

class A2APerformative(str, Enum):
    REQUEST = "REQUEST"           # Solicit execution of a task or subtask
    INFORM = "INFORM"             # Deliver final data, report, or status
    PROPOSE = "PROPOSE"           # Offer hypothesis or vision proposal
    REFUTE = "REFUTE"             # Critique / counter-argument / gap detection
    STREAM_CHUNK = "STREAM_CHUNK" # Real-time streaming log/token payload
    FAILURE = "FAILURE"           # Execution error notification

class AgentCard(BaseModel):
    agent_id: str
    name: str
    role: str
    description: str
    capabilities: List[str] = Field(default_factory=list)
    transport_type: str = "in_process" # "in_process", "http_rest", "mcp", "websocket"
    endpoint_url: Optional[str] = None

class A2AMessage(BaseModel):
    protocol_version: str = "1.0"
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sender_id: str
    receiver_id: str              # Target agent_id or capability route (e.g. "capability:synthesizer")
    performative: A2APerformative
    action: str                   # e.g., "synthesize_report", "gap_analysis", "run_roadmap"
    payload: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
