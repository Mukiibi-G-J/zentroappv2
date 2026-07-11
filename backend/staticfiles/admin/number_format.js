document.addEventListener('DOMContentLoaded', function () {
    const numberInputs = document.querySelectorAll('input[type="number"]');

    function formatNumber(value) {
        // Remove any non-numeric characters except decimal point
        return parseFloat(value.toString().replace(/[^\d.-]/g, '')) || 0;
    }

    function displayFormat(value) {
        // Format number with commas for display
        return new Intl.NumberFormat().format(value);
    }

    numberInputs.forEach(input => {
        // Convert number inputs to text inputs to handle formatted values
        input.type = 'text';
        input.classList.add('numeric-input');

        let numericValue = '';

        input.addEventListener('input', function (e) {
            // Get the raw numeric value
            numericValue = formatNumber(e.target.value);

            // Show formatted value in the input
            if (numericValue) {
                e.target.value = displayFormat(numericValue);
            }

            // Trigger a custom event with the numeric value
            const event = new CustomEvent('numberValueChanged', {
                detail: { value: numericValue }
            });
            input.dispatchEvent(event);
        });

        // When input gains focus, show the numeric value
        input.addEventListener('focus', function (e) {
            if (numericValue) {
                e.target.value = numericValue;
            }
        });

        // When input loses focus, show the formatted value
        input.addEventListener('blur', function (e) {
            if (numericValue) {
                e.target.value = displayFormat(numericValue);
            }
        });

        // Initialize with any existing value
        if (input.value) {
            numericValue = formatNumber(input.value);
            input.value = displayFormat(numericValue);
        }
    });
});