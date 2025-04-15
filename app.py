import io
import logging
import os
import uuid
from datetime import datetime, date, timedelta
from logging.handlers import RotatingFileHandler

import pandas as pd
import psycopg2
import psycopg2.extras
import pytz
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, g, jsonify, send_file
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()
app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL ist nicht gesetzt!")

# Erstelle das Passwort-Hash
hashed_password = generate_password_hash("Rossboden2025?")
is_correct = check_password_hash(hashed_password, "Rossboden2025?")


# Fehlerbehandlung für die Verbindung zur DB
def test_connection():
    try:
        connection = psycopg2.connect(DATABASE_URL, sslmode='require')
        print("Verbindung erfolgreich!")
        cursor = connection.cursor()
        cursor.execute("SELECT version();")  # Überprüfe, ob die Datenbankversion abgerufen werden kann
        db_version = cursor.fetchone()
        print(f"Datenbankversion: {db_version}")
        connection.close()
    except Exception as e:
        print(f"Fehler bei der Verbindung zur Datenbank: {e}")


test_connection()

app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default_key')

if not app.debug:
    file_handler = RotatingFileHandler('error.log', maxBytes=10240, backupCount=10)
    file_handler.setLevel(logging.ERROR)
    app.logger.addHandler(file_handler)

# Verwende datetime.now() und stelle sicher, dass UTC-Zeit verwendet wird
utc_time = datetime.now(pytz.utc)

# Konvertiere die Zeit in die gewünschte Zeitzone (z.B. Europe/Zurich)
local_time = utc_time.astimezone(pytz.timezone('Europe/Zurich'))

# Formatieren des Datums im ISO 8601-Format
formatted_date = local_time.strftime("%Y-%m-%dT%H:%M:%S")


# Funktion, um die Datenbankverbindung herzustellen
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = psycopg2.connect(DATABASE_URL, sslmode='require')
        db.autocommit = True  # Setzt autocommit auf True
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


@app.context_processor
def inject_admin_status():
    return dict(is_admin=session.get('is_admin', False))


@app.context_processor
def inject_user():
    user_name = None
    if 'user_id' in session:
        db = get_db()
        cursor = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT username FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
        if user:
            user_name = user['username']
    return dict(user_name=user_name)


# Beispiel einer SQL-Anpassung für PostgreSQL
def get_rooms():
    db = get_db()
    cursor = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM rooms")
    rows = cursor.fetchall()
    rooms = {row[1]: row[3] for row in
             rows}  # Erstelle ein Dictionary aus Name und Kapazität (row[2] ist die Kapazität)
    return rooms


def get_room_data():
    db = get_db()
    cursor = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM rooms")
    rooms = cursor.fetchall()
    room_dict = {room[1]: room[2] for room in rooms}  # Nutzen der richtigen Indizes für die Daten
    group_map = {room[1]: room[3] for room in rooms}
    return room_dict, group_map


def get_age_distribution(booking_id, main_birthdate):
    today = date.today()
    ages = []
    if main_birthdate:
        ages.append(datetime.strptime(main_birthdate, "%Y-%m-%d").date())

    db = get_db()
    cursor = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute('SELECT birthdate FROM guests WHERE booking_id = %s', (booking_id,))
    guests = cursor.fetchall()
    for g in guests:
        if g[0]:
            ages.append(datetime.strptime(g[0], "%Y-%m-%d").date())

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

    # Stelle sicher, dass 'arrival' und 'departure' als Strings vorliegen, falls sie als datetime.date Objekte kommen
    arrival = str(arrival) if isinstance(arrival, date) else arrival
    departure = str(departure) if isinstance(departure, date) else departure

    arrival = safe_parse_date(arrival)
    departure = safe_parse_date(departure)

    if arrival is None or departure is None:
        return 0  # Rückgabe eines Standardwertes, wenn ein Fehler auftritt

    d1 = datetime.strptime(str(arrival), "%Y-%m-%d")
    d2 = datetime.strptime(str(departure), "%Y-%m-%d")
    num_nights = (d2 - d1).days

    for i in range((d2 - d1).days):
        day = d1 + timedelta(days=i)
        weekday = day.weekday()  # 0 = Montag, 6 = Sonntag

        if weekday in [4, 5]:  # Freitag & Samstag
            total += erw * 90 + kind * 70
        else:  # Sonntag bis Donnerstag
            total += erw * 70 + kind * 50

    # Kurtaxe pro Aufenthalt
    total += erw * 4 * num_nights + kind * 1.5 * num_nights  # Beispiel für Kurtaxe

    # Abendessen (jetzt HP: Halbpension) mit Fleisch und Vegi
    if hp == 'Ja':
        total += erw * 35 * num_nights
        total += kind * 20 * num_nights

    return round(total, 2)


