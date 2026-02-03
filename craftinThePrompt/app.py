import os
import time
import logging
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from dotenv import load_dotenv
from groq import Groq
import json
from flask import send_from_directory
from flask import abort
from collections import defaultdict
from datetime import datetime


# Terminal Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ADMIN_USER = "admin"
ADMIN_PASS = "abc"


def team_uploaded_image(team):
    if not os.path.exists("uploads"):
        return False
    return any(fname.startswith(f"round2_{team}_") for fname in os.listdir("uploads"))


load_dotenv()
app = Flask(__name__)
app.secret_key = "hack_secret_2026"

with open("teams.txt", "r", encoding="utf-8") as f:
    TEAMS = json.load(f)
with open("levels.txt", "r", encoding="utf-8") as f:
    LEVELS = json.load(f)

def write_log(team, lvl_id, start_time, prompt, response):
    """Writes detailed progress to logs.txt immediately."""
    now = time.time()
    duration = round((now - start_time) / 60, 2)
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    log_entry = {
        "team": team,
        "level": lvl_id + 1,
        "timestamp": timestamp,
        "mins_since_start": duration,
        "prompt": prompt,
        "response": response
    }

    with open("logs.txt", "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")

    logger.info(f"LOGGED: {team} | L{lvl_id + 1}")


@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_type = request.form.get('login_type')

        # 🔐 ADMIN LOGIN
        if login_type == "admin":
            username = request.form.get('admin_user', '').strip().lower()
            password = request.form.get('admin_pass', '').strip()

            if username == ADMIN_USER and password == ADMIN_PASS:
                session.clear()
                session['admin'] = True
                logger.info("ADMIN logged in.")
                return redirect(url_for('admin_dashboard'))

            flash("Invalid Admin Credentials")
            logger.warning("FAILED ADMIN LOGIN")
            return redirect(url_for('login'))

        # 👥 TEAM LOGIN
        if login_type == "team":
            team_id = request.form.get('team', '').strip().lower()
            password = request.form.get('password', '').strip()

            if team_id in TEAMS and TEAMS[team_id]['pw'] == password:
                session.clear()
                session['team'] = team_id
                session['idx'] = TEAMS[team_id]['idx']
                session['solved'] = []
                session['start_time'] = time.time()
                logger.info(f"SUCCESS: {team_id} logged in.")
                return redirect(url_for('round1'))

            flash("Invalid Team Credentials")
            logger.warning(f"FAILED TEAM LOGIN: {team_id}")
            return redirect(url_for('login'))

    return render_template('login.html', teams=TEAMS.keys())


@app.route('/round1', methods=['GET', 'POST'])
def round1():
    if 'team' not in session: return redirect(url_for('login'))
    
    lvl_idx = int(request.args.get('lvl', 0))
    last_resp = None

    if request.method == 'POST':
        user_input = request.form.get('user_input')
        lvl = LEVELS[lvl_idx]
        
        try:
            # Dynamically get the team's specific API key
            api_key = os.getenv(f"GROQ_API_{session['idx']}")
            client = Groq(api_key=api_key)
            
            completion = client.chat.completions.create(
                messages=[{"role": "system", "content": lvl['sys']}, {"role": "user", "content": user_input}],
                model="llama-3.3-70b-versatile"
            )
            last_resp = completion.choices[0].message.content
            
            # Comparison Logic
            clean_output = last_resp.lower().replace(" ", "").replace(".", "").replace("!", "")
            clean_goal = lvl['goal'].lower().replace(" ", "")
            
            if clean_goal in clean_output:
                if lvl_idx not in session['solved']:
                    session['solved'].append(lvl_idx)
                    session.modified = True
                    write_log(
    session['team'],
    lvl_idx,
    session['start_time'],
    user_input,
    last_resp
)

                    flash(f"Level {lvl_idx + 1} Cleared!", "success")
                    
        except Exception as e:
            logger.error(f"API Error: {e}")
            last_resp = f"Error: {str(e)}"

    return render_template('round1.html', levels=LEVELS, current=lvl_idx, 
                           last_resp=last_resp, solved=session['solved'])

@app.route('/round2', methods=['GET', 'POST'])
def round2():
    
    if 'team' not in session:
        return redirect(url_for('login'))

    if team_uploaded_image(session['team']):
        return "<h1 style='color:white;background:black;padding:40px;font-family:monospace'>Upload already submitted for your team.</h1>"

    if request.method == 'POST':
        file = request.files.get('image')
        if file:
            filename = f"round2_{session['team']}.png"
            file.save(os.path.join('uploads', filename))
            return "<h1 style='color:white;background:black;padding:40px;font-family:monospace'>Success! Image submitted.</h1>"

    return render_template('round2.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('login'))

    logs_by_team = defaultdict(list)

    if os.path.exists("logs.txt"):
        with open("logs.txt", "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    logs_by_team[entry["team"]].append(entry)
                except:
                    pass

    team_summaries = {}

    for team, logs in logs_by_team.items():
        # sort by time
        logs.sort(key=lambda x: x["timestamp"])

        levels_solved = len({l["level"] for l in logs})
        attempts = len(logs)

        # parse timestamps
        times = [
            datetime.strptime(l["timestamp"], "%Y-%m-%d %H:%M:%S")
            for l in logs
        ]

        start_time = min(times)
        end_time = max(times)
        total_minutes = round((end_time - start_time).total_seconds() / 60, 2)

        team_summaries[team] = {
            "levels_solved": levels_solved,
            "attempts": attempts,
            "start": start_time.strftime("%H:%M:%S"),
            "end": end_time.strftime("%H:%M:%S"),
            "total_minutes": total_minutes
        }

    # images (unchanged)
    images = []
    if os.path.exists("uploads"):
        for fname in os.listdir("uploads"):
            if fname.startswith("round2_"):
                team = fname.replace("round2_", "").replace(".png", "")
                images.append({"team": team, "file": fname})

    return render_template(
        "admin_dashboard.html",
        logs_by_team=logs_by_team,
        summaries=team_summaries,
        images=images
    )

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory('uploads', filename)

@app.route('/admin/delete_upload', methods=['POST'])
def delete_upload():
    if not session.get('admin'):
        abort(403)

    filename = request.form.get('filename')

    if not filename:
        abort(400)

    # Basic safety check (VERY important)
    if not filename.startswith("round2_") or ".." in filename:
        abort(400)

    file_path = os.path.join('uploads', filename)

    if os.path.exists(file_path):
        os.remove(file_path)
        logger.info(f"ADMIN deleted upload: {filename}")

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/clear_logs', methods=['POST'])
def clear_logs():
    if not session.get('admin'):
        abort(403)

    # Truncate logs file safely
    open("logs.txt", "w", encoding="utf-8").close()

    logger.warning("ADMIN cleared all logs")

    return redirect(url_for('admin_dashboard'))


if __name__ == '__main__':
    if not os.path.exists('uploads'): os.makedirs('uploads')
    # Run on local network
    app.run(host='0.0.0.0', port=5000, debug=True)