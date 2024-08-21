from flask import Flask, render_template, request, jsonify
import openai
import os
from werkzeug.utils import secure_filename
from PIL import Image
import pytesseract
import json

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'

# Set your OpenAI API key
openai.api_key = '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'
# Ensure the upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Load your data from JSON
with open('merged_challenges.json', 'r') as f:
    challenges = json.load(f)

# Function to find relevant context for a given challenge
def find_challenge_context(description):
    for challenge in challenges:
        if description.lower() in challenge['description'].lower():
            context = f"Challenge Name: {challenge['name']}\n"
            context += f"Category: {challenge['category']}\n"
            context += f"Description: {challenge['description']}\n"
            context += "Hints: " + ", ".join(challenge['hints']) + "\n"
            return context
    return "No specific context found. Please describe your challenge."

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.form.get("message")
    uploaded_files = request.files.getlist("files")

    # Process uploaded files
    file_contents = []
    for file in uploaded_files:
        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            # Handle image files
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff')):
                try:
                    text = pytesseract.image_to_string(Image.open(file_path))
                    file_contents.append(f"Extracted text from {filename}:\n{text}")
                except Exception as e:
                    file_contents.append(f"Could not extract text from {filename}: {e}")
            
            # Handle text and code files
            elif filename.lower().endswith(('.txt', '.py', '.md', '.html', '.css', '.js')):
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                        file_contents.append(f"Content of {filename}:\n{content}")
                except Exception as e:
                    file_contents.append(f"Could not read {filename}: {e}")
            
            # Handle other file types
            else:
                file_contents.append(f"File {filename} was uploaded but not processed.")

    file_context = "\n".join(file_contents)
    
    if user_message or file_contents:
        context = find_challenge_context(user_message) + "\n" + file_context
        full_prompt = f"Here is some context from files and user input:\n{context}\n\nProvide a helpful hint or advice to solve the challenge:"
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert in Capture The Flag (CTF) challenges."},
                    {"role": "user", "content": full_prompt}
                ],
                max_tokens=150,
                temperature=0.7,
            )
            gpt_response = response['choices'][0]['message']['content']
            return jsonify({"response": gpt_response})
        
        except openai.error.OpenAIError as e:
            return jsonify({"response": f"An error occurred: {e}"})
    
    return jsonify({"response": "No message or files received"})

if __name__ == '__main__':
    app.run(debug=True)

