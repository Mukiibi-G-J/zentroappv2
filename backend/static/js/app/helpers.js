// Validation Functions
const validators = {
    email: (value) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value),
    phone: (value) => /^[0-9]{10,}$/.test(value),
    password: (value) => /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$/.test(value),
    confirmPassword: (value, password) => value === password,
};

// Real-time Input Validation
function setupInputValidation(
    input,
    inputType,
    errorElement,
    errorMessage,
    compareValue = null
) {
    if (!input || !errorElement) return;

    input.addEventListener("input", function () {
        const currentValue = this.value.trim()
        switch (inputType) {
            case "email":
                if (!validators.email(this.value)) {
                    errorElement.textContent = errorMessage;
                    errorElement.classList.remove("hidden");
                    this.classList.add("border-red-500");
                } else {
                    errorElement.classList.add("hidden");
                    this.classList.remove("border-red-500");

                }
                break;
            case "phone":
                if (!validators.phone(this.value)) {
                    errorElement.textContent = errorMessage;
                    errorElement.classList.remove("hidden");
                    this.classList.add("border-red-500");
                } else {
                    errorElement.classList.add("hidden");
                    this.classList.remove("border-red-500");
                }
                break;
            case "password":
                if (!validators.password(this.value)) {
                    errorElement.textContent = errorMessage;
                    errorElement.classList.remove("hidden");
                    this.classList.add("border-red-500");
                } else {
                    errorElement.classList.add("hidden");
                    this.classList.remove("border-red-500");
                }
                break;
            case "confirm-password":

                if (currentValue !== compareValue) {
                    errorElement.textContent = errorMessage;
                    errorElement.classList.remove("hidden");
                    this.classList.add("border-red-500");
                } else {
                    errorElement.classList.add("hidden");
                    this.classList.remove("border-red-500");
                }
                break;
            default:
                break;
        }
    });
}


