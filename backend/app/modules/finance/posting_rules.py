"""Reusable resolution of posting accounts from the ``posting_rules`` table.

The resolver answers one question — *for this document type and fee type, which
accounts does this journal touch?* — and answers it in the only order that is
defensible:

1. the most specific active rule (``document_type`` **and** ``fee_type_id``),
2. then the document default (``fee_type_id IS NULL``),

each tier ordered by ``priority DESC``. Two rules sharing the top priority of a
tier are an ``AMBIGUOUS_POSTING_RULE`` conflict, never an arbitrary winner: the
database already forbids that state for writes that go through the service, so
the check here is the second line of defence for a row inserted by other means
(an import, a hand-written migration, a database restored without the index). A
silent wrong-account posting is far worse than a loud refusal.

Nothing here knows about document totals or journal lines: that is
``AccountingPostingService`` in ``posting.py``. Keeping the two apart is what
lets a new document type reuse account resolution without inheriting the
customer-invoice line logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict, ValidationFailed
from app.modules.finance.models import ChartOfAccount, PostingRule

POSTING_RULE_ACTIVE = "ACTIVE"

#: Audit entity and event names for posting-rule changes. Declared next to the
#: rest of the posting-rule domain so the writer (the router) and the readers
#: (the history queries) cannot drift apart.
POSTING_RULE_ENTITY = "posting_rule"
POSTING_RULE_CREATED = "POSTING_RULE_CREATED"
POSTING_RULE_UPDATED = "POSTING_RULE_UPDATED"
POSTING_RULE_DELETED = "POSTING_RULE_DELETED"

# Fetch one extra row so a priority tie is detected from the data we already have
# instead of a second round trip.
_TIER_LIMIT = 2


class RuleSource(StrEnum):
    """Where a resolved account came from. Recorded so a posting is explainable."""

    EXACT = "EXACT"
    DOCUMENT_DEFAULT = "DOCUMENT_DEFAULT"
    LEGACY_DEFAULT = "LEGACY_DEFAULT"


@dataclass(frozen=True)
class PostingRuleAccounts:
    """Accounts resolved for one document scope."""

    debit: ChartOfAccount
    credit: ChartOfAccount
    tax: ChartOfAccount | None
    source: RuleSource
    rule_id: int | None
    priority: int | None

    def explain(self) -> dict[str, Any]:
        """Audit-friendly summary; contains codes, never raw database ids."""
        return {
            "ruleId": str(self.rule_id) if self.rule_id else None,
            "source": str(self.source),
            "priority": self.priority,
            "debitAccount": self.debit.account_code,
            "creditAccount": self.credit.account_code,
            "taxAccount": self.tax.account_code if self.tax else None,
        }


def validate_postable(account: ChartOfAccount | None, label: str, field: str | None = None) -> ChartOfAccount:
    """Guard used both when a rule is configured and when one is used.

    Catching a non-postable or inactive account at configuration time is what
    stops it from surfacing as a failed posting at 2am.
    """
    errors: dict[str, str] = {}
    if account is None:
        message = f"No {label} posting account could be resolved."
        if field:
            errors[field] = f"Select an active, postable {label} account."
        raise ValidationFailed(message, field_errors=errors or None)
    if not account.is_postable:
        message = f"The {label} account {account.account_code} is not postable."
        if field:
            errors[field] = f"{account.account_code} is a header account and cannot receive postings."
        raise ValidationFailed(message, field_errors=errors or None)
    if account.status != POSTING_RULE_ACTIVE:
        message = f"The {label} account {account.account_code} must be active."
        if field:
            errors[field] = f"{account.account_code} is inactive."
        raise ValidationFailed(message, field_errors=errors or None)
    return account


class PostingRuleResolver:
    """Selects the rule that applies to a document type and fee type.

    Reusable by every posting path: document posting, manual journals that
    mirror an automated entry, and any future automation. Stateless apart from
    the session, so one instance per request is enough.
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        legacy_defaults: dict[str, tuple[str, str]] | None = None,
    ) -> None:
        """
        ``legacy_defaults`` is the last-resort account-code map used only when no
        rule is configured at all. It exists so an install that has not yet
        configured rules keeps posting the way it always did; a resolved rule
        always wins, and the caller is told which path was taken via
        :attr:`PostingRuleAccounts.source`.
        """
        self._session = session
        self._legacy_defaults = legacy_defaults or {}
        self._accounts: dict[int, ChartOfAccount] = {}

    # --- public API ----------------------------------------------------------
    async def resolve(
        self,
        document_type: str,
        fee_type_id: int | None = None,
        *,
        label_debit: str = "debit",
        label_credit: str = "credit",
        label_tax: str = "tax",
    ) -> PostingRuleAccounts:
        """Resolve the accounts for a document scope, validating them as postable."""
        rule = await self._select_rule(document_type, fee_type_id)
        if rule is None:
            return await self._legacy_accounts(document_type, label_debit, label_credit, label_tax)

        debit = validate_postable(await self._account(rule.debit_account_id), label_debit)
        credit = validate_postable(await self._account(rule.credit_account_id), label_credit)
        tax = (
            validate_postable(await self._account(rule.tax_account_id), label_tax)
            if rule.tax_account_id
            else None
        )
        return PostingRuleAccounts(
            debit=debit,
            credit=credit,
            tax=tax,
            source=RuleSource.EXACT if rule.fee_type_id is not None else RuleSource.DOCUMENT_DEFAULT,
            rule_id=rule.id,
            priority=rule.priority,
        )

    async def _select_rule(self, document_type: str, fee_type_id: int | None) -> PostingRule | None:
        """Exact scope first, then the document default."""
        if fee_type_id is not None:
            exact = await self._tier(document_type, fee_type_id)
            if exact is not None:
                return exact
        return await self._tier(document_type, None)

    async def _tier(self, document_type: str, fee_type_id: int | None) -> PostingRule | None:
        fee_filter = (
            PostingRule.fee_type_id == fee_type_id
            if fee_type_id is not None
            else PostingRule.fee_type_id.is_(None)
        )
        matches = list(
            (
                await self._session.execute(
                    select(PostingRule)
                    .where(
                        PostingRule.document_type == document_type,
                        fee_filter,
                        PostingRule.status == POSTING_RULE_ACTIVE,
                    )
                    .order_by(PostingRule.priority.desc(), PostingRule.id)
                    .limit(_TIER_LIMIT)
                )
            ).scalars().all()
        )
        if not matches:
            return None
        top = matches[0]
        if any(rule.priority == top.priority for rule in matches[1:]):
            raise Conflict(
                "AMBIGUOUS_POSTING_RULE",
                f"More than one active posting rule with priority {top.priority} matches {document_type}.",
                field_errors={
                    "feeTypeId" if fee_type_id is not None else "documentType": (
                        "Two active rules share the same priority."
                    )
                },
            )
        return top

    async def _account(self, account_id: int) -> ChartOfAccount | None:
        """One-statement account cache; a posting resolves only a handful."""
        if account_id not in self._accounts:
            account = await self._session.get(ChartOfAccount, account_id)
            if account is None:
                return None
            self._accounts[account_id] = account
        return self._accounts[account_id]

    async def account_by_code(self, code: str) -> ChartOfAccount | None:
        account = (
            await self._session.execute(select(ChartOfAccount).where(ChartOfAccount.account_code == code))
        ).scalars().first()
        if account is not None:
            self._accounts[account.id] = account
        return account

    async def account_by_id(self, account_id: int) -> ChartOfAccount | None:
        return await self._account(account_id)

    async def _legacy_accounts(
        self,
        document_type: str,
        label_debit: str,
        label_credit: str,
        label_tax: str,
    ) -> PostingRuleAccounts:
        """Last-resort path for installs with no rules configured yet."""
        codes = self._legacy_defaults.get(document_type)
        if codes is None:
            raise ValidationFailed(
                f"No posting rule is configured for {document_type}.",
                field_errors={"documentType": "Configure a posting rule for this document type before posting."},
            )
        debit = validate_postable(await self.account_by_code(codes[0]), label_debit)
        credit = validate_postable(await self.account_by_code(codes[1]), label_credit)
        return PostingRuleAccounts(
            debit=debit,
            credit=credit,
            tax=None,
            source=RuleSource.LEGACY_DEFAULT,
            rule_id=None,
            priority=None,
        )