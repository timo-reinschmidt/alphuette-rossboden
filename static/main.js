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

    const hpCheckbox = document.querySelector('input[name="hp"]');
    const hpFleischField = document.querySelector('input[name="hp_fleisch"]');
    const hpVegiField = document.querySelector('input[name="hp_vegi"]');

    // Funktion zum Aktivieren/Deaktivieren der Fleisch- und Vegi-Felder
    function toggleHPFields() {
        if (hpCheckbox.checked) {
            hpFleischField.disabled = false;  // Aktivieren der Felder
            hpVegiField.disabled = false;    // Aktivieren der Felder
        } else {
            hpFleischField.disabled = true;   // Deaktivieren der Felder
            hpVegiField.disabled = true;      // Deaktivieren der Felder
        }
    }

    // Funktion zum Initialisieren der Felder (wird aufgerufen, wenn die Seite geladen wird)
    function initializeFields() {
        toggleHPFields();  // Setzt die Felder beim ersten Laden auf Basis des HP-Checkbox-Status
    }

    // Beim Laden der Seite prüfen, ob HP aktiviert ist
    initializeFields();

    // Füge EventListener hinzu, um sofortige Reaktion auf Änderung zu gewährleisten
    hpCheckbox.addEventListener('change', toggleHPFields);  // Mit 'change', um sofortige Reaktion auf Änderungen zu garantieren.
    hpFleischField.addEventListener('input', function () {
        console.log("Fleischanteil geändert");
    });
    hpVegiField.addEventListener('input', function () {
        console.log("Vegi-Anteil geändert");
    });

    // Add event listener to dynamically calculate the price preview
    const pricePreview = document.getElementById("price-preview");

    // Update price preview function (you can further enhance this logic)
    function updatePricePreview() {
        const hpChecked = hpCheckbox.checked;
        const hpFleischValue = hpChecked ? parseInt(hpFleischField.value) || 0 : 0;
        const hpVegiValue = hpChecked ? parseInt(hpVegiField.value) || 0 : 0;

        let totalPrice = 0;

        // Calculate the price based on number of guests, HP, Fleisch, Vegi (you may modify this logic)
        totalPrice = 100 + (hpFleischValue * 20) + (hpVegiValue * 15); // Example price logic

        // Update the price preview display
        pricePreview.innerText = totalPrice.toFixed(2);  // Assuming totalPrice is calculated correctly
    }

    // Attach the function to change events of the input fields (HP, Fleisch, Vegi)
    hpCheckbox.addEventListener('change', updatePricePreview);
    hpFleischField.addEventListener('input', updatePricePreview);
    hpVegiField.addEventListener('input', updatePricePreview);

    // Initialize price preview on page load
    updatePricePreview();
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