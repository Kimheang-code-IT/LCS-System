"""Apply and audit record status changes.

The endpoints in :mod:`app.modules.master_data.status_router` are the only place a status is
written outside a collection's own workflow endpoint. Everything this module
does is therefore small and boring on purpose: resolve the policy, prove the
transition is legal and permitted, call the collection's existing service to
write it, and leave one audit event behind with the previous and the new status.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.exceptions import AccessDenied, Conflict, InvalidState, NotFound, ValidationFailed
from app.modules.audit.service import write_audit
from app.modules.master_data import service as master_data
from app.modules.master_data.models import ModuleRecord
from app.modules.master_data.repository import MasterDataRepository
from app.modules.master_data.status_policy import STATUS_POLICIES, StatusPolicy, StatusTransition

_LoadResult = tuple[Any, str]


def _normalize(value: Any) -> str:
    return str(value or "").strip().upper()


def may_perform(context: RequestContext, transition: StatusTransition) -> bool:
    return not transition.permissions or any(
        context.has_permission(code) for code in transition.permissions
    )


def policy_for(collection: str) -> StatusPolicy:
    policy = STATUS_POLICIES.get(collection)
    if policy is None:
        raise NotFound(f"No status policy is defined for '{collection}'.")
    return policy


def serialize_policy(collection: str, policy: StatusPolicy, context: RequestContext) -> dict:
    """Only the transitions this caller may actually perform are returned."""
    transitions: dict[str, list[dict[str, Any]]] = {}
    for status, items in policy.transitions.items():
        allowed = [item for item in items if may_perform(context, item)]
        if allowed:
            transitions[status] = [
                {
                    "to": item.to,
                    "action": item.action,
                    "kind": item.kind,
                    "confirm": item.confirm,
                    "reason": item.reason,
                }
                for item in allowed
            ]
    return {
        "collection": collection,
        "statuses": list(policy.statuses),
        "transitions": transitions,
    }


def _record_id(value: str) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        raise NotFound() from None


# --------------------------------------------------------------------------
# Loading the current status
# --------------------------------------------------------------------------

async def _load_reference(session: AsyncSession, collection: str, record_id: int) -> _LoadResult:
    spec = master_data.get_spec(collection)
    model = await MasterDataRepository(session).reference(spec.model, record_id)
    if model is None:
        raise NotFound()
    return model, str(getattr(model, spec.status_field, "") or "")


async def _load_generic(session: AsyncSession, collection: str, record_id: int) -> _LoadResult:
    row: ModuleRecord | None = await MasterDataRepository(session).generic(collection, record_id)
    if row is None:
        raise NotFound()
    return row, str(row.status or "")


async def _load_account(session: AsyncSession, collection: str, record_id: int) -> _LoadResult:
    from app.modules.finance.models import ChartOfAccount

    account = await session.get(ChartOfAccount, record_id)
    if account is None:
        raise NotFound("Account not found.")
    return account, account.status


async def _load_financial_account(session: AsyncSession, collection: str, record_id: int) -> _LoadResult:
    from app.modules.finance.models import FinancialAccount

    account = await session.get(FinancialAccount, record_id)
    if account is None:
        raise NotFound("Financial account not found.")
    return account, account.status


async def _load_posting_rule(session: AsyncSession, collection: str, record_id: int) -> _LoadResult:
    from app.modules.finance.models import PostingRule

    rule = await session.get(PostingRule, record_id)
    if rule is None:
        raise NotFound("Posting rule not found.")
    return rule, rule.status


async def _load_sequence(session: AsyncSession, collection: str, record_id: int) -> _LoadResult:
    from app.modules.finance.models import DocumentSequence

    sequence = await session.get(DocumentSequence, record_id)
    if sequence is None:
        raise NotFound("Document sequence not found.")
    return sequence, sequence.status


async def _load_period(session: AsyncSession, collection: str, record_id: int) -> _LoadResult:
    from app.modules.finance.models import AccountingPeriod

    period = await session.get(AccountingPeriod, record_id)
    if period is None:
        raise NotFound("Accounting period not found.")
    return period, period.status


async def _load_order(session: AsyncSession, collection: str, record_id: int) -> _LoadResult:
    from app.modules.operations.repository import OperationsRepository

    order = await OperationsRepository(session).resolve_order(record_id)
    if order is None:
        raise NotFound("Service order not found.")
    return order, order.status


async def _load_charge(session: AsyncSession, collection: str, record_id: int) -> _LoadResult:
    from app.modules.operations.models import ServiceOrderCharge

    charge = await session.get(ServiceOrderCharge, record_id)
    if charge is None:
        raise NotFound("Service charge not found.")
    return charge, charge.status


async def _load_document(session: AsyncSession, collection: str, record_id: int) -> _LoadResult:
    from app.modules.finance.models import FinancialDocument

    document = await session.get(FinancialDocument, record_id)
    if document is None:
        raise NotFound("Financial document not found.")
    return document, document.status


async def _load_journal(session: AsyncSession, collection: str, record_id: int) -> _LoadResult:
    from app.modules.finance.models import JournalEntry

    entry = await session.get(JournalEntry, record_id)
    if entry is None:
        raise NotFound("Journal not found.")
    return entry, entry.status


async def _load_quotation(session: AsyncSession, collection: str, record_id: int) -> _LoadResult:
    from app.modules.quotations.models import QuotationRevision

    revision = await session.get(QuotationRevision, record_id)
    if revision is None:
        raise NotFound("Quotation revision not found.")
    return revision, revision.status


async def _load_user(session: AsyncSession, collection: str, record_id: int) -> _LoadResult:
    from app.modules.auth.models import User

    user = await session.get(User, record_id)
    if user is None:
        raise NotFound("User not found.")
    return user, user.status


async def _load_role(session: AsyncSession, collection: str, record_id: int) -> _LoadResult:
    from app.modules.auth.models import Role

    role = await session.get(Role, record_id)
    if role is None:
        raise NotFound("Role not found.")
    return role, role.status


_LOADERS: dict[str, Callable[[AsyncSession, str, int], Any]] = {
    "reference": _load_reference,
    "generic": _load_generic,
    "account": _load_account,
    "financial_account": _load_financial_account,
    "posting_rule": _load_posting_rule,
    "sequence": _load_sequence,
    "period": _load_period,
    "order": _load_order,
    "charge": _load_charge,
    "document": _load_document,
    "journal": _load_journal,
    "quotation": _load_quotation,
    "user": _load_user,
    "role": _load_role,
}


# --------------------------------------------------------------------------
# Applying a plain status transition
# --------------------------------------------------------------------------

async def _apply_reference(
    session: AsyncSession, context: RequestContext, collection: str, record_id: int, target: str
) -> dict:
    return await master_data.update_reference(session, collection, record_id, {"status": target})


async def _apply_generic(
    session: AsyncSession, context: RequestContext, collection: str, record_id: int, target: str
) -> dict:
    return await master_data.update_generic(session, context, collection, record_id, {"status": target})


async def _apply_account(
    session: AsyncSession, context: RequestContext, collection: str, record_id: int, target: str
) -> dict:
    from app.modules.finance import service as finance

    return await finance.update_account(session, context, record_id, {"status": target})


async def _apply_financial_account(
    session: AsyncSession, context: RequestContext, collection: str, record_id: int, target: str
) -> dict:
    from app.modules.finance import service as finance

    return await finance.update_financial_account(session, context, record_id, {"status": target})


async def _apply_posting_rule(
    session: AsyncSession, context: RequestContext, collection: str, record_id: int, target: str
) -> dict:
    from app.modules.finance import service as finance

    return await finance.update_posting_rule(session, context, record_id, {"status": target})


async def _apply_sequence(
    session: AsyncSession, context: RequestContext, collection: str, record_id: int, target: str
) -> dict:
    from app.modules.finance import service as finance

    sequence = await session.get(finance.DocumentSequence, record_id)
    if sequence is None:
        raise NotFound("Document sequence not found.")
    sequence.status = target
    await session.commit()
    return finance.sequence_payload(sequence)


async def _apply_period(
    session: AsyncSession, context: RequestContext, collection: str, record_id: int, target: str
) -> dict:
    from app.modules.finance import service as finance

    if _normalize(target) == "OPEN":
        # Reopening always stores OPEN and clears the closure stamp, so the
        # period reads the same way to posting, reporting and the list.
        return await finance.reopen_period(session, context, record_id)
    raise InvalidState("A period is closed through the close action.")


async def _apply_order(
    session: AsyncSession, context: RequestContext, collection: str, record_id: int, target: str
) -> dict:
    from app.modules.operations import service as operations

    return await operations.set_service_order_status(session, record_id, target)


async def _apply_user(
    session: AsyncSession, context: RequestContext, collection: str, record_id: int, target: str
) -> dict:
    from app.modules.auth import service as auth

    user = await auth.update_user(session, record_id, {"status": target}, context)
    return await auth.user_payload(session, user)


async def _apply_role(
    session: AsyncSession, context: RequestContext, collection: str, record_id: int, target: str
) -> dict:
    from app.modules.auth import service as auth

    role = await auth.update_role(session, record_id, {"status": target}, context)
    return await auth.role_payload(session, role)


_APPLIERS: dict[str, Callable[[AsyncSession, RequestContext, str, int, str], Any]] = {
    "reference": _apply_reference,
    "generic": _apply_generic,
    "account": _apply_account,
    "financial_account": _apply_financial_account,
    "posting_rule": _apply_posting_rule,
    "sequence": _apply_sequence,
    "period": _apply_period,
    "order": _apply_order,
    "user": _apply_user,
    "role": _apply_role,
}


async def _denied(session: AsyncSession, context: RequestContext, transition: StatusTransition) -> None:
    """Record the refusal, exactly like ``require_permission`` does."""
    code = ",".join(transition.permissions)
    await write_audit(
        session,
        context,
        event_type="AUTHORIZATION_DENIED",
        entity_type="permission",
        entity_id=0,
        action=code,
        result="REJECTED",
        reason=f"Missing permission: {code}",
    )
    await session.commit()
    raise AccessDenied(f"Missing permission: {code}")


async def change_status(
    session: AsyncSession,
    context: RequestContext,
    collection: str,
    item_id: str,
    target: str,
    reason: str | None = None,
) -> dict:
    """Move one record to ``target`` if the policy, the permission and the
    record's own business rules allow it, and leave an audit event behind."""
    policy = policy_for(collection)
    canonical = policy.canonical(target)
    if canonical is None:
        raise ValidationFailed(
            f"Unknown status '{target}'.",
            {"status": f"Allowed values: {', '.join(policy.statuses)}."},
        )
    record_id = _record_id(item_id)
    loader = _LOADERS.get(policy.store)
    if loader is None:
        raise NotFound(f"'{collection}' does not support direct status changes.")
    record, current = await loader(session, collection, record_id)

    changed = _normalize(current) != _normalize(canonical)
    transition: StatusTransition | None = None
    if changed:
        transition = policy.transition(current, canonical)
        if transition is None:
            raise InvalidState(f"Cannot change status from {current or 'unknown'} to {canonical}.")
        if not may_perform(context, transition):
            await _denied(session, context, transition)
        if transition.kind != "status":
            raise Conflict(
                "TRANSITION_REQUIRES_COMMAND",
                f"'{canonical}' is applied by the {transition.action} action, not by a direct status change.",
            )
        if transition.reason and not str(reason or "").strip():
            raise ValidationFailed("A reason is required.", {"reason": "Enter a reason."})

    applier = _APPLIERS.get(policy.store)
    if applier is None:
        raise NotFound(f"'{collection}' does not support direct status changes.")
    payload = await applier(session, context, collection, record_id, canonical)

    if changed and transition is not None:
        await write_audit(
            session,
            context,
            event_type=transition.event_type,
            entity_type=policy.entity_type,
            entity_id=record_id,
            action=transition.action,
            before={"status": current},
            after={"status": canonical},
            reason=str(reason).strip() or None if reason else None,
        )
        await session.commit()
    return payload
