import os
from dotenv import load_dotenv
from src.data_ingestor import DataIngestor
from src.agent_manager import AgentManager
from typing import List
from datetime import datetime
import re

# Cargar variables de entorno (Solo se mantiene para otras configuraciones, aunque no necesite la clave de OpenAI)
load_dotenv()

# --- CONFIGURACIÓN GLOBAL ---
PDF_DOCUMENT_PATH = "sample_banca_reporte.pdf" 
DATA_SOURCES_DIR = "data_sources"
INDEX_DIR = "faiss_index"
MODEL_NAME = "llama3.1" # 🌟 Actualizado a un modelo que tienes instalado (llama3.1)
REPORTS_DIR = "reports"

def save_report(content: str, metadata: str, mode: str, topic: str = "analysis") -> str:
    """
    Guarda el informe en un archivo Markdown en la carpeta de reportes.
    """
    if not os.path.exists(REPORTS_DIR):
        os.makedirs(REPORTS_DIR)
        
    # Sanitizar el nombre del tema para el nombre de archivo
    clean_topic = re.sub(r'[^\w\s-]', '', topic).strip().replace(' ', '_').lower()[:30]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"reporte_{mode}_{clean_topic}_{timestamp}.md"
    file_path = os.path.join(REPORTS_DIR, filename)
    
    full_content = f"# INFORME EJECUTIVO: {topic.upper()}\n"
    full_content += f"*Generado por Synapse AI el {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
    full_content += content
    full_content += "\n\n---\n"
    full_content += "## 🕵️‍♂️ LOG DE TRABAJO Y METADATOS\n"
    full_content += metadata
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(full_content)
        return file_path
    except Exception as e:
        print(f"⚠️ Error al guardar el reporte: {e}")
        return ""

def run_pdf_ingestion(file_path: str, index_dir: str):
    """
    Ejecuta el proceso de carga e indexación de documentos PDF (PDF RAG).
    """
    print("\n" + "="*60)
    print("       [ FASE 1 ] INGESTA Y CREACIÓN DE LA MEMORIA DOCUMENTAL (PDF RAG)")
    print("="*60)
    
    try:
        ingestor = DataIngestor()
        # 1. Cargar texto
        texts = ingestor.load_local_data(file_path)
        
        if not texts:
            print("No se pudo extraer texto del documento. Verifique el archivo PDF.")
            return None

        # 2. Indexar y guardar
        index_path = ingestor.index_data(texts, "PDF", index_dir)
        print(f"\n✅ ¡Memoria Documental Creada! Índice guardado en: {index_path}")
        return ingestor.get_retriever()

    except FileNotFoundError as e:
        print(f"❌ ERROR CRÍTICO: {e}")
        return None
    except Exception as e:
        print(f"❌ ERROR durante la ingesta PDF: {e}")
        return None

def run_pdf_analysis_pipeline(retriever):
    """
    Ejecuta la cadena de agentes: Retrieval -> Extractor -> Synthesizer (PDF).
    """
    print("\n" + "="*60)
    print("       [ FASE 2 ] EJECUCIÓN DEL PATRÓN 'INVESTIGACIÓN Y SÍNTESIS' (PDF)")
    print("="*60)

    # 1. Definir la tarea y contexto de búsqueda
    TASK_GOAL = "Viabilidad de implementar tokenización de activos en el sector bancario peruano. Se deben contrastar los requerimientos regulatorios con las capacidades operativas."
    print(f"💡 Objetivo de Análisis: {TASK_GOAL}")

    # 2. Recuperación de Información (RAG)
    retrieved_docs = retriever.invoke(TASK_GOAL)
    context = "\n\n--- CONTEXTO RECOPILADO POR EL SISTEMA (RAG) ---\n"
    context += "\n".join([doc.page_content for doc in retrieved_docs])
    context += "\n\n----------------------------------------------------"
    
    print("\n✅ Contexto de soporte recuperado exitosamente. Iniciando debate de expertos...")

    # 3. Inicializar y ejecutar agentes
    # Se cambia la inicialización para usar el modelo local
    agent_manager = AgentManager(model_name=MODEL_NAME)
    
    # 3a. Extractor (Detective)
    extracted_data = agent_manager.extract_information(
        context=context, 
        task_context=TASK_GOAL
    )
    
    # 3b. Sintetizador (Editor Jefe)
    final_report = agent_manager.synthesize_report(
        extracted_data=extracted_data, 
        task_context=TASK_GOAL
    )
    
    return final_report, extracted_data

