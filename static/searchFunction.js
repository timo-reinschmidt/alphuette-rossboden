document.addEventListener("DOMContentLoaded", function () {
    // Sucheingabefeld
    const searchInput = document.getElementById("searchInput");

    // Suche durchführen, wenn der Benutzer etwas eintippt
    searchInput.addEventListener("input", function () {
        const searchTerm = searchInput.value.toLowerCase();  // Kleinbuchstaben für Fallunempfindlichkeit
        const bookingCards = document.querySelectorAll(".booking-card");  // Alle Buchungskarten

        bookingCards.forEach(card => {
            const cardText = card.textContent.toLowerCase();  // Textinhalt der Buchungskarten
            if (cardText.includes(searchTerm)) {
                card.style.display = "";  // Anzeigen der Buchungskarte, wenn der Text übereinstimmt
            } else {
                card.style.display = "none";  // Ausblenden der Buchungskarte, wenn der Text nicht übereinstimmt
            }
        });
    });
});