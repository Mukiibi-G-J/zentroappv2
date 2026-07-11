/**
 * BOM Line - Unit of Measure Dynamic Filtering
 * 
 * This script filters the Unit of Measure dropdown based on the selected item.
 * It fetches the item's available unit of measures from the API and updates the dropdown accordingly.
 */

(function () {
    'use strict';

    // Helper function to get CSRF token from cookies
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Wait for DOM to be ready
    document.addEventListener('DOMContentLoaded', function () {
        initializeUOMFiltering();
    });

    // Also initialize when Django adds new inline forms
    if (typeof django !== 'undefined' && django.jQuery) {
        django.jQuery(document).on('formset:added', function (event, $row, formsetName) {
            if (formsetName === 'lines') {
                initializeUOMFilteringForRow($row[0]);
            }
        });
    }

    function initializeUOMFiltering() {
        // Find all BOM line inline forms
        const inlineForms = document.querySelectorAll('.dynamic-lines, #lines-group .tabular');

        inlineForms.forEach(function (inlineForm) {
            const rows = inlineForm.querySelectorAll('tr.form-row, tr.dynamic-lines');
            rows.forEach(function (row) {
                initializeUOMFilteringForRow(row);
            });
        });
    }

    function initializeUOMFilteringForRow(row) {
        // Find the item select field
        const itemSelect = row.querySelector('select[name*="item"]');
        const uomSelect = row.querySelector('select[name*="unit_of_measure"]');

        if (!itemSelect || !uomSelect) {
            return; // Not a BOM line row or fields not found
        }

        // Store all original UOM options
        if (!uomSelect.dataset.originalOptions) {
            const options = Array.from(uomSelect.options).map(opt => ({
                value: opt.value,
                text: opt.text
            }));
            uomSelect.dataset.originalOptions = JSON.stringify(options);
        }

        // Add change event listener to item select
        itemSelect.addEventListener('change', function () {
            handleItemChange(itemSelect, uomSelect);
        });

        // Trigger initial filtering if item is already selected
        if (itemSelect.value) {
            handleItemChange(itemSelect, uomSelect);
        }
    }

    function handleItemChange(itemSelect, uomSelect) {
        const itemNo = itemSelect.value;

        if (!itemNo) {
            // No item selected, restore all UOM options
            restoreAllUOMOptions(uomSelect);
            return;
        }

        // Get the selected item's text to extract the item number
        const selectedOption = itemSelect.options[itemSelect.selectedIndex];
        const itemText = selectedOption.text;

        // Extract item number from text (format is usually "ITEM-XXX-#### - Item Name")
        let extractedItemNo = itemNo;

        // Fetch the item's unit of measures
        fetchItemUnitOfMeasures(extractedItemNo, uomSelect);
    }

    function fetchItemUnitOfMeasures(itemNo, uomSelect) {
        // Show loading state
        const currentValue = uomSelect.value;
        uomSelect.disabled = true;

        // Build API URL
        const apiUrl = `/api/production/items/${encodeURIComponent(itemNo)}/unit-of-measures/`;

        // Get CSRF token from Django cookie
        const csrfToken = getCookie('csrftoken');

        fetch(apiUrl, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrfToken
            },
            credentials: 'same-origin'
        })
            .then(response => {
                if (!response.ok) {
                    return response.text().then(text => {
                        console.error('API Error Response:', text);
                        throw new Error('Failed to fetch unit of measures: ' + response.status);
                    });
                }
                return response.json();
            })
            .then(data => {
                filterUOMOptions(uomSelect, data.unitOfMeasures, currentValue);
            })
            .catch(error => {
                console.error('Error fetching unit of measures:', error);
                // Restore all options on error
                restoreAllUOMOptions(uomSelect);
            })
            .finally(() => {
                uomSelect.disabled = false;
            });
    }

    function filterUOMOptions(uomSelect, itemUOMs, currentValue) {
        // Get original options
        const originalOptions = JSON.parse(uomSelect.dataset.originalOptions || '[]');

        // Clear current options except the empty option
        const emptyOption = uomSelect.querySelector('option[value=""]');
        uomSelect.innerHTML = '';
        if (emptyOption) {
            uomSelect.appendChild(emptyOption);
        }

        // Get the list of valid UOM codes for this item
        const validUOMCodes = itemUOMs.map(uom => uom.code);

        // Add back only the options that are valid for this item
        originalOptions.forEach(function (optData) {
            if (optData.value && validUOMCodes.includes(optData.value)) {
                const option = document.createElement('option');
                option.value = optData.value;
                option.text = optData.text;
                uomSelect.appendChild(option);
            }
        });

        // Try to restore the previous value if it's still valid
        if (currentValue && validUOMCodes.includes(currentValue)) {
            uomSelect.value = currentValue;
        } else if (itemUOMs.length > 0) {
            // Auto-select the default UOM if available
            const defaultUOM = itemUOMs.find(uom => uom.isDefault);
            if (defaultUOM) {
                uomSelect.value = defaultUOM.code;
            } else {
                // Select the first available UOM
                uomSelect.value = itemUOMs[0].code;
            }
        }
    }

    function restoreAllUOMOptions(uomSelect) {
        const originalOptions = JSON.parse(uomSelect.dataset.originalOptions || '[]');

        uomSelect.innerHTML = '';
        originalOptions.forEach(function (optData) {
            const option = document.createElement('option');
            option.value = optData.value;
            option.text = optData.text;
            uomSelect.appendChild(option);
        });
    }

})();

