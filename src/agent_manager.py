from langchain_community.chat_models import ChatOllama
from typing import List, Dict, Any
from langchain.schema import HumanMessage, SystemMessage

class AgentManager:
    """
    Orquesta los roles de los agentes (Extractor, Sintetizador) y el patrón de debate,
    utilizando un modelo local de Ollama.
    """
    def __init__(self, model_name: str = "llama2"):
        # Cambiamos ChatOpenAI por ChatOllama para usar modelos locales.
        # Asegúrate de tener el modelo especificado (ej: llama2, mistral) ejecutándose en Ollama.
        print(f"Inicializando el motor de IA con Ollama usando el modelo: {model_name}")
        try:
            self.llm = ChatOllama(model=model_name)
        except Exception as e:
            print(f"❌ ERROR al inicializar Ollama: {e}")
            print("Asegúrate de que Ollama está corriendo en segundo plano y el modelo ('llama2' por defecto) ha sido descargado con 'ollama pull llama2'")
            self.llm = None

    def _run_agent_task(self, role: str, system_prompt: str, context: str, task: str) -> str:
        """Ejecuta la llamada al LLM para un agente específico."""
        if not self.llm:
            return "[FALLO: El motor LLM no está inicializado. Revise la configuración de Ollama.]"

        messages = [
            SystemMessage(content=f"Eres un experto profesional con el rol de: {role}. Tu metodología es {system_prompt}. Mantén un tono analítico, profundo, y altamente estructurado."),
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
        system_prompt = "Tu enfoque es forense. No interpretas; extraes. Debes identificar cifras, fechas, términos clave, nombres de regulaciones y relaciones causa-efecto explícitas. Presenta los hallazgos en listas, viñetas o tablas. Tu salida debe ser un material de soporte para la síntesis, no un artículo final."
        task = f"Analiza el siguiente contexto de documentos. Tu misión es extraer, en detalle y sin interpretación, toda la información clave relacionada con el objetivo: '{task_context}'. Indica de forma estructurada los datos y patrones más relevantes."
        return self._run_agent_task(role, system_prompt, context, task)

    def synthesize_report(self, extracted_data: str, task_context: str) -> str:
        """
        Implementa el rol de 'Editor en Jefe' o 'Sintetizador' (PDF).
        Toma datos crudos y los estructura en un informe ejecutivo coherente.
        """
        role = "Editor Jefe / Agente Sintetizador"
        system_prompt = "Tu función es dar cohesión y narrativa. Tomas la información fragmentada (los datos extraídos) y la transformas en un informe ejecutivo fluido, coherente y listo para la presentación en una junta directiva. Debes identificar la tesis principal y los puntos de riesgo/oportunidad. IMPORTANTE: El informe DEBE estar en el mismo idioma que el objetivo del usuario."
        task = f"Utiliza los hallazgos y datos estructurados que te proporciono a continuación. Redacta un informe ejecutivo de análisis de mercado sobre '{task_context}'. El informe debe tener: 1) Tesis Central, 2) Argumentos Clave, y 3) Recomendaciones Estratégicas. Datos a usar:\n\n{extracted_data}"
        return self._run_agent_task(role, system_prompt, "", task)

    # --- PATRÓN 2: BÚSQUEDA GLOBAL Y REFERENCIADA (WEB) ---

    def generate_search_queries(self, topic: str) -> Dict[str, str]:
        """
        Genera queries optimizadas (Inglés para academia, idioma original para general).
        """
        role = "Arquitecto de Búsqueda multilingüe"
        system_prompt = "Tu misión es traducir y optimizar temas de investigación. Debes generar una query técnica en inglés para obtener los mejores resultados científicos y una query en el idioma original para contexto local."
        task = f"Para el tema '{topic}', genera una respuesta con este formato EXACTO:\nEN_QUERY: <query en inglés>\nORIG_QUERY: <query en idioma original>"
        
        response = self._run_agent_task(role, system_prompt, "", task)
        
        queries = {"en": topic, "orig": topic}
        for line in response.split('\n'):
            if "EN_QUERY:" in line:
                queries["en"] = line.split("EN_QUERY:")[1].strip().strip('"')
            if "ORIG_QUERY:" in line:
                queries["orig"] = line.split("ORIG_QUERY:")[1].strip().strip('"')
        
        print(f"🔍 Queries generadas -> [EN]: {queries['en']} | [ORIG]: {queries['orig']}")
        return queries

    def select_best_sources(self, search_results: List[Dict[str, Any]], task_context: str) -> List[Dict[str, Any]]:
        """
        El Agente Investigador analiza los resultados y elije los relevantes. Puede rechazar todos.
        """
        role = "Investigador / Curador de Contenido Científico"
        system_prompt = """Eres un experto en bibliometría con tolerancia cero a la irrelevancia. 
        Tu tarea es evaluar resultados de búsqueda y seleccionar los 2 mejores que tengan relación DIRECTA con el tema.
        REGLA DE ORO: Si un resultado no tiene nada que ver con el tema (ej: asteroides cuando se busca banca), NO LO SELECCIONES. 
        Si NINGÚN resultado es relevante, responde 'NONE'."""
        
        # Preparar la lista para el LLM
        formatted_list = ""
        for i, res in enumerate(search_results):
            formatted_list += f"\n[{i}] TÍTULO: {res['title']}\nRESUMEN: {res['summary']}\n"

        import re
        task = f"Evalúa estos resultados para el tema: '{task_context}'. Responde indicando los índices elegidos en este formato EXACTO: [[índice1, índice2]] y luego tu justificación. Si no hay nada relevante responde [[NONE]]."
        
        selection_response = self._run_agent_task(role, system_prompt, "", task)
        print(f"\n✅ Justificación del Investigador: {selection_response}")
        
        if "[[NONE]]" in selection_response.upper():
            return []
            
        # Extraer bloques de índices usando regex: busca lo que esté dentro de [[ ]]
        match = re.search(r'\[\[(.*?)\]\]', selection_response)
        selected_indices = []
        if match:
            # Dividir por comas por si el agente puso varios resultados
            parts = match.group(1).split(',')
            for part in parts:
                # Buscar el primer número que aparezca en esta parte (el índice)
                num_match = re.search(r'\d+', part)
                if num_match:
                    try:
                        idx = int(num_match.group())
                        if 0 <= idx < len(search_results) and idx not in selected_indices:
                            selected_indices.append(idx)
                    except:
                        continue
            
        return [search_results[i] for i in selected_indices[:2]]

    # --- PATRÓN 2: ANÁLISIS DE CONTRASTE (WEB SCRAPING) ---

    def conduct_contrast_analysis(self, content_optimista: str, content_escetico: str, task_context: str) -> str:
        """
        Orquesta el patrón de debate entre dos contenidos con sesgos opuestos o complementarios.
        """
        
        # 1. Analista Optimista (El 'Pros')
        role_optimista = "Consultor Estratégico Optimista"
        system_prompt_optimista = "Tu perspectiva es inherentemente positiva y proactiva. Tu objetivo es destacar las oportunidades, los potenciales de crecimiento, las sinergias y las razones por las que el proyecto o tema en cuestión es viable. Articula tu análisis con un tono entusiasta y visionario."
        
        print("\n" + "="*20 + " -> INICIO DE DEBATE: PERSPECTIVA A " + "="*20)
        response_optimista = self._run_agent_task(
            role_optimista, system_prompt_optimista, content_optimista, f"Analiza los puntos fuertes y oportunidades de este contenido respecto a: {task_context}")

        # 2. Abogado del Diablo (El 'Contras')
        role_escetico = "Analista de Riesgos / Abogado del Diablo"
        system_prompt_escetico = "Tu perspectiva es inherentemente cautelosa y crítica. Tu objetivo es encontrar riesgos, debilidades, presuposiciones no verificadas y contradicciones. Nunca aceptes una premisa sin cuestionarla. Articula tu análisis con un tono sobrio, de advertencia y precaución."
        
        print("\n" + "="*20 + " -> INICIO DE DEBATE: PERSPECTIVA B " + "="*20)
        response_escetico = self._run_agent_task(
            role_escetico, system_prompt_escetico, content_escetico, f"Identifica riesgos significativos y debilidades estructurales en este contenido respecto a: {task_context}")

        # 3. Síntesis Final (Mediador)
        role_mediador = "Director de Análisis Senior"
        system_prompt_mediador = f"Tu tarea es sintetizar el debate. Debes crear una Matriz de Decisión de Riesgos/Oportunidades. IMPORTANTE: El informe final DEBE estar redactado íntegramente en el idioma del tema solicitado ('{task_context}')."
        
        task_mediador = f"""
        Basándote en los siguientes análisis de debate, redacta un informe final de "Matriz de Decisión" sobre: {task_context}.
        1. RESUMEN DEL DEBATE.
        2. MATRIZ RIESGO/OPORTUNIDAD.
        3. JUICIO FINAL Y ACCIÓN RECOMENDADA.
        
        ANÁLISIS DE PERSPECTIVA A: {response_optimista}
        ANÁLISIS DE PERSPECTIVA B: {response_escetico}
        """
        
        report = self._run_agent_task(role_mediador, system_prompt_mediador, "", task_mediador)
        return report

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
        4. Cita siempre: [Fuente Interna] o [Fuente Externa/Web].
        5. IMPORTANTE: Responde SIEMPRE en el mismo idioma en que se te ha planteado el tema ('{topic}').
        """

        combined_web = "\n\n".join(web_contents)
        context_hybrid = f"--- CONTENIDO LOCAL (BIE) ---\n{local_context}\n\n--- CONTENIDO WEB (EXTERNO) ---\n{combined_web}"

        task = f"""
        Realiza un análisis profundo sobre el tema: '{topic}'.
        Sigue la estructura de tu estrategia seleccionada y asegúrate de cumplir con todas las reglas de resolución de conflictos si es que los detectas. 
        El objetivo es dar una visión 360 al cliente.
        """

        return self._run_agent_task(role, system_prompt, context_hybrid, task)
