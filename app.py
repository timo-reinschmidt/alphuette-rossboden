from flask import Flask, render_template, request, redirect, url_for, session, g
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import uuid

app = Flask(__name__)
app.secret_key = 'rossboden_secret'

DATABASE = 'database.db'

rooms = {
    "Doppelzimmer": 2,
    "Viererzimmer 1": 4,
    "Viererzimmer 2": 4,
    "Sechserzimmer 1": 6,
    "Sechserzimmer 2": 6
}

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route('/')
def index():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    db = get_db()
    cur = db.execute('SELECT * FROM bookings ORDER BY arrival')
    bookings = cur.fetchall()
    return render_template('index.html', bookings=bookings)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ?', (request.form['username'],)).fetchone()
        if user and check_password_hash(user['password'], request.form['password']):
            session['user_id'] = user['id']
            return redirect(url_for('index'))
        return render_template('login.html', error='Login fehlgeschlagen')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/new', methods=['GET', 'POST'])
def new_booking():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    if request.method == 'POST':
        data = request.form
        room = data['room']
        guests = int(data['guests'])
        if guests > rooms[room]:
            return "Zimmer überbelegt", 400
        db = get_db()
        booking_id = str(uuid.uuid4())[:8]
        db.execute('INSERT INTO bookings (id, name, birthdate, room, guests, arrival, departure, breakfast, dinner) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                   (booking_id, data['name'], data['birthdate'], room, guests, data['arrival'], data['departure'], data.get('breakfast','Nein'), data.get('dinner','Nein')))
        db.commit()
        return redirect(url_for('index'))
    return render_template('new_booking.html', rooms=rooms)

if __name__ == '__main__':
    app.run(debug=True)
