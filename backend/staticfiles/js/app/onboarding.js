const initialCompanyName = document.getElementById("initial-company-name");
const statusElement = document.getElementById("company-name-status");
const organization_size = document.getElementById("organization-size");
const continueBtn = document.getElementById("continue-btn");
var isExistingResponse = true;

// Add these variables at the top with other constants
let isLoading = false;
let hasError = false;

let isSubmitting = false;

// modal
const modal = document.getElementById("company-information-modal");
const modalCompanyName = document.getElementById("modal-company-name");
const modalCompanyEmail = document.getElementById("modal-company-email");
const modalCompanyAddress = document.getElementById("modal-company-address");
const modalCompanyPhone = document.getElementById("modal-company-phone");
const modalCompanyPassword = document.getElementById("modal-company-password");
const modalCompanyConfirmPassword = document.getElementById("modal-company-confirm-password");


// Error Elements
const passwordError = document.getElementById("password-error");
const confirmPasswordError = document.getElementById(
    "confirm-password-error"
);
const emailError = document.getElementById("email-error");
const phoneError = document.getElementById("phone-error");

const SELECTED_STYLE = 'ring-2 ring-primary-600 border-primary-600 bg-primary-50';

continueBtn.addEventListener("click", function (evt) {
    // clear all local storage item 
    console.log("clear all local storage item");
    clearSelections();
});

initialCompanyName.addEventListener("keyup", function (evt) {
    if (evt.target.value.length > 0 && evt.target.value.length < 3) {
        statusElement.textContent = "Company name must be at least 3 characters long";
        statusElement.style.color = "red";
        hasError = true;
    } else {
        statusElement.textContent = "";
        statusElement.style.color = "green";
        hasError = false;
    }
    updateContinueButtonState();
});

document.body.addEventListener("htmx:beforeRequest", function (evt) {
    if (evt.detail.target.id === "company-name-status") {
        isLoading = true;
        updateContinueButtonState();
    }
});

document.body.addEventListener("htmx:afterRequest", function (evt) {
    if (evt.detail.target.id === "company-name-status") {
        isLoading = false;
        const response = JSON.parse(evt.detail.xhr.responseText);

        // Update the status message
        evt.detail.target.innerHTML = response.html;

        // Check if response contains an error
        hasError = response.html.includes('text-red-500') || response.html.includes('error');

        // Enable/disable continue button based on validation
        isExistingResponse = response.is_existing;

        if (isExistingResponse) {
            organization_size.disabled = true;
        } else {
            organization_size.disabled = false;
        }

        if (initialCompanyName.value.length > 0) {
            organization_size.disabled = false;
        } else {
            organization_size.disabled = true;
        }

        updateContinueButtonState();
    }
});



// Add this new function to handle button state
function updateContinueButtonState() {
    if (isLoading || hasError || isExistingResponse || !organization_size.value || initialCompanyName.value.length < 3) {
        continueBtn.setAttribute("disabled", "");
    } else {
        continueBtn.removeAttribute("disabled");
    }
}

organization_size.addEventListener("change", function (evt) {
    updateContinueButtonState();
});


function handleSelection(element, type) {
    // Remove selection from other elements
    document.querySelectorAll(`.selection-option[data-${type}]`).forEach(el => {
        el.classList.remove(...SELECTED_STYLE.split(' '));
    });

    // Add selection to clicked element
    element.classList.add(...SELECTED_STYLE.split(' '));

    // Store the selection
    const selectedId = element.dataset[type];
    document.getElementById(`selected-${type}`).value = selectedId;

    // Store in localStorage for persistence
    localStorage.setItem(`selected-${type}`, selectedId);
}

// Restore selections on page load
document.addEventListener('DOMContentLoaded', function () {
    // Restore category selection
    const selectedCategory = localStorage.getItem('selected-category');
    if (selectedCategory) {
        const categoryElement = document.querySelector(`.selection-option[data-category="${selectedCategory}"]`);
        if (categoryElement) {
            categoryElement.classList.add(...SELECTED_STYLE.split(' '));
            document.getElementById('selected-category').value = selectedCategory;
        }
    }
    // Restore objective selection
    const selectedObjective = localStorage.getItem('selected-objective');
    if (selectedObjective) {
        const objectiveElement = document.querySelector(`.selection-option[data-objective="${selectedObjective}"]`);
        if (objectiveElement) {
            objectiveElement.classList.add(...SELECTED_STYLE.split(' '));
            document.getElementById('selected-objective').value = selectedObjective;
        }
    }
});

