document.addEventListener("DOMContentLoaded", function () {
    console.log("JavaScript geladen");

    // Button zum Hinzufügen von Mitreisenden
    const addGuestButton = document.getElementById("add-guest");
    const guestDetailsContainer = document.getElementById("guest-details");
    let guestCount = 0;

    // Sicherstellen, dass der Button vorhanden ist
    if (addGuestButton) {
        console.log("Button gefunden: + Mitreisenden hinzufügen");
    } else {
        console.error("Der Button zum Hinzufügen von Mitreisenden wurde nicht gefunden.");
        return;
    }

    // Funktion, um neue Felder für Mitreisende hinzuzufügen
    function addGuestFields() {
        guestCount++; // Erhöhe die Anzahl der Gäste
        const guestFieldSet = document.createElement("div");
        guestFieldSet.classList.add("guest-fieldset");

        // Mitreisender Name
        const nameLabel = document.createElement("label");
        nameLabel.textContent = `Name Mitreisender ${guestCount}`;
        const nameInput = document.createElement("input");
        nameInput.classList.add("w3-input", "w3-margin-bottom");
        nameInput.name = `guest_name_${guestCount}`;

        // Geburtsdatum des Mitreisenden
        const birthLabel = document.createElement("label");
        birthLabel.textContent = `Geburtsdatum Mitreisender ${guestCount}`;
        const birthInput = document.createElement("input");
        birthInput.classList.add("w3-input", "w3-margin-bottom");
        birthInput.type = "date";
        birthInput.name = `guest_birth_${guestCount}`;

        // Entfernen-Button für das Gast-Feld
        const removeButton = document.createElement("button");
        removeButton.classList.add("w3-button", "w3-red", "w3-margin-top");
        removeButton.type = "button";
        removeButton.textContent = "Entfernen";
        removeButton.onclick = function () {
            guestDetailsContainer.removeChild(guestFieldSet);
        };

        guestFieldSet.appendChild(nameLabel);
        guestFieldSet.appendChild(nameInput);
        guestFieldSet.appendChild(birthLabel);
        guestFieldSet.appendChild(birthInput);
        guestFieldSet.appendChild(removeButton);

        guestDetailsContainer.appendChild(guestFieldSet);
    }

    // EventListener für den "+"-Button
    addGuestButton.addEventListener("click", function () {
        console.log("Button geklickt: Mitreisenden hinzufügen");
        addGuestFields();
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