def run_web_analysis_pipeline(query: str):
    """
    Ejecuta el patrón de investigación autónoma (Búsqueda -> Selección -> Scraping -> Debate).
    """
    print("\n" + "="*60)
    print("       [ FASE 2 ] EJECUCIÓN DEL PATRÓN 'INVESTIGADOR WEB AUTÓNOMO'")
    print("="*60)
    
    print(f"💡 Objetivo de Investigación: {query}")

    # 1. Inicializar componentes
    ingestor = DataIngestor()
    agent_manager = AgentManager(model_name=MODEL_NAME)

    # 2. Generar Queries Globales (Inglés + Idioma Original)
    print(f"\n🌍 Paso 1: Generando estrategia de búsqueda global para '{query}'...")
    queries = agent_manager.generate_search_queries(query)
    
    # 3. Búsqueda Global y General
    print(f"\n🕸️ Paso 2: Realizando investigación web global y general...")
    search_results = ingestor.get_combined_research(queries)
    if not search_results:
        return "❌ No se encontraron fuentes relevantes para el tema proporcionado.", []

    # 4. Selección Autónoma de Fuentes (Agente Investigador)
    print("\n🧐 Paso 3: Agente Investigador curando las mejores fuentes...")
    selected_sources = agent_manager.select_best_sources(search_results, query)
    
    if not selected_sources:
        return "⚠️ El Investigador determinó que los resultados encontrados no son suficientemente pertinentes para este tema.", []

    # 5. Scraping de las fuentes seleccionadas
    print(f"\n📄 Paso 4: Extrayendo contenido de {len(selected_sources)} fuentes...")
    research_contents = []
    for source in selected_sources:
        content = ingestor.scrape_url(source['url'])
        research_contents.append(content)

    # 6. Ejecutar el debate de contraste
    print("\n🧠 Paso 5: Iniciando Debate de Contraste entre expertos...")
    if len(research_contents) >= 2:
        final_report = agent_manager.conduct_contrast_analysis(
            content_optimista=research_contents[0], 
            content_escetico=research_contents[1], 
            task_context=query
        )
    else:
        # Fallback si solo se pudo scrapear una fuente: Sintetizar en el idioma del usuario
        print("\n📝 Paso 5: Sintetizando fuente única en el idioma del usuario...")
        final_report = agent_manager.synthesize_report(
            extracted_data=research_contents[0], 
            task_context=query
        )
    
    return final_report, selected_sources

def run_hybrid_analysis_pipeline(topic: str, strategy: str):
    """
    Orquesta la investigación híbrida (Local Folder + Web Search).
    """
    print("\n" + "="*60)
    print(f"       [ FASE 3 ] EJECUCIÓN DEL MODO HÍBRIDO PRO ({'COMPARATIVO' if strategy == 'C' else 'INTEGRADOR'})")
    print("="*60)

    ingestor = DataIngestor()
    agent_manager = AgentManager(model_name=MODEL_NAME)

    # 1. Ingesta de la carpeta local
    print(f"\n📂 Paso 1: Indexando carpeta local '{DATA_SOURCES_DIR}'...")
    local_texts = ingestor.load_local_data(DATA_SOURCES_DIR)
    if local_texts:
        ingestor.index_data(local_texts, "LOCAL_FOLDER", "hybrid_index")
        retriever = ingestor.get_retriever()
        
        # Recuperar contexto local relevante para el tema
        retrieved_docs = retriever.invoke(topic)
        local_context = "\n".join([doc.page_content for doc in retrieved_docs])
    else:
        local_context = "[No se encontraron documentos locales relevantes en la carpeta.]"

    # 2. Investigación Web Autónoma
    print(f"\n🕸️ Paso 2: Realizando investigación web global y general...")
    queries = agent_manager.generate_search_queries(topic)
    search_results = ingestor.get_combined_research(queries)
    selected_web_sources = agent_manager.select_best_sources(search_results, topic)
    
    web_contents = []
    if selected_web_sources:
        for source in selected_web_sources:
            web_contents.append(ingestor.scrape_url(source['url']))
    else:
        print("⚠️ No se seleccionaron fuentes web relevantes. El análisis será puramente local.")

    # 3. Análisis Híbrido Final (Contradicciones & Recomendación)
    print("\n🧠 Paso 3: Agente Híbrido cruzando fuentes y resolviendo conflictos...")
    final_report = agent_manager.conduct_hybrid_analysis(
        local_context=local_context, 
        web_contents=web_contents, 
        strategy=strategy, 
        topic=topic
    )

    return final_report, selected_web_sources

