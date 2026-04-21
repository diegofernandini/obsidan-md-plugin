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
        system_prompt = "Tu función es dar cohesión y narrativa. Tomas la información fragmentada (los datos extraídos) y la transformas en un informe ejecutivo fluido, coherente y listo para la presentación en una junta directiva. Debes identificar la tesis principal y los puntos de riesgo/oportunidad."
        task = f"Utiliza los hallazgos y datos estructurados que te proporciono a continuación. Redacta un informe ejecutivo de análisis de mercado. El informe debe tener: 1) Tesis Central (la respuesta directa), 2) Argumentos Clave (desarrollando los puntos), y 3) Recomendaciones Estratégicas (acciones recomendadas). Asegúrate de que el tono sea profesional, de alto impacto y accionable. Datos a usar:\n\n{extracted_data}"
        return self._run_agent_task(role, system_prompt, "", task)

    # --- PATRÓN 2: INVESTIGADOR REFENCIADO (WEB AUTÓNOMA) ---

    def select_best_sources(self, search_results: List[Dict[str, Any]], task_context: str) -> List[Dict[str, Any]]:
        """
        El Agente Investigador analiza los resultados de búsqueda y elige los más relevantes.
        """
        role = "Investigador / Curador de Contenido Científico"
        system_prompt = "Eres un experto en bibliometría y análisis de fuentes. Tu tarea es evaluar una lista de resultados de búsqueda (Título, Resumen, Fuente) y seleccionar los 2 resultados más prometedores y rigurosos para un análisis profundo. Justifica brevemente tu elección."
        
        # Preparar la lista para el LLM
        formatted_list = ""
        for i, res in enumerate(search_results):
            formatted_list += f"\n[{i}] TÍTULO: {res['title']}\nRESUMEN: {res['summary']}\nFUENTE: {res['source']}\n"

        task = f"Analiza los siguientes resultados de búsqueda para el objetivo: '{task_context}'. \nResultados:\n{formatted_list}\n\nResponde ÚNICAMENTE con los índices (ej: 0, 2) de los 2 mejores resultados, seguidos de una breve justificación."
        
        selection_response = self._run_agent_task(role, system_prompt, "", task)
        print(f"\n✅ Justificación del Investigador: {selection_response}")
        
        # Intentar extraer los índices (muy rudimentario, mejorable con regex)
        # Por ahora, simplemente tomaremos los índices si aparecen en el texto
        selected_indices = []
        for i in range(len(search_results)):
            if str(i) in selection_response.split('\n')[0]: # Buscamos en la primera línea
                selected_indices.append(i)
        
        # Si falló la extracción, tomamos los 2 primeros por defecto
        if not selected_indices:
            selected_indices = [0, 1]
            
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
        system_prompt_mediador = "Tu tarea es sintetizar el debate. Debes actuar como el Director que escucha a las dos partes y, en lugar de simplemente listar pros y contras, debe crear una Matriz de Decisión de Riesgos/Oportunidades. Tu tono debe ser decisivo y balanceado. Nunca tomes partido, solo presenta el estado del arte y la decisión recomendada basada en el riesgo residual."
        
        task_mediador = f"""
        Basándote en los siguientes análisis de debate, redacta un informe final de "Matriz de Decisión".
        1. RESUMEN DEL DEBATE: (Brevemente, qué ha dicho cada parte).
        2. MATRIZ RIESGO/OPORTUNIDAD: (Crear una tabla/lista comparativa).
        3. JUICIO FINAL: (Una conclusión equilibrada y la siguiente acción recomendada al cliente).
        
        ANÁLISIS DE PERSPECTIVA A: {response_optimista}
        ANÁLISIS DE PERSPECTIVA B: {response_escetico}
        """
        
        report = self._run_agent_task(role_mediador, system_prompt_mediador, "", task_mediador)
        return report
