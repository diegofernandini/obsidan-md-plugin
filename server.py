import os
import sys
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
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
# Se usa llama3.2:1b por defecto como en el PoC
MODEL_NAME = "llama3.2:1b"
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

import logging
import traceback

# Configurar log de emergencia
logging.basicConfig(
    filename="MIAI_DEBUG.log",
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logging.info("--- SERVIDOR MI-AI INICIADO ---")

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
        try:
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
                                source_file = d.metadata.get("source", "Nota Local Desconocida")
                                # Limpiar path, nos quedamos con el nombre del archivo
                                basename = str(source_file).split("/")[-1]
                                if basename.endswith(".md"):
                                    basename = basename[:-3]
                                context_blocks.append(f"--- ARCHIVO ORIGEN: {basename} ---\n{d.page_content}")
                            context = "\n\n".join(context_blocks)
                    except Exception as e:
                        print(f"Error recuperando contexto: {e}")

                if chat_request.active_note_content:
                    context += f"\n\n--- NOTA ACTIVA (Para Contexto/Edición) ---\n{chat_request.active_note_content}"

                system_prompt = "Eres un asistente de inteligencia de mercado experto. SIEMPRE debes citar tus fuentes usando el formato [[Nombre de la Nota]] para archivos locales y [Título](URL) para enlaces web. Al final de tu respuesta, incluye siempre una sección de '## Bibliografía'."
                if "Detective" in chat_request.agent_role:
                    system_prompt = "Tu enfoque es forense. No interpretas; extraes datos puros y citas SIEMPRE el origen usando [[Wikilinks]]. Incluye bibliografía final."
                elif "Editor" in chat_request.agent_role:
                    system_prompt = "Tu función es dar cohesión y narrativa. Estructuras reportes profesionales e incluyes SIEMPRE una sección de '## Bibliografía' al final detallando las fuentes."

                yield {"data": "LOG: Analizando el contexto local..."}
                async for chunk in agent_manager.stream_agent_task(chat_request.agent_role, system_prompt, context, chat_request.message):
                    if await request.is_disconnected():
                        break
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
                    content = await loop.run_in_executor(None, ingestor.scrape_url, source["url"])
                    research_contents.append(content)

                yield {"data": "LOG: Iniciando debate de contraste..." if len(research_contents) >= 2 else "LOG: Sintetizando hallazgos..."}
                if len(research_contents) >= 2:
                    report = await loop.run_in_executor(None, agent_manager.conduct_contrast_analysis, research_contents[0], research_contents[1], chat_request.message)
                else:
                    report = await loop.run_in_executor(None, agent_manager.synthesize_report, research_contents[0], chat_request.message)

                bibliography = "\n\n## Bibliografía\n" + "\n".join([f"- [{s.get('title', 'Fuente Web')}]({s['url']})" for s in selected_sources])
                yield {"data": f"RESULT: {report}{bibliography}"}

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
                            source_file = d.metadata.get("source", "Nota Local Desconocida")
                            basename = str(source_file).split("/")[-1]
                            if basename.endswith(".md"):
                                basename = basename[:-3]
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
                    web_contents.append(await loop.run_in_executor(None, ingestor.scrape_url, source["url"]))

                yield {"data": "LOG: Agente Híbrido resolviendo conflictos y sintetizando..."}
                report = await loop.run_in_executor(None, agent_manager.conduct_hybrid_analysis, local_context, web_contents, "I", chat_request.message)

                # Post-procesamiento estricto: Eliminar alucinaciones del formato por defecto de Llama
                report = report.replace("[Fuente interna]", "")
                report = report.replace("[Fuente externa]", "")
                report = report.replace("[Fuente Externa]", "")
                report = report.replace("[Fuente Interna]", "")

                bibliography = "\n\n## Bibliografía\n" + "\n".join([f"- [{s.get('title', 'Fuente Web')}]({s['url']})" for s in selected_web])
                yield {"data": f"RESULT: {report}{bibliography}"}
            else:
                yield {"data": "RESULT: Modo de chat no soportado. Usa local, web o hybrid."}
        except Exception as e:
            error_trace = traceback.format_exc()
            logging.error(f"ERROR EN CHAT ({chat_request.mode}): {str(e)}\n{error_trace}")
            yield {"data": f"LOG: ❌ Error crítico en chat (Ver log): {str(e)}"}
            yield {"data": f"RESULT: Ocurrió un error. Consulta MIAI_DEBUG.log para más detalles."}

    return EventSourceResponse(event_generator())

@app.post("/blueprint/roadmap")
async def blueprint_roadmap(request: ChatRequest, fastapi_request: Request):
    async def event_generator():
        queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def log_to_queue(msg):
            loop.call_soon_threadsafe(queue.put_nowait, msg)

        # Send first event immediately to keep connection alive
        yield {"data": "LOG: 🧠 Motor MI-AI Sincronizado. Iniciando Roadmap..."}
        await asyncio.sleep(0)  # flush to client

        try:
            engine = BlueprintEngine(model_name=MODEL_NAME, log_callback=log_to_queue, agent_manager=agent_manager, ingestor=ingestor)

            vault_path = request.vault_path
            executor_task = loop.run_in_executor(None, engine.run_research_roadmap, request.message, vault_path)

            last_heartbeat = loop.time()
            disconnected = False
            while True:
                # Drain all pending log messages before checking if done
                while not queue.empty():
                    msg = queue.get_nowait()
                    yield {"data": f"LOG: {msg}"}
                    last_heartbeat = loop.time()

                if executor_task.done():
                    break

                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=2.0)
                    yield {"data": f"LOG: {msg}"}
                    last_heartbeat = loop.time()
                except asyncio.TimeoutError:
                    if loop.time() - last_heartbeat > 10:
                        yield {"comment": "ping"}
                        last_heartbeat = loop.time()

                    if await fastapi_request.is_disconnected():
                        logging.warning("Cliente desconectado durante Roadmap.")
                        executor_task.cancel()
                        disconnected = True
                        break
            if disconnected:
                return
            result = await executor_task
            yield {"data": f"RESULT: {result['report']}"}
            yield {"data": f"TRANSCRIPT: {result['transcript']}"}
            await save_to_vault(request.vault_path, f"ROADMAP_{request.message[:20]}", result['report'])
        except BrokenPipeError:
            logging.warning("Broken pipe: cliente desconectado durante Roadmap.")
            return
        except Exception as e:
            error_trace = traceback.format_exc()
            logging.error(f"ERROR EN ROADMAP: {str(e)}\n{error_trace}")
            yield {"data": f"LOG: ❌ Error crítico (Ver log): {str(e)}"}
            yield {"data": f"RESULT: Lo siento, ocurrió un error en el Roadmap. Detalles: {str(e)}"}

    return EventSourceResponse(event_generator())

