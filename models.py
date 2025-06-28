# models.py

from datetime import datetime
from flask_login import UserMixin
# Import db instance and bcrypt instance (defined in extensions.py)
from extensions import db, bcrypt

# --- Database Models Definition ---

class User(db.Model, UserMixin): # Inherit from UserMixin
    """Represents the 'users' table for authentication."""
    __tablename__ = 'users' # Explicit table name

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(60), nullable=False) # Bcrypt hash length is 60
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # --- is_admin field has been REMOVED ---

    # --- Password Hashing Methods ---
    def set_password(self, password):
        """Hashes the provided password using bcrypt and stores the hash."""
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        """Checks if the provided password matches the stored hash."""
        return bcrypt.check_password_hash(self.password_hash, password)
    
    # --- End Password Hashing Methods ---

    def to_dict(self):
        """Returns a dictionary representation of the user, excluding sensitive info."""
        # is_admin field removed from response
        return {
            "id": self.id,
            "email": self.email
        }

    def __repr__(self):
        """String representation for debugging."""
        return f"<User {self.id}: {self.email}>"


# --- Curriculum Models (Subject, Grade, Strand, etc.) ---
# (These remain exactly the same as before)
class Subject(db.Model):
    __tablename__ = 'subjects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    strands = db.relationship('Strand', backref='subject', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {"id": self.id, "name": self.name}

    def __repr__(self):
        return f"<Subject {self.id}: {self.name}>"

class Grade(db.Model):
    __tablename__ = 'grades'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    strands = db.relationship('Strand', backref='grade', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {"id": self.id, "name": self.name}

    def __repr__(self):
        return f"<Grade {self.id}: {self.name}>"

class Strand(db.Model):
    __tablename__ = 'strands'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    grade_id = db.Column(db.Integer, db.ForeignKey('grades.id'), nullable=False)
    substrands = db.relationship('SubStrand', backref='strand', lazy=True, cascade="all, delete-orphan")
    __table_args__ = (db.UniqueConstraint('subject_id', 'grade_id', 'name', name='uq_strand_subject_grade_name'),)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "subject_id": self.subject_id, "grade_id": self.grade_id}

    def __repr__(self):
        return f"<Strand {self.id}: {self.name} (Subj:{self.subject_id}, Grd:{self.grade_id})>"

class SubStrand(db.Model):
    __tablename__ = 'substrands'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    strand_id = db.Column(db.Integer, db.ForeignKey('strands.id'), nullable=False)
    learning_outcomes = db.relationship('LearningOutcome', backref='substrand', lazy=True, cascade="all, delete-orphan")
    key_inquiry_questions = db.relationship('KeyInquiryQuestion', backref='substrand', lazy=True, cascade="all, delete-orphan")
    __table_args__ = (db.UniqueConstraint('strand_id', 'name', name='uq_substrand_strand_name'),)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "strand_id": self.strand_id}

    def __repr__(self):
        return f"<SubStrand {self.id}: {self.name} (Strand:{self.strand_id})>"

class LearningOutcome(db.Model):
    __tablename__ = 'learning_outcomes'
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    substrand_id = db.Column(db.Integer, db.ForeignKey('substrands.id'), nullable=False)

    def to_dict(self):
        return {"id": self.id, "description": self.description, "substrand_id": self.substrand_id}

    def __repr__(self):
        return f"<LearningOutcome {self.id}: {self.description[:50]}... (SubStrand:{self.substrand_id})>"

class KeyInquiryQuestion(db.Model):
    __tablename__ = 'key_inquiry_questions'
    id = db.Column(db.Integer, primary_key=True)
    question_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    substrand_id = db.Column(db.Integer, db.ForeignKey('substrands.id'), nullable=False)

    def to_dict(self):
        return {"id": self.id, "question_text": self.question_text, "substrand_id": self.substrand_id}

    def __repr__(self):
        return f"<KeyInquiryQuestion {self.id}: {self.question_text[:50]}... (SubStrand:{self.substrand_id})>"
