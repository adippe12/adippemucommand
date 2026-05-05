import os
import google.generativeai as genai
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

app = FastAPI()

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')

@app.get("/adippe")
async def get_adippe_art():
    prompt = (
        "Generate a very tiny, funny ASCII art or 'LaTeX-style' text art "
        "using mathematical symbols. The main word is 'adippe'. "
        "It must be ONE LINE only and under 200 characters so it fits in a Twitch chat. "
        "Make it look like a funny creature or a fancy math formula. Use colors. dont use strange Unicode character"
        "Return ONLY the art string, no explanation."
    )
    
    try:
        response = model.generate_content(prompt)
        # Clean the response to ensure it's one line
        art = response.text.replace('\n', ' ').strip()
        return PlainTextResponse(art)
    except Exception as e:
        return PlainTextResponse(f"Error: Could not find adippe's art right now.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
