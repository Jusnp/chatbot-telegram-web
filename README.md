# Chatbot Web + Telegram con Gemini

La página web y Telegram usan el mismo servicio de IA y la misma base de conocimiento local.

## 1. Requisitos

- Python 3.10 o superior
- Una API key de Gemini creada en Google AI Studio
- Un bot creado en Telegram con @BotFather

## 2. Crear/activar el entorno virtual en Windows PowerShell

```powershell
cd ruta\chatbot_telegram_web
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Si ya habías instalado la versión anterior con OpenAI, basta con activar el entorno y volver a ejecutar:

```powershell
pip install -r requirements.txt
```

Opcionalmente puedes quitar el paquete de OpenAI porque esta versión ya no lo usa:

```powershell
pip uninstall openai -y
```

## 3. Configurar las claves

Copia `.env.example` como `.env` si todavía no tienes `.env`:

```powershell
Copy-Item .env.example .env
notepad .env
```

Contenido:

```env
GEMINI_API_KEY=tu_clave_de_gemini
GEMINI_MODEL=gemini-3.6-flash
TELEGRAM_BOT_TOKEN=tu_token_de_telegram
```

Nunca publiques el archivo `.env` ni pegues las claves en GitHub.

## 4. Ejecutar el chat web

```powershell
uvicorn app.main:app --reload
```

Abre:

http://127.0.0.1:8000

## 5. Ejecutar Telegram

Abre otra ventana de PowerShell:

```powershell
cd ruta\chatbot_telegram_web
.\venv\Scripts\Activate.ps1
python -m app.telegram_bot
```

Busca tu bot en Telegram y envía `/start`.

## 6. Agregar conocimiento manual

Edita:

`data/conocimiento.txt`

El chatbot lee el archivo nuevamente para cada pregunta, por lo que los cambios quedan disponibles sin reentrenar el modelo.

## Próxima fase

- Panel administrador
- Subida de PDF, Word, TXT y Excel
- RAG con embeddings/base vectorial
- Historial de conversaciones
- Acceso público mediante dominio/hosting
- Búsqueda web controlada
