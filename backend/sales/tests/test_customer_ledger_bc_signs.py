"""BC remaining-amount sign conventions for customer ledger detailed entries."""

from django.test import SimpleTestCase


class CustomerLedgerBcSignConventionTests(SimpleTestCase):
    """
    Remaining Amount = Sum(Detailed.amount), matching Business Central:

      Invoice Initial +A, Invoice Application -A → remaining 0
      Payment Initial -A, Payment Application +A → remaining 0
    """

    def test_fully_applied_invoice_and_payment_net_to_zero(self):
        amount = 90000
        invoice_detailed = [amount, -amount]  # Initial, Application
        payment_detailed = [-amount, amount]  # Initial, Application
        self.assertEqual(sum(invoice_detailed), 0)
        self.assertEqual(sum(payment_detailed), 0)

    def test_legacy_inverted_invoice_initial_double_counts(self):
        amount = 90000
        # Bug: Invoice Initial was posted negative; Application also negative.
        legacy_invoice_detailed = [-amount, -amount]
        self.assertEqual(sum(legacy_invoice_detailed), -2 * amount)
        # Repair: flip Initial only.
        repaired = [amount, -amount]
        self.assertEqual(sum(repaired), 0)
