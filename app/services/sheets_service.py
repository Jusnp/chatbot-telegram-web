from __future__ import annotations

from pathlib import Path
from time import monotonic
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

CACHE_SECONDS = int(
    os.getenv(
        "GOOGLE_SHEET_CACHE_SECONDS",
        "60"
    )
)


# ============================================================
# CACHE
# ============================================================

_CACHE_HOJAS: list[dict] = []
_CACHE_TIMESTAMP = 0.0


# ============================================================
# STOPWORDS
# ============================================================

STOPWORDS = {
    "que",
    "como",
    "cual",
    "cuales",
    "donde",
    "cuando",
    "quien",
    "quienes",
    "para",
    "por",
    "con",
    "sin",
    "del",
    "las",
    "los",
    "una",
    "uno",
    "unos",
    "unas",
    "este",
    "esta",
    "estos",
    "estas",
    "ese",
    "esa",
    "esos",
    "esas",
    "hay",
    "son",
    "sea",
    "ser",
    "tiene",
    "tienen",
    "sobre",
    "desde",
    "hasta",
    "entre",
    "pero",
    "porque",
    "muy",
    "mas",
    "me",
    "mi",
    "mis",
    "se",
    "su",
    "sus",
    "al",
    "el",
    "la",
    "lo",
    "y",
    "o",
    "de",
    "en",
    "un",
    "es",
    "dame",
    "dime",
    "mostrar",
    "muestra",
    "muéstrame",
    "necesito",
    "puedes",
    "puede",
    "podrias",
    "podria",
    "dar",
    "quiero",
    "quisiera",
    "favor",
    "porfa",
    "saber",
}


PALABRAS_INTENCION = {
    "clave",
    "password",
    "contrasena",
    "usuario",
    "user",
    "username",
    "wifi",
    "ssid",
    "direccion",
    "calle",
    "barrio",
    "ip",
    "gateway",
    "publica",
    "publico",
    "local",
    "correo",
    "email",
    "enlace",
    "link",
    "url",
    "camara",
    "camaras",
}


# ============================================================
# ENCABEZADOS CONOCIDOS
# ============================================================

ENCABEZADOS_CONOCIDOS = {
    "plataforma",
    "usuario",
    "user",
    "username",
    "password",
    "clave",
    "contrasena",
    "url",
    "ubicacion",
    "ssid",
    "marca",
    "ip local",
    "ip publica",
    "ip publico",
    "gateway",
    "sede",
    "sedes",
    "direccion",
    "operador",
    "correo",
    "correo personal",
    "correo institucional",
    "cc",
    "nombre",
    "nombre completo",
    "cargo",
    "linea",
    "forti",
}


# ============================================================
# NORMALIZACIÓN
# ============================================================

def _normalizar(texto: str) -> str:
    texto = (texto or "").lower().strip()

    texto = unicodedata.normalize(
        "NFD",
        texto
    )

    texto = "".join(
        caracter
        for caracter in texto
        if unicodedata.category(caracter) != "Mn"
    )

    # Corrección de algunos errores comunes.
    correcciones = {
        r"\bcalve\b": "clave",
        r"\bdirrecion\b": "direccion",
        r"\bdirreccion\b": "direccion",
        r"\bdireccionn\b": "direccion",
        r"\bcontrsena\b": "contrasena",

        # Errores comunes en nombres y consultas.
        r"\bpremiun\b": "premium",
        r"\bplaz\b": "plaza",
        r"\bwiffi\b": "wifi",
        r"\bwi[ -]?fi\b": "wifi",
    }

    for patron, reemplazo in correcciones.items():
        texto = re.sub(
            patron,
            reemplazo,
            texto
        )

    return texto


def _terminos(texto: str) -> set[str]:
    palabras = re.findall(
        r"[a-z0-9]+",
        _normalizar(texto)
    )

    return {
        palabra
        for palabra in palabras
        if (
            palabra not in STOPWORDS
            and (
                len(palabra) >= 3
                or palabra.isdigit()
            )
        )
    }


