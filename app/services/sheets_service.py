from __future__ import annotations

from pathlib import Path
import os

import gspread
from google.oauth2.service_account import Credentials

BASE_DIR = Path(__file__).resolve().parents[2]
SHEET_KNOWLEDGE_FILE = BASE_DIR / "data" / "conocimiento_sheet.txt"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def _get_client() -> gspread.Client:
    creds_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials/service_account.json")
    creds_path = BASE_DIR / creds_file

    if not creds_path.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo de credenciales en '{creds_path}'. "
            "Crea una cuenta de servicio de Google, descarga el JSON y colócalo ahí."
        )

    credentials = Credentials.from_service_account_file(str(creds_path), scopes=SCOPES)
    return gspread.authorize(credentials)


def sync_sheet() -> int:
    """Descarga todas las pestañas de la hoja configurada y las guarda como texto.

    Devuelve la cantidad de pestañas sincronizadas.
    """
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    if not sheet_id:
        raise ValueError("Falta configurar GOOGLE_SHEET_ID en el archivo .env.")

    client = _get_client()
    spreadsheet = client.open_by_key(sheet_id)

    sections = []
    for worksheet in spreadsheet.worksheets():
        rows = [" | ".join(row) for row in worksheet.get_all_values() if any(cell.strip() for cell in row)]
        if rows:
            sections.append(f"[Hoja: {worksheet.title}]\n" + "\n".join(rows))

    SHEET_KNOWLEDGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    SHEET_KNOWLEDGE_FILE.write_text("\n\n".join(sections), encoding="utf-8")

    return len(sections)
