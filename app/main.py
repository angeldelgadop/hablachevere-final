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
Eres un profesor de español, eres latino, de Venezuela, que revisa textos hablados de estudiantes extranjeros (nivel A2-B1).

Analiza el siguiente texto transcrito del habla de un estudiante. Si hay errores gramaticales, de vocabulario o de expresión, explícalos de forma clara y sencilla, y da una versión corregida al final.

Si el texto está bien, simplemente di que está correcto y no inventes errores.
si el texto está bien, no des ninguna versión corregida sugerida
no busques errores que no hay, 

Texto del estudiante:
"{transcripcion}"

Formato:
1. 🔍 Error: ...
   💡 Explicación: ...
   ✅ Corrección: ...
...
✍️ Versión corregida sugerida: ...
"""
    else:
        prompt = f"""
You are a Spanish teacher, you are Latino, from Venezuela, who reviews spoken texts of foreign students (level A2-B1).
Analyze the following spoken Spanish text (transcribed). If there are real grammar or expression mistakes, explain them clearly in English and give a corrected version.

If the sentence is already correct, say so and do not invent problems.
If the sentence is already correct, dont give any suggested corrected version
do not invent mistakes that are not there

Student's text:
"{transcripcion}"

Format:
1. 🔍 Error: ...
   💡 Explanation: ...
   ✅ Correction: ...
...
✍️ Suggested corrected version: ...
"""

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5
    )
    return response.choices[0].message.content.strip()

from fastapi.responses import HTMLResponse

@app.post("/upload/", response_class=HTMLResponse)
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

        return f"""
        <html>
            <head>
                <meta charset="utf-8">
                <title>Resultado</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; }}
                    h1 {{ color: #2a7ae2; }}
                    pre {{ background-color: #f4f4f4; padding: 20px; border-radius: 8px; }}
                    a {{ margin-top: 20px; display: inline-block; color: #2a7ae2; text-decoration: none; }}
                </style>
            </head>
            <body>
                <h1>✅ Análisis completado</h1>
                <h2>🗣️ Transcripción</h2>
                <p>{transcription}</p>
                <h2>📝 Feedback</h2>
                <pre>{feedback_text}</pre>
                <a href="/">⬅️ Volver</a>
            </body>
        </html>
        """

    except subprocess.CalledProcessError:
        return HTMLResponse(content="⚠️ Error al convertir el archivo. Asegúrate de que ffmpeg está instalado.", status_code=500)
    except Exception as e:
        traceback.print_exc()
        return HTMLResponse(content=f"⚠️ Error: {str(e)}", status_code=500)
