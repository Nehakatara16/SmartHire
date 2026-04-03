from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mysqldb import MySQL
import os
import re
from datetime import datetime

#==============AI SCORING==============
def calculate_ai_score(resume_text, job_description):
    # Convert to lowercase
    resume_text = resume_text.lower()
    job_description = job_description.lower()

    # Extract words
    resume_words = set(re.findall(r'\w+', resume_text))
    job_words = set(re.findall(r'\w+', job_description))

    # Remove very common words (optional basic stopwords)
    stopwords = {"and", "or", "the", "is", "in", "at", "of", "a", "to"}
    job_words = job_words - stopwords

    # Matching
    matched = resume_words.intersection(job_words)

    if len(job_words) == 0:
        return 0

    score = (len(matched) / len(job_words)) * 100
    return round(score, 2)

# ===== LOAD ENV =====
from dotenv import load_dotenv
load_dotenv()

# ===== EMAIL =====
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ===== APP INIT =====
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "fallback_secret")

# ================= MYSQL CONFIG =================
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'root'
app.config['MYSQL_DB'] = 'smarthire'

mysql = MySQL(app)
# ================= SKILL + SCORE LOGIC =================
COMMON_SKILLS = [
    "python", "java", "c++", "sql", "machine learning",
    "flask", "django", "html", "css", "javascript", "react"
]

def extract_skills_from_text(text):
    text = text.lower()
    found = [skill for skill in COMMON_SKILLS if skill in text]
    return list(set(found))

def calculate_score(skills):
    return min(len(skills) * 10, 100)

#===================UPLOAD==================
@app.route('/upload_page')
def upload():
    if 'user' not in session:
        return redirect(url_for('login'))

    return render_template('upload.html', role=session.get('role')) 

@app.route('/upload', methods=['POST'])
def upload_page():
    if 'user' not in session:
        return redirect(url_for('login')) 

    cur = mysql.connection.cursor()

    # ===== ADMIN MULTIPLE UPLOAD =====
    if session.get('role') == 'admin':
        files = request.files.getlist('resumes')
        job_role = request.form.get('job_role')  # used as job description

        for file in files:
            if file:
                filename = file.filename
                path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(path)

                # 👉 READ FILE TEXT
                try:
                    with open(path, "r", errors="ignore") as f:
                        text = f.read()
                except:
                    text = ""

                # EXISTING LOGIC
                skills = extract_skills_from_text(text)
                score = calculate_score(skills)

                # ===== NEW AI SCORE =====
                ai_score = calculate_ai_score(text, job_role if job_role else "")

                cur.execute("""
                    INSERT INTO results(username, filename, score, status, job_role, match_score, skills, ai_score)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    session['user'],
                    filename,
                    score,
                    "Pending",
                    job_role,
                    ai_score,  # UPDATED (earlier was score)
                    ",".join(skills),
                    ai_score
                ))

    # ===== USER SINGLE UPLOAD =====
    else:
        file = request.files['resume']
        job_role = request.form.get('job_role')  # NEW

        if file:
            filename = file.filename
            path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(path)

            try:
                with open(path, "r", errors="ignore") as f:
                    text = f.read()
            except:
                text = ""

            # EXISTING LOGIC
            skills = extract_skills_from_text(text)
            score = calculate_score(skills)

            # ===== NEW AI SCORE =====
            ai_score = calculate_ai_score(text, job_role if job_role else "")

            cur.execute("""
                INSERT INTO results(username, filename, score, status, job_role, match_score, skills, ai_score)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                session['user'],
                filename,
                score,
                "Pending",
                job_role,
                ai_score,
                ",".join(skills),
                ai_score
            ))

    mysql.connection.commit()
    return redirect(url_for('dashboard'))

# ================= HTML EMAIL FUNCTION =================
def send_email(to_email, subject, username, status):
    try:
        sender_email = os.environ.get("EMAIL_USER")
        sender_password = os.environ.get("EMAIL_PASS")

        if not sender_email or not sender_password:
            print("❌ Email credentials missing")
            return

        # ===== STATUS DESIGN =====
        color = "#38bdf8"
        message = "Your application is under review."

        if status == "Shortlisted":
            color = "#facc15"
            message = "🎉 You have been shortlisted for the next round!"

        elif status == "Selected":
            color = "#22c55e"
            message = "🏆 Congratulations! You are SELECTED!"

        elif status == "Rejected":
            color = "#ef4444"
            message = "🙏 Thank you for applying. We appreciate your effort."

        # ===== GLASS MORPHISM HTML =====
        html = f"""
        <html>
        <body style="margin:0; padding:0; font-family:Arial;
                     background: linear-gradient(135deg, #0f172a, #1e293b);">

            <div style="padding:40px; text-align:center;">
                
                <div style="
                    max-width:500px;
                    margin:auto;
                    padding:30px;
                    border-radius:20px;
                    background: rgba(255,255,255,0.08);
                    backdrop-filter: blur(15px);
                    box-shadow: 0 8px 32px rgba(0,0,0,0.4);
                    color:white;
                ">

                    <h2 style="color:{color};">SmartHire Update</h2>

                    <p>Hello <b>{username}</b>,</p>

                    <p style="font-size:16px;">{message}</p>

                    <div style="
                        margin-top:20px;
                        padding:12px;
                        border-radius:10px;
                        background:{color};
                        color:white;
                        font-weight:bold;
                    ">
                        Status: {status}
                    </div>

                    <p style="margin-top:20px; font-size:12px; opacity:0.7;">
                        This is an automated message from SmartHire
                    </p>

                </div>

            </div>

        </body>
        </html>
        """

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = to_email

        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)

        print(f"✅ Stylish email sent to {to_email}")

    except Exception as e:
        print("❌ Email failed:", e)