def _numeros(texto: str) -> set[str]:
    return set(
        re.findall(
            r"\b\d+\b",
            _normalizar(texto)
        )
    )


def _extraer_emails(texto: str) -> set[str]:
    return {
        email.lower()
        for email in re.findall(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
            texto
        )
    }


# ============================================================
# CONEXIÓN GOOGLE
# ============================================================

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
            "No se encontró el archivo "
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


# ============================================================
# CACHE GOOGLE SHEET
# ============================================================

def _obtener_hojas(
    forzar: bool = False
) -> list[dict]:

    global _CACHE_HOJAS
    global _CACHE_TIMESTAMP

    ahora = monotonic()

    if (
        not forzar
        and _CACHE_HOJAS
        and (
            ahora - _CACHE_TIMESTAMP
            < CACHE_SECONDS
        )
    ):
        return _CACHE_HOJAS

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

    hojas = []

    for worksheet in spreadsheet.worksheets():

        hojas.append({
            "titulo": worksheet.title,
            "filas": worksheet.get_all_values()
        })

    _CACHE_HOJAS = hojas
    _CACHE_TIMESTAMP = ahora

    return hojas


# ============================================================
# DETECTAR ENCABEZADO REAL
# ============================================================

def _puntuar_encabezado(
    fila: list[str]
) -> int:

    score = 0

    for celda in fila:

        celda_normalizada = _normalizar(
            str(celda)
        )

        if not celda_normalizada:
            continue

        if (
            celda_normalizada
            in ENCABEZADOS_CONOCIDOS
        ):
            score += 10

        elif any(
            conocido in celda_normalizada
            for conocido
            in ENCABEZADOS_CONOCIDOS
        ):
            score += 3

    return score


def _detectar_encabezado(
    filas: list[list[str]]
) -> int:

    if not filas:
        return 0

    limite = min(
        20,
        len(filas)
    )

    mejor_indice = 0
    mejor_score = -1
    mayor_columnas = -1

    for indice in range(limite):

        fila = filas[indice]

        score = _puntuar_encabezado(
            fila
        )

        columnas = sum(
            1
            for celda in fila
            if str(celda).strip()
        )

        if (
            score > mejor_score
            or (
                score == mejor_score
                and columnas > mayor_columnas
            )
        ):
            mejor_indice = indice
            mejor_score = score
            mayor_columnas = columnas

    return mejor_indice


# ============================================================
# CONVERTIR FILA
# ============================================================

def _crear_datos(
    encabezados: list[str],
    fila: list[str]
) -> dict[str, str]:

    datos = {}

    for indice, valor in enumerate(
        fila
    ):

        valor = str(valor).strip()

        if not valor:
            continue

        if indice < len(encabezados):

            encabezado = str(
                encabezados[indice]
            ).strip()

        else:

            encabezado = ""

        if not encabezado:
            encabezado = (
                f"Columna {indice + 1}"
            )

        datos[encabezado] = valor

    return datos


# ============================================================
# INTENCIONES
# ============================================================

def _detectar_intencion(
    pregunta: str
) -> str:

    texto = _normalizar(
        pregunta
    )

    pide_clave = any(
        palabra in texto
        for palabra in (
            "clave",
            "password",
            "contrasena",
        )
    )

    if "wifi" in texto or "ssid" in texto:

        if pide_clave:
            return "wifi_clave"

        return "wifi"

    if (
        "direccion" in texto
        or "calle" in texto
        or "barrio" in texto
    ):

        # "dirección IP" no es dirección física.
        if "ip" not in texto:
            return "direccion_fisica"

    if (
        re.search(r"\bip\b", texto)
        or "gateway" in texto
        or "ip publica" in texto
        or "ip local" in texto
    ):
        return "ip"

    if (
        "camara" in texto
        or "camaras" in texto
        or "hikvision" in texto
    ):
        return "camaras"

    if pide_clave:
        return "clave_acceso"

    if any(
        palabra in texto
        for palabra in (
            "usuario",
            "username",
            "user",
        )
    ):
        return "usuario_acceso"

    return "general"


# ============================================================
# TÉRMINOS QUE IDENTIFICAN EL REGISTRO
# ============================================================

