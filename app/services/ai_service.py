from pathlib import Path
import asyncio
import os
import re
import unicodedata

from dotenv import load_dotenv
from google import genai

from app.services.sheets_service import (
    buscar_en_sheet,
    formatear_resultados_sheet,
)


# ============================================================
# CONFIGURACIÓN
# ============================================================

load_dotenv(
    override=True
)


BASE_DIR = (
    Path(__file__)
    .resolve()
    .parents[2]
)


MANUAL_KNOWLEDGE_FILE = (
    BASE_DIR
    / "data"
    / "conocimiento.txt"
)


DOCUMENT_KNOWLEDGE_FILE = (
    BASE_DIR
    / "data"
    / "conocimiento_documentos.txt"
)


MAX_FRAGMENT_CHARS = 1400

MAX_RESULTS = 3


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
}


# ============================================================
# LEER ARCHIVOS
# ============================================================

def _read_text(
    path: Path
) -> str:

    if not path.exists():
        return ""

    return path.read_text(
        encoding="utf-8",
        errors="ignore"
    ).strip()


# ============================================================
# NORMALIZAR TEXTO
# ============================================================

def _normalizar(
    texto: str
) -> str:

    texto = (
        texto
        or ""
    ).lower()

    texto = unicodedata.normalize(
        "NFD",
        texto
    )

    return "".join(
        caracter
        for caracter in texto
        if unicodedata.category(
            caracter
        ) != "Mn"
    )


def _raiz_termino(
    termino: str
) -> str:

    if termino.isdigit():
        return termino

    # actas -> acta
    if (
        len(termino) > 4
        and termino.endswith("s")
    ):
        return termino[:-1]

    return termino


def _terminos(
    texto: str
) -> set[str]:

    palabras = re.findall(
        r"[a-z0-9]+",
        _normalizar(texto)
    )

    return {
        _raiz_termino(
            palabra
        )
        for palabra
        in palabras
        if (
            palabra not in STOPWORDS
            and (
                len(palabra) >= 3
                or palabra.isdigit()
            )
        )
    }


def _numeros(
    texto: str
) -> set[str]:

    return set(
        re.findall(
            r"\b\d+\b",
            _normalizar(texto)
        )
    )


# ============================================================
# CALCULAR COINCIDENCIAS
# ============================================================

def _calcular_coincidencia(
    pregunta: str,
    texto: str
) -> tuple[int, float, int]:

    terminos_pregunta = (
        _terminos(
            pregunta
        )
    )

    if not terminos_pregunta:

        return (
            0,
            0.0,
            0
        )

    terminos_texto = (
        _terminos(
            texto
        )
    )

    numeros_pregunta = (
        _numeros(
            pregunta
        )
    )

    numeros_texto = (
        _numeros(
            texto
        )
    )

    # Si el usuario pregunta por
    # un número concreto, debe
    # aparecer exactamente.
    if numeros_pregunta:

        if not numeros_pregunta.issubset(
            numeros_texto
        ):

            return (
                0,
                0.0,
                0
            )

    coincidencias = (
        terminos_pregunta
        & terminos_texto
    )

    score = 0

    for termino in coincidencias:

        if termino.isdigit():

            score += 20

        else:

            score += 3

    if numeros_pregunta:

        score += 40

    cobertura = (
        len(coincidencias)
        / len(terminos_pregunta)
    )

    return (
        score,
        cobertura,
        len(coincidencias)
    )


# ============================================================
# VERIFICAR SI UNA COINCIDENCIA ES CONFIABLE
# ============================================================

def _es_coincidencia_confiable(
    pregunta: str,
    texto: str
) -> bool:

    score, cobertura, cantidad = (
        _calcular_coincidencia(
            pregunta,
            texto
        )
    )

    numeros_pregunta = (
        _numeros(
            pregunta
        )
    )

    terminos_pregunta = (
        _terminos(
            pregunta
        )
    )

    if numeros_pregunta:

        return score >= 40

    if not terminos_pregunta:

        return False

    if len(
        terminos_pregunta
    ) == 1:

        return cantidad >= 1

    if len(
        terminos_pregunta
    ) == 2:

        return (
            cantidad >= 1
            and cobertura >= 0.50
        )

    return (
        cantidad >= 2
        and cobertura >= 0.40
    )


# ============================================================
# CREAR FRAGMENTOS DE DOCUMENTOS
# ============================================================

