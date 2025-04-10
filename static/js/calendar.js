document.addEventListener("DOMContentLoaded", function () {
    const calendarEl = document.getElementById('calendar');
    const calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        locale: 'de',
        height: 700,
        timeZone: 'Europe/Zurich',
        events: '/api/bookings',
        eventContent: function (arg) {
            const startDate = new Date(arg.event.start).toISOString();
            const endDate = new Date(arg.event.end).toISOString();

            // Zugriff auf den Titel des Events (Name des Hauptbuchers und Gästezahl)
            const eventTitle = arg.event.title;


            // Erstellen eines Statuskreises
            const circle = document.createElement('span');
            circle.className = 'status-dot ' + 'status-' + arg.event.extendedProps.statusClass;  // Statuskreis mit Farbe

            // Erstellen des Texts (Name des Hauptbuchers + Gästezahl)
            const text = document.createElement('span');
            text.textContent = `${eventTitle}`;
            text.style.color = "black";  // Setzt die Textfarbe auf Schwarz

            // Geben Sie das DOM zurück (Kreis und Text)
            return {domNodes: [circle, text]};
        }
    });

    // Rendern des Kalenders
    calendar.render();
});