def is_room_available(room, arrival, departure):
    db = get_db()
    rooms, room_groups = get_room_data()

    room_type = room_groups.get(room, room)
    max_count = rooms.get(room, 0)

    query = """
        SELECT COUNT(*) as count 
        FROM bookings
        WHERE room = %s
        AND NOT (departure <= %s OR arrival >= %s)
    """

    cursor = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute(query, (room, arrival, departure))
    res = cursor.fetchone()
    return res[0] < max_count


def get_booking_history(booking_id):
    db = get_db()
    query = """
        SELECT bh.*, u.username as changed_by
        FROM booking_history bh
        JOIN users u ON bh.changed_by = u.id
        WHERE bh.booking_id = %s
        ORDER BY bh.changed_at DESC
    """
    cursor = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute(query, (booking_id,))
    history = cursor.fetchall()
    return history


def safe_parse_date(date_value):
    if isinstance(date_value, date):  # Wenn es bereits ein datetime.date ist
        return date_value
    if date_value in ['Ja', 'Nein', '']:  # Hier fangen wir "Ja" und "Nein" ab, die ungültige Daten sind
        return None
    try:
        # Falls es ein String ist, wandeln wir ihn in ein datetime.date Objekt um
        return datetime.strptime(date_value, "%Y-%m-%d").date()
    except ValueError:
        return None


@app.route('/')
def index():
    if not session.get('user_id'):
        return redirect(url_for('login'))

    is_admin_value = session.get('is_admin', False)
    db = get_db()
    cursor = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute('SELECT * FROM bookings ORDER BY arrival')
    bookings = cursor.fetchall()
    today = date.today()
    day_before_today = today - timedelta(days=1)
    lists = {
        'in_house': [],
        'today_arrivals': [],
        'upcoming': [],
        'past': [],
        'cancelled': []
    }
    for b in bookings:
        booking_number = str(b['id'])[:8]
        age_text, (erw, kind, baby) = get_age_distribution(b['id'], b['birthdate'])
        price = calculate_price(b['arrival'], b['departure'], erw, kind, baby, b['hp'], b['hp_fleisch'], b['hp_vegi'])
        enriched = b.copy()
        enriched['age_group'] = age_text
        enriched['total_price'] = price
        enriched['booking_number'] = booking_number

        arrival = b['arrival']  # Stellt sicher, dass 'arrival' aus der Buchung kommt
        departure = b['departure']  # Stellt sicher, dass 'departure' aus der Buchung kommt

        arrival = str(arrival) if isinstance(arrival, datetime) else arrival
        departure = str(departure) if isinstance(departure, datetime) else departure

        arrival = safe_parse_date(arrival)
        departure = safe_parse_date(departure)

        if arrival is None or departure is None:
            print(f"Ungültiges Datum für Ankunft oder Abreise: {b['arrival']}, {b['departure']}")
            continue  # Überspringe diese Buchung

        # Nur "Checked In" kommen in "Im Haus", auch wenn Abreise heute ist
        if b['status'] == 'Checked In' and (arrival <= today < departure or departure == today):
            lists['in_house'].append(enriched)

        # Wenn der Status "Ausgecheckt" ist, kommt die Buchung in "Vergangene"
        elif b['status'] == 'Ausgecheckt' and departure <= day_before_today:
            lists['past'].append(enriched)

        # Wenn der Status "Storniert" ist, kommt die Buchung in "Storniert"
        elif b['status'] == 'Storniert':
            lists['cancelled'].append(enriched)

        # Anstehende Reservierungen
        elif arrival > today:
            lists['upcoming'].append(enriched)

        elif arrival == today:
            lists['today_arrivals'].append(enriched)

        else:
            lists['past'].append(enriched)
    return render_template('index.html', lists=lists, is_admin=is_admin_value)


