from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse
import os
import shutil
import subprocess
import uuid
import speech_recognition as sr
from pydub import AudioSegment
from dotenv import load_dotenv
import openai
import traceback

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def index():
    with open("static/index.html", encoding="utf-8") as f:
        return f.read()

def obtener_feedback_con_gpt(transcripcion, idioma="en"):
    if idioma == "es":
        prompt = f"""
Eres un profesor de español (latino, venezolano) que da retroalimentación solo si es necesaria.

Tienes que:
- Detectar errores gramaticales o de vocabulario real, nivel A2-B1
- Ignorar pequeños detalles si no afectan el sentido
- No inventar errores
- Si todo está correcto, responde: "✅ Todo está correcto. ¡Buen trabajo!"
- Si hay errores, usa este formato:

1. 🔍 Error: ...
   💡 Explicación: ...
   ✅ Corrección: ...
...
✍️ Versión corregida sugerida: ...

Texto del estudiante:
"""{transcripcion}"""
"""
    else:
        prompt = f"""
You are a Latin American Spanish teacher from Venezuela. Your job is to give feedback to a Spanish student (level A2-B1).

Give feedback ONLY if there are actual mistakes in grammar or vocabulary.
- DO NOT invent problems or rephrase things that are already correct.
- If the text is correct, just say: "✅ Everything looks correct. Great job!"
- If there are real mistakes, give friendly, clear feedback like this:

1. 🔍 Error: ...
   💡 Explanation: ...
   ✅ Correction: ...
...
✍️ Suggested corrected version: ...

Student's text:
"""{transcripcion}"""
"""

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    return response.choices[0].message.content.strip()

@app.post("/upload/")
async def upload_audio(file: UploadFile = File(...), language: str = Form("en")):
    try:
        os.makedirs("uploads", exist_ok=True)
        input_filename = f"uploads/{uuid.uuid4()}_{file.filename}"

        with open(input_filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        if input_filename.endswith(".webm"):
            audio_path = input_filename.replace(".webm", ".wav")
            command = [
                "ffmpeg", "-y", "-i", input_filename,
                "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                audio_path
            ]
            subprocess.run(command, check=True)
        else:
            audio = AudioSegment.from_file(input_filename)
            audio_path = input_filename + ".wav"
            audio.export(audio_path, format="wav")

        recognizer = sr.Recognizer()
        with sr.AudioFile(audio_path) as source:
            audio_data = recognizer.record(source)
        transcription = recognizer.recognize_google(audio_data, language="es-ES")

        feedback_text = obtener_feedback_con_gpt(transcription, idioma=language)

        return {
            "filename": file.filename,
            "transcription": transcription,
            "feedback": feedback_text
        }

    except subprocess.CalledProcessError:
        return {"error": "⚠️ Error converting video. Make sure ffmpeg is installed."}
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}
