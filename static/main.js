document.addEventListener("DOMContentLoaded", function () {
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