@app.route('/export', methods=['GET', 'POST'])
def export_excel():
    if not session.get('user_id'):
        return redirect(url_for('login'))

    # Wenn ein Zeitraum ausgewählt wurde (POST-Anfrage)
    if request.method == 'POST':
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')

        db = get_db()
        cursor = db.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # SQL-Abfrage mit Zeitraum
        query = """
            SELECT * FROM bookings
            WHERE arrival BETWEEN %s AND %s
        """
        cursor.execute(query, (start_date, end_date))
        bookings = cursor.fetchall()
    else:
        # Standardabfrage, wenn kein Zeitraum angegeben wurde
        db = get_db()
        cursor = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute('SELECT * FROM bookings')
        bookings = cursor.fetchall()

    rows = []
    for b in bookings:
        # Altersverteilung der Gäste abrufen
        age_text, (erw, kind, baby) = get_age_distribution(b[0], b[2])  # b[0] = booking_id, b[2] = birthdate
        # Berechnung des Preises
        price = calculate_price(b[6], b[7], erw, kind, baby, b[8], b[9], b[10])  # b[6] = arrival, b[7] = departure
        # Fleisch- und Vegan-Anzahl für das Abendessen
        hp_fleisch = b[9] if b[8] == 'Ja' else 0
        hp_vegi = b[10] if b[8] == 'Ja' else 0

        rows.append({
            'Buchungsnummer': b[0],  # b[0] = booking_id
            'Name': b[1],  # b[1] = name
            'Status': b[12],  # b[11] = status
            'Zimmer': b[3],  # b[3] = room
            'Anreise': b[5],  # b[6] = arrival
            'Abreise': b[6],  # b[7] = departure
            'Fleisch': b[8],
            'Vegan': b[9],
            'Altersverteilung': age_text,
            'Notizen': b[17],
            'Bezahlt': b[18],
            'Zahlart': b[19],
        })

    df = pd.DataFrame(rows)

    df = df.sort_values(by='Anreise', ascending=True)  # Nach Anreise-Datum sortieren

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
        cursor = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute('SELECT * FROM users WHERE username = %s', (request.form['username'],))
        user = cursor.fetchone()
        # Debugging-Ausgabe
        print(f"Benutzer: {user}")  # Zeigt die abgerufenen Daten in der Konsole an

        if user and check_password_hash(user['password'], request.form['password']):  # user[2] ist das Passwort
            session['user_id'] = user['id']
            session['user'] = user['username']
            session['is_admin'] = user['is_admin']
            return redirect(url_for('index'))
        print("Login fehlgeschlagen!")
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
    cursor = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("UPDATE bookings SET status = 'Storniert' WHERE id = %s", (id,))
    db.commit()
    return redirect(url_for('index'))


@app.route('/delete_booking/<id>', methods=['POST'])
def delete_booking(id):
    db = get_db()
    cursor = db.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Zuerst die Gäste der Buchung löschen
    cursor.execute('DELETE FROM guests WHERE booking_id = %s', (id,))

    # Dann die Buchung aus der Buchungstabelle löschen
    cursor.execute('DELETE FROM bookings WHERE id = %s', (id,))

    # Änderungen in der Datenbank speichern
    db.commit()

    return redirect(url_for('index'))