@app.post("/blueprint/synergy")
async def blueprint_synergy(request: Request):
    data = await request.json()
    topics = data.get("topics", [])
    vault_path = data.get("vault_path")

    async def event_generator():
        queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def log_to_queue(msg):
            loop.call_soon_threadsafe(queue.put_nowait, msg)

        # Send first event immediately to keep connection alive
        yield {"data": "LOG: 🧠 Motor MI-AI Sincronizado. Iniciando análisis..."}
        await asyncio.sleep(0)

        try:
            engine = BlueprintEngine(model_name=MODEL_NAME, log_callback=log_to_queue, agent_manager=agent_manager, ingestor=ingestor)

            executor_task = loop.run_in_executor(None, engine.run_synergy_matrix, topics, vault_path)

            last_heartbeat = loop.time()
            disconnected = False
            while True:
                # Drain all pending log messages before checking if done
                while not queue.empty():
                    msg = queue.get_nowait()
                    yield {"data": f"LOG: {msg}"}
                    last_heartbeat = loop.time()

                if executor_task.done():
                    break

                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield {"data": f"LOG: {msg}"}
                    last_heartbeat = loop.time()
                except asyncio.TimeoutError:
                    if loop.time() - last_heartbeat > 10:
                        yield {"comment": "ping"}
                        last_heartbeat = loop.time()

                    if await request.is_disconnected():
                        logging.warning("Cliente desconectado durante Sinergia.")
                        executor_task.cancel()
                        disconnected = True
                        break
            if disconnected:
                return
            result = await executor_task
            yield {"data": f"RESULT: {result['report']}"}
        except BrokenPipeError:
            logging.warning("Broken pipe: cliente desconectado durante Sinergia.")
            return
        except Exception as e:
            error_trace = traceback.format_exc()
            logging.error(f"ERROR EN SINERGIA: {str(e)}\n{error_trace}")
            yield {"data": f"LOG: ❌ Error crítico (Ver log): {str(e)}"}
            yield {"data": f"RESULT: Lo siento, ocurrió un error al procesar la sinergia. Detalles: {str(e)}"}

    return EventSourceResponse(event_generator())

