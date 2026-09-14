from pathlib import Path
import asyncio
import os

from dotenv import load_dotenv
from google import genai

load_dotenv(override=True)

BASE_DIR = Path(__file__).resolve().parents[2]
MANUAL_KNOWLEDGE_FILE = BASE_DIR / "data" / "conocimiento.txt"
DOCUMENT_KNOWLEDGE_FILE = BASE_DIR / "data" / "conocimiento_documentos.txt"


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def cargar_conocimiento() -> str:
    sections = []

    manual = _read_text(MANUAL_KNOWLEDGE_FILE)
    if manual:
        sections.append("===== INFORMACIÓN MANUAL =====\n" + manual)

    documents = _read_text(DOCUMENT_KNOWLEDGE_FILE)
    if documents:
        sections.append("===== DOCUMENTOS CARGADOS =====\n" + documents)

    return "\n\n".join(sections)


def _consultar_gemini(api_key: str, modelo: str, instrucciones: str, pregunta: str) -> str:
    client = genai.Client(api_key=api_key)

    try:
        interaction = client.interactions.create(
            model=modelo,
            system_instruction=instrucciones,
            input=pregunta,
        )

        texto = (interaction.output_text or "").strip()
        return texto or "No pude generar una respuesta en este momento."
    finally:
        client.close()


async def responder_pregunta(pregunta: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key or api_key == "pon_aqui_tu_clave_de_gemini":
        return (
            "El sistema está funcionando, pero falta configurar GEMINI_API_KEY "
            "en el archivo .env."
        )

    modelo = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    conocimiento = cargar_conocimiento()

    instrucciones = """
Eres un asistente virtual útil, claro y amable.
Responde siempre en español.

Prioriza la información proporcionada en la BASE DE CONOCIMIENTO.
Si la respuesta está en la base, úsala como fuente principal.
Cuando ayude al usuario, menciona de forma natural el nombre del documento fuente.

Si la base no contiene la respuesta, puedes responder con conocimiento general.
No inventes datos específicos de la organización, institución o documentos.
Si no sabes un dato específico, dilo claramente.
""".strip()

    if conocimiento:
        instrucciones += f"\n\nBASE DE CONOCIMIENTO:\n\n{conocimiento}"

    return await asyncio.to_thread(
        _consultar_gemini,
        api_key,
        modelo,
        instrucciones,
        pregunta,
    )
