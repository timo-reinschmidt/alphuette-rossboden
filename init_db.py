import sqlite3

from werkzeug.security import generate_password_hash

# Verbindung zur Datenbank
conn = sqlite3.connect("database.db")
cursor = conn.cursor()

# Tabellen erstellen
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    notes TEXT
);
""")

cursor.execute("PRAGMA table_info(bookings);")
columns = cursor.fetchall()
print(columns)

cursor.execute('''
    CREATE TABLE IF NOT EXISTS guests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id TEXT,
        name TEXT,
        birthdate TEXT,
        FOREIGN KEY(booking_id) REFERENCES bookings(id)
    );
''')

# Beispiel-Benutzer: admin / demo
hashed_pw = generate_password_hash("demo")
cursor.execute("INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)", ("admin", hashed_pw))

# Änderungen speichern und schließen
conn.commit()
conn.close()

print("✔️ Datenbank erstellt: database.db")
