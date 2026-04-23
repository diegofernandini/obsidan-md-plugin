from typing import List, Dict, Any
from src.agent_manager import AgentManager
from src.data_ingestor import DataIngestor

class BlueprintEngine:
    """
    Orquesta flujos de trabajo multi-agente complejos (Blueprints).
    """
    def __init__(self, model_name: str = "llama3.1", log_callback=None):
        self.agent_manager = AgentManager(model_name=model_name)
        self.ingestor = DataIngestor()
        self.log_callback = log_callback

    def _log(self, message: str):
        print(message)
        if self.log_callback:
            self.log_callback(message)

    def run_research_roadmap(self, topic: str) -> Dict[str, Any]:
        """
        Blueprint: Roadmap de Investigación.
        Secuencia: Estado del Arte -> Crítica de Brechas -> Visión Futura.
        """
        self._log(f"\n🚀 Iniciando Blueprint: ROADMAP DE INVESTIGACIÓN para '{topic}'")
        
        # 0. Preparar registro de actividad (Transcript)
        log = []
        log.append(f"--- INICIO DE BLUEPRINT: ROADMAP DE INVESTIGACIÓN ---")
        log.append(f"Objetivo: {topic}")

        # 1. Obtener contexto global (Híbrido: Local + Web)
        self._log("\n🌐 PASO 1: Recopilando base de conocimiento global...")
        log.append("Paso 1: Iniciando motor de búsqueda global (EN/ORIG).")
        queries = self.agent_manager.generate_search_queries(topic)
        web_results = self.ingestor.get_combined_research(queries)
        selected_web = self.agent_manager.select_best_sources(web_results, topic)
        log.append(f"Paso 1: Seleccionadas {len(selected_web)} fuentes web académicas/generales.")
        
        web_contents = [self.ingestor.scrape_url(s['url']) for s in selected_web]
        local_texts = self.ingestor.load_local_data("data_sources")
        local_context = ""
        if local_texts:
            log.append(f"Paso 1: Indexando carpeta local 'data_sources'.")
            self.ingestor.index_data(local_texts, "LOCAL", "roadmap_index")
            retriever = self.ingestor.get_retriever()
            docs = retriever.invoke(topic)
            local_context = "\n".join([d.page_content for d in docs])
            log.append(f"Paso 1: Contexto local recuperado (RAG).")

        combined_context = f"--- CONTEXTO LOCAL ---\n{local_context}\n\n--- CONTEXTO WEB ---\n" + "\n".join(web_contents)

        # 2. Estado del Arte (Sintetizador)
        self._log("\n📚 PASO 2: Generando 'Estado del Arte' (Sintetizador)...")
        state_of_the_art = self.agent_manager.synthesize_report(combined_context, topic)
        
        # Extraer una síntesis del log
        log_sintesis = state_of_the_art[:150].replace('\n', ' ') + "..."
        log.append(f"Paso 2: Agente [Sintetizador] definió la tesis central: '{log_sintesis}'")

        # 3. Análisis de Brechas (Crítico)
        self._log("\n⚖️ PASO 3: Identificando brechas y contradicciones (Crítico)...")
        gaps = self.agent_manager.perform_critical_gap_analysis(combined_context, topic)
        
        # Extraer una síntesis del log
        log_gaps = gaps[:150].replace('\n', ' ') + "..."
        log.append(f"Paso 3: Agente [Crítico] detectó las siguientes brechas/vulnerabilidades: '{log_gaps}'")

        # 4. Propuesta Visionaria (Visionario)
        self._log("\n🔭 PASO 4: Proyectando líneas de investigación futuras (Visionario)...")
        vision = self.agent_manager.propose_visionary_ideas(combined_context, gaps, topic)
        
        # Extraer una síntesis del log
        log_vision = vision[:150].replace('\n', ' ') + "..."
        log.append(f"Paso 4: Agente [Visionario] proyectó soluciones disruptivas basadas en: '{log_vision}'")

        # Estructurar resultado
        full_report = f"""
# ROADMAP DE INVESTIGACIÓN: {topic.upper()}

## 1. ESTADO DEL ARTE Y SÍNTESIS GLOBAL
{state_of_the_art}

## 2. ANÁLISIS CRÍTICO Y BRECHAS DETECTADAS
{gaps}

## 3. LÍNEAS DE INVESTIGACIÓN Y PROPUESTAS VISIONARIAS
{vision}
"""
        return {
            "report": full_report,
            "transcript": "\n".join(log)
        }

    def run_synergy_matrix(self, topics: List[str]) -> Dict[str, Any]:
        """
        Blueprint: Matriz de Sinergias (Híbrida).
        Busca conexiones no obvias entre múltiples conceptos usando Web y Local.
        """
        combined_topics = " y ".join(topics)
        self._log(f"\n🚀 Iniciando Blueprint: MATRIZ DE SINERGIAS HÍBRIDA para '{combined_topics}'")
        
        log = []
        log.append(f"--- INICIO DE BLUEPRINT: MATRIZ DE SINERGIAS HÍBRIDA ---")
        log.append(f"Temas: {combined_topics}")

        # 0. Preparar índice local una sola vez si existe
        local_texts = self.ingestor.load_local_data("data_sources")
        retriever = None
        if local_texts:
            log.append("Paso 0: Indexando fuentes locales ('data_sources').")
            self.ingestor.index_data(local_texts, "LOCAL", "synergy_index")
            retriever = self.ingestor.get_retriever()

        # 1. Extraer esencia de cada concepto (Híbrido)
        essences = {}
        for t in topics:
            self._log(f"🔍 Extrayendo esencia híbrida de: {t}...")
            log.append(f"Paso 1: Agente [Detective] extrayendo esencia híbrida de '{t}'.")
            
            # A. Contexto Web
            queries = {"en": t, "orig": t}
            web_res = self.ingestor.get_combined_research(queries)
            web_context = "\n".join([r['summary'] for r in web_res[:3]])
            
            # B. Contexto Local
            local_context = ""
            if retriever:
                docs = retriever.invoke(t)
                local_context = "\n".join([d.page_content for d in docs])
                
            combined_item_context = f"--- WEB ---\n{web_context}\n\n--- LOCAL ---\n{local_context}"
            essence = self.agent_manager.extract_information(combined_item_context, t)
            essences[t] = essence
            log.append(f"Paso 1: [Detective] extrajo esencia de '{t}': {essence[:100]}...")

        # 2. Agente Visionario busca sinergias
        self._log("\n🔮 PASO 2: Agente Visionario trazando conexiones disruptivas...")
        context_all = "\n\n".join([f"CONCEPTO {k}:\n{v}" for k, v in essences.items()])
        synergies = self.agent_manager._run_agent_task(
            "Arquitecto de Sinergias",
            "Tu misión es encontrar el 'puerto común' entre conceptos dispares. Debes crear una Matriz de Sinergias donde expliques cómo A potencia a B, y qué solución nueva surge de la unión de ambos.",
            context_all,
            f"Crea una Matriz de Sinergias para: {combined_topics}. Enfócate en innovación radical y usa los datos locales si aportan valor diferencial."
        )
        
        log_sinergia = synergies[:200].replace('\n', ' ') + "..."
        log.append(f"Paso 2: Agente [Visionario] detectó una oportunidad de unión: '{log_sinergia}'")

        full_report = f"""
# MATRIZ DE SINERGIAS HÍBRIDA: {combined_topics.upper()}

## ANÁLISIS DE INTERSECCIÓN DISRUPTIVA (LOCAL + WEB)
{synergies}
"""
        return {
            "report": full_report,
            "transcript": "\n".join(log)
        }