// Optional: Clear selections when completing onboarding
function clearSelections() {
    localStorage.removeItem('selected-category');
    localStorage.removeItem('selected-objective');
}


document
    .getElementById("company-information-modal")
    .addEventListener("show.bs.modal", function () {
        const initialCompanyName = document.getElementById(
            "initial-company-name"
        ).value;
        document.getElementById("modal-company-name").value = initialCompanyName;
    });


// Email Validation

setupInputValidation(modalCompanyEmail, "email", emailError, "Please enter a valid email");

// Phone Validation

setupInputValidation(modalCompanyPhone, "phone", phoneError, "Please enter a valid phone number");

// Password Validation

setupInputValidation(modalCompanyPassword, "password", passwordError,
    "Password must be at least 8 characters long and contain uppercase, lowercase, and numbers")

// Confirm Password Validation

modalCompanyPassword.addEventListener('input', function (evt) {
    // Update confirm password validation whenever original password changes
    setupInputValidation(
        modalCompanyConfirmPassword,
        "confirm-password",
        confirmPasswordError,
        "Passwords do not match",
        this.value
    );
});


function togglePasswordVisibility(inputId, button) {
    // Get the input element and icons within the button's parent container
    const input = document.getElementById(inputId);
    const showIcon = button.querySelector('.show-password-icon');
    const hideIcon = button.querySelector('.hide-password-icon');

    // Toggle password visibility
    if (input.type === 'password') {
        input.type = 'text';
        showIcon.classList.add('hidden');
        hideIcon.classList.remove('hidden');
    } else {
        input.type = 'password';
        showIcon.classList.remove('hidden');
        hideIcon.classList.add('hidden');
    }
}

document.addEventListener('DOMContentLoaded', function () {
    // Fix the selector to match the correct class
    const passwordToggles = document.querySelectorAll('.password-toggle');
    const confirmPasswordToggles = document.querySelectorAll('.confirm-password-toggle');

    passwordToggles.forEach(toggle => {
        toggle.addEventListener('click', function () {
            // Find the closest input field within the parent container
            const input = this.closest('.input-wrapper').querySelector('input');
            togglePasswordVisibility(input.id, this);
        });
    });

    confirmPasswordToggles.forEach(toggle => {
        toggle.addEventListener('click', function () {
            const input = this.closest('.input-wrapper').querySelector('input');
            togglePasswordVisibility(input.id, this);
        });
    });
});



function validateForm() {
    const requiredInputs = document.querySelectorAll('input[required]');
    const completeButton = document.querySelector('#complete-setup-btn');

    let isValid = true;

    requiredInputs.forEach(input => {
        // Check if input is empty
        if (!input.value) {
            isValid = false;
            return;
        }

        // Check for visible error messages
        const errorElement = document.querySelector(`#${input.name}-error`);
        if (errorElement && !errorElement.classList.contains('hidden')) {
            isValid = false;
            return;
        }
    });

    // Enable/disable button based on validation result
    if (isValid) {
        completeButton.removeAttribute('disabled');
    } else {
        completeButton.setAttribute('disabled', '');
    }
}

document.addEventListener('DOMContentLoaded', function () {
    const requiredInputs = document.querySelectorAll('input[required]');
    requiredInputs.forEach(input => {
        ['input', 'change', 'blur'].forEach(evenType => {
            input.addEventListener(evenType, () => {
                validateForm();
                // Uncomment next line to debug
                // debugValidation();
            });
        });
    });

    // Initial validation check
    validateForm();
});


