import io
import sqlite3
from datetime import datetime, date, timedelta

import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session, g, jsonify, send_file
from werkzeug.security import check_password_hash

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

room_groups = {
    "Doppelzimmer": "Doppelzimmer",
    "4er-Zimmer 1": "Viererzimmer",
    "4er-Zimmer 2": "Viererzimmer",
    "6er-Zimmer 1": "Sechserzimmer",
    "6er-Zimmer 2": "Sechserzimmer"
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

    # Zimmertypen und deren Gruppierungen (Doppelzimmer, Viererzimmer, etc.)
    room_type = room_groups.get(room, room)

    # Bestimme die maximale Anzahl an verfügbaren Zimmern für das Zimmer
    max_count = rooms.get(room, 0)  # Hier wird die Anzahl der Zimmer aus der 'rooms'-Variable genommen

    # Abruf der bereits gebuchten Zimmer innerhalb des angegebenen Zeitraums
    query = """
        SELECT COUNT(*) as count 
        FROM bookings
        WHERE room = ?
        AND NOT (departure <= ? OR arrival >= ?)
    """

    res = db.execute(query, (room, arrival, departure)).fetchone()

    return res[
        'count'] < max_count  # Überprüfe, ob die Anzahl der bereits gebuchten Zimmer weniger als die maximale Anzahl ist


@app.route('/')
def index():
    if not session.get('user_id'):
        return redirect(url_for('login'))
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
    return render_template('index.html', lists=lists)


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

    if request.method == 'POST':
        data = request.form

        # Verbinde mit der Datenbank
        db = get_db()

        try:
            # Formulardaten ausgeben (Debugging)
            print("Formulardaten:", data)

            # Buchungsdaten vorbereiten
            room = data['room']
            guests = int(data['guests'])

            # Prüfe, ob das Zimmer verfügbar ist
            if guests > rooms[room]:
                return "Zimmer überbelegt", 400

            # Erstelle eine eindeutige Buchungs-ID (UUID)
            hp = 'Ja' if 'hp' in data else 'Nein'
            hp_fleisch = int(data.get('hp_fleisch', 0)) if hp == 'Ja' else 0
            hp_vegi = int(data.get('hp_vegi', 0)) if hp == 'Ja' else 0

            # Führe die INSERT INTO-Abfrage aus
            db.execute('''
                INSERT INTO bookings
                (name, birthdate, room, guests, arrival, departure, hp, hp_fleisch, hp_vegi, email, phone, status, address, postal_code, city, country, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
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

            # Speichere die Änderungen in der DB
            db.commit()

            # Holen der Buchungs-ID durch SELECT
            booking_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            print(f"Booking ID: {booking_id}")

            # Gäste erfassen (ab Person 2)
            for i in range(1, guests):  # Wenn mehr als 1 Gast, füge Gäste hinzu
                guest_name = data.get(f'guest_name_{i}')
                guest_birth = data.get(f'guest_birth_{i}')
                if guest_name and guest_birth:
                    db.execute('INSERT INTO guests (booking_id, name, birthdate) VALUES (?, ?, ?)',
                               (booking_id, guest_name, guest_birth))

            # Bestätige die Änderungen in der DB
            db.commit()

            print("Buchung erfolgreich hinzugefügt")

            return redirect(url_for('index'))

        except sqlite3.Error as e:
            # Fehlerbehandlung und Rollback, falls ein Fehler auftritt
            print(f"Fehler bei der DB-Operation: {e}")
            db.rollback()  # Rollback bei Fehlern
            return "Fehler beim Hinzufügen der Buchung", 500

    return render_template('new_booking.html', rooms=rooms)


@app.route('/edit/<id>', methods=['GET', 'POST'])
def edit_booking(id):
    db = get_db()
    if request.method == 'POST':
        data = request.form

        # Wenn der Status auf "Storniert" gesetzt wird, die Buchung als storniert kennzeichnen
        if data.get('status') == 'Storniert':
            # Hier kannst du zusätzlich sicherstellen, dass die Zimmerverfügbarkeit freigegeben wird.
            # Dazu könnte man die Buchung und alle Gäste auf "Storniert" setzen oder aus der DB löschen.

            # Setze den Status auf "Storniert"
            db.execute('UPDATE bookings SET status = "Storniert" WHERE id = ?', (id,))
            db.commit()

        # Update der Buchung
        hp = 'Ja' if 'hp' in data else 'Nein'

        def safe_int(value):
            try:
                return int(value)
            except ValueError:
                return 0

        hp_fleisch = safe_int(data.get('hp_fleisch', 0)) if hp == 'Ja' else 0
        hp_vegi = safe_int(data.get('hp_vegi', 0)) if hp == 'Ja' else 0

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

        # Lösche die bestehenden Gäste und füge die neuen hinzu
        db.execute('DELETE FROM guests WHERE booking_id = ?', (id,))
        for i in range(1, int(data['guests']) + 1):  # Gastanzahl entsprechend der Anzahl erhöhen
            guest_name = data.get(f'guest_name_{i}')
            guest_birth = data.get(f'guest_birth_{i}')
            if guest_name and guest_birth:
                db.execute('INSERT INTO guests (booking_id, name, birthdate) VALUES (?, ?, ?)',
                           (id, guest_name, guest_birth))

        db.commit()
        return redirect(url_for('index'))

    booking = db.execute('SELECT * FROM bookings WHERE id = ?', (id,)).fetchone()
    guests = db.execute('SELECT * FROM guests WHERE booking_id = ?', (id,)).fetchall()
    return render_template('edit_booking.html', booking=booking, guests=guests, rooms=rooms)


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


if __name__ == '__main__':
    app.run(debug=True)
