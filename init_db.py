import sqlite3

from werkzeug.security import generate_password_hash

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

# Benutzer
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    is_admin BOOLEAN DEFAULT 0
);
""")

# Zimmer
cursor.execute("""
CREATE TABLE IF NOT EXISTS rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    type TEXT,
    capacity INTEGER
);
""")

cursor.executemany("""
INSERT OR IGNORE INTO rooms (name, type, capacity)
VALUES (?, ?, ?)
""", [
    ("Doppelzimmer", "Doppelzimmer", 2),
    ("4er-Zimmer 1", "Viererzimmer", 4),
    ("4er-Zimmer 2", "Viererzimmer", 4),
    ("6er-Zimmer 1", "Sechserzimmer", 6),
    ("6er-Zimmer 2", "Sechserzimmer", 6)
])

# Buchungen (UUID)
cursor.execute("""
CREATE TABLE IF NOT EXISTS bookings (
    id TEXT PRIMARY KEY,
    name TEXT,
    birthdate TEXT,
    room TEXT,
    guests INTEGER,
    arrival TEXT,
    departure TEXT,
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
    payment_status BOOLEAN DEFAULT 0,
    payment_method TEXT
);
""")

# Gäste
cursor.execute("""
CREATE TABLE IF NOT EXISTS guests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id TEXT,
    name TEXT,
    birthdate TEXT,
    FOREIGN KEY(booking_id) REFERENCES bookings(id)
);
""")

# Buchungsverlauf
cursor.execute("""
CREATE TABLE IF NOT EXISTS booking_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id TEXT,
    status TEXT,
    changed_at TEXT,
    changed_by INTEGER,
    FOREIGN KEY(booking_id) REFERENCES bookings(id),
    FOREIGN KEY(changed_by) REFERENCES users(id)
);
""")

# Preisstruktur
cursor.execute("""
CREATE TABLE IF NOT EXISTS prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT,
    age_min REAL,
    age_max REAL,
    weekend_price REAL,
    weekday_price REAL
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS city_tax (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    age_min REAL,
    age_max REAL,
    tax REAL
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS dinner_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    age_max REAL,
    price REAL
);
""")

# Einfügen der Preisdaten
cursor.executemany("""
INSERT INTO prices (category, age_min, age_max, weekend_price, weekday_price)
VALUES (?, ?, ?, ?, ?)
""", [
    ("adult", 16.0, 200.0, 90.0, 70.0),
    ("child_12_15", 12.0, 15.99, 70.0, 50.0),
    ("child_6_11", 6.0, 11.99, 45.0, 35.0),
    ("child_0_5", 0.0, 5.99, 0.0, 0.0)
])

cursor.executemany("""
INSERT INTO city_tax (age_min, age_max, tax)
VALUES (?, ?, ?)
""", [
    (16.0, 200.0, 4.0),
    (6.0, 15.99, 1.5)
])

cursor.executemany("""
INSERT INTO dinner_prices (age_max, price)
VALUES (?, ?)
""", [
    (11.99, 20.0),
    (200.0, 35.0)
])

# Admin
hashed_pw = generate_password_hash("demo")
cursor.execute("INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)", ("admin", hashed_pw))

conn.commit()
conn.close()
print("✔️ Neue Datenbank erstellt – mit UUIDs, Preisen und Zimmern.")
