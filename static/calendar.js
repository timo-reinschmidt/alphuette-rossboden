// calendar.js
document.addEventListener("DOMContentLoaded", function () {
    const calendarEl = document.getElementById('calendar');
    const calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        locale: 'de',
        height: 700,
        events: '/api/bookings',
        eventContent: function (arg) {
            console.log(arg.event);
            const eventTitle = arg.event.title;
            const circle = document.createElement('span');
            circle.className = 'status-dot status-' + arg.event.extendedProps.statusClass;
            const text = document.createElement('span');
            text.textContent = `${eventTitle}`;
            return {domNodes: [circle, text]};
        }
    });

    calendar.render();
});