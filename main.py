import os
import requests
import io
from flask import Flask
from pypdf import PdfReader
import google.generativeai as genai

app = Flask(__name__)

genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')

@app.route("/adippe")
def get_adippe_art():
    prompt = (
        "Generate a very tiny, funny ASCII art or 'LaTeX-style' text art "
        "using mathematical symbols. The main word is 'adippe'. "
        "It must be ONE LINE only and under 200 characters so it fits in a Twitch chat. "
        "Make it funny or fancy math formula. Use colors. dont use strange Unicode character. "
        "Return ONLY the art string, no explanation."
    )
    
    try:
        response = model.generate_content(prompt)
        # Clean the response to ensure it's one line
        art = response.text.replace('\n', ' ').strip()
        return art
    except Exception as e:
        print(f"Error: {e}")
        return "Error: Could not find adippe's art right now."

@app.route('/theorem')
def get_theorem():
    try:
        # 1. Get the PDF (Handle Redirect)
        url = "http://www.theoremoftheday.org/todays.php"
        response = requests.get(url, allow_redirects=True, timeout=5)
        
        if response.status_code != 200:
            return "Could not reach the theorem site."

        # 2. Extract Text from PDF
        pdf_file = io.BytesIO(response.content)
        reader = PdfReader(pdf_file)
        
        # Get text from the first page (usually contains the main theorem info)
        text_content = ""
        for i in range(min(2, len(reader.pages))): # Read first 2 pages max
            text_content += reader.pages[i].extract_text()

        # 3. Ask Gemini to summarize
        prompt = (
            f"Here is a mathematical theorem text: {text_content[:3000]}. "
            "Give me a 1-sentence, extremely brief summary for a Twitch chat. "
            "Explain it Maximum 200 characters."
        )
        
        summary_response = model.generate_content(prompt)
        summary = summary_response.text.replace('\n', ' ').strip()
        
        return f"Today's Theorem: {summary}"

    except Exception as e:
        print(f"Error: {e}")
        return "The math was too hard for the bot to read today. (Error processing PDF)"