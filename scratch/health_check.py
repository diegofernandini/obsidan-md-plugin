import asyncio
import sys
import os

# Put root directory on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import src.auto_venv


def run_health_checks():
    print("==================================================")
    print(" 🏥 RUNNING SYSTEM HEALTH CHECK")
    print("==================================================")

    # 1. Imports & Core Syntax Check
    print("\n1️⃣  Checking Core Module Imports...")
    try:
        from src.a2a.protocol import A2AMessage, A2APerformative, AgentCard
        from src.a2a.router import A2AMessageRouter
        from src.a2a.orchestrator import A2APipelineOrchestrator
        from src.a2a.agents.ollama_agent import LocalOllamaA2AAgent
        from src.pipeline_runners import PIPELINES_CATALOG
        print("   ✅ Core A2A and Pipeline modules imported successfully.")
    except Exception as e:
        print(f"   ❌ Failed to import core modules: {e}")
        sys.exit(1)

    # 2. Router & Default Agent Manifest Check
    print("\n2️⃣  Checking A2A Message Router & Default Agents...")
    try:
        router = A2AMessageRouter()
        orchestrator = A2APipelineOrchestrator(router=router)
        agents = router.list_agents()
        agent_names = [a.name for a in agents]
        print(f"   ✅ Registered Sub-Agents ({len(agents)}): {agent_names}")
        assert len(agents) >= 4, "Expected 4 default local sub-agents."
    except Exception as e:
        print(f"   ❌ Router check failed: {e}")
        sys.exit(1)

    # 3. FastAPI Endpoint Health Check
    print("\n3️⃣  Checking FastAPI Endpoints via TestClient...")
    try:
        from fastapi.testclient import TestClient
        from server import app

        client = TestClient(app)

        # GET /health
        res_health = client.get("/health")
        print(f"   GET /health -> status={res_health.status_code}, body={res_health.json()}")
        assert res_health.status_code == 200, "Health endpoint failed"

        # GET /.well-known/agent.json
        res_manifest = client.get("/.well-known/agent.json")
        print(f"   GET /.well-known/agent.json -> status={res_manifest.status_code}")
        assert res_manifest.status_code == 200, "Agent manifest discovery failed"
        manifest_data = res_manifest.json()
        assert manifest_data["agent_id"] == "mi-ai-orchestrator", "Invalid agent_id in manifest"

        # POST /a2a/v1/trigger
        trigger_msg = {
            "protocol_version": "1.0",
            "sender_id": "health-check-client",
            "receiver_id": "capability:synthesizer",
            "performative": "REQUEST",
            "action": "synthesize_report",
            "payload": {
                "topic": "System Health Check",
                "context": "Validating A2A message routing and endpoint health."
            }
        }
        res_trigger = client.post("/a2a/v1/trigger", json=trigger_msg)
        print(f"   POST /a2a/v1/trigger -> status={res_trigger.status_code}")
        assert res_trigger.status_code == 200, "A2A Trigger endpoint failed"
        res_data = res_trigger.json()
        assert res_data["performative"] == "INFORM", "Expected INFORM performative response"
        print("   ✅ All FastAPI endpoints passed validation.")
    except Exception as e:
        print(f"   ❌ FastAPI endpoint check failed: {e}")
        sys.exit(1)

    # 4. MCP Server Readiness Check
    print("\n4️⃣  Checking FastMCP Server Readiness...")
    try:
        import mcp_server
        print(f"   ✅ MCP Server module imported cleanly. Model configured: {mcp_server.MODEL_NAME}")
    except Exception as e:
        print(f"   ❌ MCP server check failed: {e}")
        sys.exit(1)

    print("\n==================================================")
    print(" 🎉 HEALTH CHECK PASSED COMPLETELY! ALL SYSTEMS OK")
    print("==================================================")

if __name__ == "__main__":
    run_health_checks()
