function togglePaymentMethod() {
    const isChecked = document.querySelector('[name="payment_status"]').checked;
    document.getElementById("payment-method-container").style.display = isChecked ? 'block' : 'none';
    document.querySelector('[name="payment_method"]').disabled = !isChecked;
}