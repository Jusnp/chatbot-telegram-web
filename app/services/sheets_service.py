from __future__ import annotations

from pathlib import Path
import os
import re
import unicodedata

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials


load_dotenv(override=True)

BASE_DIR = Path(__file__).resolve().parents[2]

SHEET_KNOWLEDGE_FILE = (
    BASE_DIR / "data" / "conocimiento_sheet.txt"
)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly"
]


STOPWORDS = {
    "que", "como", "cual", "cuales",
    "donde", "cuando", "quien", "quienes",
    "para", "por", "con", "sin",
    "del", "las", "los", "una",
    "uno", "unos", "unas",
    "el", "la", "lo", "de",
    "en", "y", "o", "un",
    "es", "me", "mi", "se",
    "su", "sus"
}


def _normalizar(texto: str) -> str:
    texto = texto.lower()

    texto = unicodedata.normalize(
        "NFD",
        texto
    )

    texto = "".join(
        c
        for c in texto
        if unicodedata.category(c) != "Mn"
    )

    return texto


def _terminos(texto: str) -> list[str]:
    palabras = re.findall(
        r"[a-z0-9]+",
        _normalizar(texto)
    )

    return [
        palabra
        for palabra in palabras
        if (
            palabra not in STOPWORDS
            and (
                len(palabra) >= 3
                or palabra.isdigit()
            )
        )
    ]


def _numeros(texto: str) -> set[str]:
    return set(
        re.findall(
            r"\b\d+\b",
            _normalizar(texto)
        )
    )


def _get_client() -> gspread.Client:

    creds_file = os.getenv(
        "GOOGLE_SERVICE_ACCOUNT_FILE",
        "credentials/service_account.json"
    )

    creds_path = (
        BASE_DIR / creds_file
    )

    if not creds_path.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo "
            f"de credenciales en '{creds_path}'."
        )

    credentials = (
        Credentials.from_service_account_file(
            str(creds_path),
            scopes=SCOPES
        )
    )

    return gspread.authorize(
        credentials
    )


def _detectar_encabezado(
    filas: list[list[str]]
) -> int:
    """
    Busca entre las primeras filas cuál parece
    contener los encabezados de la tabla.
    """

    if not filas:
        return 0

    mejor_indice = 0
    mayor_columnas = 0

    limite = min(
        10,
        len(filas)
    )

    for indice in range(limite):

        cantidad = sum(
            1
            for celda in filas[indice]
            if celda.strip()
        )

        if cantidad > mayor_columnas:
            mayor_columnas = cantidad
            mejor_indice = indice

    return mejor_indice


def buscar_en_sheet(
    pregunta: str,
    limite: int = 3
) -> list[dict]:
    """
    Busca DIRECTAMENTE en el Google Sheet real.

    No utiliza conocimiento_sheet.txt para
    decidir si existe la información.
    """

    sheet_id = os.getenv(
        "GOOGLE_SHEET_ID"
    )

    if not sheet_id:
        print(
            "[SHEET] Falta GOOGLE_SHEET_ID."
        )
        return []

    client = _get_client()

    spreadsheet = client.open_by_key(
        sheet_id
    )

    terminos_pregunta = set(
        _terminos(pregunta)
    )

    numeros_pregunta = _numeros(
        pregunta
    )

    resultados = []

    for worksheet in spreadsheet.worksheets():

        filas = worksheet.get_all_values()

        if not filas:
            continue

        encabezado_index = (
            _detectar_encabezado(filas)
        )

        encabezados = filas[
            encabezado_index
        ]

        for numero_fila, fila in enumerate(
            filas[encabezado_index + 1:],
            start=encabezado_index + 2
        ):

            if not any(
                celda.strip()
                for celda in fila
            ):
                continue

            texto_fila = " | ".join(
                fila
            )

            texto_normalizado = (
                _normalizar(texto_fila)
            )

            numeros_fila = _numeros(
                texto_fila
            )

            # --------------------------------
            # Si preguntan por un número
            # específico, ese número DEBE
            # aparecer en la fila.
            # --------------------------------

            if numeros_pregunta:

                if not numeros_pregunta.issubset(
                    numeros_fila
                ):
                    continue

            terminos_fila = set(
                _terminos(texto_fila)
            )

            coincidencias = (
                terminos_pregunta
                & terminos_fila
            )

            score = 0

            for termino in coincidencias:

                if termino.isdigit():
                    score += 20
                else:
                    score += 3

            # Si hay un número exacto encontrado,
            # es una coincidencia muy importante.
            if numeros_pregunta:
                score += 50

            pregunta_normalizada = (
                _normalizar(pregunta)
            )

            if (
                pregunta_normalizada
                in texto_normalizado
            ):
                score += 30

            # Sin número necesitamos al menos
            # alguna coincidencia textual.
            if (
                not numeros_pregunta
                and len(coincidencias) == 0
            ):
                continue

            datos = {}

            for indice, encabezado in enumerate(
                encabezados
            ):

                if indice >= len(fila):
                    continue

                encabezado = encabezado.strip()
                valor = fila[indice].strip()

                if encabezado and valor:

                    datos[encabezado] = valor

            # Si no pudimos asociar encabezados,
            # conservamos igualmente la fila.
            if not datos:

                datos["Fila"] = texto_fila

            resultados.append({
                "hoja": worksheet.title,
                "fila": numero_fila,
                "datos": datos,
                "texto": texto_fila,
                "score": score
            })

    resultados.sort(
        key=lambda resultado: resultado["score"],
        reverse=True
    )

    print(
        f"[SHEET] Resultados encontrados: "
        f"{len(resultados)}"
    )

    return resultados[:limite]


def formatear_resultados_sheet(
    resultados: list[dict]
) -> str:

    if not resultados:
        return ""

    bloques = []

    for resultado in resultados:

        lineas = []

        for campo, valor in (
            resultado["datos"].items()
        ):

            lineas.append(
                f"• {campo}: {valor}"
            )

        bloques.append(
            "\n".join(lineas)
        )

    respuesta = (
        "Encontré esta información "
        "en el Google Sheet:\n\n"
        + "\n\n".join(bloques)
    )

    hojas = list(
        dict.fromkeys(
            resultado["hoja"]
            for resultado in resultados
        )
    )

    respuesta += (
        "\n\nFuente: Google Sheet → "
        + ", ".join(hojas)
    )

    return respuesta


def sync_sheet() -> int:
    """
    Mantiene la función anterior para crear
    conocimiento_sheet.txt cuando sea necesario.
    """

    sheet_id = os.getenv(
        "GOOGLE_SHEET_ID"
    )

    if not sheet_id:
        raise ValueError(
            "Falta configurar GOOGLE_SHEET_ID."
        )

    client = _get_client()

    spreadsheet = client.open_by_key(
        sheet_id
    )

    sections = []

    for worksheet in spreadsheet.worksheets():

        rows = [
            " | ".join(row)
            for row in worksheet.get_all_values()
            if any(
                cell.strip()
                for cell in row
            )
        ]

        if rows:

            sections.append(
                f"[Hoja: {worksheet.title}]\n"
                + "\n".join(rows)
            )

    SHEET_KNOWLEDGE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    SHEET_KNOWLEDGE_FILE.write_text(
        "\n\n".join(sections),
        encoding="utf-8"
    )

    return len(sections)