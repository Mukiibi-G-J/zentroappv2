(function($) {
    'use strict';
    
    function toggleBankAccountField() {
        var repaymentAccount = $('#id_repayment_account').val();
        var bankAccountRow = $('.form-row.field-bank_account');
        
        if (repaymentAccount === 'Bank/Mobile Money') {
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
        $('#id_repayment_account').on('change', toggleBankAccountField);
    });
})(django.jQuery);

