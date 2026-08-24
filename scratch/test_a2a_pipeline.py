import asyncio
import sys
import os

# Put root directory on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.a2a.protocol import A2AMessage, A2APerformative
from src.a2a.router import A2AMessageRouter
from src.a2a.orchestrator import A2APipelineOrchestrator
from fastapi.testclient import TestClient
from server import app

def test_http_a2a_endpoints():
    print("\n🌐 Testing FastAPI A2A Endpoints (TestClient)...")
    client = TestClient(app)

    # 1. Test Agent Discovery Endpoint
    res = client.get("/.well-known/agent.json")
    assert res.status_code == 200, f"Discovery endpoint failed: {res.status_code}"
    data = res.json()
    print("✅ Discovery Endpoint Manifest:")
    print(f"   Agent ID: {data['agent_id']}")
    print(f"   Registered Sub-Agents: {[a['name'] for a in data['registered_sub_agents']]}")

    # 2. Test A2A Trigger Endpoint
    trigger_payload = {
        "protocol_version": "1.0",
        "sender_id": "external-test-agent",
        "receiver_id": "capability:synthesizer",
        "performative": "REQUEST",
        "action": "synthesize_report",
        "payload": {
            "topic": "Redes de Agentes Autónomos",
            "context": "Las redes de agentes permiten la delegación de sub-tareas entre nodos especializados."
        }
    }
    res_trigger = client.post("/a2a/v1/trigger", json=trigger_payload)
    assert res_trigger.status_code == 200, f"Trigger endpoint failed: {res_trigger.status_code}"
    res_data = res_trigger.json()
    print("✅ Trigger Endpoint Response:")
    print(f"   Performative: {res_data['performative']}")
    print(f"   Sender ID: {res_data['sender_id']}")
    print(f"   Action: {res_data['action']}")

async def main():
    print("🚀 Initializing A2A Protocol Core Test...")
    router = A2AMessageRouter()
    orchestrator = A2APipelineOrchestrator(router=router)

    # 1. Verify registered agents
    agents = router.list_agents()
    print(f"✅ Registered A2A Agents: {[a.name for a in agents]}")
    assert len(agents) >= 4, "Expected at least 4 registered A2A agents"

    # 2. Test direct A2A Message Routing
    msg = A2AMessage(
        sender_id="test_client",
        receiver_id="capability:synthesizer",
        performative=A2APerformative.REQUEST,
        action="synthesize_report",
        payload={
            "topic": "Protocolo Agent-to-Agent (A2A)",
            "context": "El protocolo A2A permite la comunicación desacoplada entre agentes autónomos usando sobres de mensajes estandarizados."
        }
    )
    print(f"\n📡 Dispatching test A2AMessage [{msg.message_id}] to capability:synthesizer...")
    res = await router.send_message(msg)
    print(f"📥 Received Response Envelope: performative={res.performative}, sender={res.sender_id}")
    assert res.performative == A2APerformative.INFORM, f"Expected INFORM performative, got {res.performative}"

    # 3. Test HTTP Endpoints
    test_http_a2a_endpoints()

    print("\n🎉 ALL A2A PROTOCOL TESTS PASSED CLEANLY!")

if __name__ == "__main__":
    asyncio.run(main())
