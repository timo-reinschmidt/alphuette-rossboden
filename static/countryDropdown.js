document.addEventListener('DOMContentLoaded', function () {
    const countrySelect = document.getElementById("country");
    const otherCountryField = document.getElementById("other-country-field");

    countrySelect.addEventListener('change', function () {
        if (countrySelect.value === "Other") {
            otherCountryField.style.display = 'block';  // Zeigt das Textfeld an
        } else {
            otherCountryField.style.display = 'none';   // Versteckt das Textfeld
        }
    });
});