@app.route('/new', methods=['GET', 'POST'])
def new_booking():
    if not session.get('user_id'):
        return redirect(url_for('login'))

    rooms = get_rooms()

    if request.method == 'POST':
        data = request.form
        arrival = data.get('arrival')
        departure = data.get('departure')

        # Validierung der An- und Abreisedaten
        if not safe_parse_date(arrival):
            return "Ungültiges Anreisedatum", 400
        if not safe_parse_date(departure):
            return "Ungültiges Abreisedatum", 400

        db = get_db()

        try:
            room = data['room']
            guests = int(data['guests'])
            if guests > rooms[room]:
                return "Zimmer überbelegt", 400

            booking_id = str(uuid.uuid4())
            hp = 'Ja' if 'hp' in data else 'Nein'
            hp_fleisch = int(data.get('hp_fleisch', 0)) if data.get('hp_fleisch') != '' else 0
            hp_vegi = int(data.get('hp_vegi', 0)) if data.get('hp_vegi') != '' else 0

            cursor = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute('''
                INSERT INTO bookings
                (id, name, birthdate, room, guests, arrival, departure, hp, hp_fleisch, hp_vegi, email, phone, status, address, postal_code, city, country, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                booking_id,
                data['name'],
                data['birthdate'],
                room,
                guests,
                arrival,
                departure,
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
                    cursor.execute('INSERT INTO guests (booking_id, name, birthdate) VALUES (%s, %s, %s)',
                                   (booking_id, guest_name, guest_birth))

            db.commit()
            return redirect(url_for('index'))

        except psycopg2.Error as e:
            print(f"Fehler bei der DB-Operation: {e}")
            db.rollback()
            return "Fehler beim Hinzufügen der Buchung", 500

    return render_template('new_booking.html', rooms=rooms)


@app.route('/edit/<id>', methods=['GET', 'POST'])
def edit_booking(id):
    db = get_db()
    rooms = get_rooms()

    cursor = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute('SELECT * FROM bookings WHERE id = %s', (id,))
    booking = cursor.fetchone()

    # Hole die Gäste der Buchung
    cursor.execute('SELECT * FROM guests WHERE booking_id = %s', (id,))
    guests = cursor.fetchall()

    # Hole die Buchungshistorie
    history = get_booking_history(id)

    if request.method == 'POST':
        data = request.form

        if data.get('status') == 'Storniert':
            cursor.execute('UPDATE bookings SET status = "Storniert" WHERE id = %s', (id,))
            db.commit()

        # Behandle Zahlungseingabe
        payment_status = 'payment_status' in data and data['payment_status'] == 'on'  # Checkbox-Status
        payment_method = data.get('payment_method') if payment_status else None

        if data.get('status') == 'Ausgecheckt':
            # Überprüfen, ob das Abreisedatum dem heutigen Datum entspricht
            today = date.today().strftime("%Y-%m-%d")
            if data['departure'] != today:
                return "Die Buchung kann nicht auf 'Ausgecheckt' gesetzt werden, wenn das Abreisedatum nicht heute ist.", 400

            # Behandle Zahlungseingabe
            payment_status = 'payment_status' in data and data['payment_status'] == 'on'  # Checkbox-Status
            payment_method = data.get('payment_method') if payment_status else None

            # Überprüfe, ob Status geändert wurde
            if data.get('status') == 'Ausgecheckt' and not payment_status:
                return "Bitte markieren Sie 'Bezahlt', bevor Sie Ausgecheckt wählen.", 400

        # Überprüfe, ob Status geändert wurde
        if data.get('status') == 'Ausgecheckt' and not payment_status:
            return "Bitte markieren Sie 'Bezahlt', bevor Sie Ausgecheckt wählen.", 400

        def safe_int(value):
            try:
                return int(value)
            except ValueError:
                return 0

        hp = 'Ja' if 'hp' in data else 'Nein'
        hp_fleisch = safe_int(data.get('hp_fleisch', 0)) if hp == 'Ja' else 0
        hp_vegi = safe_int(data.get('hp_vegi', 0)) if hp == 'Ja' else 0

        new_status = data.get('status')
        if new_status != booking[1]:  # booking[1] ist der Name, daher Status
            cursor.execute('''
                INSERT INTO booking_history (booking_id, status, changed_at, changed_by)
                VALUES (%s, %s, %s, %s)
            ''', (id, new_status, datetime.now(), session.get('user_id')))

        cursor.execute('''
            UPDATE bookings SET
            name=%s, birthdate=%s, email=%s, phone=%s, room=%s, guests=%s,
            arrival=%s, departure=%s, hp=%s, hp_fleisch=%s, hp_vegi=%s, status=%s,
            address=%s, postal_code=%s, city=%s, country=%s, notes=%s,
            payment_status=%s, payment_method=%s
            WHERE id=%s
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
            payment_status,
            payment_method,
            id
        ))

        # Lösche die alten Gäste und füge neue hinzu
        cursor.execute('DELETE FROM guests WHERE booking_id = %s', (id,))
        for i in range(1, int(data['guests']) + 1):
            guest_name = data.get(f'guest_name_{i}')
            guest_birth = data.get(f'guest_birth_{i}')
            if guest_name and guest_birth:
                cursor.execute('INSERT INTO guests (booking_id, name, birthdate) VALUES (%s, %s, %s)',
                               (id, guest_name, guest_birth))

        db.commit()
        return redirect(url_for('index'))

    # Hole die Buchung und die Gäste
    cursor.execute('SELECT * FROM bookings WHERE id = %s', (id,))
    booking = cursor.fetchone()
    cursor.execute('SELECT * FROM guests WHERE booking_id = %s', (id,))
    guests = cursor.fetchall()

    return render_template('edit_booking.html', booking=booking, guests=guests, history=history, rooms=rooms)