// form submit
document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('company-setup-form');
    const selectedObjective = document.getElementById('selected-objective').value;
    const organization_size = document.getElementById('organization-size');

    form.addEventListener("submit", function (e) {
        e.preventDefault();

        setSubmittingState(true);
        const formData = new FormData(this);
        const formDataObj = {};
        formData.forEach((value, key) => (formDataObj[key] = value));

        // Explicitly add the business objective and organization size
        if (localStorage.getItem('selected-objective')) {
            formDataObj.business_objective = localStorage.getItem('selected-objective');
        }
        if (localStorage.getItem('selected-objective')) {
            formDataObj.business_category = localStorage.getItem('selected-category');

        }
        formDataObj.organization_size = organization_size.value;

        fetch("/company-onboarding/", {
            method: "POST",
            body: JSON.stringify(formDataObj),
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": document.querySelector('input[name="csrfmiddlewaretoken"]').value,
            }
        }).then(response => response.json()).then(data => {
            const responseData = data;
            console.log("responseData");
            console.log(responseData);
            handleSubmissionResponse(responseData);
        }).catch((error) => {
            console.log(error);
        })
    })

});


function handleSubmissionResponse(data) {
    const taskId = data.task_id;

    // Start checking task status
    checkTaskStatus(taskId);
}

async function checkTaskStatus(taskId) {
    try {
        const response = await fetch(`/task-status/${taskId}/`, {
            headers: {
                "X-CSRFToken": document.querySelector('input[name="csrfmiddlewaretoken"]').value,
            }
        });
        const data = await response.json();

        // Update UI based on status
        updateUIStatus(data);

        // Continue polling if not complete
        if (data.state === 'PROGRESS' || data.state === 'PENDING') {
            setTimeout(() => checkTaskStatus(taskId), 1000);
        } else if (data.state === 'SUCCESS') {
            updateUIStatus({
                progress: 100,
                message: "Setup completed successfully!"
            });
            completeSetup();
        } else if (data.state === 'FAILURE') {
            handleError(data.message || 'An error occurred during setup');
        }
    } catch (error) {
        console.error('Error checking task status:', error);
        handleError('Failed to check task status');
    }
}

function updateUIStatus(data) {
    const progressContainer = document.getElementById('setup-progress');
    const statusElement = document.getElementById('setup-status');
    const progressBar = document.getElementById('progress-bar');
    const progressPercentage = document.getElementById('progress-percentage');

    // Show progress container when task starts
    if (progressContainer.classList.contains('hidden')) {
        progressContainer.classList.remove('hidden');
    }

    // Update progress bar and percentage
    if (data.progress !== undefined) {
        const progress = data.progress;
        progressBar.style.width = `${progress}%`;
        progressPercentage.textContent = `${progress}%`;
    }

    // Update status message
    if (data.message) {
        statusElement.textContent = data.message;
    }
}

function completeSetup() {
    // Hide progress container when complete
    document.getElementById('setup-progress').classList.add('hidden');
    setSubmittingState(false);
    const elements = {
        fillNowBtn: document.getElementById("fill-now-btn"),
        loginNowBtn: document.getElementById("login-now-btn"),
        successIcon: document.getElementById("success-icon"),
        backBtn: document.getElementById("latest-back-btn"),
        closeBtn: document.querySelector('[data-bs-dismiss="modal"]'),
    };

    // Update UI elements
    elements.fillNowBtn?.setAttribute("disabled", "");
    elements.loginNowBtn?.removeAttribute("disabled");
    if (elements.successIcon) {
        elements.successIcon.classList.remove("text-gray-400");
        elements.successIcon.classList.add("text-green-500");
    }
    elements.backBtn?.remove();
    elements.closeBtn?.click();
}

function handleError(errorMessage) {
    // Show error message to user
    const errorElement = document.getElementById('setup-error');
    if (errorElement) {
        errorElement.textContent = errorMessage;
        errorElement.classList.remove('hidden');
    }
}

// Add this function to handle form submission state
function setSubmittingState(submitting) {
    isSubmitting = submitting;
    const submitBtn = document.getElementById('complete-setup-btn');

    if (submitting) {
        submitBtn.setAttribute("disabled", "");
        submitBtn.innerHTML = 'Processing...';
    } else {
        submitBtn.removeAttribute("disabled");
        submitBtn.innerHTML = 'Complete Setup';
        isSubmitting = false;

    }
}

// Add navigation warning
window.addEventListener('beforeunload', function (e) {
    if (isSubmitting) {
        e.preventDefault();
        e.returnValue = '';
        return '';
    }
});



// Handle modal close attempts during submission
document.getElementById('company-information-modal').addEventListener('hide.bs.modal', function (e) {
    if (isSubmitting) {
        e.preventDefault();
        alert('Please wait while your information is being processed.');
    }
});


