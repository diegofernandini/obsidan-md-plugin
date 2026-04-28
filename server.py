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
from src.blueprint_engine import BlueprintEngine

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

async def save_to_vault(vault_path: str, title: str, content: str):
    """Guarda un reporte en el vault de Obsidian."""
    if not vault_path: return
    
    reports_dir = os.path.join(vault_path, "MI-AI Reports")
    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir)
        
    filename = f"{title}_{asyncio.get_event_loop().time()}.md".replace(" ", "_")
    file_path = os.path.join(reports_dir, filename)
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Reporte guardado en: {file_path}")

class ChatRequest(BaseModel):
    message: str
    vault_path: Optional[str] = None
    active_note_content: Optional[str] = None
    agent_role: Optional[str] = "Detective / Agente Extractor"
    mode: Optional[str] = "local" # local, web, hybrid, blueprint

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

class SharePointRequest(BaseModel):
    site_url: str
    client_id: str
    client_secret: str
    folder_url: str

@app.post("/sync-sharepoint")
async def sync_sharepoint(request: SharePointRequest):
    from src.sharepoint_connector import SharePointConnector
    
    # 1. Conectar y descargar
    connector = SharePointConnector(
        site_url=request.site_url,
        client_id=request.client_id,
        client_secret=request.client_secret
    )
    
    # Usamos una carpeta temporal dentro del proyecto
    temp_dir = os.path.join("data_sources", "sharepoint_sync")
    try:
        downloaded_files = connector.download_folder_files(request.folder_url, temp_dir)
        if not downloaded_files:
            return {"status": "warning", "message": "No se encontraron archivos compatibles en la carpeta de SharePoint."}

        # 2. Indexar
        texts = ingestor.load_local_data(temp_dir)
        index_path = ingestor.index_data(texts, "SHAREPOINT", "sharepoint_index")
        
        return {
            "status": "success", 
            "files_synced": len(downloaded_files),
            "index_path": index_path
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def chat(chat_request: ChatRequest, request: Request):
    async def event_generator():
        loop = asyncio.get_running_loop()
        
        # Función auxiliar para asegurar que el vault esté indexado
        async def ensure_vault_indexed():
            if chat_request.vault_path and ingestor.vectorstore is None:
                yield {"data": "LOG: Construyendo Segunda Memoria (Indexando Vault por primera vez). Esto tomará un momento..."}
                try:
                    texts = await loop.run_in_executor(None, ingestor.load_local_data, chat_request.vault_path)
                    if texts:
                        await loop.run_in_executor(None, ingestor.index_data, texts, "VAULT", "vault_index")
                        yield {"data": "LOG: Vault indexado correctamente."}
                    else:
                        yield {"data": "LOG: No se encontraron documentos válidos en el Vault."}
                except Exception as e:
                    print(f"Error indexando vault: {e}")
                    yield {"data": f"LOG: Error al indexar el Vault: {e}"}

        # 1. MODO LOCAL (RAG Vault)
        if chat_request.mode == "local":
            context = ""
            if chat_request.vault_path:
                try:
                    async for msg in ensure_vault_indexed():
                        yield msg
                    if ingestor.vectorstore is not None:
                        retriever = ingestor.get_retriever()
                        docs = await loop.run_in_executor(None, retriever.invoke, chat_request.message)
                        context_blocks = []
                        for d in docs:
                            source_file = d.metadata.get('source', 'Nota Local Desconocida')
                            # Limpiar path, nos quedamos con el nombre del archivo
                            basename = str(source_file).split('/')[-1]
                            if basename.endswith('.md'): basename = basename[:-3]
                            context_blocks.append(f"--- ARCHIVO ORIGEN: {basename} ---\n{d.page_content}")
                        context = "\n\n".join(context_blocks)
                except Exception as e:
                    print(f"Error recuperando contexto: {e}")
            
            if chat_request.active_note_content:
                context += f"\n\n--- NOTA ACTIVA (Para Contexto/Edición) ---\n{chat_request.active_note_content}"

            system_prompt = "Eres un asistente de inteligencia de mercado."
            if "Detective" in chat_request.agent_role:
                 system_prompt = "Tu enfoque es forense. No interpretas; extraes."
            elif "Editor" in chat_request.agent_role:
                 system_prompt = "Tu función es dar cohesión y narrativa."

            yield {"data": "LOG: Analizando el conexto local..."}
            async for chunk in agent_manager.stream_agent_task(chat_request.agent_role, system_prompt, context, chat_request.message):

                if await request.is_disconnected(): break
                yield {"data": chunk}

        # 2. MODO WEB (Investigador Autónomo)
        elif chat_request.mode == "web":
            yield {"data": "LOG: Generando estrategia de búsqueda global..."}
            queries = agent_manager.generate_search_queries(chat_request.message)
            
            yield {"data": "LOG: Consultando fuentes académicas y generales..."}
            search_results = await loop.run_in_executor(None, ingestor.get_combined_research, queries)
            
            yield {"data": "LOG: Seleccionando las fuentes más relevantes..."}
            selected_sources = agent_manager.select_best_sources(search_results, chat_request.message)
            
            if not selected_sources:
                yield {"data": "RESULT: El investigador no encontró fuentes suficientemente relevantes para este tema."}
                return

            research_contents = []
            for i, source in enumerate(selected_sources):
                yield {"data": f"LOG: Analizando contenido de {source['title']}..."}
                content = await loop.run_in_executor(None, ingestor.scrape_url, source['url'])
                research_contents.append(content)

            yield {"data": "LOG: Iniciando debate de contraste..." if len(research_contents) >= 2 else "LOG: Sintetizando hallazgos..."}
            
            if len(research_contents) >= 2:
                report = await loop.run_in_executor(None, agent_manager.conduct_contrast_analysis, research_contents[0], research_contents[1], chat_request.message)
            else:
                report = await loop.run_in_executor(None, agent_manager.synthesize_report, research_contents[0], chat_request.message)
            
            yield {"data": f"RESULT: {report}"}

        # 3. MODO HÍBRIDO (Vault + Web)
        elif chat_request.mode == "hybrid":
            yield {"data": "LOG: Validando memoria local (Vault)..."}
            local_context = ""
            try:
                async for msg in ensure_vault_indexed():
                    yield msg
                if ingestor.vectorstore is not None:
                    retriever = ingestor.get_retriever()
                    local_docs = await loop.run_in_executor(None, retriever.invoke, chat_request.message)
                    context_blocks = []
                    for d in local_docs:
                        source_file = d.metadata.get('source', 'Nota Local Desconocida')
                        basename = str(source_file).split('/')[-1]
                        if basename.endswith('.md'): basename = basename[:-3]
                        context_blocks.append(f"--- ARCHIVO ORIGEN: {basename} ---\n{d.page_content}")
                    local_context = "\n\n".join(context_blocks)
            except Exception as e:
                print(f"Error recuperando contexto híbrido: {e}")

            yield {"data": "LOG: Lanzando investigación web complementaria..."}
            queries = agent_manager.generate_search_queries(chat_request.message)
            search_results = await loop.run_in_executor(None, ingestor.get_combined_research, queries)
            selected_web = agent_manager.select_best_sources(search_results, chat_request.message)
            
            web_contents = []
            for source in selected_web:
                yield {"data": f"LOG: Cruzando información con {source['title']}..."}
                web_contents.append(await loop.run_in_executor(None, ingestor.scrape_url, source['url']))

            yield {"data": "LOG: Agente Híbrido resolviendo conflictos y sintetizando..."}
            report = await loop.run_in_executor(None, agent_manager.conduct_hybrid_analysis, local_context, web_contents, "I", chat_request.message)
            
            # Post-procesamiento estricto: Eliminar alucinaciones del formato por defecto de Llama
            report = report.replace("[Fuente interna]", "")
            report = report.replace("[Fuente externa]", "")
            report = report.replace("[Fuente Externa]", "")
            report = report.replace("[Fuente Interna]", "")

            yield {"data": f"RESULT: {report}"}

    return EventSourceResponse(event_generator())

@app.post("/blueprint/roadmap")
async def blueprint_roadmap(request: ChatRequest, fastapi_request: Request):
    async def event_generator():
        # Cola para recibir logs de forma asíncrona
        queue = asyncio.Queue()
        loop = asyncio.get_running_loop() # Capturamos el loop actual

        def log_to_queue(msg):
            # Usamos el loop capturado para enviar el mensaje a la cola de forma segura
            loop.call_soon_threadsafe(queue.put_nowait, msg)

        engine = BlueprintEngine(model_name=MODEL_NAME, log_callback=log_to_queue)

        # Ejecutar blueprint en un hilo separado
        executor_task = loop.run_in_executor(None, engine.run_research_roadmap, request.message)

        while not executor_task.done() or not queue.empty():
            try:
                # Esperar logs o finalizar
                msg = await asyncio.wait_for(queue.get(), timeout=1.0)
                yield {"data": f"LOG: {msg}"}
            except asyncio.TimeoutError:
                if await fastapi_request.is_disconnected():
                    break
                continue

        result = await executor_task
        yield {"data": f"RESULT: {result['report']}"}
        yield {"data": f"TRANSCRIPT: {result['transcript']}"}
        await save_to_vault(request.vault_path, f"ROADMAP_{request.message[:20]}", result['report'])

    return EventSourceResponse(event_generator())

@app.post("/blueprint/synergy")
async def blueprint_synergy(request: Request):
    data = await request.json()
    topics = data.get("topics", [])
    
    async def event_generator():
        queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def log_to_queue(msg):
            loop.call_soon_threadsafe(queue.put_nowait, msg)

        engine = BlueprintEngine(model_name=MODEL_NAME, log_callback=log_to_queue)
        
        executor_task = loop.run_in_executor(None, engine.run_synergy_matrix, topics)

        while not executor_task.done() or not queue.empty():
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=1.0)
                yield {"data": f"LOG: {msg}"}
            except asyncio.TimeoutError:
                if await request.is_disconnected():
                    break
                continue
        
        result = await executor_task
        yield {"data": f"RESULT: {result['report']}"}
@app.post("/blueprint/organize")
async def blueprint_organize(request: ChatRequest, fastapi_request: Request):
    async def event_generator():
        queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def log_to_queue(msg):
            loop.call_soon_threadsafe(queue.put_nowait, msg)

        engine = BlueprintEngine(model_name=MODEL_NAME, log_callback=log_to_queue)

        # Ejecutar blueprint en un hilo separado con solo vault_path (modo incremental)
        executor_task = loop.run_in_executor(None, engine.run_batch_organize, request.vault_path)

        while not executor_task.done() or not queue.empty():
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=0.1)
                yield {"data": msg}
            except asyncio.TimeoutError:
                continue

        result = executor_task.result()
        yield {"data": f"RESULT: {result['report']}"}

    return EventSourceResponse(event_generator())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