def main():
    """
    Función principal que orquesta el flujo de trabajo de MI-AI.
    """
    # 1. PREGUNTAR AL USUARIO EL MODO DE ANÁLISIS
    print("\n" + "="*80)
    print("          👋 BIENVENIDO AL MI-AI | ORQUESTADOR DE CONOCIMIENTO (LOCAL LLM) 🌐")
    print("="*80)
    
    while True:
        mode = input("¿Modo de análisis: [P]DF local, [W]eb autónoma o [H]íbrido (Carpeta + Web)? (P/W/H): ").strip().upper()
        if mode in ['P', 'W', 'H']:
            break
        print("Por favor, ingrese 'P', 'W' o 'H'.")

    # 2. EJECUCIÓN SEGÚN EL MODO
    if mode == 'H':
        # --- MODO HÍBRIDO (FASE 3) ---
        print("\n" + "="*60)
        print("   📂🔎 MODO: INVESTIGADOR HÍBRIDO PRO (Local Folder + Web)")
        print("="*60)
        
        topic = input("Ingrese el TEMA para el análisis híbrido: ").strip()
        while True:
            strat = input("Elija el ENFOQUE: [C]omparativo o [I]ntegrador: ").strip().upper()
            if strat in ['C', 'I']:
                break
            print("Elija 'C' o 'I'.")

        if not topic:
            print("\n❌ Fallo: Debe proporcionar un tema.")
            return

        final_report, sources = run_hybrid_analysis_pipeline(topic, strat)
        
        # --- MOSTRAR Y GUARDAR ---
        print("\n" + "="*80)
        print(f"✨ 📄🌐 INFORME HÍBRIDO FINAL ({'COMPARATIVO' if strat == 'C' else 'INTEGRADOR'}) ✨")
        print("="*80)
        print(final_report)
        
        meta_hybrid = f"--- ESTRATEGIA: {'Comparativa' if strat == 'C' else 'Integradora'} ---\n"
        meta_hybrid += f"--- FUENTE LOCAL: Carpeta '{DATA_SOURCES_DIR}' ---\n"
        meta_hybrid += "--- FUENTES WEB SELECCIONADAS ---\n"
        if sources:
            for s in sources:
                meta_hybrid += f"- {s['title']} ({s['source']}) -> {s['url']}\n"
        else:
            meta_hybrid += "- No se seleccionaron fuentes web adicionales por falta de relevancia técnica.\n"
        
        saved_path = save_report(final_report, meta_hybrid, "HYBRID", topic)
        if saved_path:
            print(f"\n💾 Informe híbrido guardado exitosamente en: {saved_path}")

    elif mode == 'P':
        # --- MODO PDF (FASE 1) ---
        retriever = run_pdf_ingestion(PDF_DOCUMENT_PATH, INDEX_DIR)
        if retriever:
            final_report, extracted_data = run_pdf_analysis_pipeline(retriever)
        
            print("\n" + "="*80)
            print("✨ 📄 INFORME EJECUTIVO FINAL (PDF) 📄 ✨")
            print("="*80)
            print(final_report)
            
            # --- GUARDAR REPORTE ---
            meta_pdf = f"--- 🔍 RESULTADOS BRUTOS DEL DETECTIVE ---\n{extracted_data}"
            saved_path = save_report(final_report, meta_pdf, "PDF", "PDF_Analysis")
            if saved_path:
                print(f"\n💾 Informe guardado exitosamente en: {saved_path}")

            print("\n\n" + "="*80)
            print("🕵️‍♂️ LOG DE TRABAJO (Trajectoria de Pensamiento del MI-AI) 🕵️‍♂️")
            print("="*80)
            print("--- 🔍 1. RESULTADOS BRUTOS DEL DETECTIVE (Agente Extractor) ---")
            print(extracted_data)
        
    elif mode == 'W':
        # --- MODO WEB (FASE 2) ---
        print("\n" + "="*60)
        print("   🛒 MODO: INVESTIGADOR WEB AUTÓNOMO (Peer-Review & Journals)")
        print("="*60)
        
        topic = input("Ingrese el TEMA o KEYWORD para investigar automáticamente: ").strip()

        if not topic:
            print("\n❌ Fallo: Debe proporcionar un tema de investigación.")
            return
        
        final_report, sources = run_web_analysis_pipeline(topic)
        
        print("\n" + "="*80)
        print("✨ 🕸️ INFORME EJECUTIVO FINAL (INVESTIGACIÓN AUTÓNOMA) 🕸️ ✨")
        print("="*80)
        print(final_report)
        
        # --- GUARDAR REPORTE ---
        meta_web = "--- MODO: Investigación Web Autónoma ---\n"
        meta_web += "--- 🧠 FUENTES WEB SELECCIONADAS ---\n"
        if isinstance(sources, list) and sources:
            for s in sources:
                meta_web += f"- {s['title']} ({s['source']}) -> {s['url']}\n"
        else:
            meta_web += "- No se seleccionaron fuentes web por falta de relevancia técnica.\n"
        
        saved_path = save_report(final_report, meta_web, "WEB", topic)
        if saved_path:
            print(f"\n💾 Informe web guardado exitosamente en: {saved_path}")

        print("\n\n" + "="*80)
        print("🧠 FUENTES SELECCIONADAS POR EL SISTEMA:")
        if isinstance(sources, list) and sources:
            for s in sources:
                print(f"- {s['title']} ({s['source']}) -> {s['url']}")
        else:
            print("- Ninguna fuente web fue considerada lo suficientemente relevante.")
        print("="*80)


if __name__ == '__main__':
    main()
