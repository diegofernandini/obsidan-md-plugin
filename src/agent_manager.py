try:
    from langchain_ollama import ChatOllama
except ImportError:
    try:
        from langchain_community.chat_models import ChatOllama
    except ImportError:
        ChatOllama = None

from typing import List, Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage

class AgentManager:
    """
    Orquesta los roles de los agentes (Extractor, Sintetizador) y el patrón de debate,
    utilizando un modelo local de Ollama.
    """
    def __init__(self, model_name: str = "llama3.2:1b"):
        # Cambiamos ChatOpenAI por ChatOllama para usar modelos locales.
        # Asegúrate de tener el modelo especificado (ej: llama2, mistral) ejecutándose en Ollama.
        print(f"Inicializando el motor de IA con Ollama usando el modelo: {model_name}")
        try:
            if ChatOllama is not None:
                self.llm = ChatOllama(model=model_name)
            else:
                print("❌ ERROR: Ni 'langchain_ollama' ni 'langchain_community' están instalados en este entorno Python.")
                self.llm = None
        except Exception as e:
            print(f"❌ ERROR al inicializar Ollama: {e}")
            print("Asegúrate de que Ollama está corriendo en segundo plano y el modelo ('llama2' por defecto) ha sido descargado con 'ollama pull llama2'")
            self.llm = None


    async def stream_agent_task(self, role: str, system_prompt: str, context: str, task: str):
        """Generador asíncrono para streaming del LLM."""
        if not self.llm:
            yield "[FALLO: El motor LLM no está inicializado.]"
            return
            
        obsidian_rules = "\n\nREGLA: Usa sintaxis de Obsidian: crea etiquetas (#tag) para conceptos, wikilinks ([[término]]) para entidades o nombres concretos y Callouts (> [!info] o > [!warning]) para advertencias."

        messages = [
            SystemMessage(content=f"Eres un experto profesional con el rol de: {role}. Tu metodología es {system_prompt}. Responde con párrafos fluidos y usa listas solo si es necesario.{obsidian_rules}"),
            HumanMessage(content=f"\n\n[CONTEXTO RECUPERADO]:\n---{context}---\n\n[TAREA PRINCIPAL]:\n{task}")
        ]
        
        try:
            async for chunk in self.llm.astream(messages):
                yield chunk.content
        except Exception as e:
            yield f"[ERROR en streaming: {e}]"

    def _run_agent_task(self, role: str, system_prompt: str, context: str, task: str) -> str:
        """Ejecuta la llamada al LLM para un agente específico (Sincrónico)."""
        if not self.llm:
            return "[FALLO: El motor LLM no está inicializado. Revise la configuración de Ollama.]"

        obsidian_rules = "\n\nREGLA: Usa sintaxis de Obsidian: crea etiquetas (#tag) para conceptos, wikilinks ([[término]]) para entidades o nombres concretos y Callouts (> [!info] o > [!warning]) para advertencias."

        messages = [
            SystemMessage(content=f"Eres un experto profesional con el rol de: {role}. Tu metodología es {system_prompt}. Responde con párrafos fluidos y usa listas solo si es necesario.{obsidian_rules}"),
            HumanMessage(content=f"\n\n[CONTEXTO RECUPERADO]:\n---{context}---\n\n[TAREA PRINCIPAL]:\n{task}")
        ]
        
        print(f"\n>>> AGENTE [ {role} ] está procesando la información...")
        
        try:
            # Usamos invoke() para enviar los mensajes al modelo local
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
            return f"[ERROR al ejecutar el agente {role} con Ollama: {e}]"

    # --- PATRÓN 1: INVESTIGACIÓN Y SÍNTESIS (PDF) ---

    def extract_information(self, context: str, task_context: str) -> str:
        """
        Implementa el rol de 'Detective' o 'Extractor' (PDF).
        Busca patrones y extrae datos estructurados del contexto.
        """
        role = "Detective / Agente Extractor de Patrones"
        system_prompt = "Tu enfoque es forense. No interpretas; extraes. Debes identificar cifras, fechas, términos clave y relaciones causa-efecto. Presenta la información de forma fluida y legible, usando párrafos y listas de forma equilibrada."
        task = f"Analiza el siguiente contexto. Extrae la información clave relacionada con: '{task_context}'. Responde con claridad."
        return self._run_agent_task(role, system_prompt, context, task)

    def synthesize_report(self, extracted_data: str, task_context: str) -> str:
        """
        Implementa el rol de 'Editor en Jefe' o 'Sintetizador' (PDF).
        Toma datos crudos y los estructura en un informe ejecutivo coherente.
        """
        role = "Editor Jefe / Agente Sintetizador"
        system_prompt = "Tu función es dar cohesión y narrativa. Tomas la información fragmentada (los datos extraídos) y la transformas en un informe ejecutivo fluido y profesional. Cita las fuentes usando la sintaxis de Obsidian [[Nota]] o [Link](URL) dentro del texto. IMPORTANTE: NO incluyas ninguna sección de 'Bibliografía' al final de tu respuesta, ya que el sistema lo hará automáticamente."
        task = f"Utiliza los hallazgos y datos que te proporciono a continuación. Redacta un informe ejecutivo de investigación sobre '{task_context}'. Informe:\n\n{extracted_data}"
        return self._run_agent_task(role, system_prompt, "", task)

    # --- PATRÓN 2: BÚSQUEDA GLOBAL Y REFERENCIADA (WEB) ---

    def generate_search_queries(self, topic: str) -> Dict[str, str]:
        """
        Genera queries optimizadas (Inglés para academia, idioma original para general).
        """
        role = "Experto en Búsquedas"
        system_prompt = "Genera términos de búsqueda técnicos y precisos. Responde Directamente con el formato solicitado."
        task = f"Tema: '{topic}'. Responde solo con esto:\nEN_QUERY: <términos en inglés>\nORIG_QUERY: <términos en el idioma original>"
        
        response = self._run_agent_task(role, system_prompt, "", task)
        
        print(f"📡 Query detectada -> {response.strip()}")
        
        queries = {"en": topic, "orig": topic}
        for line in response.split('\n'):
            if "EN_QUERY:" in line:
                queries["en"] = line.split("EN_QUERY:")[1].strip().strip('<').strip('>').strip('"')
            if "ORIG_QUERY:" in line:
                queries["orig"] = line.split("ORIG_QUERY:")[1].strip().strip('<').strip('>').strip('"')
        
        print(f"🔍 Queries generadas -> [EN]: {queries['en']} | [ORIG]: {queries['orig']}")
        return queries

    def select_best_sources(self, search_results: List[Dict[str, Any]], task_context: str) -> List[Dict[str, Any]]:
        """
        El Agente Investigador analiza los resultados y elije los relevantes. 
        """
        if not search_results:
            return []

        role = "Investigador / Curador de Contenido"
        system_prompt = """Eres un experto en análisis de información. 
        Tu tarea es evaluar resultados de búsqueda y seleccionar todos aquellos que tengan relación con el tema.
        NO seas demasiado estricto: si una fuente aporta un ángulo diferente o contexto útil, selecciónala. 
        Prioriza tener una bibliografía extensa y variada (hasta 10 fuentes).
        Responde SIEMPRE en el formato solicitado para que el sistema pueda procesarlo."""
        
        # Preparar la lista para el LLM
        formatted_list = ""
        for i, res in enumerate(search_results):
            formatted_list += f"\n[{i}] TÍTULO: {res['title']}\nRESUMEN: {res['summary']}\n"

        import re
        task = f"Evalúa estos resultados para el tema: '{task_context}'. Responde indicando los índices elegidos en este formato EXACTO: [[índice1, índice2]]. Si NINGUNO tiene sentido absoluto, responde [[NONE]]."
        
        selection_response = self._run_agent_task(role, system_prompt, "", task)
        print(f"\n✅ Análisis del Investigador: {selection_response}")
        
        # Extraer bloques de índices usando regex
        match = re.search(r'\[\[(.*?)\]\]', selection_response)
        selected_indices = []
        if match:
            parts = match.group(1).split(',')
            for part in parts:
                num_match = re.search(r'\d+', part)
                if num_match:
                    try:
                        idx = int(num_match.group())
                        if 0 <= idx < len(search_results) and idx not in selected_indices:
                            selected_indices.append(idx)
                    except:
                        continue
        
        # Fallback de seguridad: Si no se detectaron índices o el AI fue demasiado estricto
        if not selected_indices and search_results:
            print("⚠️ Aplicando fallback automático (Top 5 fuentes)...")
            return search_results[:5]
            
        return [search_results[i] for i in selected_indices[:10]]

    # --- PATRÓN 2: ANÁLISIS DE CONTRASTE (WEB SCRAPING) ---

    def conduct_contrast_analysis(self, content_optimista: str, content_escetico: str, task_context: str) -> Dict[str, str]:
        """
        Orquesta el patrón de debate entre dos contenidos con sesgos opuestos o complementarios.
        Retorna un diccionario con 'report' y 'transcript'.
        """
        
        transcript_log = []
        
        # 1. Analista Optimista (El 'Pros')
        role_optimista = "Consultor Estratégico Optimista"
        system_prompt_optimista = "Tu perspectiva es inherentemente positiva y proactiva. Tu objetivo es destacar las oportunidades, los potenciales de crecimiento, las sinergias y las razones por las que el proyecto o tema en cuestión es viable. Articula tu análisis con un tono entusiasta y visionario."
        
        msg_perspectiva_a = "INICIO DE DEBATE: PERSPECTIVA A (Optimista)"
        print("\n" + "="*20 + f" -> {msg_perspectiva_a} " + "="*20)
        transcript_log.append(f"\n--- {msg_perspectiva_a} ---")
        response_optimista = self._run_agent_task(
            role_optimista, system_prompt_optimista, content_optimista, f"Analiza los puntos fuertes y oportunidades de este contenido respecto a: {task_context}")
        transcript_log.append(response_optimista[:500] + "..." if len(response_optimista) > 500 else response_optimista)

        # 2. Abogado del Diablo (El 'Contras')
        role_escetico = "Analista de Riesgos / Abogado del Diablo"
        system_prompt_escetico = "Tu perspectiva es inherentemente cautelosa y crítica. Tu objetivo es encontrar riesgos, debilidades, presuposiciones no verificadas y contradicciones. Nunca aceptes una premisa sin cuestionarla. Articula tu análisis con un tono sobrio, de advertencia y precaución."
        
        msg_perspectiva_b = "INICIO DE DEBATE: PERSPECTIVA B (Crítica)"
        print("\n" + "="*20 + f" -> {msg_perspectiva_b} " + "="*20)
        transcript_log.append(f"\n--- {msg_perspectiva_b} ---")
        response_escetico = self._run_agent_task(
            role_escetico, system_prompt_escetico, content_escetico, f"Identifica riesgos significativos y debilidades estructurales en este contenido respecto a: {task_context}")
        transcript_log.append(response_escetico[:500] + "..." if len(response_escetico) > 500 else response_escetico)

        # 3. Síntesis Final (Mediador)
        role_mediador = "Director de Análisis Senior"
        system_prompt_mediador = f"Tu tarea es sintetizar el debate. Debes crear una Matriz de Decisión de Riesgos/Oportunidades. Cita tus fuentes usando la sintaxis de Obsidian dentro del cuerpo del texto. IMPORTANTE: El informe final DEBE estar redactado íntegramente en el idioma del tema solicitado ('{task_context}'). NO crees una sección de Bibliografía al final."
        
        msg_sintesis = "SÍNTESIS FINAL (Mediador)"
        transcript_log.append(f"\n--- {msg_sintesis} ---")
        
        task_mediador = f"""
        Basándote en los siguientes análisis de debate, redacta un informe final de "Matriz de Decisión" sobre: {task_context}.
        1. RESUMEN DEL DEBATE.
        2. MATRIZ RIESGO/OPORTUNIDAD.
        3. JUICIO FINAL Y ACCIÓN RECOMENDADA.
        
        ANÁLISIS DE PERSPECTIVA A: {response_optimista}
        ANÁLISIS DE PERSPECTIVA B: {response_escetico}
        """
        
        report = self._run_agent_task(role_mediador, system_prompt_mediador, "", task_mediador)
        transcript_log.append(report[:500] + "..." if len(report) > 500 else report)
        
        return {
            "report": report,
            "transcript": "\n".join(transcript_log)
        }

    # --- PATRÓN 3: ANÁLISIS HÍBRIDO (LOCAL + WEB) ---

    def conduct_hybrid_analysis(self, local_context: str, web_contents: List[str], strategy: str, topic: str) -> str:
        """
        Orquesta el análisis híbrido cruzando la memoria local con la investigación web.
        """
        role = "Consultor de Inteligencia Híbrida Senior"
        
        # Ajustar el enfoque según la estrategia elegida
        if strategy == "C":
            strategy_focus = "ENFOQUE COMPARATIVO: Resalta las diferencias, vacíos y discrepancias entre nuestra documentación interna y lo hallado en la web externa."
        else:
            strategy_focus = "ENFOQUE INTEGRADOR: Fusiona ambas fuentes para crear una respuesta única, coherente y enriquecida, usando la web para llenar los vacíos de lo local."

        system_prompt = f"""
        Eres un analista experto con acceso a bases de conocimiento internas y externas.
        Tu metodología actual es: {strategy_focus}

        REGLAS CRUCIALES:
        1. Resuelve conflictos entre fuentes explicando por qué ocurren.
        2. Analiza oportunidades de cada postura.
        3. Da una RECOMENDACIÓN FINAL accionable.
        4. NUNCA uses frases genéricas como "[Fuente interna]" o "[Fuente externa]".
        5. Cita SIEMPRE usando la sintaxis exacta de Obsidian dentro del texto. 
           - Si la info viene de una URL, usa el formato: [Texto](URL)
           - Si la info viene de un archivo local, usa WIKILINKS: [[Nombre_del_Archivo]]
        6. IMPORTANTE: Responde SIEMPRE en el mismo idioma en que se te ha planteado el tema ('{topic}').
        7. REGLA CRUCIAL: NO incluyas una sección final de 'Bibliografía', limítate a citar dentro del contenido.
        """

        combined_web = "\n\n".join(web_contents)
        context_hybrid = f"--- CONTENIDO LOCAL (BIE) ---\n{local_context}\n\n--- CONTENIDO WEB (EXTERNO) ---\n{combined_web}"

        task = f"""
        Realiza un análisis profundo sobre el tema: '{topic}'.
        Sigue la estructura de tu estrategia seleccionada y asegúrate de cumplir con todas las reglas de resolución de conflictos si es que los detectas. 
        El objetivo es dar una visión 360 al cliente.
        """

        return self._run_agent_task(role, system_prompt, context_hybrid, task)

    # --- PATRÓN 4: AGENTES DE MAESTRÍA (VISIÓN Y CRÍTICA) ---

    def perform_critical_gap_analysis(self, context: str, topic: str) -> str:
        """
        Rol de 'Abogado del Diablo / Crítico Académico'.
        Busca vacíos, contradicciones y áreas no exploradas.
        """
        role = "Analista de Brechas y Crítico Académico"
        system_prompt = "Tu enfoque es detectar el 'silencio' en los datos. ¿Qué no se está diciendo? ¿Qué contradicciones existen? ¿En qué fallan las teorías actuales? Tu tono debe ser incisivo, serio y riguroso."
        task = f"Analiza la siguiente base de conocimiento sobre '{topic}'. Tu misión es identificar 3 brechas críticas (vacíos de información o problemas no resueltos) y 2 contradicciones potenciales. IMPORTANTE: Responde en el idioma del tema solicitado."
        return self._run_agent_task(role, system_prompt, context, task)

    def propose_visionary_ideas(self, context: str, gaps: str, topic: str) -> str:
        """
        Rol de 'Visionario / Generativo'.
        Propone hipótesis disruptivas y conexiones inesperadas.
        """
        role = "Visionario / Arquitecto de Innovación"
        system_prompt = "Tu función es la extrapolación creativa. Tomas las brechas identificadas y propones soluciones 'fuera de la caja', analogías con otras industrias y modelos conceptuales nuevos. Tu tono debe ser inspirador, visionario y vanguardista."
        task = f"Basándote en el contexto y las brechas identificadas ({gaps}), propón 3 hipótesis disruptivas o líneas de investigación futuras para '{topic}'. Usa analogías si es posible. IMPORTANTE: Responde en el idioma del tema solicitado."
        return self._run_agent_task(role, system_prompt, context, task)
