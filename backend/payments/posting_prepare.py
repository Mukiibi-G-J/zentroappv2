"""Prepare PaymentJournal headers from lines + payment method before preview/post."""

from django.contrib.contenttypes.models import ContentType

from financials.enums import BalacingAccountType, coerce_balancing_account_type
from payments.enums import AccountType


def _resolve_account_gfk(account_type: str | None, account_no: str | None):
    if not account_type or not account_no:
        return None, None

    model = None
    if account_type == AccountType.VENDOR.value:
        from purchases.models import Vendor
        model = Vendor
    elif account_type == AccountType.CUSTOMER.value:
        from sales.models import Customer
        model = Customer
    elif account_type == AccountType.GL.value:
        from financials.models import G_LAccount
        model = G_LAccount
    else:
        return None, None

    obj = model.objects.filter(no=account_no).first()
    if obj is None:
        raise ValueError(
            f'No matching {model.__name__} record found for account "{account_no}".'
        )

    content_type = ContentType.objects.get_for_model(model)
    pk_name = model._meta.pk.name
    object_id = getattr(obj, pk_name)
    return content_type, object_id


def _bal_account_type_for_journal(payment_method) -> str:
    bal_key = coerce_balancing_account_type(payment_method.bal_account_type)
    if bal_key == BalacingAccountType.Bank_Account.name:
        return AccountType.GL.value
    if bal_key:
        try:
            return BalacingAccountType[bal_key].value or AccountType.GL.value
        except KeyError:
            pass
    return AccountType.GL.value


def apply_payment_method_balancing_account(journal) -> bool:
    """Copy balancing account from Payment Method (BC-style)."""
    payment_method = journal.payment_method
    if payment_method is None:
        return False

    changed = False
    bal_key = coerce_balancing_account_type(payment_method.bal_account_type)

    if bal_key == BalacingAccountType.Bank_Account.name and payment_method.bal_bank_account_no:
        from bank_account.models import BankAccount

        bank = payment_method.bal_bank_account_no
        content_type = ContentType.objects.get_for_model(BankAccount)
        if (
            journal.bal_account_content_type_id != content_type.id
            or journal.bal_account_object_id != bank.pk
        ):
            journal.bal_account_type = _bal_account_type_for_journal(payment_method)
            journal.bal_account_content_type = content_type
            journal.bal_account_object_id = bank.pk
            changed = True
    elif payment_method.bal_account_no:
        gl_account = payment_method.bal_account_no
        content_type = ContentType.objects.get_for_model(gl_account.__class__)
        object_id = gl_account.no
        if (
            journal.bal_account_content_type_id != content_type.id
            or journal.bal_account_object_id != object_id
        ):
            journal.bal_account_type = _bal_account_type_for_journal(payment_method)
            journal.bal_account_content_type = content_type
            journal.bal_account_object_id = object_id
            changed = True
    elif not journal.bal_account_type:
        journal.bal_account_type = _bal_account_type_for_journal(payment_method)
        changed = True

    return changed


def sync_payment_journal_from_lines(journal) -> bool:
    """Copy the first line's account onto the header for legacy posting processors."""
    line = journal.lines.order_by('line_no').first()
    if line is None:
        return False

    changed = False

    if line.account_type and line.account_type != journal.account_type:
        journal.account_type = line.account_type
        changed = True

    if line.account_no:
        content_type, object_id = _resolve_account_gfk(line.account_type, line.account_no)
        if (
            journal.account_content_type_id != content_type.id
            or journal.account_object_id != object_id
        ):
            journal.account_content_type = content_type
            journal.account_object_id = object_id
            changed = True

    if line.description and not journal.description:
        journal.description = line.description
        changed = True

    return changed


def prepare_payment_journal_for_posting(journal, *, save: bool = True):
    """
    Ensure header fields required by PaymentJournalProcessor are populated
    from document lines and the selected payment method.
    """
    changed = sync_payment_journal_from_lines(journal)
    changed = apply_payment_method_balancing_account(journal) or changed

    if journal.account_type in (AccountType.VENDOR.value, AccountType.CUSTOMER.value):
        if journal.bal_account_type != AccountType.GL.value:
            journal.bal_account_type = AccountType.GL.value
            changed = True

    if save and changed:
        journal.save()

    if journal.payment_method and not journal.bal_account_type:
        raise ValueError(
            f'Payment method "{journal.payment_method.code}" has no balancing account type configured.'
        )
    if journal.payment_method and not journal.bal_account_no:
        raise ValueError(
            f'Payment method "{journal.payment_method.code}" has no balancing account configured. '
            'Set Bal. Account No. on the payment method card.'
        )

    return journal
