import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from passlib.hash import sha256_crypt
from datetime import date
from werkzeug.utils import secure_filename

# --- APP CONFIGURATION ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'a-very-secret-key-that-you-should-change' # Change this!
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///portal.db' # Using SQLite for simplicity
app.config['UPLOAD_FOLDER'] = 'static/images/profile_pics'
db = SQLAlchemy(app)

# --- DATABASE MODELS ---
# The UserMixin helps with Flask-Login
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    index_number = db.Column(db.String(10), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    exam_year = db.Column(db.Integer, nullable=False)
    school = db.Column(db.String(150))
    birthday = db.Column(db.Date, nullable=False)
    guardian_contact = db.Column(db.String(15))
    whatsapp_number = db.Column(db.String(15), nullable=False)
    profile_picture = db.Column(db.String(100), default='default.jpg')
    is_admin = db.Column(db.Boolean, default=False)
    # Relationships
    enrollments = db.relationship('Enrollment', backref='student', lazy=True)
    marks = db.relationship('Mark', backref='student', lazy=True)

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)

class Enrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    payment_status = db.Column(db.String(20), default='pending') # pending, paid, manual_active

class Mark(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    paper_name = db.Column(db.String(100), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    date_recorded = db.Column(db.Date, default=date.today)

    # ... (add this after your database models in app.py)

# --- HELPER FUNCTION ---
def generate_index_number():
    last_user = User.query.order_by(User.index_number.desc()).first()
    if last_user and last_user.index_number:
        last_index = int(last_user.index_number)
        return str(last_index + 1)
    else:
        return "8374000" # Starting number

# --- ROUTES ---
@app.route('/')
def home():
    courses = Course.query.all()
    # You can add logic for a daily quote here
    daily_quote = "The best way to predict the future is to create it."
    return render_template('index.html', courses=courses, quote=daily_quote)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Get form data
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        # ... get all other fields (exam_year, school, etc.)
        
        # --- VALIDATION ---
        if password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return redirect(url_for('register'))

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already registered.', 'danger')
            return redirect(url_for('register'))

        # --- OTP VERIFICATION STEP (Simulation) ---
        # In a real app, you would:
        # 1. Generate a random OTP code.
        # 2. Store it temporarily (e.g., in the user's session).
        # 3. Use Twilio API to send the OTP to the whatsapp_number.
        # 4. Redirect to an OTP verification page.
        # 5. After they enter the correct OTP, you proceed.
        # For now, we will skip this and register the user directly.

        hashed_password = sha256_crypt.hash(password)
        new_index_number = generate_index_number()
        
        new_user = User(
            index_number=new_index_number,
            name=name,
            email=email,
            password=hashed_password,
            # ... add all other fields from the form
            exam_year=request.form.get('exam_year'),
            school=request.form.get('school'),
            birthday=date.fromisoformat(request.form.get('birthday')),
            guardian_contact=request.form.get('guardian_contact'),
            whatsapp_number=request.form.get('whatsapp_number')
        )
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

# ... (add this after the app configuration in app.py)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Redirect here if user is not logged in

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ROUTES (continued) ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password_candidate = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and sha256_crypt.verify(password_candidate, user.password):
            login_user(user)
            flash('You are now logged in.', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
            return redirect(url_for('login'))
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

# ... (add to your routes)

@app.route('/dashboard')
@login_required
def dashboard():
    # Birthday wish logic
    birthday_wish = ""
    today = date.today()
    if current_user.birthday.month == today.month and current_user.birthday.day == today.day:
        birthday_wish = f"Happy Birthday, {current_user.name}! 🎉"
    
    # Get student's marks and sort them by date
    student_marks = Mark.query.filter_by(user_id=current_user.id).order_by(Mark.date_recorded.desc()).all()
    
    # Prepare data for the chart
    chart_labels = [mark.paper_name for mark in reversed(student_marks)]
    chart_data = [mark.score for mark in reversed(student_marks)]

    return render_template(
        'dashboard.html', 
        wish=birthday_wish, 
        marks=student_marks,
        chart_labels=chart_labels,
        chart_data=chart_data
    )

# ... (add to your routes)

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    # IMPORTANT: Ensure only admin can access this page
    if not current_user.is_admin:
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        # Logic to handle different admin forms
        form_type = request.form.get('form_type')

        if form_type == 'add_course':
            course_name = request.form.get('course_name')
            course_price = request.form.get('course_price')
            new_course = Course(name=course_name, price=float(course_price))
            db.session.add(new_course)
            db.session.commit()
            flash('Course added successfully.', 'success')

        elif form_type == 'add_mark':
            index_number = request.form.get('index_number')
            paper_name = request.form.get('paper_name')
            score = request.form.get('score')
            student = User.query.filter_by(index_number=index_number).first()
            if student:
                new_mark = Mark(user_id=student.id, paper_name=paper_name, score=int(score))
                db.session.add(new_mark)
                db.session.commit()
                flash('Mark added successfully.', 'success')
            else:
                flash('Student with that index number not found.', 'danger')

        elif form_type == 'manual_activate':
            # Logic to activate manual payments
            pass # Add your logic here based on enrollment table
            
        return redirect(url_for('admin'))
    
    students = User.query.all()
    courses = Course.query.all()
    return render_template('admin.html', students=students, courses=courses)

# Add this entire function to your app.py

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        # Update text fields
        current_user.name = request.form.get('name')
        current_user.email = request.form.get('email')
        current_user.school = request.form.get('school')
        current_user.exam_year = request.form.get('exam_year')
        current_user.whatsapp_number = request.form.get('whatsapp_number')
        current_user.guardian_contact = request.form.get('guardian_contact')

        # Handle profile picture upload
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file.filename != '':
                upload_folder = app.config['UPLOAD_FOLDER']
                os.makedirs(upload_folder, exist_ok=True) # Creates folder if it's missing

                filename = secure_filename(file.filename)
                unique_filename = current_user.index_number + '_' + filename
                
                save_path = os.path.join(upload_folder, unique_filename)
                file.save(save_path)
                
                current_user.profile_picture = unique_filename
        
        db.session.commit()
        flash('Your profile has been updated successfully!', 'success')
        return redirect(url_for('dashboard'))

    # For a GET request, show the edit page
    return render_template('edit_profile.html')

if __name__ == '__main__':
    app.run(debug=True)