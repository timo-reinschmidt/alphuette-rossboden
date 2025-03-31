import io
import sqlite3
import uuid
from datetime import datetime, date, timedelta

import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session, g, jsonify, send_file
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = 'rossboden_secret'

DATABASE = 'database.db'


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


@app.context_processor
def inject_admin_status():
    return dict(is_admin=session.get('is_admin', False))


def get_rooms():
    db = get_db()
    rows = db.execute("SELECT * FROM rooms").fetchall()
    return {row['name']: row['capacity'] for row in rows}


def get_room_data():
    db = get_db()
    rooms = db.execute("SELECT * FROM rooms").fetchall()
    room_dict = {room['name']: room['capacity'] for room in rooms}
    group_map = {room['name']: room['type'] for room in rooms}
    return room_dict, group_map


def get_age_distribution(booking_id, main_birthdate):
    today = date.today()
    ages = []
    if main_birthdate:
        ages.append(datetime.strptime(main_birthdate, "%Y-%m-%d").date())

    db = get_db()
    guests = db.execute('SELECT birthdate FROM guests WHERE booking_id = ?', (booking_id,)).fetchall()
    for g in guests:
        if g['birthdate']:
            ages.append(datetime.strptime(g['birthdate'], "%Y-%m-%d").date())

    erw, kind, baby = 0, 0, 0
    for b in ages:
        age = (today - b).days // 365
        if age >= 16:
            erw += 1
        elif age >= 6:
            kind += 1
        else:
            baby += 1
    result = []
    if erw: result.append(f"{erw} Erw.")
    if kind: result.append(f"{kind} Kind")
    if baby: result.append(f"{baby} Baby")
    return ', '.join(result), (erw, kind, baby)


def calculate_price(arrival, departure, erw, kind, baby, hp, hp_fleisch, hp_vegi):
    total = 0
    d1 = datetime.strptime(arrival, "%Y-%m-%d")
    d2 = datetime.strptime(departure, "%Y-%m-%d")

    for i in range((d2 - d1).days):
        day = d1 + timedelta(days=i)
        weekday = day.weekday()  # 0 = Montag, 6 = Sonntag

        if weekday in [4, 5]:  # Freitag & Samstag
            total += erw * 90 + kind * 70
        else:  # Sonntag bis Donnerstag
            total += erw * 70 + kind * 50

    # Kurtaxe pro Aufenthalt
    total += erw * 4 + kind * 1.5

    # Abendessen (jetzt HP: Halbpension) mit Fleisch und Vegi
    if hp == 'Ja':
        total += erw * 35 + (hp_fleisch) * 20 + (hp_vegi) * 20

    return round(total, 2)


def is_room_available(room, arrival, departure):
    db = get_db()
    rooms, room_groups = get_room_data()

    room_type = room_groups.get(room, room)
    max_count = rooms.get(room, 0)

    query = """
        SELECT COUNT(*) as count 
        FROM bookings
        WHERE room = ?
        AND NOT (departure <= ? OR arrival >= ?)
    """

    res = db.execute(query, (room, arrival, departure)).fetchone()
    return res['count'] < max_count


def get_booking_history(booking_id):
    db = get_db()
    query = """
        SELECT bh.*, u.username as changed_by
        FROM booking_history bh
        JOIN users u ON bh.changed_by = u.id
        WHERE bh.booking_id = ?
        ORDER BY bh.changed_at DESC
    """
    history = db.execute(query, (booking_id,)).fetchall()
    return history


@app.route('/')
def index():
    if not session.get('user_id'):
        return redirect(url_for('login'))

    is_admin_value = session.get('is_admin', False)  # Standardwert False setzen
    db = get_db()
    cur = db.execute('SELECT * FROM bookings ORDER BY arrival')
    bookings = cur.fetchall()
    today = date.today()
    lists = {
        'in_house': [],
        'upcoming': [],
        'past': [],
        'cancelled': []
    }
    for b in bookings:
        age_text, (erw, kind, baby) = get_age_distribution(b['id'], b['birthdate'])
        price = calculate_price(b['arrival'], b['departure'], erw, kind, baby, b['hp'], b['hp_fleisch'], b['hp_vegi'])
        enriched = dict(b, age_group=age_text, total_price=price)
        arrival = datetime.strptime(b['arrival'], "%Y-%m-%d").date()
        departure = datetime.strptime(b['departure'], "%Y-%m-%d").date()
        if b['status'] == 'Storniert':
            lists['cancelled'].append(enriched)
        elif arrival <= today < departure:
            lists['in_house'].append(enriched)
        elif arrival > today:
            lists['upcoming'].append(enriched)
        else:
            lists['past'].append(enriched)
    return render_template('index.html', lists=lists, is_admin=is_admin_value)


