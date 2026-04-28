---
# 🧠 Knowledge System PoC: MI-AI (Inteligencia de Mercado Artificial)
## La Propuesta de Valor: Su Segundo Cerebro Corporativo

El MI-AI transforma la complejidad de la investigación (múltiples fuentes, múltiples disciplinas) en **Informes Ejecutivos estructurados y listos para la toma de decisiones.**

Nuestro objetivo principal es resolver el principal cuello de botella de la consultoría moderna: **la dispersión y el tiempo dedicado a sintetizar la información.**

**Diferenciador Clave:** El MI-AI no solo responde; demuestra **CÓMO** se llegó a la respuesta, forzando un diálogo visible entre especialistas virtuales. Esto genera confianza y permite la auditoría intelectual del análisis.

---

## ⚙️ ARQUITECTURA Y BACKEND: AUTO-HOSTED LLMs

El sistema está diseñado para ejecutarse con modelos de lenguaje localmente vía **Ollama**. Esto garantiza **privacidad total** y elimina la dependencia de APIs de terceros, lo que es fundamental para la gestión de datos sensibles.

### 💻 Requisito de Ejecución
*   **Ollama:** Debe estar instalado y corriendo en segundo plano.
*   **Modelo Local:** Debe haber descargado un modelo compatible (ej: `llama2`, `mistral`) usando el comando `ollama pull <nombre_modelo>`.

---

## 🔍 Arquitectura Multi-Agente: El Motor del Análisis

El sistema sigue manteniendo la orquestación de roles, pero el motor de razonamiento ahora se alimenta de modelos locales.

### 🏛️ Tipologías de Agentes (Los Especialistas):
*   **Agente Extractor/Detective:** (Rol: Detective). Extrae datos sin interpretación.
*   **Agente Sintetizador/Curador:** (Rol: Editor en jefe). Crea la narrativa coherente.
*   **Agente Analista Crítico:** (Rol: Crítico). Busca falencias lógicas.
*   **Agente Generativo:** (Rol: Visionario). Propone nuevas hipótesis.

---

## 🌐 Fuentes de Datos (El Combustible)

El *backend* sigue soportando múltiples fuentes de información:

1.  **Base de Conocimiento Documental:** (RAG - PDF/Documentos)
    *   *Mecanismo:* Vectorización y búsqueda semántica.
2.  **Web Crawling:** (URLs proporcionadas)
    *   *Mecanismo:* Scraping avanzado para contenido web.

---

## 🚀 Roadmap de Desarrollo (Rumbo al Producto Completo)

*   **FASE 1 (Completado):** Analista de Texto Avanzado (PDF/Documentos).
*   **FASE 2 (Actual): Investigador Web Básico:**
    *   *Foco:* Integrar Web Scraping y el patrón de Debate.
    *   *Resultado:* La capacidad de comparar perspectivas basadas en fuentes en tiempo real (URLs).
*   **FASE 3: Maestría: Laboratorio de Ideas:** (Mantener el enfoque en la orquestación total).