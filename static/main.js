document.addEventListener("DOMContentLoaded", function () {
    // Initialize the FullCalendar instance
    const calendarEl = document.getElementById('calendar');
    const calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',  // Startansicht
        locale: 'de',  // Setze die Sprache auf Deutsch
        height: 700,  // Setze die Höhe des Kalenders
        events: '/api/bookings',  // Hole Events von diesem Endpunkt
        eventContent: function (arg) {
            console.log(arg.event);
            // Zugriff auf zusätzliche Daten des Events über extendedProps
            const eventTitle = arg.event.title; // Der Titel des Events (Name des Hauptbuchers)
            const circle = document.createElement('span');
            circle.className = 'status-dot status-' + arg.event.extendedProps.statusClass;
            const text = document.createElement('span');
            text.textContent = `${eventTitle}`;  // Nur Name und Gästezahl anzeigen
            return {domNodes: [circle, text]};  // Gibt die DOM-Knoten zurück
        }
    });

    // Render den Kalender
    calendar.render();

    const guestInput = document.getElementById("guests");
    const container = document.getElementById("guest-details");

    function updateGuestFields() {
        const count = parseInt(guestInput.value);
        const existing = container.querySelectorAll('input[name^="guest_name_"]').length;

        // Falls mehr als 1 Gast gebucht ist
        if (count > existing) {
            for (let i = existing + 1; i <= count; i++) {
                const nameLabel = document.createElement("label");
                nameLabel.textContent = `Name Mitreisender ${i}`;
                const nameInput = document.createElement("input");
                nameInput.className = "w3-input w3-margin-bottom";
                nameInput.name = `guest_name_${i}`;

                const birthLabel = document.createElement("label");
                birthLabel.textContent = `Geburtsdatum Mitreisender ${i}`;
                const birthInput = document.createElement("input");
                birthInput.type = "date";
                birthInput.className = "w3-input w3-margin-bottom";
                birthInput.name = `guest_birth_${i}`;

                container.appendChild(nameLabel);
                container.appendChild(nameInput);
                container.appendChild(birthLabel);
                container.appendChild(birthInput);
            }
        } else {
            // Entferne Felder, falls Gästeanzahl reduziert wurde
            for (let i = count; i < existing; i++) {
                container.removeChild(container.lastChild); // Entferne das letzte Element
                container.removeChild(container.lastChild); // Entferne das Geburtsdatum
            }
        }
    }

    if (guestInput && container) {
        guestInput.addEventListener("input", updateGuestFields);
        updateGuestFields(); // falls geladen mit >1 Gast
    }
});

let debounceTimeout;

function filterBookings() {
    const input = document.getElementById("searchInput");
    const filter = input.value.toUpperCase();
    const bookingCards = document.querySelectorAll(".booking-card");
    let found = false;

    bookingCards.forEach(function (card) {
        const textContent = card.textContent || card.innerText;

        if (textContent.toUpperCase().indexOf(filter) > -1) {
            card.style.display = "";
            found = true;
        } else {
            card.style.display = "none";
        }
    });

    if (!found) {
        if (document.querySelector('.no-results-message') === null) {
            const message = document.createElement('p');
            message.classList.add('no-results-message');
            message.textContent = 'Keine Buchungen gefunden.';
            document.body.appendChild(message);
        }
    } else {
        const message = document.querySelector('.no-results-message');
        if (message) {
            message.remove();
        }
    }
}

// Debouncing
document.getElementById("searchInput").addEventListener("keyup", function () {
    clearTimeout(debounceTimeout);
    debounceTimeout = setTimeout(filterBookings, 300);  // 300ms warten, bevor die Filter-Funktion ausgeführt wird
});