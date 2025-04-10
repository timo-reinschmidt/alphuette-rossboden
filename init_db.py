import os

import psycopg2
from flask.cli import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()

# Verbindung zur PostgreSQL-Datenbank herstellen
conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME"),  # Datenbankname aus der Umgebungsvariable
    user=os.getenv("DB_USER"),  # Datenbankbenutzername aus der Umgebungsvariable
    password=os.getenv("DB_PASSWORD"),  # Datenbankpasswort aus der Umgebungsvariable
    host=os.getenv("DB_HOST"),  # Datenbankhost aus der Umgebungsvariable
    port=os.getenv("DB_PORT")  # Datenbankport aus der Umgebungsvariable
)

cursor = conn.cursor()

# Benutzer-Tabelle
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE
);
""")

# Admin-Benutzer erstellen
hashed_pw = generate_password_hash("demo")
cursor.execute("""
INSERT INTO users (username, password) 
VALUES (%s, %s)
ON CONFLICT (username) DO NOTHING;
""", ("admin", hashed_pw))

# Zimmer-Tabelle
cursor.execute("""
CREATE TABLE IF NOT EXISTS rooms (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    type TEXT,
    capacity INTEGER
);
""")

# Einfügen der Zimmerdaten
cursor.executemany("""
INSERT INTO rooms (name, type, capacity)
VALUES (%s, %s, %s)
ON CONFLICT (name) DO NOTHING;
""", [
    ("Doppelzimmer", "Doppelzimmer", 2),
    ("4er-Zimmer 1", "Viererzimmer", 4),
    ("4er-Zimmer 2", "Viererzimmer", 4),
    ("6er-Zimmer 1", "Sechserzimmer", 6),
    ("6er-Zimmer 2", "Sechserzimmer", 6)
])

# Buchungen-Tabelle mit UUID als Primärschlüssel
cursor.execute("""
CREATE TABLE IF NOT EXISTS bookings (
    id UUID PRIMARY KEY,
    name TEXT,
    birthdate TEXT,
    room TEXT,
    guests INTEGER,
    arrival DATE,
    departure DATE,
    hp TEXT DEFAULT 'Nein',
    hp_fleisch INTEGER DEFAULT 0,
    hp_vegi INTEGER DEFAULT 0,
    email TEXT,
    phone TEXT,
    status TEXT DEFAULT 'Option',
    address TEXT,
    postal_code TEXT,
    city TEXT,
    country TEXT,
    notes TEXT,
    payment_status BOOLEAN DEFAULT FALSE,
    payment_method TEXT
);
""")

# Gäste-Tabelle
cursor.execute("""
CREATE TABLE IF NOT EXISTS guests (
    id SERIAL PRIMARY KEY,
    booking_id UUID,
    name TEXT,
    birthdate TEXT,
    FOREIGN KEY(booking_id) REFERENCES bookings(id)
);
""")

# Buchungsverlauf-Tabelle
cursor.execute("""
CREATE TABLE IF NOT EXISTS booking_history (
    id SERIAL PRIMARY KEY,
    booking_id UUID,
    status TEXT,
    changed_at TIMESTAMP,
    changed_by INTEGER,
    FOREIGN KEY(booking_id) REFERENCES bookings(id),
    FOREIGN KEY(changed_by) REFERENCES users(id)
);
""")

# Preisstruktur-Tabelle
cursor.execute("""
CREATE TABLE IF NOT EXISTS prices (
    id SERIAL PRIMARY KEY,
    category TEXT UNIQUE NOT NULL,
    age_min REAL,
    age_max REAL,
    weekend_price REAL,
    weekday_price REAL
);
""")

# Stadtsteuer-Tabelle
cursor.execute("""
CREATE TABLE IF NOT EXISTS city_tax (
    id SERIAL PRIMARY KEY,
    age_min REAL,
    age_max REAL,
    tax REAL,
    CONSTRAINT unique_age_range UNIQUE (age_min, age_max)
);
""")

# Abendessen-Preis-Tabelle
cursor.execute("""
CREATE TABLE IF NOT EXISTS dinner_prices (
    id SERIAL PRIMARY KEY,
    age_max REAL UNIQUE,
    price REAL
);
""")

cursor.executemany("""
INSERT INTO dinner_prices (age_max, price)
VALUES (%s, %s)
ON CONFLICT (age_max) DO NOTHING;
""", [
    (11.99, 20.0),
    (200.0, 35.0)
])

# Einfügen der Preisdaten
cursor.executemany("""
INSERT INTO prices (category, age_min, age_max, weekend_price, weekday_price)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (category) DO NOTHING;
""", [
    ("adult", 16.0, 200.0, 90.0, 70.0),
    ("child_12_15", 12.0, 15.99, 70.0, 50.0),
    ("child_6_11", 6.0, 11.99, 45.0, 35.0),
    ("child_0_5", 0.0, 5.99, 0.0, 0.0)
])

cursor.executemany("""
INSERT INTO city_tax (age_min, age_max, tax)
VALUES (%s, %s, %s)
ON CONFLICT (age_min, age_max) DO NOTHING;
""", [
    (16.0, 200.0, 4.0),
    (6.0, 15.99, 1.5)
])

# Änderungen in der Datenbank speichern
conn.commit()

# Verbindung schließen
conn.close()

print("✔️ Neue PostgreSQL-Datenbank erstellt – mit UUIDs, Preisen und Zimmern.")
