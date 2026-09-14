from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.services.ai_service import responder_pregunta
from app.services.document_service import (
    delete_document,
    list_documents,
    save_document,
)

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Chatbot Web + Telegram")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


class ChatRequest(BaseModel):
    message: str


@app.get("/", response_class=HTMLResponse)
async def inicio(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"title": "Asistente Virtual"},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/chat")
async def chat(body: ChatRequest):
    pregunta = body.message.strip()
    if not pregunta:
        return {"answer": "Escribe una pregunta."}

    try:
        respuesta = await responder_pregunta(pregunta)
        return {"answer": respuesta}
    except Exception as exc:
        return {"answer": f"Ocurrió un error al generar la respuesta: {exc}"}


@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request, ok: str | None = None, error: str | None = None):
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "documents": list_documents(),
            "ok": ok,
            "error": error,
        },
    )


@app.post("/admin/upload")
async def upload_document(file: UploadFile = File(...)):
    try:
        content = await file.read()
        saved_name = save_document(file.filename or "", content)
        message = quote(f"Documento '{saved_name}' agregado correctamente.")
        return RedirectResponse(url=f"/admin?ok={message}", status_code=303)
    except Exception as exc:
        message = quote(str(exc))
        return RedirectResponse(url=f"/admin?error={message}", status_code=303)
    finally:
        await file.close()


@app.post("/admin/delete/{filename}")
async def remove_document(filename: str):
    try:
        delete_document(filename)
        message = quote(f"Documento '{filename}' eliminado.")
        return RedirectResponse(url=f"/admin?ok={message}", status_code=303)
    except Exception as exc:
        message = quote(str(exc))
        return RedirectResponse(url=f"/admin?error={message}", status_code=303)