@app.route('/export')
def export_excel():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    db = get_db()
    bookings = db.execute('SELECT * FROM bookings').fetchall()
    rows = []
    for b in bookings:
        age_text, (erw, kind, baby) = get_age_distribution(b['id'], b['birthdate'])
        price = calculate_price(b['arrival'], b['departure'], erw, kind, baby, b['dinner'])
        rows.append({
            'Buchungsnummer': b['id'],
            'Name': b['name'],
            'Zimmer': b['room'],
            'Anreise': b['arrival'],
            'Abreise': b['departure'],
            'Abendessen': b['dinner'],
            'Altersverteilung': age_text,
            'Preis CHF': price
        })
    df = pd.DataFrame(rows)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Buchungen')
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='buchungen.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ?', (request.form['username'],)).fetchone()
        if user and check_password_hash(user['password'], request.form['password']):
            session['user_id'] = user['id']
            session['is_admin'] = user['is_admin']
            return redirect(url_for('index'))
        return render_template('login.html', error='Login fehlgeschlagen')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/cancel_booking/<id>', methods=['POST'])
def cancel_booking(id):
    if not session.get('user_id'):
        return redirect(url_for('login'))
    db = get_db()
    db.execute("UPDATE bookings SET status = 'Storniert' WHERE id = ?", (id,))
    db.commit()
    return redirect(url_for('index'))


@app.route('/delete_booking/<id>', methods=['POST'])
def delete_booking(id):
    db = get_db()

    # Zuerst die Gäste der Buchung löschen
    db.execute('DELETE FROM guests WHERE booking_id = ?', (id,))

    # Dann die Buchung aus der Buchungstabelle löschen
    db.execute('DELETE FROM bookings WHERE id = ?', (id,))

    # Änderungen in der Datenbank speichern
    db.commit()

    # Hier könnte man optional die Verfügbarkeit im Kalender oder anderen Systemen aktualisieren

    return redirect(url_for('index'))  # Zurück zur Buchungsübersicht oder zur gewünschten Seite


