from typing import List, Optional, Dict, Any
from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
import os
from bs4 import BeautifulSoup
import requests
import arxiv
from duckduckgo_search import DDGS

class DataIngestor:
    """
    Maneja la ingesta de documentos (PDF) y la indexación de fuentes web (URLs).
    """
    def __init__(self, embedding_model_name: str = "all-MiniLM-L6-v2"):
        # Usamos un embedding local robusto
        print(f"Inicializando embeddings con modelo: {embedding_model_name}...")
        self.embeddings = HuggingFaceEmbeddings(model_name=embedding_model_name)
        self.vectorstore = None
        
    def load_local_data(self, path: str) -> List[Dict[str, str]]:
        """
        Carga documentos (PDF, DOCX, TXT, MD) de un archivo o carpeta extrayendo el contenido y el nombre del archivo.
        """
        all_texts = []
        if os.path.isfile(path):
            file_paths = [path]
        elif os.path.isdir(path):
            # Buscar archivos con las extensiones soportadas de forma recursiva
            extensions = ('.pdf', '.docx', '.txt', '.md')
            file_paths = []
            
            for root, dirs, files in os.walk(path):
                # Ignorar carpetas ocultas o del sistema
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', 'venv', 'env']]
                for f in files:
                    if f.lower().endswith(extensions):
                        file_paths.append(os.path.join(root, f))
        else:
            if not os.path.exists(path):
                raise FileNotFoundError(f"La ruta no existe: {path}")
            file_paths = []

        if not file_paths:
            print(f"⚠️ No se encontraron archivos soportados en: {path}")
            return []

        print(f"📂 Encontrados {len(file_paths)} archivos. Iniciando carga...")
        for p in file_paths:
            ext = os.path.splitext(p)[1].lower()
            filename = os.path.basename(p)
            print(f"📄 Cargando {ext.upper()}: {filename}...")
            
            try:
                if ext == '.pdf':
                    loader = PyPDFLoader(p)
                elif ext == '.docx':
                    loader = Docx2txtLoader(p)
                elif ext in ['.txt', '.md']:
                    loader = TextLoader(p, encoding='utf-8')
                else:
                    continue

                documents = loader.load()
                for doc in documents:
                    all_texts.append({"text": doc.page_content, "source": filename})
            except Exception as e:
                print(f"❌ Error al cargar {p}: {e}")
        
        return all_texts

    def scrape_url(self, url: str) -> str:
        """
        Realiza Web Scraping básico para extraer contenido de una URL.
        """
        print(f"🕸️ Intentando hacer Web Scraping en: {url}...")
        try:
            if url.endswith('.pdf') or 'arxiv.org/pdf' in url:
                print(f"📄 Detectado PDF. Procesando enlace: {url}")
                
                # Usar un archivo temporal seguro
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                    temp_pdf_path = tmp_file.name
                
                try:
                    r = requests.get(url, stream=True, timeout=20)
                    # Verificar si realmente es un PDF
                    if 'application/pdf' not in r.headers.get('Content-Type', '').lower():
                        return f"[ERROR: La URL {url} no devolvió un PDF válido (Content-Type: {r.headers.get('Content-Type')})]"
                        
                    with open(temp_pdf_path, 'wb') as f:
                        f.write(r.content)
                    
                    loader = PyPDFLoader(temp_pdf_path)
                    docs = loader.load()
                    text = "\n".join([doc.page_content for doc in docs])
                    return f"*** CONTENIDO PDF ({url}) ***\n{text}"
                finally:
                    if os.path.exists(temp_pdf_path):
                        os.remove(temp_pdf_path)

            # Intentar simular un navegador para evitar bloqueos sencillos
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/ST/Lac'
            }
            response = requests.get(url, headers=headers, timeout=5)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Eliminar scripts y estilos
            for script in soup(["script", "style"]):
                script.extract()

            # Intentar obtener texto limpio
            text = soup.get_text(separator='\n')
            
            # Limpieza de espacios en blanco excesivos
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            # ESTAMPAR URL PARA BIBLIOGRAFÍA
            return f"--- FUENTE WEB: {url} ---\n{text[:10000]}"
            
        except Exception as e:
            return f"[ERROR al leer {url}: {str(e)}]"

    def search_arxiv(self, query: str, max_results: int = 5) -> List[dict]:
        """
        Busca artículos científicos en arXiv.
        """
        print(f"🔎 Buscando en arXiv: {query}...")
        try:
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.Relevance
            )
            results = []
            for res in search.results():
                results.append({
                    "title": res.title,
                    "summary": res.summary,
                    "url": res.pdf_url,
                    "source": "arXiv"
                })
            return results
        except Exception as e:
            print(f"⚠️ Error en búsqueda de arXiv: {e}")
            return []

    def search_academic(self, query: str, max_results: int = 8) -> List[dict]:
        """
        Busca en la web filtrando por dominios confiables.
        """
        # Filtros un poco más flexibles pero orientados a calidad
        academic_query = f"{query} (site:edu OR site:org OR site:nature.com OR site:ieee.org OR site:scholar.google.com)"
        print(f"🔎 Buscando fuentes de alta calidad: {query}...")
        
        results = []
        try:
            with DDGS() as ddgs:
                ddgs_results = list(ddgs.text(academic_query, max_results=max_results))
                for r in ddgs_results:
                    results.append({
                        "title": r['title'],
                        "summary": r['body'],
                        "url": r['href'],
                        "source": "Web Académica/Org"
                    })
        except Exception as e:
            print(f"⚠️ Error en búsqueda académica DuckDuckGo: {e}")
            
        return results

    def search_general(self, query: str, max_results: int = 8) -> List[dict]:
        """
        Busca en la web general sin filtros restrictivos (Contexto actual).
        """
        print(f"🔎 Buscando en la web general: {query}...")
        results = []
        try:
            with DDGS() as ddgs:
                ddgs_results = list(ddgs.text(query, max_results=max_results))
                for r in ddgs_results:
                    url = r['href'].lower()
                    # Filtrar ruido de soporte y dominios genéricos de "ayuda"
                    noise_domains = ['support.google.com', 'google.com/docs', 'microsoft.com', 'apple.com', 'youtube.com']
                    if any(domain in url for domain in noise_domains):
                        continue
                        
                    results.append({
                        "title": r['title'],
                        "summary": r['body'],
                        "url": r['href'],
                        "source": "Web General"
                    })
        except Exception as e:
            print(f"⚠️ Error en búsqueda general DuckDuckGo: {e}")
        return results

    def get_combined_research(self, queries: Dict[str, str]) -> List[dict]:
        """
        Combina arXiv (EN),Académico (EN) y General (ORIG).
        """
        # 1. Academia Global (Inglés)
        arxiv_results = self.search_arxiv(queries['en'], max_results=2)
        academic_results = self.search_academic(queries['en'], max_results=2)
        
        # 2. Contexto General (Idioma Original)
        general_results = self.search_general(queries['orig'], max_results=4)
        
        return arxiv_results + academic_results + general_results


    def index_data(self, texts: List[Any], source_type: str, directory: str = "faiss_index") -> str:
        """
        Divide el texto (de PDF o Web) y crea un índice FAISS.
        
        Args:
            texts: Lista de fragmentos de texto (strings) o diccionarios con 'text' y 'source'.
            source_type: Tipo de fuente ('PDF' o 'WEB').
            directory: Directorio donde se guardará el índice.
            
        Returns:
            Ruta del índice guardado.
        """
        if not texts:
            raise ValueError("No se proporcionaron textos para la indexación.")

        # 1. Dividir el texto en chunks recursivamente
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        chunks = []
        for x in texts:
            if isinstance(x, dict):
                content = x.get('text', '')
                meta = {"source": x.get('source', source_type), "type": source_type}
            else:
                content = x
                meta = {"source": source_type, "type": source_type}
                
            if content.strip():
                doc_chunks = text_splitter.create_documents([content], metadatas=[meta])
                chunks.extend(doc_chunks)

        
        # 2. Crear el vector store y guardarlo
        print(f"Creando índice vectorial FAISS con {len(chunks)} chunks...")
        self.vectorstore = FAISS.from_documents(chunks, self.embeddings)
        self.vectorstore.save_local(directory)
        
        return os.path.join(directory, "index.faiss")

    def get_retriever(self):
        """
        Retorna el objeto retriever configurado.
        """
        if self.vectorstore is None:
            raise RuntimeError("El índice de datos debe ser creado primero llamando a index_data().")
        return self.vectorstore.as_retriever(k=3)