def is_admin(user_id):
    db = get_db()
    cursor = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    return user and user[3] == 1  # Überprüfe, ob der Benutzer Admin-Rechte hat


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('user_id') or not session.get('is_admin'):
        return redirect(url_for('login'))  # Wenn nicht eingeloggt oder kein Admin

    db = get_db()

    cursor = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM prices")
    prices = cursor.fetchall()
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    error = None

    if request.method == 'POST':
        # Benutzer hinzufügen
        if 'add_user' in request.form:
            username = request.form.get('username')
            password = request.form.get('password')

            # Stelle sicher, dass der Benutzername nicht bereits existiert
            cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
            existing_user = cursor.fetchone()
            if existing_user:
                return render_template('admin.html', prices=prices, users=users, error="Benutzername existiert bereits")

            if not username or not password:
                return render_template('admin.html', prices=prices, users=users,
                                       error="Benutzername und Passwort dürfen nicht leer sein")

            hashed_pw = generate_password_hash(password)
            is_admin = True if 'is_admin' in request.form else False

            try:
                cursor.execute("INSERT INTO users (username, password, is_admin) VALUES (%s, %s, %s)",
                               (username, hashed_pw, is_admin))
                db.commit()
            except Exception as e:
                print(f"Fehler beim Hinzufügen des Benutzers: {e}")
                return render_template('admin.html', prices=prices, users=users,
                                       error="Fehler beim Hinzufügen des Benutzers")

            return redirect(url_for('admin'))

        # Benutzer entfernen
        elif 'remove_user' in request.form:
            user_id = request.form.get('user_id')

            # Previous code used to remove users:
            # elif 'remove_user' in request.form:
            # user_id = request.form.get('user_id')
            # cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
            # db.commit()
            if not user_id:
                return render_template('admin.html', error="Kein Benutzer angegeben")

            try:
                # Debugging-Ausgabe: Zeigt die user_id und die SQL-Abfrage an
                print(f"Versuche Benutzer mit ID {user_id} zu löschen.")

                cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                user = cursor.fetchone()

                if not user:
                    print(f"Benutzer mit ID {user_id} nicht gefunden.")  # Debugging
                    return render_template('admin.html', error="Benutzer nicht gefunden.")

                # Benutzer löschen
                cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
                db.commit()

                print(f"Benutzer mit ID {user_id} erfolgreich gelöscht.")  # Debugging
                return redirect(url_for('admin'))

            except Exception as e:
                # Fehlerbehandlung und Logging
                db.rollback()
                print(f"Fehler beim Löschen des Benutzers: {e}")
                return render_template('admin.html', error="Fehler beim Löschen des Benutzers")

        # Preis anpassen
        elif 'update_price' in request.form:
            category = request.form.get('category')
            weekend_price = float(request.form.get('weekend_price'))
            weekday_price = float(request.form.get('weekday_price'))

            cursor.execute("""
                UPDATE prices 
                SET weekend_price = %s, weekday_price = %s 
                WHERE category = %s
            """, (weekend_price, weekday_price, category))
            db.commit()

        return redirect(url_for('admin'))

    return render_template('admin.html', prices=prices, users=users, error=error)


