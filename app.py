from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime
import uuid

app = Flask(__name__)
app.secret_key = 'very_secret'

# Dummy data structures
rooms = {
    "Doppelzimmer": 2,
    "Viererzimmer 1": 4,
    "Viererzimmer 2": 4,
    "Sechserzimmer 1": 6,
    "Sechserzimmer 2": 6
}

bookings = []

@app.route('/')
def index():
    return render_template('index.html', bookings=bookings)

@app.route('/new', methods=['GET', 'POST'])
def new_booking():
    if request.method == 'POST':
        data = request.form
        room = data['room']
        guests = int(data['guests'])
        if guests > rooms[room]:
            return f"Maximale Belegung für {room} ist {rooms[room]} Personen.", 400

        booking = {
            "id": str(uuid.uuid4())[:8],
            "name": data['name'],
            "birthdate": data['birthdate'],
            "room": room,
            "guests": guests,
            "arrival": data['arrival'],
            "departure": data['departure'],
            "breakfast": "Ja" if 'breakfast' in data else "Nein",
            "dinner": "Ja" if 'dinner' in data else "Nein"
        }
        bookings.append(booking)
        return redirect(url_for('index'))
    return render_template('new_booking.html', rooms=rooms)

@app.route('/search')
def search():
    query = request.args.get('q', '').lower()
    results = [b for b in bookings if query in b['name'].lower() or query in b['id'].lower()]
    return render_template('index.html', bookings=results)

if __name__ == '__main__':
    app.run(debug=True)
