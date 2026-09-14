# Chatbot Web + Telegram con Gemini

La página web y Telegram usan el mismo servicio de IA y la misma base de conocimiento local.

## Estado de la integración con Google Sheet (Armagedón)

**Ya aplicado:**

- Sincronización manual del Google Sheet privado (todas las pestañas) hacia `data/conocimiento_sheet.txt`, vía botón "Sincronizar Google Sheet" en `/admin` (ver sección 7).
- Esa información se suma automáticamente a la base de conocimiento que usa el chatbot, tanto en web como en Telegram.
- Cuenta de servicio de Google creada y con acceso de Lector al Sheet; credenciales guardadas en `credentials/` (ignorado por git).
- Autenticación del chat web y del panel `/admin` con usuario/clave (`WEB_AUTH_USER` / `WEB_AUTH_PASSWORD` en `.env`) — ya configurados con una clave real (ver sección 8).
- Base del control de acceso en Telegram por lista blanca de IDs (`TELEGRAM_ALLOWED_IDS`), con el bot rechazando por defecto a cualquiera que no esté en la lista.

**Falta / pendiente:**

- `TELEGRAM_ALLOWED_IDS` está vacío en `.env` → el bot de Telegram no responde a nadie todavía. Hay que agregar los IDs autorizados (ver sección 8).
- La sincronización del Sheet es manual: si el Sheet cambia y nadie aprieta el botón en `/admin`, el bot sigue respondiendo con la versión anterior.
- No hay roles diferenciados (todo el que tiene la clave web puede tanto chatear como administrar documentos/Sheet desde `/admin`).
- No hay límite de intentos de login (rate-limiting) en el chat web ni en `/admin`.
- No se filtra ni se enmascara ninguna pestaña del Sheet: si en el futuro se agregan más datos sensibles, van directo a la base de conocimiento del chatbot.

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

## 7. Conectar un Google Sheet privado

1. Ve a [Google Cloud Console](https://console.cloud.google.com/) → crea/selecciona un proyecto.
2. Habilita la **Google Sheets API**.
3. Crea una **cuenta de servicio** (IAM y administración → Cuentas de servicio) y genera una clave JSON.
4. Guarda ese JSON como `credentials/service_account.json` en la raíz del proyecto (la carpeta `credentials/` ya está en `.gitignore`).
5. Abre tu Google Sheet, dale clic en "Compartir" y agrega el email de la cuenta de servicio (termina en `...iam.gserviceaccount.com`) con permiso de **Lector**.
6. En `.env`, define `GOOGLE_SHEET_ID` con el ID de la hoja (la parte de la URL entre `/d/` y `/edit`).
7. Entra a `/admin` y presiona **Sincronizar Google Sheet**. Repite este paso cada vez que la hoja cambie.

## 8. Proteger el acceso (importante si sincronizas datos sensibles)

Como la base de conocimiento puede incluir datos sensibles (por ejemplo, accesos a plataformas), el chat web, el panel `/admin` y el bot de Telegram requieren autorización:

- **Web**: define `WEB_AUTH_USER` y `WEB_AUTH_PASSWORD` en `.env`. El navegador pedirá usuario/clave al entrar a `/`, `/admin` o al usar el chat.
- **Telegram**: define `TELEGRAM_ALLOWED_IDS` en `.env` con los IDs numéricos de Telegram autorizados, separados por coma. Si está vacío, el bot no responde a nadie. Para averiguar tu ID, escríbele a `@userinfobot` en Telegram, o intenta usar tu bot: en la consola donde corre `python -m app.telegram_bot` se imprime tu ID cuando el acceso es rechazado.

## Próxima fase

- Panel administrador
- Subida de PDF, Word, TXT y Excel
- RAG con embeddings/base vectorial
- Historial de conversaciones
- Acceso público mediante dominio/hosting
- Búsqueda web controlada
