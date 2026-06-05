import os
import logging
from google import genai

# Configuración de logging - Subimos a INFO para ver resultados en consola
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class GeminiManager:
    def __init__(self, api_key):
        if not api_key:
            logger.error("La variable de entorno GEMINI_API_KEY no está configurada.")
            raise ValueError("GEMINI_API_KEY no configurada.")
        
        # Cliente correcto para el SDK 'google-genai'
        self.client = genai.Client(api_key=api_key)

    def list_models(self):
        try:
            logger.info("Solicitando lista de modelos a Google AI...")
            
            # El SDK nuevo usa client.models.list()
            models = self.client.models.list()
            
            print("\n--- Modelos Disponibles ---")
            found = False
            for model in models:
                # model.display_name es más legible, model.name es el ID técnico
                print(f"ID: {model.name} | Nombre: {model.display_name}")
                found = True
            
            if not found:
                print("No se encontraron modelos vinculados a esta API Key.")
            
            print("---------------------------\n")
            
        except Exception as e:
            logger.error(f"Error al listar modelos: {e}")

if __name__ == "__main__":
    # Asegúrate de haber hecho 'export GEMINI_API_KEY=tu_llave' en la terminal antes
    MI_API_KEY = os.getenv("GEMINI_API_KEY")
    
    try:
        manager = GeminiManager(MI_API_KEY)
        manager.list_models()
    except ValueError as ve:
        print(f"Error de configuración: {ve}")
    except Exception as e:
        print(f"Ocurrió un error inesperado: {e}")