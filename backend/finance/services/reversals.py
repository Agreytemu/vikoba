"""Reversal orchestration at the application level.

The engine's ``reverse_transaction`` keeps the ledger balanced. Beyond the
journal, reversing a savings-linked transaction must also bring the cached
``SavingsAccount.balance`` back in line with the ledger (the authoritative
truth) inside the same database transaction.
"""
from django.db import transaction

from finance.services.engine import FinancialError, reverse_transaction


def reverse_financial_transaction(*, fin_tx, reason, actor=None, audit_ip=None):
    """Reverse a financial transaction and sync any linked cached balances."""
    with transaction.atomic():
        reversal = reverse_transaction(
            fin_tx,
            reason=reason,
            initiated_by=actor,
            audit_ip=audit_ip,
        )

        linked_savings = fin_tx.savings_transaction_id
        if linked_savings:
            from accounts.models import SavingsAccount

            savings = SavingsAccount.objects.select_for_update().get(pk=fin_tx.savings_transaction.account_id)
            from finance.services.balances import savings_account_balance

            savings.balance = savings_account_balance(savings)
            savings.save(update_fields=["balance"])

        return reversal