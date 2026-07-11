(function($) {
    'use strict';
    
    function toggleBankAccountField() {
        var paymentMethod = $('#id_payment_method').val();
        var bankAccountRow = $('.form-row.field-bank_account');
        
        if (paymentMethod === 'Bank/Mobile Money') {
            bankAccountRow.show();
            $('#id_bank_account').prop('required', true);
        } else {
            bankAccountRow.hide();
            $('#id_bank_account').val('').prop('required', false);
        }
    }
    
    $(document).ready(function() {
        // Initial state
        toggleBankAccountField();
        
        // Watch for changes
        $('#id_payment_method').on('change', toggleBankAccountField);
    });
})(django.jQuery);