@app.post("/blueprint/explore")
async def blueprint_explore(request: Request):
    data = await request.json()
    topics = data.get("topics", [])
    vault_path = data.get("vault_path")

    async def event_generator():
        queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def log_to_queue(msg):
            loop.call_soon_threadsafe(queue.put_nowait, msg)

        yield {"data": "LOG: 🧠 Motor MI-AI Sincronizado. Exploración literaria multi-concepto..."}
        await asyncio.sleep(0)

        try:
            engine = BlueprintEngine(
                model_name=MODEL_NAME,
                log_callback=log_to_queue,
                agent_manager=agent_manager,
                ingestor=ingestor,
            )

            executor_task = loop.run_in_executor(
                None, engine.run_literature_relation_exploration, topics, vault_path
            )

            last_heartbeat = loop.time()
            disconnected = False
            while True:
                while not queue.empty():
                    msg = queue.get_nowait()
                    yield {"data": f"LOG: {msg}"}
                    last_heartbeat = loop.time()

                if executor_task.done():
                    break

                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield {"data": f"LOG: {msg}"}
                    last_heartbeat = loop.time()
                except asyncio.TimeoutError:
                    if loop.time() - last_heartbeat > 10:
                        yield {"comment": "ping"}
                        last_heartbeat = loop.time()

                    if await request.is_disconnected():
                        logging.warning("Cliente desconectado durante Explore.")
                        executor_task.cancel()
                        disconnected = True
                        break
            if disconnected:
                return
            result = await executor_task
            yield {"data": f"RESULT: {result['report']}"}
            yield {"data": f"TRANSCRIPT: {result['transcript']}"}
            slug = "_".join(
                (str(t) or "").replace(" ", "_")[:14] for t in (topics or [])[:3]
            )[:48] or "concepts"
            await save_to_vault(vault_path, f"EXPLORE_{slug}", result["report"])
        except BrokenPipeError:
            logging.warning("Broken pipe: cliente desconectado durante Explore.")
            return
        except Exception as e:
            error_trace = traceback.format_exc()
            logging.error(f"ERROR EN EXPLORE: {str(e)}\n{error_trace}")
            yield {"data": f"LOG: ❌ Error crítico (Ver log): {str(e)}"}
            yield {
                "data": f"RESULT: Lo siento, ocurrió un error en la exploración literaria. Detalles: {str(e)}"
            }

    return EventSourceResponse(event_generator())

