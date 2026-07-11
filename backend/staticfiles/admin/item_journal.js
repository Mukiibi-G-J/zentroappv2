document.addEventListener('DOMContentLoaded', function () {
    // Wait for Django's jQuery to be loaded
    var checkJquery = setInterval(function () {
        if (window.django && window.django.jQuery) {
            clearInterval(checkJquery);
            initializeItemJournal(window.django.jQuery);
        }
    }, 100);
});

function initializeItemJournal($) {
    'use strict';

    // Add these variables at the top of your initializeItemJournal function
    var quantityField = $('#id_quantity');
    var unitAmountField = $('#id_unit_amount');
    var amountField = $('#id_amount');
    var unitCostField = $('#id_unit_cost');
    var unitOfMeasureField = $('#id_unit_of_measure');

    function parseFormattedNumber(value) {
        return parseFloat(value.toString().replace(/[^\d.-]/g, '')) || 0;
    }

    function formatNumber(value) {
        return new Intl.NumberFormat().format(value);
    }

    function calculateAmount() {
        var quantity = parseFormattedNumber(quantityField.val());
        var unitAmount = parseFormattedNumber(unitAmountField.val());
        var total = quantity * unitAmount;
        
        // Update the amount field with formatted value
        unitAmountField.val(formatNumber(unitAmount.toFixed(2)));
        amountField.val(formatNumber(total.toFixed(2)));
        calculateUnitCost();
    }

    function calculateUnitCost() {
        if (unitOfMeasureField.val()) {
            console.log('Unit of measure field:', unitOfMeasureField.val());
            fetchItemUnitOfMeasure(unitOfMeasureField.val());
        }
    }

    // Listen for both direct input and custom number format events
    quantityField.on('input numberValueChanged', calculateAmount);
    unitAmountField.on('input numberValueChanged', calculateAmount);
    unitOfMeasureField.on('change', calculateUnitCost);

    function updateUnitCost(itemId) {
        if (!itemId) {
            console.log('No item ID provided');
            return;
        }

        var adminUrl = '/admin/items/itemjournal/';
        var apiUrl = adminUrl + 'get_item_cost/' + itemId + '/';

        $.ajax({
            url: apiUrl,
            method: 'GET',
            beforeSend: function () {
                console.log('Making AJAX request to:', apiUrl);
            },
            success: function (data) {
                console.log('Received data:', data);
                if (data.unit_cost !== undefined) {
                    $('#id_unit_cost').val(data.unit_cost);
                    console.log('Updated unit cost to:', data.unit_cost);
                } else {
                    console.log('No unit_cost in response');
                }
            },
            error: function (xhr, status, error) {
                console.error('Error fetching item cost:', error);
                console.error('Status:', status);
                console.error('Response:', xhr.responseText);
            }
        });
    }

    // Check if element exists
    console.log('Item select field exists:', $('#id_item').length > 0);

    // Watch for changes on the item select field
    $('#id_item').on('change', function () {
        var itemId = $(this).val();
        console.log('Item selected:', itemId);
        updateUnitCost(itemId);
        updateUOM(itemId);
    });

    // Log initial value
    console.log('Initial item value:', $('#id_item').val());

    var uomField = $('#id_unit_of_measure');
    
    function updateUOM(itemId) {
        if (!itemId) return;
        
        var adminUrl = '/admin/items/itemjournal/';
        var apiUrl = adminUrl + 'get_item_uom/' + itemId + '/';
        var currentValue = uomField.val();  // Store current selection
        
        $.ajax({
            url: apiUrl,
            type: 'GET',
            success: function(data) {
                uomField.empty();
                
                if (data.success && data.units_of_measure.length > 0) {
                    uomField.append(new Option('--------', ''));
                    
                    data.units_of_measure.forEach(function(uom) {
                        var optionText = `${uom.code} - ${uom.description}`;
                        if (uom.quantity_per_unit > 1) {
                            optionText += ` (${uom.quantity_per_unit} units)`;
                        }
                        
                        var option = new Option(
                            optionText,
                            uom.id,
                            false,  // Not selected by default
                            currentValue == uom.id  // Selected if matches current value
                        );
                        uomField.append(option);
                    });

                    // If no current value but we have a default
                    if (!currentValue) {
                        var defaultUom = data.units_of_measure.find(uom => uom.is_default);
                        if (defaultUom) {
                            uomField.val(defaultUom.id);
                        }
                    } else {
                        // Restore previous selection if it exists in new options
                        uomField.val(currentValue);
                    }
                    
                    uomField.prop('disabled', false);
                    // Trigger change to update unit cost
                    uomField.trigger('change');
                } else {
                    uomField.append(new Option('No units of measure available', ''));
                    uomField.prop('disabled', true);
                }
            },
            error: function(xhr, status, error) {
                console.error('Error fetching UOM:', error);
                uomField.empty();
                uomField.append(new Option('Error loading units of measure', ''));
                uomField.prop('disabled', true);
            }
        });
    }

    function fetchItemUnitOfMeasure(uomId) {
        var adminUrl = '/admin/items/itemjournal/';
        var apiUrl = adminUrl + 'get_item_uom_by_id/' + uomId + '/';
        
        $.ajax({
            url: apiUrl,
            type: 'GET',
            success: function(data) {
                if (data.success) {
                    console.log('Received UOM data:', data);

                    // var quantityPerUnit = data.units_of_measure.quantity_per_unit;

                    
                    var amountValue = parseFormattedNumber(unitAmountField.val());
                    var unitCost = amountValue;
                    
                    // Update the unit cost field with formatted value
                    unitCostField.val(formatNumber(unitCost.toFixed(2)));
                } else {
                    console.error('Error fetching UOM:', data.error);
                }
            },
            error: function(xhr, status, error) {
                console.error('Error fetching UOM:', error);
            }
        });
    }

    // Initialize the UOM updates
    $(document).ready(function() {
        // Update UOM when item changes
        $('#id_item').on('change', function() {
            updateUOM($(this).val());
        });

        // Initial load if item is already selected
        if ($('#id_item').val()) {
            updateUOM($('#id_item').val());
        }
    });

    // Calculate initial amount if values exist
    calculateAmount();
    // Calculate initial unit cost if values exist
    calculateUnitCost();

    // Add this to your form submit handler
    $('form').on('submit', function(e) {
        // Ensure values are calculated one last time before submit
        calculateAmount();
        
        // Remove any formatting from all numeric fields
        $('.numeric-input').each(function() {
            var $field = $(this);
            var rawValue = parseFormattedNumber($field.val());
            console.log('Raw value:', rawValue);
            $field.val(rawValue);
        });
    });
}