def _terminos_objetivo(
    pregunta: str
) -> set[str]:

    # Quitamos emails completos antes
    # de separar las palabras.
    sin_emails = re.sub(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        " ",
        pregunta
    )

    terminos = _terminos(
        sin_emails
    )

    return {
        termino
        for termino in terminos
        if termino not in PALABRAS_INTENCION
    }


# ============================================================
# HOJAS PREFERIDAS
# ============================================================

def _hoja_preferida(
    titulo: str,
    intencion: str
) -> bool:

    titulo = _normalizar(
        titulo
    )

    if intencion in {
        "wifi",
        "wifi_clave"
    }:
        return (
            "wifi" in titulo
            or "redes wifi" in titulo
        )

    if intencion == "direccion_fisica":
        return (
            "direccion" in titulo
            and "sede" in titulo
        )

    if intencion == "ip":
        return any(
            palabra in titulo
            for palabra in (
                "mikrotik",
                "direccionamiento",
                "red",
                "forti",
            )
        )

    if intencion == "camaras":
        return (
            "camara" in titulo
        )

    if intencion in {
        "clave_acceso",
        "usuario_acceso"
    }:
        return (
            "acceso" in titulo
            or "web" in titulo
        )

    return True


# ============================================================
# BUSCAR CAMPOS
# ============================================================

def _buscar_campo_exacto(
    datos: dict[str, str],
    aliases: tuple[str, ...]
) -> tuple[str, str] | None:

    aliases_normalizados = {
        _normalizar(alias)
        for alias in aliases
    }

    for campo, valor in datos.items():

        campo_normalizado = (
            _normalizar(campo)
        )

        if (
            campo_normalizado
            in aliases_normalizados
        ):
            return campo, valor

    return None


def _tiene_campo_necesario(
    datos: dict[str, str],
    intencion: str
) -> bool:

    if intencion == "wifi_clave":

        return (
            _buscar_campo_exacto(
                datos,
                (
                    "PASSWORD",
                    "CLAVE WIFI",
                    "CONTRASEÑA WIFI",
                    "CONTRASENA WIFI",
                    "CONTRASEÑA",
                )
            )
            is not None
        )

    if intencion == "direccion_fisica":

        return (
            _buscar_campo_exacto(
                datos,
                (
                    "DIRECCION",
                    "DIRECCIÓN",
                )
            )
            is not None
        )

    if intencion == "ip":

        return any(
            _buscar_campo_exacto(
                datos,
                aliases
            )
            is not None
            for aliases in (
                (
                    "IP LOCAL",
                ),
                (
                    "IP PUBLICA",
                    "IP PÚBLICA",
                ),
                (
                    "GATEWAY",
                ),
                (
                    "IP",
                ),
            )
        )

    if intencion == "clave_acceso":

        return (
            _buscar_campo_exacto(
                datos,
                (
                    "PASSWORD",
                    "CLAVE",
                    "CONTRASEÑA",
                    "CONTRASENA",
                    "PASS",
                )
            )
            is not None
        )

    return True


# ============================================================
# EVALUAR FILA
# ============================================================

