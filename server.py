import os
import json
import asyncio
from typing import List, Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from src.data_ingestor import DataIngestor
from src.agent_manager import AgentManager

app = FastAPI(title="MI-AI Brain Server")

# Configuración de CORS para Obsidian
app.add_middleware(
    CORSMiddleware,
    allow_origins=["app://obsidian.md", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicialización de componentes
# Se usa llama3.1 por defecto como en el PoC
MODEL_NAME = "llama3.1"
ingestor = DataIngestor()
agent_manager = AgentManager(model_name=MODEL_NAME)

class ChatRequest(BaseModel):
    message: str
    vault_path: Optional[str] = None
    active_note_content: Optional[str] = None
    agent_role: Optional[str] = "Detective / Agente Extractor"

@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL_NAME}

@app.post("/index-vault")
async def index_vault(request: Request):
    data = await request.json()
    path = data.get("path")
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=400, detail="Invalid vault path")
    
    print(f"Indexando vault en: {path}")
    texts = ingestor.load_local_data(path)
    if not texts:
        return {"status": "warning", "message": "No se encontraron archivos indexables."}
    
    index_path = ingestor.index_data(texts, "VAULT", "vault_index")
    return {"status": "success", "index_path": index_path, "count": len(texts)}

@app.post("/chat")
async def chat(request: ChatRequest):
    async def event_generator():
        # 1. Recuperar contexto si hay un índice
        context = ""
        if request.vault_path:
            try:
                # Si no está cargado el retriever, intentamos obtenerlo
                retriever = ingestor.get_retriever()
                docs = retriever.invoke(request.message)
                context = "\n".join([d.page_content for d in docs])
            except Exception as e:
                print(f"Error recuperando contexto: {e}")
        
        # Agregar contenido de la nota activa si se provee
        if request.active_note_content:
            context += f"\n\n--- NOTA ACTIVA ---\n{request.active_note_content}"

        # 2. Definir sistema y tarea basado en el rol (simplificado para el chat)
        system_prompt = "Eres un asistente de inteligencia de mercado. Ayuda al usuario a navegar su conocimiento."
        if "Detective" in request.agent_role:
             system_prompt = "Tu enfoque es forense. No interpretas; extraes."
        elif "Editor" in request.agent_role:
             system_prompt = "Tu función es dar cohesión y narrativa."

        # 3. Streaming
        async for chunk in agent_manager.stream_agent_task(
            role=request.agent_role,
            system_prompt=system_prompt,
            context=context,
            task=request.message
        ):
            if await request.is_disconnected():
                break
            yield {"data": chunk}

    return EventSourceResponse(event_generator())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
