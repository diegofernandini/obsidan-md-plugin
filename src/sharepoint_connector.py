import os
import tempfile
from typing import List, Dict, Any
from office365.sharepoint.client_context import ClientContext
from office365.runtime.auth.client_credential import ClientCredential
from office365.sharepoint.files.file import File

class SharePointConnector:
    """
    Maneja la conexión y descarga de archivos desde SharePoint.
    """
    def __init__(self, site_url: str, client_id: str, client_secret: str):
        self.site_url = site_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.ctx = self._get_context()

    def _get_context(self):
        """Establece el contexto de cliente usando credenciales de App-Only."""
        print(f"Conectando a SharePoint: {self.site_url}...")
        credentials = ClientCredential(self.client_id, self.client_secret)
        return ClientContext(self.site_url).with_credentials(credentials)

    def download_folder_files(self, folder_relative_url: str, target_dir: str) -> List[str]:
        """
        Descarga todos los archivos soportados de una carpeta de SharePoint a un directorio local.
        """
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)

        print(f"Explorando carpeta en SharePoint: {folder_relative_url}...")
        library_root = self.ctx.web.get_folder_by_server_relative_url(folder_relative_url)
        files = library_root.files
        self.ctx.load(files)
        self.ctx.execute_query()

        downloaded_paths = []
        supported_extensions = ('.pdf', '.docx', '.txt', '.md')

        for sp_file in files:
            file_name = sp_file.properties['Name']
            if file_name.lower().endswith(supported_extensions):
                print(f"⬇️ Descargando de SharePoint: {file_name}...")
                local_path = os.path.join(target_dir, file_name)
                
                with open(local_path, "wb") as local_file:
                    sp_file.download(local_file).execute_query()
                
                downloaded_paths.append(local_path)
        
        return downloaded_paths

    def test_connection(self) -> bool:
        """Verifica si la conexión es exitosa."""
        try:
            web = self.ctx.web
            self.ctx.load(web)
            self.ctx.execute_query()
            print(f"✅ Conexión exitosa al sitio: {web.properties['Title']}")
            return True
        except Exception as e:
            print(f"❌ Error de conexión a SharePoint: {e}")
            return False
