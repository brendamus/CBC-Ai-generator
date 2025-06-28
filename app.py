# app.py

# --- Imports ---
import os
import json
from flask import Flask, jsonify, request, render_template, redirect, url_for
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from flask_cors import CORS
from flask_login import login_user, logout_user, login_required, current_user
from dotenv import load_dotenv
# --- Import Extensions from extensions.py ---
from extensions import db, bcrypt, login_manager

# --- Define ai_model globally ---
ai_model = None

# --- Application Factory Function ---
def create_app():
    """Creates and configures the Flask application."""
    print("Creating Flask app instance...")
    # Ensure Flask knows where to find your HTML files
    app = Flask(__name__, template_folder='templates')

    # --- Load Environment Variables ---
    load_dotenv()

    # --- Configuration ---
    db_user = os.environ.get('DB_USERNAME', 'postgres')
    db_password = os.environ.get('DB_PASSWORD', 'password')
    db_host = os.environ.get('DB_HOST', 'localhost')
    db_port = os.environ.get('DB_PORT', '5432')
    db_name = os.environ.get('DB_NAME', 'cbc_curriculum_db')
    DATABASE_URI = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-replace-in-prod')
    if app.config['SECRET_KEY'] == 'dev-secret-key-replace-in-prod':
        print("WARNING: Using default SECRET_KEY. Set FLASK_SECRET_KEY environment variable!")
    print(f"Connecting to database: {DATABASE_URI.replace(db_password, '********')}")

    # --- Initialize Extensions with App ---
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    CORS(app, supports_credentials=True)

    # --- Import Models AFTER db is initialized ---
    import models

    # --- Configure Flask-Login (inside factory) ---
    login_manager.login_view = 'login_page'
    login_manager.session_protection = "strong"

    @login_manager.user_loader
    def load_user(user_id):
        try: return db.session.get(models.User, int(user_id))
        except (ValueError, TypeError): return None
        except Exception as e: app.logger.error(f"Error loading user {user_id}: {e}"); return None

    @login_manager.unauthorized_handler
    def unauthorized():
        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            return jsonify(error="Login required to access this resource"), 401
        return redirect(url_for('login_page'))

    # --- Register CLI Commands (inside factory) ---
    try:
        import commands
        commands.register_commands(app)
        print("CLI commands registered.")
    except Exception as e:
        app.logger.warning(f"Could not register commands: {e}")

    # --- AI Configuration (inside factory) ---
    print("Configuring AI...")
    global ai_model
    try:
        GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
        if GOOGLE_API_KEY:
            import google.generativeai as genai
            genai.configure(api_key=GOOGLE_API_KEY)
            ai_model = genai.GenerativeModel(os.environ.get('AI_MODEL_NAME', 'gemini-1.5-flash'))
            print(f"AI Configured successfully with model: {ai_model.model_name}")
        else:
            print("WARNING: GOOGLE_API_KEY not set. AI generation will be disabled.")
    except Exception as e:
        print(f"ERROR configuring AI: {e}.")

    # --- Page Serving Routes ---
    @app.route('/')
    def home():
        return render_template('landing.html')

    @app.route('/generator')
    @login_required
    def generator_page():
        return render_template('index.html')

    @app.route('/login')
    def login_page():
        return render_template('login.html')

    @app.route('/register')
    def register_page():
        return render_template('register.html')
        
    @app.route('/blog')
    def blog_page():
        return render_template('blog.html')
        
    @app.route('/test-generator')
    @login_required
    def test_generator_page():
        return render_template('test_generator.html')

    # --- API Routes ---
    @app.route('/api/health', methods=['GET'])
    def health_check():
        return jsonify({"status": "ok"}), 200

    @app.route('/api/register', methods=['POST'])
    def register():
        if not request.is_json: return jsonify(error="Request must be JSON"), 400
        data = request.get_json(); email = data.get('email'); password = data.get('password')
        if not email or not password: return jsonify(error="Missing credentials"), 400
        if models.User.query.filter_by(email=email.strip().lower()).first(): return jsonify(error="Email exists"), 409
        user = models.User(email=email.strip().lower()); user.set_password(password)
        db.session.add(user); db.session.commit()
        return jsonify(user.to_dict()), 201

    @app.route('/api/login', methods=['POST'])
    def login():
        if not request.is_json: return jsonify(error="Request must be JSON"), 400
        data = request.get_json(); email = data.get('email'); password = data.get('password')
        if not email or not password: return jsonify(error="Missing credentials"), 400
        user = models.User.query.filter_by(email=email.strip().lower()).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            return jsonify(user.to_dict()), 200
        return jsonify(error="Invalid credentials"), 401

    @app.route('/api/logout', methods=['POST'])
    @login_required
    def logout():
        logout_user()
        return jsonify(message="Logout successful"), 200

    @app.route('/api/current_user', methods=['GET'])
    @login_required
    def get_current_user():
        return jsonify(user=current_user.to_dict()), 200

    @app.route('/api/subjects', methods=['GET'])
    def get_subjects():
        try:
            subjects = models.Subject.query.order_by(models.Subject.name).all()
            return jsonify([s.to_dict() for s in subjects]), 200
        except Exception as e: app.logger.error(f"Error getting subjects: {e}"); return jsonify({"error": "Server error"}), 500

    @app.route('/api/grades', methods=['GET'])
    def get_grades():
        try:
            grades = models.Grade.query.order_by(models.Grade.name).all()
            return jsonify([g.to_dict() for g in grades]), 200
        except Exception as e: app.logger.error(f"Error getting grades: {e}"); return jsonify({"error": "Server error"}), 500

    @app.route('/api/strands', methods=['GET'])
    def get_strands():
        subject_id = request.args.get('subject_id', type=int)
        grade_id = request.args.get('grade_id', type=int)
        # Add a check for an 'all' parameter for the test generator
        if request.args.get('all') == 'true':
            try:
                strands = models.Strand.query.order_by(models.Strand.name).all()
                return jsonify([s.to_dict() for s in strands]), 200
            except Exception as e: app.logger.error(f"Error getting all strands: {e}"); return jsonify({"error": "Server error"}), 500

        if not all([subject_id, grade_id]): return jsonify({"error": "subject_id and grade_id are required"}), 400
        try:
            strands = models.Strand.query.filter_by(subject_id=subject_id, grade_id=grade_id).order_by(models.Strand.name).all()
            return jsonify([s.to_dict() for s in strands]), 200
        except Exception as e: app.logger.error(f"Error getting strands: {e}"); return jsonify({"error": "Server error"}), 500

    @app.route('/api/substrands', methods=['GET'])
    def get_substrands():
        strand_id = request.args.get('strand_id', type=int)
        if not strand_id: return jsonify({"error": "strand_id is required"}), 400
        try:
            items = models.SubStrand.query.filter_by(strand_id=strand_id).order_by(models.SubStrand.name).all()
            return jsonify([i.to_dict() for i in items]), 200
        except Exception as e: app.logger.error(f"Error getting substrands: {e}"); return jsonify({"error": "Server error"}), 500

    @app.route('/api/learning_outcomes', methods=['GET'])
    def get_learning_outcomes():
        substrand_id = request.args.get('substrand_id', type=int)
        if not substrand_id: return jsonify({"error": "substrand_id is required"}), 400
        try:
            items = models.LearningOutcome.query.filter_by(substrand_id=substrand_id).order_by(models.LearningOutcome.id).all()
            return jsonify([i.to_dict() for i in items]), 200
        except Exception as e: app.logger.error(f"Error getting learning outcomes: {e}"); return jsonify({"error": "Server error"}), 500

    # --- AI Question Generation Endpoint ---
    @app.route('/api/questions/generate', methods=['POST'])
    @login_required
    def generate_questions_endpoint():
        if not request.is_json: return jsonify({"error": "Request must be JSON"}), 400
        data = request.get_json()
        req = ['learning_outcome_id', 'num_questions', 'question_type']
        if not data or not all(f in data for f in req): return jsonify({"error": "Missing required fields"}), 400

        try:
            lo_id = int(data['learning_outcome_id'])
            num_q = int(data['num_questions'])
            q_type = str(data['question_type']).lower()
        except (ValueError, TypeError): return jsonify({"error": "Invalid data types for required fields"}), 400

        if not (0 < num_q <= 20): return jsonify({"error": "num_questions must be between 1 and 20"}), 400

        allowed_q = ["multiple_choice", "short_answer", "true_false", "fill_in_the_blank"]
        q_type_map = { "mcq": "multiple_choice", **{t:t for t in allowed_q} }
        mapped_q_type = q_type_map.get(q_type)
        if not mapped_q_type: return jsonify({"error": f"Unsupported question_type. Use one of: {list(q_type_map.keys())}"}), 400

        try: # Fetch context
            lo = db.session.get(models.LearningOutcome, lo_id)
            if not lo: return jsonify({"error": f"Learning Outcome ID {lo_id} not found."}), 404
            ss=lo.substrand; s=ss.strand if ss else None; subj=s.subject if s else None; gr=s.grade if s else None
            if not all([ss, s, subj, gr]):
                 app.logger.error(f"Incomplete context for LO ID {lo_id}"); return jsonify({"error": "Could not retrieve full context."}), 500
            ctx = {"subject": subj.name, "grade": gr.name, "strand": s.name, "substrand": ss.name, "outcome_description": lo.description }
        except Exception as e:
            app.logger.error(f"DB error fetching context for LO {lo_id}: {e}")
            return jsonify({"error": "Database error fetching context"}), 500

        prompt = f"""
        Generate {num_q} unique question(s) based on the Kenyan CBC curriculum.
        Question Type: {mapped_q_type}.
        Context:
        - Subject: {ctx['subject']}
        - Grade: {ctx['grade']}
        - Strand: {ctx['strand']}
        - Sub-Strand: {ctx['substrand']}
        - Specific Learning Outcome: "{ctx['outcome_description']}"

        Instructions:
        1.  Strictly assess the specified Learning Outcome.
        2.  Ensure questions are clear, concise, and grade-appropriate for {ctx['grade']}.
        3.  Vary the cognitive skill level of the questions according to Bloom's Taxonomy. Aim for a mix of levels (e.g., Remembering, Understanding, Applying, Analyzing).
        4.  For each question, indicate the targeted Bloom's Taxonomy level.

        Output Format:
        Respond ONLY with a valid JSON list of question objects. No extra text before or after the list.
        Each question object MUST include 'type', 'question', 'taxonomy_level', and 'answer'.
        For 'multiple_choice', also include 'options' (a list of 4 strings).

        Example JSON Output (list of objects):
        [
            {{
                "type": "multiple_choice",
                "question": "Which of these is a primary color?",
                "options": ["Green", "Orange", "Blue", "Purple"],
                "answer": "Blue",
                "taxonomy_level": "Remembering"
            }}
        ]
        """
        try: # Call AI
            global ai_model
            if not ai_model:
                 app.logger.error("AI Model not configured during request.")
                 return jsonify({"error": "AI Model not available"}), 500

            print("==========================================================")
            print("--- PROMPT SENT TO AI (Single Question) ---")
            print(prompt)
            print("----------------------------------------------------------")

            response = ai_model.generate_content(prompt)
            
            print("--- RAW AI RESPONSE RECEIVED ---")
            print(response.text)
            print("----------------------------------------------------------")

            try: # Parse AI response
                clean_text = response.text.strip().removeprefix("```json").removesuffix("```").strip()
                if not clean_text:
                    app.logger.warning(f"AI returned an empty string for LO ID {lo_id}")
                    return jsonify({"error": "AI returned an empty response."}), 500
                gen_q = json.loads(clean_text)
                if not isinstance(gen_q, list): raise ValueError("AI response is not a JSON list.")
            except json.JSONDecodeError as json_err:
                app.logger.error(f"JSON Parse Error: {json_err} on text: '{clean_text}'")
                return jsonify({"error": "AI response format error (JSON).", "details": str(json_err)}), 500
            
            if not gen_q:
                app.logger.warning(f"AI returned an empty JSON list [] for LO ID {lo_id}.")

            app.logger.info(f"User '{current_user.email}' generated {len(gen_q)} questions for LO ID {lo_id}")
            return jsonify(gen_q), 200

        except Exception as e:
            app.logger.error(f"AI Generation Error for LO ID {lo_id}: {e}")
            return jsonify({"error": "AI generation failed.", "details": str(e)}), 500
            
    # --- Full Test Generation Endpoint ---
    @app.route('/api/tests/generate', methods=['POST'])
    @login_required
    def generate_full_test_endpoint():
        if not request.is_json: return jsonify({"error": "Request must be JSON"}), 400
        
        data = request.get_json()
        subject_id = data.get('subject_id'); grade_id = data.get('grade_id'); topics = data.get('topics')

        if not all([subject_id, grade_id, topics]) or not isinstance(topics, list) or len(topics) == 0:
            return jsonify({"error": "Missing or invalid required fields: subject_id, grade_id, topics"}), 400

        try:
            subject = db.session.get(models.Subject, subject_id)
            grade = db.session.get(models.Grade, grade_id)
            if not subject or not grade: return jsonify({"error": "Invalid subject_id or grade_id"}), 404

            prompt_sections = ""
            for i, topic in enumerate(topics):
                strand_id = topic.get('strand_id')
                num_questions = topic.get('num_questions', 3)
                strand = db.session.get(models.Strand, strand_id)
                if not strand: continue
                learning_outcomes = models.LearningOutcome.query.join(models.SubStrand).filter(models.SubStrand.strand_id == strand_id).all()
                if not learning_outcomes: continue
                lo_texts = "\\n- ".join([lo.description for lo in learning_outcomes])
                prompt_sections += f"""
---
**Section {i+1}: {strand.name}**
Generate {num_questions} questions (mix of multiple_choice and short_answer) that assess the following learning outcomes:
- {lo_texts}
---
"""
            if not prompt_sections: return jsonify({"error": "No valid topics with learning outcomes found."}), 400

            prompt = f"""
            You are an expert exam creator for the Kenyan CBC curriculum.
            Create a full, well-structured {grade.name} {subject.name} test paper.
            The test must have the following sections, with the specified number of questions for each.
            {prompt_sections}
            GLOBAL INSTRUCTIONS:
            1. For the entire test, ensure a good mix of question types (multiple_choice, short_answer) and cognitive levels based on Bloom's Taxonomy (Remembering, Understanding, Applying, Analyzing).
            2. Each generated question must be a JSON object with 'type', 'question', 'answer', and 'taxonomy_level'. Multiple choice questions must also have an 'options' list.
            FINAL OUTPUT FORMAT:
            Respond ONLY with a single, valid JSON object. Do not include any text before or after the JSON.
            The JSON object should have the structure: {{"test_title": "...", "sections": [{{"section_title": "...", "questions": [...]}}]}}
            """
            
            global ai_model
            if not ai_model: return jsonify({"error": "AI Model not available"}), 500
            
            print("--- SENDING FULL TEST PROMPT TO AI ---")
            response = ai_model.generate_content(prompt)
            print("--- FULL TEST RESPONSE RECEIVED ---")
            
            clean_text = response.text.strip().removeprefix("```json").removesuffix("```").strip()
            if not clean_text: return jsonify({"error": "AI returned an empty response."}), 500
            
            generated_test = json.loads(clean_text)
            return jsonify(generated_test), 200

        except Exception as e:
            app.logger.error(f"Full test generation failed: {e}")
            return jsonify({"error": "An internal error occurred during test generation.", "details": str(e)}), 500

    # Return the configured app instance from the factory
    return app

# --- Run the Application ---
if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        print("Ensuring database tables exist...")
        db.create_all()
        print("Database tables checked/created.")
    app.run(host='0.0.0.0', port=5000, debug=True)