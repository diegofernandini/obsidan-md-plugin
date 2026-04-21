from typing import List, Optional
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
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
        
    def load_pdfs(self, file_path: str) -> List[str]:
        """
        Carga documentos de PDF y devuelve las cadenas de texto (chunks).
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"El archivo PDF no se encuentra en la ruta: {file_path}")
        
        print(f"Cargando documentos PDF desde: {file_path}...")
        loader = PyPDFLoader(file_path)
        documents = loader.load()
        
        # Extraemos el texto
        texts = [doc.page_content for doc in documents]
        return texts

    def scrape_url(self, url: str) -> str:
        """
        Realiza Web Scraping básico para extraer contenido de una URL.
        """
        print(f"🕸️ Intentando hacer Web Scraping en: {url}...")
        try:
            # Si es un PDF de arxiv u otro sitio
            if url.endswith('.pdf') or 'arxiv.org/pdf' in url:
                print(f"📄 Detectado PDF. Usando cargador de PDF para: {url}")
                # Descargar temporalmente el PDF
                temp_pdf = "temp_research_paper.pdf"
                r = requests.get(url, stream=True, timeout=20)
                with open(temp_pdf, 'wb') as f:
                    f.write(r.content)
                loader = PyPDFLoader(temp_pdf)
                docs = loader.load()
                text = "\n".join([doc.page_content for doc in docs])
                os.remove(temp_pdf)
                return f"*** CONTENIDO PDF ({url}) ***\n{text}"

            # Intentar simular un navegador para evitar bloqueos sencillos
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/ST/Lac'
            }
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status() # Lanza excepción para códigos de error HTTP
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Eliminar scripts y estilos
            for script in soup(["script", "style"]):
                script.extract()

            # Intentar obtener texto limpio
            text = soup.get_text(separator='\n', strip=True)
            
            # Limpieza final para evitar ruido
            cleaned_text = '\n'.join(filter(lambda x: len(x.strip()) > 20, text.split('\n')))
            
            if len(cleaned_text) < 100:
                 return f"[FALLO SCRAPING: Contenido muy corto o bloqueado. URL: {url}]"
            
            return f"*** FUENTE WEB ({url}) ***\n{cleaned_text}"
            
        except Exception as e:
            return f"[FALLO WEB SCRAPING: No se pudo acceder a la URL '{url}'. Error: {e}]"

    def search_arxiv(self, query: str, max_results: int = 3) -> List[dict]:
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

    def search_academic(self, query: str, max_results: int = 5) -> List[dict]:
        """
        Busca en la web general filtrando por dominios académicos.
        """
        # Filtros para dominios académicos
        academic_query = f"{query} (site:edu OR site:org OR site:nature.com OR site:science.org OR site:scholar.google.com)"
        print(f"🔎 Buscando fuentes académicas web: {query}...")
        
        results = []
        try:
            with DDGS() as ddgs:
                ddgs_results = list(ddgs.text(academic_query, max_results=max_results))
                for r in ddgs_results:
                    results.append({
                        "title": r['title'],
                        "summary": r['body'],
                        "url": r['href'],
                        "source": "Web Académica"
                    })
        except Exception as e:
            print(f"⚠️ Error en búsqueda académica DuckDuckGo: {e}")
            
        return results

    def get_combined_research(self, query: str) -> List[dict]:
        """
        Combina resultados de arXiv y búsqueda académica general.
        """
        arxiv_results = self.search_arxiv(query, max_results=2)
        web_results = self.search_academic(query, max_results=3)
        return arxiv_results + web_results


    def index_data(self, texts: List[str], source_type: str, directory: str = "faiss_index") -> str:
        """
        Divide el texto (de PDF o Web) y crea un índice FAISS.
        
        Args:
            texts: Lista de fragmentos de texto.
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
        chunks = text_splitter.create_documents(texts, metadict={"source": source_type})
        
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