def _crear_fragmentos_documentos(
    texto: str
) -> list[str]:

    if not texto:

        return []

    parrafos = [
        parrafo.strip()
        for parrafo
        in re.split(
            r"\n\s*\n",
            texto
        )
        if parrafo.strip()
    ]

    fragmentos: list[str] = []

    actual = ""

    for parrafo in parrafos:

        if (
            len(actual)
            + len(parrafo)
            + 2
            <= MAX_FRAGMENT_CHARS
        ):

            if actual:

                actual += "\n\n"

            actual += parrafo

            continue

        if actual:

            fragmentos.append(
                actual
            )

        if (
            len(parrafo)
            > MAX_FRAGMENT_CHARS
        ):

            for inicio in range(
                0,
                len(parrafo),
                MAX_FRAGMENT_CHARS
            ):

                fragmentos.append(
                    parrafo[
                        inicio:
                        inicio
                        + MAX_FRAGMENT_CHARS
                    ]
                )

            actual = ""

        else:

            actual = parrafo

    if actual:

        fragmentos.append(
            actual
        )

    return fragmentos


# ============================================================
# BUSCADOR GENERAL EN TEXTO
# ============================================================

def _buscar_en_texto(
    pregunta: str,
    contenido: str,
    limite: int = MAX_RESULTS
) -> list[dict]:

    if not contenido:

        return []

    candidatos: list[dict] = []

    fragmentos = (
        _crear_fragmentos_documentos(
            contenido
        )
    )

    for fragmento in fragmentos:

        if not _es_coincidencia_confiable(
            pregunta,
            fragmento
        ):

            continue

        score, cobertura, cantidad = (
            _calcular_coincidencia(
                pregunta,
                fragmento
            )
        )

        candidatos.append({
            "texto": fragmento,
            "score": score,
            "cobertura": cobertura,
            "cantidad": cantidad,
        })

    candidatos.sort(
        key=lambda item: (
            item["score"],
            item["cobertura"]
        ),
        reverse=True
    )

    return candidatos[:limite]


# ============================================================
# 2. BUSCAR EN ARCHIVOS SUBIDOS
# ============================================================

def buscar_documentos(
    pregunta: str
) -> list[dict]:

    contenido = _read_text(
        DOCUMENT_KNOWLEDGE_FILE
    )

    return _buscar_en_texto(
        pregunta,
        contenido
    )


# ============================================================
# 3. BUSCAR EN conocimiento.txt
# ============================================================

def buscar_conocimiento_manual(
    pregunta: str
) -> list[dict]:

    contenido = _read_text(
        MANUAL_KNOWLEDGE_FILE
    )

    return _buscar_en_texto(
        pregunta,
        contenido
    )


# ============================================================
# FORMATEAR RESPUESTAS DE ARCHIVOS
# ============================================================

def _formatear_resultado_texto(
    resultados: list[dict],
    titulo: str,
    fuente: str
) -> str:

    if not resultados:

        return ""

    textos = [
        resultado["texto"]
        for resultado
        in resultados
    ]

    return (
        titulo
        + "\n\n"
        + "\n\n".join(
            textos
        )
        + f"\n\nFuente: {fuente}"
    )


# ============================================================
# 4. GEMINI
# ============================================================

def _consultar_gemini(
    api_key: str,
    modelo: str,
    pregunta: str
) -> str:

    client = genai.Client(
        api_key=api_key
    )

    instrucciones = """
Eres un asistente virtual útil, claro y amable.

Responde siempre en español.

Antes de consultarte, el sistema ya buscó en:

1. Google Sheet compartido.
2. Archivos internos subidos.
3. Base de conocimiento manual.

No se encontró una respuesta interna suficientemente confiable.

Puedes responder preguntas de conocimiento general.

Si la pregunta solicita información privada,
específica o interna de una organización,
institución, acta, documento, persona o registro
al que no tienes acceso, no inventes datos.

Indica claramente que esa información no fue
encontrada en las fuentes internas disponibles.
""".strip()

    try:

        interaction = (
            client.interactions.create(
                model=modelo,
                system_instruction=instrucciones,
                input=pregunta,
            )
        )

        texto = (
            interaction.output_text
            or ""
        ).strip()

        return (
            texto
            or
            "No pude generar una "
            "respuesta en este momento."
        )

    finally:

        client.close()


# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================