@app.route('/new', methods=['GET', 'POST'])
def new_booking():
    if not session.get('user_id'):
        return redirect(url_for('login'))

    rooms = get_rooms()

    if request.method == 'POST':
        data = request.form
        db = get_db()

        try:
            room = data['room']
            guests = int(data['guests'])
            if guests > rooms[room]:
                return "Zimmer überbelegt", 400

            booking_id = str(uuid.uuid4())
            hp = 'Ja' if 'hp' in data else 'Nein'
            hp_fleisch = int(data.get('hp_fleisch', 0)) if hp == 'Ja' else 0
            hp_vegi = int(data.get('hp_vegi', 0)) if hp == 'Ja' else 0

            db.execute('''
                INSERT INTO bookings
                (id, name, birthdate, room, guests, arrival, departure, hp, hp_fleisch, hp_vegi, email, phone, status, address, postal_code, city, country, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                booking_id,
                data['name'],
                data['birthdate'],
                room,
                guests,
                data['arrival'],
                data['departure'],
                hp,
                hp_fleisch,
                hp_vegi,
                data.get('email', ''),
                data.get('phone', ''),
                data.get('status', 'Option'),
                data['address'],
                data['postal_code'],
                data['city'],
                data['country'],
                data.get('note', '')
            ))

            for i in range(1, guests):
                guest_name = data.get(f'guest_name_{i}')
                guest_birth = data.get(f'guest_birth_{i}')
                if guest_name and guest_birth:
                    db.execute('INSERT INTO guests (booking_id, name, birthdate) VALUES (?, ?, ?)',
                               (booking_id, guest_name, guest_birth))

            db.commit()
            return redirect(url_for('index'))

        except sqlite3.Error as e:
            print(f"Fehler bei der DB-Operation: {e}")
            db.rollback()
            return "Fehler beim Hinzufügen der Buchung", 500

    return render_template('new_booking.html', rooms=rooms)


@app.route('/edit/<id>', methods=['GET', 'POST'])
def edit_booking(id):
    db = get_db()
    rooms = get_rooms()

    booking = db.execute('SELECT * FROM bookings WHERE id = ?', (id,)).fetchone()
    guests = db.execute('SELECT * FROM guests WHERE booking_id = ?', (id,)).fetchall()
    history = get_booking_history(id)

    if request.method == 'POST':
        data = request.form

        if data.get('status') == 'Storniert':
            db.execute('UPDATE bookings SET status = "Storniert" WHERE id = ?', (id,))
            db.commit()

        hp = 'Ja' if 'hp' in data else 'Nein'

        def safe_int(value):
            try:
                return int(value)
            except ValueError:
                return 0

        hp_fleisch = safe_int(data.get('hp_fleisch', 0)) if hp == 'Ja' else 0
        hp_vegi = safe_int(data.get('hp_vegi', 0)) if hp == 'Ja' else 0

        new_status = data.get('status')
        if new_status != booking['status']:
            db.execute('''
                INSERT INTO booking_history (booking_id, status, changed_at, changed_by)
                VALUES (?, ?, ?, ?)
            ''', (id, new_status, datetime.now(), session.get('user_id')))

        db.execute('''
            UPDATE bookings SET
            name=?, birthdate=?, email=?, phone=?, room=?, guests=?,
            arrival=?, departure=?, hp=?, hp_fleisch=?, hp_vegi=?, status=?,
            address=?, postal_code=?, city=?, country=?, notes=?
            WHERE id=?
        ''', (
            data['name'],
            data['birthdate'],
            data.get('email', ''),
            data.get('phone', ''),
            data['room'],
            int(data['guests']),
            data['arrival'],
            data['departure'],
            hp,
            hp_fleisch,
            hp_vegi,
            data.get('status', 'Option'),
            data['address'],
            data['postal_code'],
            data['city'],
            data['country'],
            data['note'],
            id
        ))

        db.execute('DELETE FROM guests WHERE booking_id = ?', (id,))
        for i in range(1, int(data['guests']) + 1):
            guest_name = data.get(f'guest_name_{i}')
            guest_birth = data.get(f'guest_birth_{i}')
            if guest_name and guest_birth:
                db.execute('INSERT INTO guests (booking_id, name, birthdate) VALUES (?, ?, ?)',
                           (id, guest_name, guest_birth))

        db.commit()
        return redirect(url_for('index'))

    booking = db.execute('SELECT * FROM bookings WHERE id = ?', (id,)).fetchone()
    guests = db.execute('SELECT * FROM guests WHERE booking_id = ?', (id,)).fetchall()
    return render_template('edit_booking.html', booking=booking, guests=guests, history=history, rooms=rooms)


def is_admin(user_id):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return user and user['is_admin'] == 1  # Überprüfe, ob der Benutzer Admin-Rechte hat


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('user_id') or not session.get('is_admin'):
        return redirect(url_for('login'))  # Wenn nicht eingeloggt oder kein Admin

    db = get_db()

    # Preise aus der Datenbank holen
    prices = db.execute("SELECT * FROM prices").fetchall()
    users = db.execute("SELECT * FROM users").fetchall()
    error = None

    if request.method == 'POST':
        # Benutzer hinzufügen
        if 'add_user' in request.form:
            username = request.form.get('username')
            password = request.form.get('password')

            # Debugging: Logge die erhaltenen Formulardaten
            print(f"Benutzername: {username}, Passwort: {password}")

            # Stelle sicher, dass der Benutzername nicht bereits existiert
            existing_user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
            if existing_user:
                return render_template('admin.html', prices=prices, users=users, error="Benutzername existiert bereits")

            # Passworteingabe überprüfen
            if not username or not password:
                return render_template('admin.html', prices=prices, users=users,
                                       error="Benutzername und Passwort dürfen nicht leer sein")

            # Debugging: Logge, bevor der Benutzer hinzugefügt wird
            print(f"Füge Benutzer hinzu: {username}")

            hashed_pw = generate_password_hash(password)
            is_admin = 1 if 'is_admin' in request.form else 0  # Admin-Flag setzen

            try:
                # Füge den Benutzer zur Datenbank hinzu
                db.execute("INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)",
                           (username, hashed_pw, is_admin))
                db.commit()  # Änderungen speichern
                print("Benutzer hinzugefügt!")  # Debugging: Bestätigung
            except Exception as e:
                print(f"Fehler beim Hinzufügen des Benutzers: {e}")
                return render_template('admin.html', prices=prices, users=users,
                                       error="Fehler beim Hinzufügen des Benutzers")

            return redirect(url_for('admin'))

        # Benutzer entfernen
        elif 'remove_user' in request.form:
            user_id = request.form.get('user_id')
            db.execute("DELETE FROM users WHERE id = ?", (user_id,))
            db.commit()

        # Preis anpassen
        elif 'update_price' in request.form:
            category = request.form.get('category')
            weekend_price = float(request.form.get('weekend_price'))
            weekday_price = float(request.form.get('weekday_price'))

            db.execute("""
                UPDATE prices 
                SET weekend_price = ?, weekday_price = ? 
                WHERE category = ?
            """, (weekend_price, weekday_price, category))
            db.commit()

        return redirect(url_for('admin'))

    return render_template('admin.html', prices=prices, users=users, error=error)


@app.route('/update_booking_date/<booking_id>', methods=['POST'])
def update_booking_date(booking_id):
    db = get_db()
    new_arrival = request.form['arrival']
    new_departure = request.form['departure']

    # Überprüfen, ob das Zimmer verfügbar ist
    room = request.form['room']
    if not is_room_available(room, new_arrival, new_departure):
        return "Zimmer nicht verfügbar für das neue Datum", 400

    # Berechne den neuen Preis basierend auf den neuen Daten
    erw, kind, baby = get_age_distribution(booking_id)
    price = calculate_price(new_arrival, new_departure, erw, kind, baby, 'Ja', 0, 0)  # Beispiel für Halbpension

    # Aktualisieren des Buchungsdatums und Preises
    db.execute('''
        UPDATE bookings 
        SET arrival = ?, departure = ?, total_price = ? 
        WHERE id = ?
    ''', (new_arrival, new_departure, price, booking_id))

    # Änderungen in der Datenbank speichern
    db.commit()

    # Rückgabe der Bestätigung
    return "Buchung erfolgreich aktualisiert"


@app.route('/calendar')
def calendar():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    return render_template('calendar.html')


@app.route('/api/bookings')
def api_bookings():
    if not session.get('user_id'):
        return jsonify([])

    db = get_db()
    cur = db.execute('SELECT * FROM bookings WHERE status != "Storniert"')
    bookings = cur.fetchall()

    room_class_map = {
        "Doppelzimmer": "room-doppel",
        "Viererzimmer 1": "room-vz1",
        "Viererzimmer 2": "room-vz2",
        "Sechserzimmer 1": "room-sz1",
        "Sechserzimmer 2": "room-sz2"
    }

    status_classes = {
        'Option': 'option',  # Gelb
        'Bestätigt': 'confirmed',  # Blau
        'Checked In': 'checkedin',  # Grün
        'Storniert': 'cancelled'  # Rot
    }

    events = []
    for b in bookings:
        main_guest_name = b['name']
        num_guests = b['guests']
        room_class = room_class_map.get(b['room'], 'default-room')  # Zimmerfarbe zuweisen
        status_class = status_classes.get(b['status'], 'option')  # Statusfarbe zuweisen

        events.append({
            'title': f"{main_guest_name} ({num_guests} P)",
            'start': b['arrival'],
            'end': b['departure'],
            'url': f"/edit/{b['id']}",
            'extendedProps': {
                'statusClass': status_classes.get(b['status'], 'option')  # Status wird hier zugewiesen
            },
            'className': f"{room_class} {status_class}"  # Klasse für Zimmer und Status
        })

    return jsonify(events)


@app.route('/reports', methods=['GET', 'POST'])
def reports():
    if not session.get('user_id'):
        return redirect(url_for('login'))

    db = get_db()
    error = None
    reports = []
    today = datetime.today().date()

    if request.method == 'POST':
        report_type = request.form.get('report_type')

        if report_type == 'arrival':
            # Anreisen im gewählten Zeitraum
            start_date = request.form.get('start_date')
            end_date = request.form.get('end_date')
            query = """
                SELECT b.name, b.guests, b.hp, b.hp_fleisch, b.hp_vegi, b.arrival, b.departure, g.name as guest_name, g.birthdate
                FROM bookings b
                LEFT JOIN guests g ON b.id = g.booking_id
                WHERE b.arrival BETWEEN ? AND ?
            """
            rows = db.execute(query, (start_date, end_date)).fetchall()

            # Berechnung des Alters der Gäste
            report_data = []
            today = date.today()
            for row in rows:
                guest_age = None
                if row['birthdate']:
                    guest_age = (today - datetime.strptime(row['birthdate'], "%Y-%m-%d").date()).days // 365
                report_data.append({
                    'name': row['name'],
                    'guests': row['guests'],
                    'hp': row['hp'],
                    'hp_fleisch': row['hp_fleisch'],
                    'hp_vegi': row['hp_vegi'],
                    'guest_name': row['guest_name'],
                    'guest_age': guest_age,
                    'arrival': row['arrival'],
                    'departure': row['departure']
                })
            reports.append(('Anreisen', report_data))

        elif report_type == 'in_house':
            # Im Haus Liste
            query = """
                SELECT b.name, b.guests, b.hp, b.hp_fleisch, b.hp_vegi, b.arrival, b.departure, r.type as room_type, g.name as guest_name, g.birthdate
                FROM bookings b
                LEFT JOIN guests g ON b.id = g.booking_id
                LEFT JOIN rooms r ON b.room = r.name
                WHERE b.status = 'Bestätigt' AND b.arrival <= ? AND b.departure >= ?
            """
            rows = db.execute(query, (today, today)).fetchall()

            # Berechnung des Alters der Gäste
            report_data = []
            for row in rows:
                guest_age = None  # Setze einen Standardwert
                if row['birthdate']:
                    guest_age = (today - datetime.strptime(row['birthdate'], "%Y-%m-%d").date()).days // 365
                report_data.append({
                    'name': row['name'],
                    'guests': row['guests'],
                    'hp': row['hp'],
                    'hp_fleisch': row['hp_fleisch'],
                    'hp_vegi': row['hp_vegi'],
                    'room_type': row['room_type'],
                    'guest_name': row['guest_name'],
                    'guest_age': guest_age,
                    'arrival': row['arrival'],
                    'departure': row['departure']
                })
            reports.append(('Im Haus', report_data))

        elif report_type == 'departure':
            # Heutige Abreise Liste
            query = """
                SELECT b.name, b.guests, b.hp, b.hp_fleisch, b.hp_vegi, b.arrival, b.departure, g.name as guest_name, g.birthdate
                FROM bookings b
                LEFT JOIN guests g ON b.id = g.booking_id
                WHERE b.departure = ?
            """
            rows = db.execute(query, (today,)).fetchall()

            # Berechnung des Alters der Gäste und Gesamtpreis
            report_data = []
            for row in rows:
                guest_age = None  # Setze einen Standardwert
                if row['birthdate']:
                    guest_age = (today - datetime.strptime(row['birthdate'], "%Y-%m-%d").date()).days // 365
                price = calculate_price(row['arrival'], row['departure'], row['guests'], row['hp'],
                                        row['hp_fleisch'], row['hp_vegi'])
                report_data.append({
                    'name': row['name'],
                    'guests': row['guests'],
                    'hp': row['hp'],
                    'hp_fleisch': row['hp_fleisch'],
                    'hp_vegi': row['hp_vegi'],
                    'guest_name': row['guest_name'],
                    'guest_age': guest_age,
                    'total_price': price
                })
            reports.append(('Heutige Abreise', report_data))

    return render_template('reports.html', reports=reports, error=error)


if __name__ == '__main__':
    app.run(debug=True)
