from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image
import pytesseract
import openai
import os
import json

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with your own secret key

# Configure the SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads/'  # Folder to store uploaded files

db = SQLAlchemy(app)

# Set your OpenAI API key
openai.api_key = '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'

# Ensure the upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Load CTF challenges from JSON
with open('merged_challenges.json', 'r') as f:
    challenges = json.load(f)

# Define User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)  # Adjusted length for the hashed password

# Create the database
with app.app_context():
    db.create_all()

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
def home():
    if 'email' in session:
        return render_template('index.html')
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        # Fetch the user from the database
        user = User.query.filter_by(email=email).first()
        
        # Check if user exists and password matches
        if user and check_password_hash(user.password, password):
            session['email'] = email
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials. Please try again.')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('User already exists. Please log in.')
            return redirect(url_for('login'))
        
        # Hash the password before storing it
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        
        # Create a new user instance and add to the database
        new_user = User(username=username, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful. Please log in.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('email', None)
    flash('You have been logged out.')
    return redirect(url_for('login'))

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