# ================= LOGIN =================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        pwd = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute(
            "SELECT id, username, email, password, role FROM users WHERE username=%s OR email=%s",
            (user, user)
        )
        data = cur.fetchone()

        if data and check_password_hash(data[3], pwd):
            session['user'] = data[1]
            session['role'] = data[4]
            return redirect(url_for('dashboard'))

        return render_template('login.html', error="Invalid Credentials")

    return render_template('login.html')


# ================= SIGNUP =================
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        user = request.form['username']
        email = request.form['email']
        pwd = generate_password_hash(request.form['password'])
        role = request.form['role']

        cur = mysql.connection.cursor()
        cur.execute(
            "INSERT INTO users(username, email, password, role) VALUES(%s,%s,%s,%s)",
            (user, email, pwd, role)
        )
        mysql.connection.commit()

        return redirect(url_for('login'))

    return render_template('signup.html')


# ================= DASHBOARD =================
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    if session.get('role') == "admin":
        cur.execute("""
            SELECT id, username, filename, score, status, rank_no, notes, job_role, match_score, skills, upload_time
            FROM results ORDER BY score DESC
        """)
    else:
        cur.execute("""
            SELECT id, username, filename, score, status, rank_no, notes, job_role, match_score, skills, upload_time
            FROM results WHERE username=%s ORDER BY score DESC
        """, (session['user'],))

    data = cur.fetchall()

    total = len(data)
    shortlisted = sum(1 for r in data if r[4] == "Shortlisted")
    rejected = sum(1 for r in data if r[4] == "Rejected")

    # ===== USER ANALYTICS =====
    scores = [float(r[3]) for r in data if r[3]]
    avg_score = round(sum(scores)/len(scores), 2) if scores else 0
    highest = max(scores) if scores else 0

    rank = 1
    results = []

    for row in data:
        cur.execute("UPDATE results SET rank_no=%s WHERE id=%s", (rank, row[0]))

        results.append({
            "id": row[0],
            "username": row[1],
            "name": row[2],
            "score": float(row[3]) if row[3] else 0,
            "status": row[4] if row[4] else "Pending",
            "rank": rank,
            "notes": row[6] if row[6] else "",
            "job_role": row[7] if row[7] else "",
            "match": float(row[8]) if row[8] else 0,
            "skills": row[9].split(",") if row[9] else [],
            "time": str(row[10])
        })
        rank += 1

    mysql.connection.commit()

    return render_template("dashboard.html",
                           results=results,
                           total=total,
                           shortlisted=shortlisted,
                           rejected=rejected,
                           avg_score=avg_score,
                           highest=highest)

#=====================ADMIN PANEL============
@app.route('/admin')
def admin():
    if 'user' not in session:
        return redirect(url_for('login'))

    if session.get('role') != "admin":
        return redirect(url_for('dashboard'))

    cur = mysql.connection.cursor()

    cur.execute("SELECT id, username, email, role FROM users")

    users = cur.fetchall()

    return render_template("admin.html", users=users)


# ================= STATUS UPDATE =================
@app.route('/update_status/<int:id>/<string:status>')
def update_status(id, status):
    if session.get('role') != "admin":
        return redirect(url_for('dashboard'))

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT users.email, users.username
        FROM users
        JOIN results ON users.username = results.username
        WHERE results.id=%s
    """, (id,))
    user_data = cur.fetchone()

    cur.execute("UPDATE results SET status=%s WHERE id=%s", (status, id))
    mysql.connection.commit()

    if user_data:
        email, username = user_data

        subject = f"SmartHire Status Update: {status}"
        send_email(email, subject, username, status)

    return redirect(url_for('dashboard'))


# ================= ADD NOTES =================
@app.route('/add_note/<int:id>', methods=['POST'])
def add_note(id):
    if session.get('role') != "admin":
        return redirect(url_for('dashboard'))

    note = request.form.get('note')

    cur = mysql.connection.cursor()
    cur.execute("UPDATE results SET notes=%s WHERE id=%s", (note, id))
    mysql.connection.commit()

    return redirect(url_for('dashboard'))


# ================= PREVIEW =================
@app.route('/preview/<string:filename>')
def preview(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# ================= DELETE =================
@app.route('/delete_result/<int:id>')
def delete_result(id):
    if session.get('role') != "admin":
        return redirect(url_for('dashboard'))

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM results WHERE id=%s", (id,))
    mysql.connection.commit()

    return redirect(url_for('dashboard'))

#=================SCORE ANALYTICS===========
@app.route('/admin_analytics')
def admin_analytics():

    if 'user' not in session:
        return redirect(url_for('login'))

    if session.get('role') != "admin":
        return redirect(url_for('dashboard'))

    cur = mysql.connection.cursor()

    # 📊 Analytics Queries
    cur.execute("SELECT AVG(score) FROM results")
    avg_score = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM results WHERE status='Selected'")
    selected = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM results WHERE status='Rejected'")
    rejected = cur.fetchone()[0]

    cur.execute("SELECT MAX(score) FROM results")
    highest = cur.fetchone()[0] or 0

    cur.execute("SELECT MIN(score) FROM results")
    lowest = cur.fetchone()[0] or 0

    return render_template("analytics.html",
                           avg_score=round(avg_score, 2),
                           selected=selected,
                           rejected=rejected,
                           highest=highest,
                           lowest=lowest)


# ================= LOGOUT =================
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ================= RUN =================
if __name__ == "__main__":
    app.run(debug=True)