from typing import List, Dict, Any, Optional, Tuple
from itertools import combinations
import time
from src.agent_manager import AgentManager
from src.data_ingestor import DataIngestor
import os
import re

class BlueprintEngine:
    """
    Orquesta flujos de trabajo multi-agente complejos (Blueprints).
    """
    def __init__(self, model_name: str = "llama3.1", log_callback=None, agent_manager=None, ingestor=None):
        self.agent_manager = agent_manager or AgentManager(model_name=model_name)
        self.ingestor = ingestor or DataIngestor()
        self.log_callback = log_callback

    def _log(self, message: str):
        print(message)
        if self.log_callback:
            self.log_callback(message)

    def run_research_roadmap(self, topic: str, vault_path: str = None) -> Dict[str, Any]:
        """
        Blueprint: Roadmap de Investigación.
        Secuencia: Estado del Arte -> Crítica de Brechas -> Visión Futura.
        """
        self._log(f"\n🚀 Iniciando Blueprint: ROADMAP DE INVESTIGACIÓN para '{topic}'")
        
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
        
        local_context = ""
        if vault_path:
            self._log(f"📂 Cargando contexto local de: {vault_path}")
            local_texts = self.ingestor.load_local_data(vault_path)
            if local_texts:
                log.append(f"Paso 1: Indexando documentos locales del Vault.")
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

## 4. BIBLIOGRAFÍA Y FUENTES
{chr(10).join([f"- [{s.get('title', 'Fuente Web')}]({s['url']})" for s in selected_web])}
- **Contexto Local:** {'Utilizado (Vault)' if vault_path else 'No utilizado'}

---
*Este reporte fue generado por MI-AI Intelligence usando una orquestación de agentes autónomos.*
"""
        return {
            "report": full_report,
            "transcript": "\n".join(log)
        }

    def run_synergy_matrix(self, topics: List[str], vault_path: str = None) -> Dict[str, Any]:
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
        local_texts = []
        if vault_path:
            self._log("📂 Cargando contexto local del Vault...")
            local_texts = self.ingestor.load_local_data(vault_path)
        else:
            # Fallback a carpeta data_sources si no hay vault_path
            local_texts = self.ingestor.load_local_data("data_sources")

        retriever = None
        if local_texts:
            self._log(f"🧠 Indexando {len(local_texts)} documentos locales para sinergia...")
            self.ingestor.index_data(local_texts, "LOCAL", "synergy_index")
            retriever = self.ingestor.get_retriever()

        # 1. Extraer esencia de cada concepto (Híbrido) - PROCESAMIENTO EN PARALELO
        from concurrent.futures import ThreadPoolExecutor
        essences = {}
        all_sources = []
        
        def process_single_topic(t):
            self._log(f"🔍 [PARALELO] Investigando esencia de: {t}...")
            # A. Contexto Web
            queries = self.agent_manager.generate_search_queries(t)
            web_res = self.ingestor.get_combined_research(queries)
            selected_web = self.agent_manager.select_best_sources(web_res, t)
            
            web_contents = []
            current_sources = []
            for s in selected_web[:5]: # Aumentado a 5 fuentes por tema
                content = self.ingestor.scrape_url(s['url'])
                web_contents.append(content[:5000])
                current_sources.append(s)
                
            web_context = "\n".join(web_contents)
            
            # B. Contexto Local
            local_context = ""
            if retriever:
                docs = retriever.invoke(t)
                local_context = "\n".join([d.page_content for d in docs[:3]])
                
            combined_item_context = f"--- WEB ---\n{web_context}\n\n--- LOCAL ---\n{local_context}"
            essence = self.agent_manager.extract_information(combined_item_context, t)
            return t, essence, current_sources

        # Lanzar hilos en paralelo
        self._log(f"🧵 Lanzando investigación paralela para {len(topics)} temas...")
        with ThreadPoolExecutor(max_workers=len(topics)) as executor:
            thread_results = list(executor.map(process_single_topic, topics))
            
        for t, essence, sources in thread_results:
            essences[t] = essence
            all_sources.extend(sources)
            log.append(f"Paso 1: Esencia de '{t}' extraída correctamente.")

        # 2. Agente Visionario busca sinergias
        self._log("\n🔮 PASO 2: Agente Visionario trazando conexiones disruptivas...")
        context_all = "\n\n".join([f"CONCEPTO {k}:\n{v}" for k, v in essences.items()])
        synergies = self.agent_manager._run_agent_task(
            "Arquitecto de Sinergias",
            "Tu misión es encontrar el 'puerto común' entre conceptos dispares. Debes crear una Matriz de Sinergias donde expliques cómo A potencia a B, y qué solución nueva surge de la unión de ambos. Cita tus fuentes locales o web si son necesarias.",
            context_all,
            f"Crea una Matriz de Sinergias para: {combined_topics}. Enfócate en innovación radical y usa los datos locales si aportan valor diferencial."
        )
        
        log_sinergia = synergies[:200].replace('\n', ' ') + "..."
        log.append(f"Paso 2: Agente [Visionario] detectó una oportunidad de unión: '{log_sinergia}'")

        # Construir bibliografía unificada
        unique_urls = {s['url']: s for s in all_sources}.values()
        biblio_links = "\n".join([f"- [{s.get('title', 'Fuente Web')}]({s['url']})" for s in unique_urls])

        full_report = f"""