@app.post("/blueprint/ask")
async def blueprint_ask(request: Request):
    data = await request.json()
    message = data.get("message", "")
    vault_path = data.get("vault_path")
    target_path = data.get("target_path")

    async def event_generator():
        queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def log_to_queue(msg):
            loop.call_soon_threadsafe(queue.put_nowait, msg)

        yield {"data": "LOG: 🧠 Motor MI-AI Sincronizado. Iniciando Deep Ask..."}
        await asyncio.sleep(0)

        try:
            engine = BlueprintEngine(
                model_name=MODEL_NAME,
                log_callback=log_to_queue,
                agent_manager=agent_manager,
                ingestor=ingestor,
            )

            executor_task = loop.run_in_executor(
                None, engine.run_deep_ask, message, vault_path, target_path
            )

            last_heartbeat = loop.time()
            disconnected = False
            while True:
                while not queue.empty():
                    msg = queue.get_nowait()
                    yield {"data": f"LOG: {msg}"}
                    last_heartbeat = loop.time()

                if executor_task.done():
                    break

                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield {"data": f"LOG: {msg}"}
                    last_heartbeat = loop.time()
                except asyncio.TimeoutError:
                    if loop.time() - last_heartbeat > 10:
                        yield {"comment": "ping"}
                        last_heartbeat = loop.time()

                    if await request.is_disconnected():
                        logging.warning("Cliente desconectado durante Deep Ask.")
                        executor_task.cancel()
                        disconnected = True
                        break
            if disconnected:
                return
            result = await executor_task
            yield {"data": f"RESULT: {result['report']}"}
            yield {"data": f"TRANSCRIPT: {result['transcript']}"}
            slug = str(message).replace(" ", "_")[:20] or "query"
            await save_to_vault(vault_path, f"DEEP_ASK_{slug}", result["report"])
        except BrokenPipeError:
            logging.warning("Broken pipe: cliente desconectado durante Deep Ask.")
            return
        except Exception as e:
            error_trace = traceback.format_exc()
            logging.error(f"ERROR EN DEEP ASK: {str(e)}\n{error_trace}")
            yield {"data": f"LOG: ❌ Error crítico (Ver log): {str(e)}"}
            yield {
                "data": f"RESULT: Lo siento, ocurrió un error en la exploración profunda. Detalles: {str(e)}"
            }

    return EventSourceResponse(event_generator())

@app.post("/blueprint/organize")
async def blueprint_organize(request: ChatRequest, fastapi_request: Request):
    async def event_generator():
        queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def log_to_queue(msg):
            loop.call_soon_threadsafe(queue.put_nowait, msg)

        # Send first event immediately to keep connection alive
        yield {"data": "LOG: 🧠 Motor MI-AI Sincronizado. Iniciando organización incremental..."}
        await asyncio.sleep(0)

        try:
            engine = BlueprintEngine(model_name=MODEL_NAME, log_callback=log_to_queue, agent_manager=agent_manager, ingestor=ingestor)

            executor_task = loop.run_in_executor(None, engine.run_batch_organize, request.vault_path)
            last_heartbeat = loop.time()
            disconnected = False

            while not executor_task.done() or not queue.empty():
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=2.0)
                    yield {"data": f"LOG: {msg}"}
                    last_heartbeat = loop.time()
                except asyncio.TimeoutError:
                    if loop.time() - last_heartbeat > 10:
                        yield {"comment": "ping"}
                        last_heartbeat = loop.time()

                    if await fastapi_request.is_disconnected():
                        logging.warning("Cliente desconectado durante Organize.")
                        executor_task.cancel()
                        disconnected = True
                        break
            if disconnected:
                return
            result = await executor_task
            yield {"data": f"RESULT: {result['report']}"}
        except BrokenPipeError:
            logging.warning("Broken pipe: cliente desconectado durante Organize.")
            return
        except Exception as e:
            error_trace = traceback.format_exc()
            logging.error(f"ERROR EN ORGANIZE: {str(e)}\n{error_trace}")
            yield {"data": f"LOG: ❌ Error crítico (Ver log): {str(e)}"}
            yield {"data": f"RESULT: Lo siento, ocurrió un error organizando la bóveda. Detalles: {str(e)}"}

    return EventSourceResponse(event_generator())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)