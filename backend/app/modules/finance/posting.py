"""Reusable generation of balanced journals from financial documents.

``post_document`` used to carry the accounting logic inline: which side is the
control account, whether the detail side is per fee line, and whether tax is
split out. That made a new document type a copy-paste of the customer-invoice
branch. Here each document type is a named strategy, and the shared service
turns a resolved document plus its lines into a balanced ``JournalDraft``.

Design constraints this file exists to hold:

* **No account ids in code.** Every account comes from :class:`PostingRuleResolver`.
* **Balanced by construction.** A draft is only produced when debits equal
  credits; the caller never gets a half-built entry to commit.
* **Correct side per document type.** A customer invoice debits the control
  account and credits revenue per fee line; a supplier bill does the mirror; a
  receipt debits cash and credits receivables; a credit note mirrors its
  originating invoice.
* **Decimal only.** Amounts are read from and written back as ``Decimal``.
* **Explainable after the fact.** The draft carries the rule and the accounting
  shape that produced it; ``post_document`` snapshots both onto the journal row,
  so an entry stays traceable once the rule behind it has changed.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from app.core.exceptions import Conflict, ValidationFailed
from app.modules.finance.models import ChartOfAccount
from app.modules.finance.posting_rules import PostingRuleAccounts, PostingRuleResolver


class JournalSide(StrEnum):
    """Which side of the entry the document detail lands on.

    ``CONTROL_DEBIT`` means the control account (receivable, payable, cash) is
    debited and the detail is credited — the shape of a customer invoice.
    ``CONTROL_CREDIT`` is its mirror, the shape of a supplier bill.
    """

    CONTROL_DEBIT = "CONTROL_DEBIT"
    CONTROL_CREDIT = "CONTROL_CREDIT"


@dataclass(frozen=True)
class DocumentLineInput:
    """One source line, already normalised to Decimal."""

    description: str
    amount: Decimal
    tax: Decimal = Decimal("0")
    fee_type_id: int | None = None
    account_id: int | None = None


@dataclass
class DraftLine:
    account: ChartOfAccount
    amount: Decimal
    debit: bool
    description: str = ""


@dataclass
class JournalDraft:
    """A balanced, not-yet-persisted journal."""

    lines: list[DraftLine] = field(default_factory=list)
    total: Decimal = Decimal("0")
    #: Rule that produced the accounts, as a real id so the caller can persist a
    #: joinable link rather than parse it back out of ``resolution``.
    rule_id: int | None = None
    #: Human-readable explanation of the resolution, for the audit trail.
    resolution: dict[str, object] = field(default_factory=dict)

    @property
    def debit_total(self) -> Decimal:
        return sum((line.amount for line in self.lines if line.debit), Decimal("0"))

    @property
    def credit_total(self) -> Decimal:
        return sum((line.amount for line in self.lines if not line.debit), Decimal("0"))

    def add(self, account: ChartOfAccount, amount: Decimal, *, debit: bool, description: str = "") -> None:
        """Append a line, skipping zero amounts so no noise enters the ledger."""
        if amount <= 0:
            return
        self.lines.append(DraftLine(account=account, amount=amount, debit=debit, description=description))

    def assert_balanced(self) -> None:
        if self.debit_total != self.credit_total:
            raise Conflict(
                "JOURNAL_UNBALANCED",
                "The generated journal is not balanced.",
                field_errors={
                    "total": f"Debits {self.debit_total} do not equal credits {self.credit_total}."
                },
            )


@dataclass(frozen=True)
class PostingStrategy:
    """How one document type turns into journal lines."""

    side: JournalSide
    #: Detailed types resolve an account per fee line and split tax out.
    detailed: bool = False
    #: Tax is held on a separate account instead of being netted into the detail.
    splits_tax: bool = False
    description: str = ""


# The accounting meaning of each document type, in one table.
#
# CUSTOMER_INVOICE  Dr receivable (control) / Cr revenue per fee line, tax to the
#                   rule's tax account.
# CREDIT_NOTE       The mirror: Cr receivable / Dr revenue per fee line, tax Dr.
# SUPPLIER_BILL     Dr expense per fee line / Cr payable (control), tax Dr.
# SUPPLIER_CREDIT_NOTE  The mirror of a supplier bill.
# CUSTOMER_RECEIPT  Dr cash / Cr receivable.  SUPPLIER_PAYMENT  Dr payable / Cr cash.
# OTHER_*           Simple two-sided entries; TRANSFER and ADJUSTMENT likewise.
STRATEGIES: dict[str, PostingStrategy] = {
    "CUSTOMER_INVOICE": PostingStrategy(JournalSide.CONTROL_DEBIT, detailed=True, splits_tax=True, description="Receivable control, revenue per fee line"),
    "CREDIT_NOTE": PostingStrategy(JournalSide.CONTROL_CREDIT, detailed=True, splits_tax=True, description="Customer credit note mirroring its invoice"),
    "SUPPLIER_BILL": PostingStrategy(JournalSide.CONTROL_CREDIT, detailed=True, splits_tax=True, description="Payable control, expense per fee line"),
    "SUPPLIER_CREDIT_NOTE": PostingStrategy(JournalSide.CONTROL_DEBIT, detailed=True, splits_tax=True, description="Supplier credit note mirroring its bill"),
    "CUSTOMER_RECEIPT": PostingStrategy(JournalSide.CONTROL_CREDIT, description="Cash received against receivable"),
    "SUPPLIER_PAYMENT": PostingStrategy(JournalSide.CONTROL_CREDIT, description="Cash paid against payable"),
    "OTHER_INCOME": PostingStrategy(JournalSide.CONTROL_DEBIT, description="Other income"),
    "OTHER_EXPENSE": PostingStrategy(JournalSide.CONTROL_CREDIT, description="Other expense"),
    "TRANSFER": PostingStrategy(JournalSide.CONTROL_DEBIT, description="Transfer between own accounts"),
    "ADJUSTMENT": PostingStrategy(JournalSide.CONTROL_CREDIT, description="Adjustment"),
}

# Document types a payment may be allocated against. Credit notes are excluded
# on purpose: an allocation settles an invoice, and letting it settle a credit
# note as well would change what receivables mean without a subledger to show it.
ALLOCATABLE_TYPES = frozenset({"CUSTOMER_INVOICE", "SUPPLIER_BILL"})

DEFAULT_STRATEGY = PostingStrategy(JournalSide.CONTROL_DEBIT, description="Default two-sided entry")


def strategy_for(document_type: str) -> PostingStrategy:
    return STRATEGIES.get(str(document_type).upper(), DEFAULT_STRATEGY)


class AccountingPostingService:
    """Builds a balanced :class:`JournalDraft` for a financial document.

    Stateless apart from the resolver it is handed, so one instance can serve an
    entire request — or an entire batch — without carrying accounting state.
    """

    def __init__(self, resolver: PostingRuleResolver) -> None:
        self._resolver = resolver

    async def build(
        self,
        *,
        document_type: str,
        total: Decimal,
        lines: Sequence[DocumentLineInput] = (),
        description: str = "",
        strategy: PostingStrategy | None = None,
    ) -> JournalDraft:
        """Resolve accounts and return balanced draft lines.

        Raises ``ValidationFailed`` when no control account is configured and
        ``Conflict('JOURNAL_UNBALANCED')`` if the result does not balance, so a
        caller can never commit an unbalanced journal.
        """
        document_type = str(document_type).upper()
        plan = strategy or strategy_for(document_type)
        if total <= 0:
            raise ValidationFailed(
                "Document total must be greater than zero before posting.",
                field_errors={"total": "Enter a total greater than zero."},
            )

        control = await self._resolver.resolve(document_type)
        # Recorded on the draft so a posted entry can be traced back to the rule
        # and the accounting shape that produced it, months later.
        draft = JournalDraft(
            rule_id=control.rule_id,
            resolution={**control.explain(), "strategy": plan.description, "side": str(plan.side)},
        )

        if plan.detailed and lines:
            await self._add_detailed(draft, plan, document_type, total, lines, control, description)
        else:
            self._add_two_sided(draft, control, total, description)

        draft.assert_balanced()
        return draft

    # --- strategies ----------------------------------------------------------
    def _add_two_sided(
        self,
        draft: JournalDraft,
        control: PostingRuleAccounts,
        total: Decimal,
        description: str,
    ) -> None:
        """Simple entry: the rule's debit and credit account for the whole total."""
        draft.add(control.debit, total, debit=True, description=description)
        draft.add(control.credit, total, debit=False, description=description)

    async def _add_detailed(
        self,
        draft: JournalDraft,
        plan: PostingStrategy,
        document_type: str,
        total: Decimal,
        lines: Sequence[DocumentLineInput],
        control: PostingRuleAccounts,
        description: str,
    ) -> None:
        """Control side takes the total; each fee line resolves its own account.

        A line may override the rule with an account chosen on the document
        itself, which is how a user books one-off revenue or expense without a
        dedicated rule. Tax is netted out of the detail amount and posted to the
        rule's tax account so the tax ledger reconciles independently.
        """
        detail_is_credit = plan.side is JournalSide.CONTROL_DEBIT
        draft.add(
            control.debit if detail_is_credit else control.credit,
            total,
            debit=detail_is_credit,
            description=description,
        )

        resolved_any = False
        for line in lines:
            line_description = line.description or description
            amount = line.amount
            if plan.splits_tax and control.tax is not None:
                tax = min(line.tax, amount)
                amount = amount - tax
                if tax > 0:
                    draft.add(
                        control.tax,
                        tax,
                        debit=not detail_is_credit,
                        description=f"Tax: {line_description}",
                    )
            if amount <= 0:
                continue
            account = await self._detail_account(document_type, line)
            draft.add(account, amount, debit=not detail_is_credit, description=line_description)
            resolved_any = True

        if not resolved_any:
            # Detail lines were all zero after tax split; fall back to the rule's
            # own accounts so the entry still balances rather than half-posting.
            draft.add(control.credit, total, debit=False, description=description)

    async def _detail_account(self, document_type: str, line: DocumentLineInput) -> ChartOfAccount:
        """Prefer an account chosen on the line, else the rule for its fee type."""
        if line.account_id is not None:
            account = await self._resolver.account_by_id(line.account_id)
            if account is None:
                raise ValidationFailed(
                    "A document line references an account that no longer exists.",
                    field_errors={"lines": "Remove the line or pick another account."},
                )
            return account
        resolved = await self._resolver.resolve(document_type, line.fee_type_id, label_debit="line", label_credit="line")
        return resolved.credit if line_detail_is_credit(document_type) else resolved.debit

    async def detail_account_code(self, document_type: str, line: DocumentLineInput) -> str | None:
        """The account code a detail line posts to, or None when none resolves.

        Read-only explainer for the document form: it runs the same resolution
        ``_detail_account`` runs at posting time, so the account an operator sees on
        a line is the account the journal will use. A missing or ambiguous posting
        rule is not an error here — the line simply shows no account yet.
        """
        try:
            return (await self._detail_account(document_type, line)).account_code
        except (ValidationFailed, Conflict):
            return None


def line_detail_is_credit(document_type: str) -> bool:
    """Whether a document's detail lines are credited (revenue) or debited (cost)."""
    return strategy_for(document_type).side is JournalSide.CONTROL_DEBIT