import os
import time
import logging
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from dotenv import load_dotenv
from groq import Groq
import json
# Terminal Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
app = Flask(__name__)
app.secret_key = "hack_secret_2026"

with open("teams.txt", "r", encoding="utf-8") as f:
    TEAMS = json.load(f)
with open("levels.txt", "r", encoding="utf-8") as f:
    LEVELS = json.load(f)

def write_log(team, lvl_id, start_time):
    """Writes progress to logs.txt immediately."""
    now = time.time()
    duration = round((now - start_time) / 60, 2)
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    log_entry = f"TEAM: {team} | LEVEL: {lvl_id + 1} | TIME: {timestamp} | MINS_SINCE_START: {duration}\n"
    
    with open("logs.txt", "a") as f:
        f.write(log_entry)
    logger.info(f"FILE LOGGED: {log_entry.strip()}")

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
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
        
        flash("Invalid Credentials")
        logger.warning(f"FAILED LOGIN: {team_id}")
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
                    write_log(session['team'], lvl_idx, session['start_time'])
                    flash(f"Level {lvl_idx + 1} Cleared!", "success")
                    
        except Exception as e:
            logger.error(f"API Error: {e}")
            last_resp = f"Error: {str(e)}"

    return render_template('round1.html', levels=LEVELS, current=lvl_idx, 
                           last_resp=last_resp, solved=session['solved'])

@app.route('/round2', methods=['GET', 'POST'])
def round2():
    if 'team' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        file = request.files.get('image')
        if file:
            filename = f"round2_{session['team']}_{int(time.time())}.png"
            file.save(os.path.join('uploads', filename))
            return "<h1>Success! Your image has been uploaded for evaluation.</h1>"
    return render_template('round2.html')

if __name__ == '__main__':
    if not os.path.exists('uploads'): os.makedirs('uploads')
    # Run on local network
    app.run(host='0.0.0.0', port=5000, debug=True)