# MATRIZ DE SINERGIAS HÍBRIDA: {combined_topics.upper()}

## ANÁLISIS DE INTERSECCIÓN DISRUPTIVA (LOCAL + WEB)
{synergies}

## BIBLIOGRAFÍA Y FUENTES CONSULTADAS
{biblio_links}
- **Contexto Local:** {'Utilizado (Vault)' if vault_path else 'No utilizado'}

---
*Este reporte fue generado por MI-AI Intelligence usando una orquestación de agentes autónomos.*
"""
        return {
            "report": full_report,
            "transcript": "\n".join(log)
        }

    def _normalize_explore_concepts(self, topics: List[str]) -> Tuple[List[str], Optional[str]]:
        """
        Devuelve (conceptos_ok, mensaje_error). Entre 2 y 5 conceptos no vacíos.
        """
        if not topics:
            return [], "Se requieren al menos 2 conceptos separados por comas."
        cleaned = [t.strip() for t in topics if t and str(t).strip()]
        if len(cleaned) < 2:
            return [], "Se requieren al menos 2 conceptos no vacíos."
        if len(cleaned) > 5:
            # Plan: máximo 5; truncar con aviso
            cleaned = cleaned[:5]
        return cleaned, None

    def _build_literature_search_axes(self, concepts: List[str]) -> List[Tuple[str, str]]:
        """
        Ejes deterministas: un single por concepto, pares (cap 6 si n=5), y eje full si n<=4.
        Cada tupla es (etiqueta_eje, query_en_ingles).
        """
        axes: List[Tuple[str, str]] = []
        for c in concepts:
            axes.append((f"single:{c}", c.strip()))

        pair_list = list(combinations(concepts, 2))
        if len(concepts) == 5 and len(pair_list) > 6:
            pair_list = pair_list[:6]

        for a, b in pair_list:
            q = f'relationship between "{a}" and "{b}" interdisciplinary research'
            axes.append((f"pair:{a}|{b}", q))

        if 2 <= len(concepts) <= 4:
            quoted = " ".join(f'"{c}"' for c in concepts)
            axes.append(
                (f"full:{'+'.join(concepts)}", f"{quoted} survey systematic review interdisciplinary")
            )
        return axes

    def _dedupe_hits_by_url(self, hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        by_url: Dict[str, Dict[str, Any]] = {}
        for h in hits:
            url = h.get("url") or ""
            if not url:
                continue
            axis = h.get("axis", "")
            if url not in by_url:
                row = {k: v for k, v in h.items() if k != "axis"}
                row["axes"] = [axis] if axis else []
                by_url[url] = row
            else:
                if axis and axis not in by_url[url]["axes"]:
                    by_url[url]["axes"].append(axis)
        return list(by_url.values())

    def run_literature_relation_exploration(
        self, topics: List[str], vault_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Blueprint: exploración multi-concepto por literatura (fan-out académico).

        A diferencia de `/synergy`, que investiga cada tema en paralelo y luego busca
        sinergias en texto ya resumido, este flujo lanza consultas explícitas por eje
        (concepto suelto, pares, y tupla completa si n<=4) contra arXiv y búsqueda
        académica, fusiona resultados y produce un informe por eje más síntesis cruzada.
        """
        log: List[str] = []
        non_empty = [str(t).strip() for t in (topics or []) if t and str(t).strip()]
        if len(non_empty) > 5:
            self._log("⚠️ Más de 5 conceptos en entrada; se usarán solo los 5 primeros.")
        concepts, err = self._normalize_explore_concepts(topics)
        if err:
            self._log(f"❌ {err}")
            return {"report": f"# Error\n\n{err}", "transcript": err}

        combined_label = ", ".join(concepts)
        self._log(
            f"\n🚀 Blueprint: EXPLORACIÓN LITERARIA MULTI-CONCEPTO ({len(concepts)} conceptos)"
        )
        log.append("--- INICIO: EXPLORACIÓN LITERARIA (RELACIONES) ---")
        log.append(f"Conceptos: {combined_label}")
        if len(non_empty) > 5:
            log.append("Aviso: entrada con más de 5 conceptos; truncado a 5.")

        axes = self._build_literature_search_axes(concepts)
        self._log(f"📐 Ejes de búsqueda definidos: {len(axes)}")
        log.append(f"Paso 0: {len(concepts)} conceptos, {len(axes)} ejes de consulta.")

        all_hits: List[Dict[str, Any]] = []
        axis_buckets: Dict[str, List[Dict[str, Any]]] = {label: [] for label, _ in axes}

        ARXIV_N = 2
        ACAD_N = 2

        for axis_label, en_query in axes:
            self._log(f"🔎 Eje [{axis_label}]: {en_query[:120]}...")
            try:
                chunk: List[Dict[str, Any]] = []
                try:
                    chunk.extend(self.ingestor.search_arxiv(en_query, max_results=ARXIV_N))
                except Exception as ex:
                    self._log(f"⚠️ arXiv falló en eje {axis_label}: {ex}")
                    log.append(f"arXiv error [{axis_label}]: {ex}")
                try:
                    chunk.extend(
                        self.ingestor.search_academic(en_query, max_results=ACAD_N)
                    )
                except Exception as ex:
                    self._log(f"⚠️ búsqueda académica falló en eje {axis_label}: {ex}")
                    log.append(f"Academic DDG error [{axis_label}]: {ex}")

                for h in chunk:
                    row = dict(h)
                    row["axis"] = axis_label
                    all_hits.append(row)
                    axis_buckets[axis_label].append(dict(h))

            except Exception as ex:
                self._log(f"⚠️ Eje completo falló [{axis_label}]: {ex}")
                log.append(f"Eje fallido [{axis_label}]: {ex}")

            time.sleep(0.35)

        deduped = self._dedupe_hits_by_url(all_hits)
        self._log(f"📚 URLs únicas tras fusión: {len(deduped)}")
        log.append(f"Paso 1: {len(deduped)} fuentes únicas (todas las ejes).")

        for_llm = []
        for d in deduped:
            for_llm.append(
                {
                    "title": d.get("title", ""),
                    "summary": d.get("summary", ""),
                    "url": d.get("url", ""),
                    "source": d.get("source", ""),
                }
            )

        if not for_llm:
            msg = "No se recuperaron fuentes en ningún eje. Prueba otros términos o revisa la conexión."
            self._log(f"❌ {msg}")
            log.append(msg)
            return {
                "report": f"# Exploración literaria: {combined_label}\n\n{msg}",
                "transcript": "\n".join(log),
            }

        self._log("🧭 Curación global de fuentes (LLM)...")
        selected = self.agent_manager.select_best_sources(for_llm, combined_label)
        selected_urls = {s["url"] for s in selected}
        log.append(f"Paso 2: Tras curación, {len(selected)} fuentes priorizadas.")

        MAX_SCRAPE = 10
        scraped_by_url: Dict[str, str] = {}
        for i, src in enumerate(selected[:MAX_SCRAPE]):
            self._log(f"🕸️ Scraping ({i + 1}/{min(len(selected), MAX_SCRAPE)}): {src.get('title', '')[:60]}...")
            try:
                scraped_by_url[src["url"]] = self.ingestor.scrape_url(src["url"])[:8000]
            except Exception as ex:
                scraped_by_url[src["url"]] = f"[scrape error: {ex}]"
            time.sleep(0.2)

        # --- Secciones por eje (solo fuentes que pasaron a selected) ---
        axis_sections_md: List[str] = []
        for axis_label, _ in axes:
            lines = [f"### Eje `{axis_label}`\n"]
            bucket = axis_buckets.get(axis_label, [])
            seen = set()
            any_row = False
            for h in bucket:
                u = h.get("url", "")
                if u not in selected_urls or u in seen:
                    continue
                seen.add(u)
                any_row = True
                title = h.get("title", "Sin título")
                summ = (h.get("summary") or "")[:400].replace("\n", " ")
                lines.append(f"- [{title}]({u}) — _{summ}_")
            if not any_row:
                lines.append("_Ninguna fuente de este eje entró en el conjunto curado final._")
            axis_sections_md.append("\n".join(lines))

        # Contexto agregado para síntesis (resúmenes + snippets)
        digest_parts: List[str] = []
        for s in selected:
            u = s["url"]
            digest_parts.append(
                f"### {s.get('title', '')}\nURL: {u}\nResumen búsqueda: {s.get('summary', '')}\n"
                f"Snippet:\n{scraped_by_url.get(u, '')[:4000]}\n"
            )
        digest = "\n".join(digest_parts)

        self._log("✍️ Síntesis cruzada (curador académico)...")
        synthesis = self.agent_manager._run_agent_task(
            "Curador académico / revisión sistemática",
            "Integras evidencia de varias consultas académicas. Explicas qué relaciones entre "
            "los conceptos aparecen en la literatura recuperada, qué tensiones o vacíos hay, y "
            "qué líneas de lectura recomiendas. Cita con [título](URL). Sin inventar papers que "
            "no estén en el digest.",
            digest,
            f"Conceptos: {combined_label}. Responde en el mismo idioma predominante de esos conceptos.",
        )
        log.append("Paso 3: Síntesis cruzada generada.")

        biblio = "\n".join(
            sorted(
                {
                    f"- [{s.get('title', 'Fuente')}]({s['url']})"
                    for s in selected
                    if s.get("url")
                }
            )
        )

        full_report = f"""# Exploración literaria por relaciones: {combined_label}

## Resumen ejecutivo
Fan-out académico en **{len(axes)}** ejes (singles, pares{" y tupla completa" if len(concepts) <= 4 else ""}), **{len(deduped)}** URLs únicas, **{len(selected)}** fuentes tras curación.

## Hallazgos por eje de búsqueda

{chr(10).join(axis_sections_md)}

## Síntesis cruzada y vacíos

{synthesis}

## Bibliografía (fuentes curadas)

{biblio}

---
*Generado por MI-AI — Blueprint de exploración literaria multi-concepto.*
"""
        log.append("--- FIN: EXPLORACIÓN LITERARIA ---")
        return {"report": full_report, "transcript": "\n".join(log)}

    def run_batch_organize(self, vault_path: str) -> Dict[str, Any]:
        """
        Blueprint: Organizador Incremental de Bóveda.
        Escanea el vault completo, salta archivos que ya tienen YAML frontmatter,
        y organiza solo los nuevos. Salida en [vault]/Organizados/
        """
        self._log(f"\n🚀 Iniciando Blueprint: ORGANIZADOR INCREMENTAL DEL VAULT")
        log = []

        if not vault_path:
            self._log("❌ LOG: Error: No se proporcionó vault_path.")
            return {"report": "Fallo: Vault Path no proveído.", "transcript": "\n".join(log)}

        # Carpeta de salida en la raíz del vault
        organized_dir = os.path.join(vault_path, "Organizados")
        os.makedirs(organized_dir, exist_ok=True)

        # Escanear TODOS los .md del vault (recursivo), excluyendo la propia carpeta Organizados
        all_md = []
        for root, dirs, files in os.walk(vault_path):
            # Excluir carpetas del sistema y la propia salida
            dirs[:] = [d for d in dirs if d not in ['.obsidian', '.git', 'Organizados', 'MI-AI Reports']]
            for f in files:
                if f.lower().endswith('.md'):
                    all_md.append(os.path.join(root, f))

        if not all_md:
            self._log("⚠️ LOG: No se encontraron archivos .md en el vault.")
            return {"report": "Sin archivos Markdown en el vault.", "transcript": "\n".join(log)}

        # Filtro incremental: saltar archivos que ya tienen frontmatter YAML
        def has_frontmatter(path: str) -> bool:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    first_line = f.readline().strip()
                return first_line == '---'
            except:
                return False

        pending = [f for f in all_md if not has_frontmatter(f)]
        skipped = len(all_md) - len(pending)

        self._log(f"LOG: 📊 {len(all_md)} notas en el vault. {skipped} ya organizadas (saltadas). {len(pending)} pendientes.")

        if not pending:
            return {
                "report": f"✅ Todas las {len(all_md)} notas ya tienen frontmatter YAML. No hay nada nuevo que organizar.",
                "transcript": "\n".join(log)
            }

        # --- Indexar el vault completo para visión sistémica (wikilinks reales) ---
        self._log("LOG: 🧠 Indexando vault para contexto sistémico...")
        vault_texts = self.ingestor.load_local_data(vault_path)
        retriever = None
        if vault_texts:
            self.ingestor.index_data(vault_texts, "LOCAL", "batch_organize_index")
            retriever = self.ingestor.get_retriever()
            self._log(f"LOG: ✅ Vault indexado. {len(vault_texts)} documentos en contexto.")

        system_prompt = """Eres el Arquitecto de Bóveda de Obsidian. Tu misión es reestructurar notas añadiendo:
1. YAML frontmatter con tags descriptivos y metadatos relevantes.
2. Wikilinks [[Nota Relacionada]] cuando detectes referencias a otras notas del vault.
3. Formato Markdown limpio manteniendo TODO el contenido original sin omitir nada.
REGLA ABSOLUTA: Retorna ÚNICAMENTE el contenido Markdown final. Sin bloques de código envolventes (```), sin explicaciones, sin saludos."""

        processed = 0
        for i, file_path in enumerate(pending):
            filename = os.path.basename(file_path)
            self._log(f"LOG: ⏳ [{i + 1}/{len(pending)}] {filename}...")

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Recuperar notas relacionadas del vault para contexto sistémico
                vault_context = ""
                if retriever:
                    related_docs = retriever.invoke(content[:500])
                    context_blocks = []
                    for d in related_docs:
                        source = d.metadata.get('source', '')
                        basename = os.path.basename(str(source)).replace('.md', '')
                        if basename != filename.replace('.md', ''):
                            context_blocks.append(f"[[{basename}]]: {d.page_content[:200]}")
                    vault_context = "\n".join(context_blocks)

                task = f"""Organiza la siguiente nota. Añade Frontmatter YAML con tags relevantes. 
Usa Wikilinks [[NombreNota]] si detectas referencias a las siguientes notas del vault:
{vault_context if vault_context else "No hay contexto adicional."}

NOTA A ORGANIZAR:
{content}"""

                response = self.agent_manager._run_agent_task("Arquitecto", system_prompt, "", task)

                # Limpieza defensiva
                for prefix in ["```markdown\n", "```md\n", "```\n"]:
                    if response.startswith(prefix):
                        response = response[len(prefix):]
                if response.endswith("```"):
                    response = response[:-3]
                response = response.strip()

                # Guardar con ruta relativa preservada dentro de Organizados/
                rel_path = os.path.relpath(file_path, vault_path)
                out_path = os.path.join(organized_dir, rel_path)
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                with open(out_path, "w", encoding="utf-8") as out_f:
                    out_f.write(response)

                processed += 1
                self._log(f"LOG: ✅ {filename} listo.")

            except Exception as e:
                self._log(f"LOG: ❌ Error en {filename}: {str(e)}")

        summary = (
            f"🎉 Organización incremental completada.\n"
            f"- Procesadas: **{processed}** notas nuevas\n"
            f"- Saltadas (ya organizadas): **{skipped}**\n"
            f"- Revisa los resultados en la carpeta `Organizados/` de tu vault."
        )
        self._log(f"LOG: {summary}")
        return {"report": summary, "transcript": "\n".join(log)}


        # --- PASO 1: Indexar el VAULT COMPLETO para visión sistémica ---
        self._log(f"LOG: 🧠 Indexando vault completo para visión sistémica...")
        vault_texts = self.ingestor.load_local_data(vault_path)
        retriever = None
        if vault_texts:
            self.ingestor.index_data(vault_texts, "LOCAL", "batch_organize_index")
            retriever = self.ingestor.get_retriever()
            self._log(f"LOG: ✅ Vault indexado. {len(vault_texts)} archivos en contexto.")
        else:
            self._log("LOG: ⚠️ No se encontraron documentos en el vault para indexar.")

        # Crear carpeta de destino (sobreescribe si ya existe)
        organized_dir = os.path.join(abspathtarget, "Organizados")
        os.makedirs(organized_dir, exist_ok=True)

        # Enlistar MDs en la carpeta objetivo
        md_files = [f for f in os.listdir(abspathtarget)
                    if f.lower().endswith('.md') and os.path.isfile(os.path.join(abspathtarget, f))]

        if not md_files:
            self._log(f"⚠️ LOG: No se encontraron archivos .md en '{target_folder}'.")
            return {"report": f"Sin archivos para organizar en '{target_folder}'.", "transcript": "\n".join(log)}

        self._log(f"LOG: 📂 {len(md_files)} archivos encontrados para organizar.")

        system_prompt = """Eres el Arquitecto de Bóveda de Obsidian. Tu misión es reestructurar notas añadiendo:
1. YAML frontmatter con tags descriptivos y metadatos.
2. Wikilinks [[Nota Relacionada]] cuando el contexto de otras notas del vault sea relevante.
3. Formato Markdown limpio y profesional manteniendo todo el contenido original.
REGLA ABSOLUTA: Retorna ÚNICAMENTE el contenido Markdown final. Sin bloques de código envolventes, sin explicaciones, sin saludos."""

        processed = 0
        for i, filename in enumerate(md_files):
            file_path = os.path.join(abspathtarget, filename)
            self._log(f"LOG: ⏳ [{i + 1}/{len(md_files)}] Organizando: {filename}...")

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # --- PASO 2: Recuperar notas relacionadas del vault para contexto sistémico ---
                vault_context = ""
                if retriever:
                    related_docs = retriever.invoke(content[:500])  # usar inicio del archivo como query
                    context_blocks = []
                    for d in related_docs:
                        source = d.metadata.get('source', '')
                        basename = os.path.basename(str(source)).replace('.md', '')
                        if basename != filename.replace('.md', ''):  # excluir el mismo archivo
                            context_blocks.append(f"--- NOTA RELACIONADA EN VAULT: [[{basename}]] ---\n{d.page_content[:300]}")
                    vault_context = "\n\n".join(context_blocks)

                task = f"""Reconfigura profesionalmente el siguiente archivo para Obsidian.
Añade Frontmatter YAML con tags relevantes. Usa Wikilinks [[NombreNota]] cuando detectes referencias a las notas relacionadas del vault.

NOTAS RELACIONADAS EN EL VAULT (para crear wikilinks reales):
{vault_context if vault_context else "No se encontraron notas relacionadas."}

CONTENIDO DEL ARCHIVO A ORGANIZAR:
{content}"""

                response = self.agent_manager._run_agent_task("Arquitecto", system_prompt, "", task)

                # Limpieza defensiva de bloques de código
                for prefix in ["```markdown\n", "```md\n", "```\n"]:
                    if response.startswith(prefix):
                        response = response[len(prefix):]
                if response.endswith("```"):
                    response = response[:-3]
                response = response.strip()

                # Sobreescribir si ya existe (comportamiento inteligente)
                out_path = os.path.join(organized_dir, filename)
                with open(out_path, "w", encoding="utf-8") as out_f:
                    out_f.write(response)

                processed += 1
                self._log(f"LOG: ✅ {filename} listo.")
            except Exception as e:
                self._log(f"LOG: ❌ Error en {filename}: {str(e)}")

        summary = f"🎉 Batch finalizado: {processed}/{len(md_files)} archivos organizados en '{target_folder}/Organizados/'. Re-ejecutar el comando actualiza los archivos existentes."
        self._log(f"LOG: {summary}")
        log.append("--- FIN DE BLUEPRINT BATCH ---")
        return {
            "report": summary,
            "transcript": "\n".join(log)
        }
