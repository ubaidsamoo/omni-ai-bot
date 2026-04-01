"""
Omni AI - FastAPI Backend
=========================
Google Gemini 1.5 Flash powered multimodal AI backend.
"""

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from dotenv import load_dotenv

load_dotenv()

from modules.chat import ChatModule
from modules.vision import VisionModule
from modules.document import DocumentModule
from modules.youtube import YouTubeModule
from modules.data_analysis import DataAnalysisModule

app = FastAPI(
    title="Omni AI API",
    description="Multimodal AI backend powered by Google Gemini 1.5 Flash",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GOOGLE_API_KEY
api_key = os.getenv("GOOGLE_API_KEY", "").strip()
if not api_key or api_key == "YOUR_GOOGLE_API_KEY_HERE":
    raise ValueError(
        "❌ GOOGLE_API_KEY not found!\n"
        "backend/.env file mein apni key daalo:\n"
        "GOOGLE_API_KEY=AIzaSy...\n"
        "Key FREE milti hai: https://aistudio.google.com/app/apikey"
    )

gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()
print(f"✅ Using model: {gemini_model}")

chat_module     = ChatModule(api_key, gemini_model)
vision_module   = VisionModule(api_key, gemini_model)
document_module = DocumentModule(api_key, gemini_model)
youtube_module  = YouTubeModule(api_key, gemini_model)
data_module     = DataAnalysisModule(api_key, gemini_model)


@app.get("/")
async def root():
    return {"status": "✅ Omni AI is running!", "version": "2.0.0", "model": gemini_model}


@app.post("/chat/message")
async def chat_message(message: str = Form(...), session_id: str = Form(default="default")):
    try:
        response = await chat_module.chat(message, session_id)
        return {"response": response, "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/clear")
async def clear_chat(session_id: str = Form(default="default")):
    chat_module.clear_history(session_id)
    return {"status": "✅ Chat history cleared"}


@app.post("/vision/analyze")
async def analyze_image(image: UploadFile = File(...), prompt: str = Form(default="")):
    try:
        image_bytes = await image.read()
        result = await vision_module.analyze_image(image_bytes, image.content_type, prompt)
        return {"analysis": result, "filename": image.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/document/upload")
async def upload_pdf(pdf: UploadFile = File(...)):
    try:
        pdf_bytes = await pdf.read()
        result = await document_module.process_pdf(pdf_bytes, pdf.filename)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/document/query")
async def query_document(question: str = Form(...), doc_id: str = Form(...)):
    try:
        answer = await document_module.query(question, doc_id)
        return {"answer": answer, "doc_id": doc_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/youtube/analyze")
async def analyze_youtube(url: str = Form(...), task: str = Form(default="summarize"), question: str = Form(default="")):
    try:
        result = await youtube_module.analyze(url, task, question)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/youtube/transcript")
async def get_transcript(url: str = Form(...)):
    try:
        transcript = await youtube_module.get_transcript_only(url)
        return {"transcript": transcript}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/data/analyze")
async def analyze_csv(csv_file: UploadFile = File(...), question: str = Form(default="Give me a complete statistical summary and key insights.")):
    try:
        csv_bytes = await csv_file.read()
        result = await data_module.analyze(csv_bytes, question)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
