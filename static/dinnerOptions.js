// hp.js
document.addEventListener("DOMContentLoaded", function () {
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
});