import os
import base64
import io
import struct
from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image
from google import genai
from google.genai import types

app = FastAPI()

# Setup folders
for folder in ["static", "templates"]:
    if not os.path.exists(folder): os.makedirs(folder)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Initialize Client (Make sure GOOGLE_API_KEY is set in your environment)
client = genai.Client()

def add_wav_header(pcm_data, sample_rate=24000):
    """Adds a WAV header to raw PCM L16 data so it's playable in browsers."""
    bits_per_sample = 16
    channels = 1
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    data_size = len(pcm_data)
    
    header = struct.pack('<4sI4s4sIHHIIHH4sI',
        b'RIFF', 36 + data_size, b'WAVE', b'fmt ', 16, 1, channels, 
        sample_rate, byte_rate, block_align, bits_per_sample, b'data', data_size)
    return header + pcm_data

@app.post("/analyze")
async def analyze_input(mode: str = Form(...), text_input: str = Form(""), file: UploadFile = File(None)):
    try:
        # 1. Prepare visual/text input
        prompt_content = [text_input if text_input else "What do you see? Give me a tour guide insight."]
        if file and mode in ['image', 'camera']:
            image_bytes = await file.read()
            prompt_content.append(Image.open(io.BytesIO(image_bytes)))

        # 2. Agent 1: Research (The 'Brain')
        research_response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt_content,
            config=types.GenerateContentConfig(
                system_instruction="You are a charismatic tour guide. Give a short, fascinating 2-sentence insight."
            )
        )
        insight_text = research_response.text

        # 3. Agent 2: Speech (The 'Voice' - Now also voicing Agent 1's insight)
        # Using Aoede for a lifelike, breezy tone
        speech_response = client.models.generate_content(
            model='gemini-2.5-flash-preview-tts',
            contents=f"Say this as a friendly guide: {insight_text}",
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name='Aoede')
                    )
                )
            )
        )

        # 4. Extract and Fix Audio
        audio_part = speech_response.candidates[0].content.parts[0]
        if audio_part.inline_data:
            raw_pcm = audio_part.inline_data.data
            # CRITICAL FIX: Wrap raw PCM in a WAV header
            wav_data = add_wav_header(raw_pcm)
            audio_base64 = base64.b64encode(wav_data).decode('utf-8')
            
            return JSONResponse(content={
                "status": "success",
                "insight": insight_text,
                "audio_data": f"data:audio/wav;base64,{audio_base64}"
            })
        
        raise Exception("No audio data generated.")

    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)