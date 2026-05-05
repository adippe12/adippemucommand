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
        return "Tell me what to draw! Example: !tikz a red circle"
    
    prompt = (
        f"Task: Write TikZ code for: {query}. "
        "Rules:\n"
        "1. Return ONLY the code starting with \\begin{{tikzpicture}} and ending with \\end{{tikzpicture}}.\n"
        "2. Do NOT use Markdown code blocks (no ```).\n"
        "3. Use valid PGF math syntax. Never use English words like 'and', 'or', or 'to' inside coordinates or math.\n"
        "4. If 3D is requested, use standard TikZ 3D coordinates (x,y,z) or pgfplots.\n"
        "5. Keep it simple and robust."
    )
    
    try:
        response = model.generate_content(prompt)
        # Clean markdown if the AI ignored the 'no markdown' instruction
        clean_text = re.sub(r'```(?:latex|tikz)?|```', '', response.text).strip()
        
        match = re.search(r'\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}', clean_text, re.DOTALL)
        if not match:
            return "Error: The AI didn't return valid TikZ code structure."
            
        tikz_code = match.group(0)

        # 2. Enhanced LaTeX Template (Added pgfplots for better 3D support)
        latex_template = r"""\documentclass[tikz,border=2pt]{standalone}
\usepackage{pgfplots}
\pgfplotsset{compat=1.18}
\usetikzlibrary{math,shapes,arrows.meta,positioning,calc}
\begin{document}
%s
\end{document}
"""
        full_doc = latex_template % tikz_code
        compressed = zlib.compress(full_doc.encode('utf-8'), 9)
        encoded = base64.urlsafe_b64encode(compressed).decode('ascii')
        
        # 1. Generate the Kroki URL
        kroki_url = f"https://kroki.io/tikz/png/{encoded}"
        
        # 2. Shorten it to bypass Twitch limits
        tiny_req = requests.get(f"https://tinyurl.com/api-create.php?url={kroki_url}", timeout=5)
        
        if tiny_req.status_code == 200:
            short_id = tiny_req.text.replace("https://tinyurl.com/", "")
            
            return f'$<img src="{request.host_url}render/{short_id}">$'
            
        return "Error shortening URL."

    except Exception as e:
        return f"TikZ Error: {e}"
        


@app.route('/diagram')
def generate_diagram():
    query = request.args.get('q', '').strip()
    if not query:
        return "TUsage: !diagram [engine] [code]"

    try:
        # 1. Split Engine and Code
        parts = query.split(None, 1)
        if len(parts) < 2:
            return "Error: Provide engine and code (e.g., !diagram d2 A -> B)"
        
        engine = parts[0].lower()
        diagram_code = parts[1]

        # 2. TikZ Auto-Wrapper
        if engine == 'tikz' and r'\documentclass' not in diagram_code:
            diagram_code = rf"""\documentclass[tikz,border=2pt]{{standalone}}
\usepackage{{pgfplots}}
\pgfplotsset{{compat=1.18}}
\usetikzlibrary{{math,shapes,arrows.meta,positioning,calc}}
\begin{{document}}
{diagram_code}
\end{{document}}"""

        # 4. Encoding for Kroki
        compressed = zlib.compress(diagram_code.encode('utf-8'), 9)
        encoded = base64.urlsafe_b64encode(compressed).decode('ascii')
        kroki_url = f"https://kroki.io/{engine}/svg/{encoded}"
        
        # 5. --- SMART ERROR CAPURE ---
        check = requests.get(kroki_url, timeout=8)
        
        if check.status_code != 200:
            content = check.text
            error_msg = ""

            if "<html" in content.lower():
                # Step A: Try to find the summary error (the "strong" tag)
                summary_match = re.search(r'<strong id="error">(?:<code>.*?</code>)?\s*(.*?)\s*</strong>', content, re.DOTALL)
                
                # Step B: Try to find detailed logs (often in <pre> tags for TikZ/LaTeX)
                detail_match = re.search(r'<pre>(.*?)</pre>', content, re.DOTALL)

                if summary_match:
                    error_msg = re.sub(r'<.*?>', '', summary_match.group(1)) # Remove any inner tags
                
                if detail_match and engine == 'tikz':
                    # For TikZ, the detail is usually more helpful than the summary
                    error_msg = detail_match.group(1).split('!', 1)[-1] # Grab the part after the LaTeX '!'

            else:
                # If it's not HTML, Kroki sent plain text error
                error_msg = content

            # Clean up and truncate for Twitch (max 400 chars)
            clean_msg = " ".join(error_msg.split()) # Remove newlines/extra spaces
            return f"❌ {engine.upper()} Error: {clean_msg[:350]}..."

        # 6. Success: Shorten and Return
        tiny_req = requests.get(f"https://tinyurl.com/api-create.php?url={kroki_url}", timeout=5)
        if tiny_req.status_code == 200:
            short_id = tiny_req.text.replace("https://tinyurl.com/", "")
            return f'$<img src="{request.host_url}render/{short_id}">$'
            
        return "Error: TinyURL failed."

    except Exception as e:
        return f"⚠️ System Error: {str(e)}"

# ==========================================
# SECURE IMAGE PROXY
# ==========================================
@app.route('/render/<short_id>')
def render_image(short_id):
    try:
        # 1. Fetch the image (Following the TinyURL redirect)
        img_response = requests.get(f"https://tinyurl.com/{short_id}", timeout=10)
        
        # 2. THE SECURITY CHECK: 
        # Only allow the request if it actually ends up at Kroki's TikZ renderer
        if not img_response.url.startswith("https://kroki.io/"):
            return "Unauthorized: Only TikZ diagrams from Kroki are allowed.", 403
        
        # 3. Return the image data
        if img_response.status_code == 200:
            content_type = img_response.headers.get('Content-Type')
            return Response(img_response.content, mimetype=content_type)
            
    except Exception as e:
        return "Proxy Error", 500