import os
import requests
import io
from flask import Flask, request, Response
from pypdf import PdfReader
import google.generativeai as genai
import zlib
import base64
import re 


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




@app.route('/tikz')
def generate_tikz():
    query = request.args.get('q')
    if not query:
        return "Tell me what to draw! Example: !tikz a red circle with a blue square"
    
    prompt = (
        f"Write TikZ code to draw: {query}. "
        "Return ONLY the raw code starting with \\begin{tikzpicture} and ending with \\end{tikzpicture}. "
        "DO NOT write \\documentclass or \\usepackage. "
        "You have access to tikz-3dplot, math, shapes, positioning, and calc libraries. "
        "No explanations, no markdown."
    )
    
    try:
        response = model.generate_content(prompt)
        raw_text = response.text
        
        match = re.search(r'\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}', raw_text, re.DOTALL)
        if not match:
            return "Error: The AI forgot how to draw (No tikzpicture found)."
            
        tikz_code = match.group(0)

        latex_template = r"""\documentclass{article}
\usepackage{tikz}
\usepackage{tikz-3dplot}
\usetikzlibrary{math,shapes,arrows.meta,positioning,calc}
\usepackage[active,tightpage]{preview}
\PreviewEnvironment{tikzpicture}
\setlength\PreviewBorder{0.125pt}
\begin{document}
%s
\end{document}
"""
        full_latex_document = latex_template % tikz_code

        # Compress for Kroki
        compressed = zlib.compress(full_latex_document.encode('utf-8'), 9)
        encoded = base64.urlsafe_b64encode(compressed).decode('ascii')
        long_img_url = f"https://kroki.io/tikz/png/{encoded}"
        
        # 1. Secretly shorten the URL to bypass Twitch Character Limits
        tiny_req = requests.get(f"https://tinyurl.com/api-create.php?url={long_img_url}", timeout=5)
        
        if tiny_req.status_code == 200:
            short_url = tiny_req.text
            # Extract just the ID (e.g., 'y3abcde')
            short_id = short_url.replace("https://tinyurl.com/", "")
            
            # 2. Build YOUR whitelisted URL using your Vercel domain
            # request.host_url automatically grabs 'https://adippemucommand.vercel.app/'
            whitelisted_url = f"{request.host_url}render/{short_id}"
            
            return f'$<img src="{whitelisted_url}">$'
        else:
            return "Error: Could not process image URL."

    except Exception as e:
        print(f"TikZ Error: {e}")
        return "Error: My LaTeX compiler broke!"


# ==========================================
# NEW ROUTE: The Image Proxy / Renderer
# ==========================================
@app.route('/render/<short_id>')
def render_image(short_id):
    try:
        # Reconstruct the TinyURL
        tiny_url = f"https://tinyurl.com/{short_id}"
        
        # Fetch the actual image data. 
        # requests will automatically follow the TinyURL redirect to Kroki!
        img_response = requests.get(tiny_url, timeout=10)
        
        if img_response.status_code == 200:
            # Return the RAW image bytes directly to your chat extension
            return Response(img_response.content, mimetype='image/png')
        else:
            return "Image generation failed.", 404
            
    except Exception as e:
        print(f"Render Error: {e}")
        return "Could not load image.", 500