def _evaluar_fila(
    pregunta: str,
    titulo_hoja: str,
    datos: dict[str, str],
    intencion: str
) -> int | None:

    texto_fila = " | ".join(
        f"{campo}: {valor}"
        for campo, valor
        in datos.items()
    )

    texto_normalizado = (
        _normalizar(texto_fila)
    )

    emails_pregunta = (
        _extraer_emails(
            pregunta
        )
    )

    emails_fila = (
        _extraer_emails(
            texto_fila
        )
    )

    numeros_pregunta = (
        _numeros(
            pregunta
        )
    )

    numeros_fila = (
        _numeros(
            texto_fila
        )
    )

    objetivo = (
        _terminos_objetivo(
            pregunta
        )
    )

    terminos_fila = (
        _terminos(
            texto_fila
        )
    )

    # Email exacto.
    if emails_pregunta:

        if not emails_pregunta.issubset(
            emails_fila
        ):
            return None

    # Número exacto.
    if numeros_pregunta:

        if not numeros_pregunta.issubset(
            numeros_fila
        ):
            return None

    # Entidad:
    # campestre, premium, alcalde, etc.
    coincidencias = (
        objetivo
        & terminos_fila
    )

    if objetivo:

        cobertura = (
            len(coincidencias)
            / len(objetivo)
        )

        if cobertura < 0.60:
            return None

    if not _tiene_campo_necesario(
        datos,
        intencion
    ):
        return None

    score = 0

    score += (
        len(coincidencias)
        * 10
    )

    if emails_pregunta:
        score += 120

    if numeros_pregunta:
        score += 80

    if _hoja_preferida(
        titulo_hoja,
        intencion
    ):
        score += 50

    if _tiene_campo_necesario(
        datos,
        intencion
    ):
        score += 20

    pregunta_normalizada = (
        _normalizar(
            pregunta
        )
    )

    if (
        pregunta_normalizada
        and pregunta_normalizada
        in texto_normalizado
    ):
        score += 30

    return score


# ============================================================
# BUSCADOR PRINCIPAL
# ============================================================

def buscar_en_sheet(
    pregunta: str,
    limite: int = 3
) -> list[dict]:

    intencion = _detectar_intencion(
        pregunta
    )

    hojas = _obtener_hojas()

    resultados = []

    # Primero buscamos en hojas compatibles
    # con la intención.
    for solo_preferidas in (
        True,
        False
    ):

        resultados = []

        for hoja in hojas:

            titulo = hoja["titulo"]
            filas = hoja["filas"]

            if not filas:
                continue

            if (
                solo_preferidas
                and not _hoja_preferida(
                    titulo,
                    intencion
                )
            ):
                continue

            encabezado_index = (
                _detectar_encabezado(
                    filas
                )
            )

            encabezados = [
                str(celda).strip()
                for celda
                in filas[encabezado_index]
            ]

            for numero_fila, fila in enumerate(
                filas[
                    encabezado_index + 1:
                ],
                start=encabezado_index + 2
            ):

                if not any(
                    str(celda).strip()
                    for celda in fila
                ):
                    continue

                datos = _crear_datos(
                    encabezados,
                    fila
                )

                score = _evaluar_fila(
                    pregunta,
                    titulo,
                    datos,
                    intencion
                )

                if score is None:
                    continue

                resultados.append({
                    "hoja": titulo,
                    "fila": numero_fila,
                    "datos": datos,
                    "score": score,
                    "intencion": intencion,
                })

        if resultados:
            break

    resultados.sort(
        key=lambda resultado: (
            resultado["score"]
        ),
        reverse=True
    )

    print(
        f"[SHEET] Intención: {intencion} | "
        f"Resultados encontrados: "
        f"{len(resultados)}"
    )

    return resultados[:limite]


# ============================================================
# SELECCIONAR SOLO CAMPOS ÚTILES
# ============================================================

def _agregar_campo(
    salida: dict[str, str],
    datos: dict[str, str],
    aliases: tuple[str, ...]
) -> None:

    encontrado = (
        _buscar_campo_exacto(
            datos,
            aliases
        )
    )

    if encontrado:

        campo, valor = encontrado

        salida[campo] = valor


