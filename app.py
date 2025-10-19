import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from passlib.hash import sha256_crypt
from datetime import date
from werkzeug.utils import secure_filename

# --- APP CONFIGURATION ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'a-very-secret-key-that-you-should-change'
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///portal.db')
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL.replace("postgres://", "postgresql://", 1)
app.config['UPLOAD_FOLDER'] = 'static/images/profile_pics'
db = SQLAlchemy(app)

# --- LOGIN MANAGER SETUP ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- DATABASE MODELS ---
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
    payment_status = db.Column(db.String(20), default='pending')
    # Add a relationship to easily access the course from an enrollment object
    course = db.relationship('Course', backref='enrollments')


class Mark(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    paper_name = db.Column(db.String(100), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    date_recorded = db.Column(db.Date, default=date.today)

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    youtube_link = db.Column(db.String(200), nullable=False)

# --- HELPER FUNCTIONS ---
def generate_index_number():
    last_user = User.query.order_by(User.index_number.desc()).first()
    if last_user and last_user.index_number:
        return str(int(last_user.index_number) + 1)
    else:
        return "8374000"

def get_embed_url(youtube_url):
    """Extracts the video ID and creates an embeddable URL."""
    video_id = None
    if "watch?v=" in youtube_url:
        video_id = youtube_url.split("watch?v=")[1].split('&')[0]
    elif "youtu.be/" in youtube_url:
        video_id = youtube_url.split("youtu.be/")[1].split('?')[0]
    
    if video_id:
        return f"https://www.youtube.com/embed/{video_id}"
    return None

# Make the Python function available to all HTML templates
app.jinja_env.globals.update(get_embed_url=get_embed_url)

# --- ROUTES ---

@app.route('/')
def home():
    courses = Course.query.all()
    videos = Video.query.order_by(Video.id.desc()).all()
    daily_quote = "The best way to predict the future is to create it."
    return render_template('index.html', courses=courses, quote=daily_quote, videos=videos)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        password = request.form.get('password')
        if password != request.form.get('confirm_password'):
            flash('Passwords do not match!', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(email=request.form.get('email')).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('register'))

        hashed_password = sha256_crypt.hash(password)
        new_user = User(
            index_number=generate_index_number(),
            name=request.form.get('name'),
            email=request.form.get('email'),
            password=hashed_password,
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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email')).first()
        if user and sha256_crypt.verify(request.form.get('password'), user.password):
            login_user(user)
            flash('You are now logged in.', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/dashboard')
@login_required
def dashboard():
    birthday_wish = ""
    today = date.today()
    if current_user.birthday.month == today.month and current_user.birthday.day == today.day:
        birthday_wish = f"Happy Birthday, {current_user.name}! 🎉"
    
    student_marks = Mark.query.filter_by(user_id=current_user.id).order_by(Mark.date_recorded.desc()).all()
    chart_labels = [mark.paper_name for mark in reversed(student_marks)]
    chart_data = [mark.score for mark in reversed(student_marks)]
    
    enrollments = current_user.enrollments

    return render_template('dashboard.html', wish=birthday_wish, marks=student_marks, chart_labels=chart_labels, chart_data=chart_data, enrollments=enrollments)

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        current_user.name = request.form.get('name')
        current_user.email = request.form.get('email')
        current_user.school = request.form.get('school')
        current_user.exam_year = request.form.get('exam_year')
        current_user.whatsapp_number = request.form.get('whatsapp_number')
        current_user.guardian_contact = request.form.get('guardian_contact')

        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file.filename != '':
                upload_folder = app.config['UPLOAD_FOLDER']
                os.makedirs(upload_folder, exist_ok=True)
                filename = secure_filename(file.filename)
                unique_filename = f"{current_user.index_number}_{filename}"
                file.save(os.path.join(upload_folder, unique_filename))
                current_user.profile_picture = unique_filename
        
        db.session.commit()
        flash('Your profile has been updated successfully!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('edit_profile.html')

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    if not current_user.is_admin:
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        form_type = request.form.get('form_type')

        if form_type == 'add_course':
            new_course = Course(name=request.form.get('course_name'), price=float(request.form.get('course_price')))
            db.session.add(new_course)
            db.session.commit()
            flash('Course added successfully.', 'success')

        elif form_type == 'add_mark':
            student = User.query.filter_by(index_number=request.form.get('index_number')).first()
            if student:
                new_mark = Mark(user_id=student.id, paper_name=request.form.get('paper_name'), score=int(request.form.get('score')))
                db.session.add(new_mark)
                db.session.commit()
                flash('Mark added successfully.', 'success')
            else:
                flash('Student with that index number not found.', 'danger')
        
        elif form_type == 'add_video':
            link = request.form.get('video_link')
            if get_embed_url(link):
                new_video = Video(title=request.form.get('video_title'), youtube_link=link)
                db.session.add(new_video)
                db.session.commit()
                flash('Video added successfully.', 'success')
            else:
                flash('Invalid YouTube URL provided.', 'danger')
        
        elif form_type == 'enroll_student':
            index_number = request.form.get('index_number')
            course_id = request.form.get('course_id')
            student = User.query.filter_by(index_number=index_number).first()
            course = Course.query.get(course_id)
            if student and course:
                existing_enrollment = Enrollment.query.filter_by(user_id=student.id, course_id=course.id).first()
                if existing_enrollment:
                    flash(f'{student.name} is already enrolled in {course.name}.', 'warning')
                else:
                    new_enrollment = Enrollment(user_id=student.id, course_id=course.id, payment_status='manual_active')
                    db.session.add(new_enrollment)
                    db.session.commit()
                    flash(f'Successfully enrolled {student.name} in {course.name}.', 'success')
            else:
                flash('Invalid Student Index or Course.', 'danger')
            
        return redirect(url_for('admin'))
    
    students = User.query.all()
    courses = Course.query.all()
    videos = Video.query.all()
    return render_template('admin.html', students=students, courses=courses, videos=videos)

@app.route('/delete_video/<int:video_id>', methods=['POST'])
@login_required
def delete_video(video_id):
    if not current_user.is_admin:
        return redirect(url_for('home'))
    
    video_to_delete = Video.query.get_or_404(video_id)
    db.session.delete(video_to_delete)
    db.session.commit()
    flash('Video deleted successfully.', 'success')
    return redirect(url_for('admin'))

@app.route('/delete_course/<int:course_id>', methods=['POST'])
@login_required
def delete_course(course_id):
    if not current_user.is_admin:
        return redirect(url_for('home'))
    
    course_to_delete = Course.query.get_or_404(course_id)
    db.session.delete(course_to_delete)
    db.session.commit()
    flash('Course deleted successfully.', 'success')
    return redirect(url_for('admin'))

# --- RUN THE APP ---
if __name__ == '__main__':
    app.run(debug=True)
