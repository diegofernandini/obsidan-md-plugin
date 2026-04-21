# 🌐 Arquitectura Detallada del Systemus (El Diagrama del Pensamiento)

## 🔬 1. Nivel de Entrada (Input Layer)
La información viene de dos fuentes, pero siempre se normaliza a *chunks* de texto:
- **PDFs:** Documentos legales, *whitepapers*, informes de la industria.
- **Web:** Artículos de noticias, comunicados de prensa.

## 🧠 2. Nivel de Memoria (Knowledge Base)
*   **Componente:** DataIngestor
*   **Proceso:** Chunking $\rightarrow$ Embedding $\rightarrow$ Indexación (FAISS).
*   **Output:** Un vectorstore que permite la búsqueda semántica.

## 🤖 3. Nivel de Orquestación (The AgentManager)
Este es el "cerebro". Recibe la consulta y coordina el diálogo.

### 🔁 Flujo de Consulta (Ejemplo: Tokenización)
1. **Input:** Tarea + Contexto Recuperado (RAG).
2. **Desglose (Pattern):** El sistema activa el patrón "Análisis 360°", asignando el contexto a 3 sesiones de LLM.
3. **Ejecución Paralela:**
    *   `RegulatorioAgent`: Filtra por riesgos de AML/GDPR.
    *   `EconomicAgent`: Filtra por impactos macro y ciclos de crédito.
    *   `TechAgent`: Filtra por viabilidad técnica y arquitectura.
4. **Síntesis:** El Manager recibe los 3 informes y los compila en la conclusión final del informe ejecutivo.
---