def _campos_para_respuesta(
    resultado: dict
) -> dict[str, str]:

    datos = resultado["datos"]

    intencion = resultado.get(
        "intencion",
        "general"
    )

    salida = {}

    # ------------------------------------------
    # WIFI
    # ------------------------------------------

    if intencion in {
        "wifi",
        "wifi_clave"
    }:

        _agregar_campo(
            salida,
            datos,
            (
                "UBICACION",
                "UBICACIÓN",
                "SEDE",
                "SEDES",
            )
        )

        _agregar_campo(
            salida,
            datos,
            (
                "SSID",
            )
        )

        if intencion == "wifi_clave":

            _agregar_campo(
                salida,
                datos,
                (
                    "PASSWORD",
                    "CLAVE WIFI",
                    "CONTRASEÑA WIFI",
                    "CONTRASENA WIFI",
                    "CONTRASEÑA",
                )
            )

        return salida

    # ------------------------------------------
    # DIRECCIÓN FÍSICA
    # ------------------------------------------

    if intencion == "direccion_fisica":

        _agregar_campo(
            salida,
            datos,
            (
                "SEDES",
                "SEDE",
                "UBICACION",
                "UBICACIÓN",
            )
        )

        _agregar_campo(
            salida,
            datos,
            (
                "DIRECCION",
                "DIRECCIÓN",
            )
        )

        return salida

    # ------------------------------------------
    # IP
    # ------------------------------------------

    if intencion == "ip":

        _agregar_campo(
            salida,
            datos,
            (
                "UBICACION",
                "UBICACIÓN",
                "SEDE",
                "SEDES",
            )
        )

        _agregar_campo(
            salida,
            datos,
            (
                "IP LOCAL",
            )
        )

        _agregar_campo(
            salida,
            datos,
            (
                "IP PUBLICA",
                "IP PÚBLICA",
            )
        )

        _agregar_campo(
            salida,
            datos,
            (
                "GATEWAY",
            )
        )

        return salida

    # ------------------------------------------
    # CLAVE DE ACCESO
    # ------------------------------------------

    if intencion == "clave_acceso":

        _agregar_campo(
            salida,
            datos,
            (
                "PLATAFORMA",
                "SISTEMA",
                "SERVICIO",
            )
        )

        _agregar_campo(
            salida,
            datos,
            (
                "USUARIO",
                "USERNAME",
                "CORREO",
                "EMAIL",
            )
        )

        _agregar_campo(
            salida,
            datos,
            (
                "PASSWORD",
                "CLAVE",
                "CONTRASEÑA",
                "CONTRASENA",
                "PASS",
            )
        )

        return salida

    # ------------------------------------------
    # USUARIO
    # ------------------------------------------

    if intencion == "usuario_acceso":

        _agregar_campo(
            salida,
            datos,
            (
                "PLATAFORMA",
                "SISTEMA",
                "SERVICIO",
            )
        )

        _agregar_campo(
            salida,
            datos,
            (
                "USUARIO",
                "USERNAME",
                "CORREO",
                "EMAIL",
            )
        )

        return salida

    # ------------------------------------------
    # CÁMARAS
    # ------------------------------------------

    if intencion == "camaras":

        for campo, valor in datos.items():

            if len(salida) >= 6:
                break

            salida[campo] = valor

        return salida

    # ------------------------------------------
    # GENERAL
    # ------------------------------------------

    for campo, valor in datos.items():

        if len(salida) >= 6:
            break

        salida[campo] = valor

    return salida


# ============================================================
# FORMATEAR RESPUESTA
# ============================================================

def formatear_resultados_sheet(
    resultados: list[dict]
) -> str:

    if not resultados:
        return ""

    bloques = []

    for resultado in resultados:

        datos = (
            _campos_para_respuesta(
                resultado
            )
        )

        if not datos:
            continue

        lineas = [
            f"• {campo}: {valor}"
            for campo, valor
            in datos.items()
            if valor
        ]

        if lineas:

            bloques.append(
                "\n".join(lineas)
            )

    if not bloques:
        return ""

    hojas = list(
        dict.fromkeys(
            resultado["hoja"]
            for resultado
            in resultados
        )
    )

    return (
        "Encontré esta información "
        "en el Google Sheet:\n\n"
        + "\n\n".join(bloques)
        + "\n\nFuente: Google Sheet → "
        + ", ".join(hojas)
    )


# ============================================================
# SINCRONIZAR ARCHIVO LOCAL
# ============================================================

def sync_sheet() -> int:

    hojas = _obtener_hojas(
        forzar=True
    )

    sections = []

    for hoja in hojas:

        titulo = hoja["titulo"]
        filas = hoja["filas"]

        rows = [
            " | ".join(
                str(celda)
                for celda in fila
            )
            for fila in filas
            if any(
                str(celda).strip()
                for celda in fila
            )
        ]

        if rows:

            sections.append(
                f"[Hoja: {titulo}]\n"
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