@app.route('/remove_user/<int:user_id>', methods=['POST'])
def remove_user(user_id):
    db = get_db()
    cursor = db.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()

        if not user:
            return render_template('admin.html', error="Benutzer nicht gefunden.")

        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        db.commit()
        return redirect(url_for('admin'))

    except Exception as e:
        db.rollback()
        return render_template('admin.html', error=f"Fehler beim Löschen des Benutzers: {e}")


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

    cursor = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute('''
        UPDATE bookings 
        SET arrival = %s, departure = %s, total_price = %s 
        WHERE id = %s
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


def format_date_to_iso(date):
    # Überprüfen, ob das Datum ein datetime-Objekt ist und es im ISO 8601 Format umwandeln
    if isinstance(date, datetime):
        return date.strftime("%Y-%m-%dT%H:%M:%S")
    return date  # Falls das Datum schon im richtigen Format ist, einfach zurückgeben


@app.route('/api/bookings')
def api_bookings():
    if not session.get('user_id'):
        return jsonify([])

    db = get_db()
    cursor = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute('SELECT * FROM bookings WHERE status != %s', ('Storniert',))
    bookings = cursor.fetchall()

    room_class_map = {
        "Doppelzimmer": "room-doppel",
        "4er-Zimmer 1": "room-vz1",
        "4er-Zimmer 2": "room-vz2",
        "6er-Zimmer 1": "room-sz1",
        "6er-Zimmer 2": "room-sz2"
    }

    status_classes = {
        'Option': 'option',  # Gelb
        'Bestätigt': 'confirmed',  # Blau
        'Checked In': 'checkedin',  # Grün
        'Ausgecheckt': 'checkedout',
        'Storniert': 'cancelled'  # Rot
    }

    events = []
    for b in bookings:
        main_guest_name = b['name']
        num_guests = b['guests']
        start_date = b['arrival'].strftime('%Y-%m-%dT%H:%M:%S')  # Startdatum als ISO 8601
        end_date = b['departure'].strftime('%Y-%m-%dT%H:%M:%S')  # Enddatum als ISO 8601

        room_class = room_class_map.get(b['room'], 'default-room')  # Zimmerfarbe zuweisen
        status_class = status_classes.get(b['status'], 'option')  # Statusfarbe zuweisen

        events.append({
            'title': f"{main_guest_name} ({num_guests} P)",
            'start': start_date,
            'end': end_date,
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
                WHERE b.arrival BETWEEN %s AND %s
            """
            cursor = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute(query, (start_date, end_date))
            rows = cursor.fetchall()

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
                WHERE b.status = 'Bestätigt' AND b.arrival <= %s AND b.departure >= %s
            """
            cursor = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute(query, (today, today))
            rows = cursor.fetchall()

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
                WHERE b.departure = %s
            """
            cursor = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute(query, (today,))
            rows = cursor.fetchall()

            # Berechnung des Alters der Gäste und Gesamtpreis
            report_data = []
            for row in rows:
                guest_age = None  # Setze einen Standardwert
                if row['birthdate']:
                    guest_age = (today - datetime.strptime(row['birthdate'], "%Y-%m-%d").date()).days // 365
                    price = calculate_price(row['arrival'], row['departure'], row['guests'], row['hp'],
                                            row['hp_fleisch'] if 'hp_fleisch' in row else 0,
                                            # Standardwert 0, wenn nicht vorhanden
                                            row[
                                                'hp_vegi'] if 'hp_vegi' in row else 0)  # Standardwert 0, wenn nicht vorhanden
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