// /**
//  * ItemJournal Module
//  * Handles the dynamic updating of unit costs in the Django admin interface.
//  */
// const ItemJournal = (function() {
//     'use strict';

//     /**
//      * Configuration object for the module
//      */
//     const config = {
//         selectors: {
//             itemField: '#id_item',
//             unitCostField: '#id_unit_cost'
//         },
//         endpoints: {
//             getItemCost: (baseUrl, itemId) => `${baseUrl}/api/item/${itemId}/cost/`
//         }
//     };

//     /**
//      * Constructs the API URL based on the current admin page
//      * @returns {string} The base URL for API requests
//      */
//     function getBaseUrl() {
//         const currentPath = window.location.pathname;
//         return currentPath.replace(/\/add\/?$/, '').replace(/\/change\/?$/, '');
//     }

//     /**
//      * Updates the unit cost field with the value from the server
//      * @param {string} itemId - The ID of the selected item
//      */
//     function updateUnitCost(itemId) {
//         if (!itemId) {
//             console.debug('No item ID provided');
//             return;
//         }

//         const baseUrl = getBaseUrl();
//         const apiUrl = config.endpoints.getItemCost(baseUrl, itemId);

//         django.jQuery.ajax({
//             url: apiUrl,
//             method: 'GET',
//             beforeSend: () => {
//                 console.debug('Fetching cost for item:', itemId);
//             },
//             success: (response) => {
//                 if (response.unit_cost !== undefined) {
//                     django.jQuery(config.selectors.unitCostField).val(response.unit_cost);
//                     console.debug('Updated unit cost to:', response.unit_cost);
//                 } else {
//                     console.warn('No unit_cost in response');
//                 }
//             },
//             error: (xhr, status, error) => {
//                 console.error('Failed to fetch item cost:', {
//                     status: status,
//                     error: error,
//                     response: xhr.responseText
//                 });
//             }
//         });
//     }

//     /**
//      * Initializes the event listeners
//      */
//     function initializeEventListeners() {
//         const $itemField = django.jQuery(config.selectors.itemField);

//         if (!$itemField.length) {
//             console.warn('Item field not found in the DOM');
//             return;
//         }

//         $itemField.on('change', function() {
//             const itemId = django.jQuery(this).val();
//             if (itemId) {
//                 updateUnitCost(itemId);
//             }
//         });

//         // Handle initial value if present
//         const initialItemId = $itemField.val();
//         if (initialItemId) {
//             updateUnitCost(initialItemId);
//         }
//     }

//     /**
//      * Initialize the module
//      */
//     function init() {
//         console.debug('Initializing ItemJournal module');
        
//         if (!window.django || !window.django.jQuery) {
//             console.error('Django jQuery is not available');
//             return;
//         }

//         initializeEventListeners();
//     }

//     // Wait for DOM to be fully loaded
//     document.addEventListener('DOMContentLoaded', function() {
//         // Ensure Django's jQuery is available before initialization
//         const checkJquery = setInterval(function() {
//             if (window.django && window.django.jQuery) {
//                 clearInterval(checkJquery);
//                 init();
//             }
//         }, 100);
//     });

//     // Public API
//     return {
//         init: init,
//         updateUnitCost: updateUnitCost
//     };
// })();