async def responder_pregunta(
    pregunta: str
) -> str:

    """
    ESTA FUNCIÓN LA USAN:

    - Telegram
    - Página Web

    PRIORIDAD:

    1. Google Sheet real
    2. PDF / DOCX / XLSX / TXT
    3. conocimiento.txt
    4. Gemini
    """

    pregunta = (
        pregunta
        or ""
    ).strip()

    if not pregunta:

        return (
            "Escribe una pregunta "
            "para poder ayudarte."
        )


    # ========================================================
    # PRIORIDAD 1
    # GOOGLE SHEET REAL
    # ========================================================

    try:

        resultados_sheet = (
            await asyncio.to_thread(
                buscar_en_sheet,
                pregunta
            )
        )

    except Exception as error:

        print(
            "[SHEET ERROR]",
            type(error).__name__,
            str(error)
        )

        resultados_sheet = []


    if resultados_sheet:

        print(
            "[BUSCADOR] "
            "Respuesta encontrada "
            "en GOOGLE SHEET."
        )

        return (
            formatear_resultados_sheet(
                resultados_sheet
            )
        )


    # ========================================================
    # PRIORIDAD 2
    # ARCHIVOS SUBIDOS
    # PDF / DOCX / XLSX / TXT
    # ========================================================

    resultados_documentos = (
        buscar_documentos(
            pregunta
        )
    )

    if resultados_documentos:

        print(
            "[BUSCADOR] "
            "Respuesta encontrada "
            "en ARCHIVOS SUBIDOS."
        )

        return (
            _formatear_resultado_texto(
                resultados_documentos,
                (
                    "Encontré esta información "
                    "en los archivos cargados:"
                ),
                "archivos subidos"
            )
        )


    # ========================================================
    # PRIORIDAD 3
    # conocimiento.txt
    # ========================================================

    resultados_manual = (
        buscar_conocimiento_manual(
            pregunta
        )
    )

    if resultados_manual:

        print(
            "[BUSCADOR] "
            "Respuesta encontrada "
            "en CONOCIMIENTO.TXT."
        )

        return (
            _formatear_resultado_texto(
                resultados_manual,
                (
                    "Encontré esta información "
                    "en la base de conocimiento:"
                ),
                "conocimiento interno"
            )
        )


    # ========================================================
    # PRIORIDAD 4
    # GEMINI
    # ========================================================

    print(
        "[BUSCADOR] "
        "No se encontró información interna. "
        "Consultando GEMINI..."
    )

    api_key = os.getenv(
        "GEMINI_API_KEY"
    )

    if (
        not api_key
        or api_key
        == "pon_aqui_tu_clave_de_gemini"
    ):

        return (
            "No encontré la respuesta "
            "en las fuentes internas y "
            "Gemini no está configurado."
        )


    modelo = os.getenv(
        "GEMINI_MODEL",
        "gemini-3.6-flash"
    )


    try:

        respuesta = (
            await asyncio.to_thread(
                _consultar_gemini,
                api_key,
                modelo,
                pregunta,
            )
        )

        return (
            respuesta
            + "\n\nFuente: Gemini."
        )


    except Exception as error:

        mensaje_error = (
            str(error)
            .lower()
        )


        # ====================================================
        # LÍMITE GRATUITO GEMINI
        # ====================================================

        if (
            "429"
            in mensaje_error
            or "quota"
            in mensaje_error
            or "too_many_requests"
            in mensaje_error
            or "rate limit"
            in mensaje_error
        ):

            return (
                "⚠️ No encontré la respuesta "
                "en las fuentes internas y "
                "Gemini alcanzó temporalmente "
                "su límite gratuito.\n\n"
                "Espera aproximadamente "
                "un minuto e intenta nuevamente."
            )


        # ====================================================
        # ERROR DE RED
        # ====================================================

        if (
            "readerror"
            in mensaje_error
            or "timeout"
            in mensaje_error
            or "network"
            in mensaje_error
            or "connection"
            in mensaje_error
        ):

            return (
                "⚠️ No encontré la respuesta "
                "en las fuentes internas y "
                "en este momento existe "
                "un problema de conexión "
                "con Gemini."
            )


        # ====================================================
        # OTRO ERROR
        # ====================================================

        print(
            "[ERROR GEMINI]",
            type(error).__name__,
            str(error)
        )

        return (
            "⚠️ No encontré la respuesta "
            "en las fuentes internas y "
            "ocurrió un error al "
            "consultar Gemini."
        )