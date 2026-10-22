"""Record status policy — the single source of truth for status transitions.

For every collection that owns a lifecycle ``status`` this table answers three
questions:

* which statuses the collection can hold,
* which transitions are legal from each status, and
* who may perform one, and how it is applied.

``kind == "status"`` means the shared status endpoint applies the change: it is
a plain, audited status write (activate / deactivate / mark / reopen). ``kind ==
"command"`` means the change belongs to the collection's own workflow endpoint
(posting a document, reversing it, issuing a charge, closing a period, sending a
quotation …) and this module refuses to bypass that engine — the frontend keeps
calling the dedicated endpoint for those, which is what keeps the accounting
logic in one place.

The table is code-defined on purpose (see ``docs/05_solution_architecture.md``
Appendix B): a configuration
mistake must not be able to weaken a workflow or an authorization rule.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Accepted permission codes per area. A transition passes when the caller holds
#: at least one of them; platform administrators bypass the check entirely.
REFERENCE_WRITE = ("master.reference.manage", "configuration.manage")
PARTY_ROLE_WRITE = ("master.party_roles.update", "master.reference.manage")
ACCOUNT_WRITE = ("chart_of_accounts.manage",)
POSTING_RULE_WRITE = ("posting_rule.manage",)
SEQUENCE_WRITE = ("configuration.manage",)
PERIOD_WRITE = ("accounting_period.close",)
ORDER_WRITE = ("service_order.update",)
CHARGE_WRITE = ("service_charge.issue",)
DOCUMENT_POST = ("financial_document.post",)
DOCUMENT_REVERSE = ("financial_document.reverse",)
JOURNAL_POST = ("journal_entry.post",)
QUOTATION_SEND = ("quotation.send",)
QUOTATION_ACCEPT = ("quotation.accept",)
QUOTATION_CONVERT = ("quotation.convert",)
QUOTATION_EDIT = ("quotation.update_draft",)
USER_WRITE = ("user.manage",)
ROLE_WRITE = ("role.manage",)


@dataclass(frozen=True)
class StatusTransition:
    """One legal status change."""

    to: str
    action: str
    permissions: tuple[str, ...] = ()
    #: "status" (shared endpoint) or "command" (own workflow endpoint).
    kind: str = "status"
    #: The frontend asks for confirmation before running it.
    confirm: bool = False
    #: A reason is required (reversal).
    reason: bool = False
    #: Audit event written for a "status" transition.
    event_type: str = "STATUS_CHANGED"


@dataclass(frozen=True)
class StatusPolicy:
    entity_type: str
    #: Which adapter applies a "status" transition (see ``service._APPLIERS``).
    store: str
    statuses: tuple[str, ...]
    #: Normalised current status (upper case) -> legal transitions.
    transitions: dict[str, tuple[StatusTransition, ...]]

    def transition(self, from_status: str, to_status: str) -> StatusTransition | None:
        wanted = str(to_status or "").strip().upper()
        for item in self.transitions.get(_normalize(from_status), ()):
            if _normalize(item.to) == wanted:
                return item
        return None

    def canonical(self, value: str) -> str | None:
        """The stored spelling of a caller-supplied status, or ``None``."""
        wanted = _normalize(value)
        for status in self.statuses:
            if _normalize(status) == wanted:
                return status
        return None


def _normalize(value: str | None) -> str:
    return str(value or "").strip().upper()


def _toggle_transitions(
    values: tuple[str, str] = ("ACTIVE", "INACTIVE"),
    permissions: tuple[str, ...] = REFERENCE_WRITE,
) -> dict[str, tuple[StatusTransition, ...]]:
    """The Activate <-> Deactivate pair every reference-like record shares."""
    active, inactive = values
    return {
        _normalize(active): (StatusTransition(to=inactive, action="deactivate", permissions=permissions),),
        _normalize(inactive): (StatusTransition(to=active, action="activate", permissions=permissions),),
    }


def _vocabulary_transitions(
    values: tuple[str, ...],
    permissions: tuple[str, ...] = REFERENCE_WRITE,
) -> dict[str, tuple[StatusTransition, ...]]:
    """Every other value of a fixed vocabulary, for progress-style statuses.

    Shipments, customs declarations, document checklists and deliveries carry a
    vocabulary rather than a state machine: the operator records where the item
    is now, and any other declared value is a legal next step.
    """
    transitions: dict[str, tuple[StatusTransition, ...]] = {}
    for value in values:
        transitions[_normalize(value)] = tuple(
            StatusTransition(to=other, action="mark", permissions=permissions)
            for other in values
            if _normalize(other) != _normalize(value)
        )
    return transitions


_REFERENCE_COLLECTIONS = (
    "businessParties",
    "placeRoles",
    "tradeDirections",
    "containerTypes",
    "transportTypes",
    "transportAssets",
    "feeTypes",
    "currencies",
)

_ACTIVE_STATUSES = ("ACTIVE", "INACTIVE")

#: Progress vocabularies for the generic reference store. The spellings match
#: the option lists the forms used before status moved to the row menu, so the
#: stored values do not change.
_GENERIC_VOCABULARIES: dict[str, tuple[str, ...]] = {
    "companies": ("Active", "Inactive"),
    "shipments": ("Scheduled", "Registered", "In Transit", "Arrived", "Completed"),
    "customs": ("Preparing", "Submitted", "Processing", "On Hold", "Cleared"),
    "documents": ("Required", "Missing", "Uploaded", "Approved"),
    "deliveries": ("Scheduled", "Arriving", "Unloading", "Delivered", "POD Received"),
    "customerPayments": ("Unpaid", "Partial", "Paid", "Overdue"),
    "supplierCosts": ("Unpaid", "Partial", "Paid", "Overdue"),
    "supplierPayments": ("Unpaid", "Partial", "Paid", "Overdue"),
}

_QUOTATION_TRANSITIONS: dict[str, tuple[StatusTransition, ...]] = {
    "DRAFT": (
        StatusTransition(to="SENT", action="send", permissions=QUOTATION_SEND, kind="command", confirm=True),
        StatusTransition(to="REJECTED", action="reject", permissions=QUOTATION_ACCEPT, kind="command", confirm=True),
        StatusTransition(to="CANCELLED", action="cancel", permissions=QUOTATION_EDIT, kind="command", confirm=True),
    ),
    "SENT": (
        StatusTransition(to="ACCEPTED", action="accept", permissions=QUOTATION_ACCEPT, kind="command", confirm=True),
        StatusTransition(to="REJECTED", action="reject", permissions=QUOTATION_ACCEPT, kind="command", confirm=True),
        StatusTransition(to="CANCELLED", action="cancel", permissions=QUOTATION_EDIT, kind="command", confirm=True),
    ),
    "ACCEPTED": (
        StatusTransition(to="CONVERTED", action="convert", permissions=QUOTATION_CONVERT, kind="command", confirm=True),
    ),
}

_PERIOD_TRANSITIONS: dict[str, tuple[StatusTransition, ...]] = {
    "OPEN": (
        StatusTransition(to="CLOSED", action="close", permissions=PERIOD_WRITE, kind="command", confirm=True),
    ),
    "REOPENED": (
        StatusTransition(to="CLOSED", action="close", permissions=PERIOD_WRITE, kind="command", confirm=True),
        # An existing record labelled REOPENED (the label the old form wrote) is
        # brought back to the status the posting paths read.
        StatusTransition(
            to="OPEN", action="reopen", permissions=PERIOD_WRITE, confirm=True, event_type="PERIOD_REOPENED",
        ),
    ),
    "CLOSED": (
        StatusTransition(
            to="OPEN", action="reopen", permissions=PERIOD_WRITE, confirm=True, event_type="PERIOD_REOPENED",
        ),
    ),
}

_ORDER_TRANSITIONS: dict[str, tuple[StatusTransition, ...]] = {
    "ACTIVE": (
        StatusTransition(to="FINISHED", action="finish", permissions=ORDER_WRITE, kind="command", confirm=True),
        StatusTransition(to="INACTIVE", action="deactivate", permissions=ORDER_WRITE),
    ),
    "INACTIVE": (
        StatusTransition(to="ACTIVE", action="activate", permissions=ORDER_WRITE),
    ),
    # A finished order can be reopened: the form used to allow it, and closing
    # the only path would strand a mistakenly finished order.
    "FINISHED": (
        StatusTransition(to="ACTIVE", action="activate", permissions=ORDER_WRITE, confirm=True),
    ),
}

_FINANCIAL_DOCUMENT_TRANSITIONS: dict[str, tuple[StatusTransition, ...]] = {
    "DRAFT": (
        StatusTransition(to="POSTED", action="post", permissions=DOCUMENT_POST, kind="command", confirm=True),
    ),
    "POSTED": (
        StatusTransition(
            to="REVERSED", action="reverse", permissions=DOCUMENT_REVERSE, kind="command", confirm=True, reason=True,
        ),
    ),
}


def _policies() -> dict[str, StatusPolicy]:
    policies: dict[str, StatusPolicy] = {}

    for collection in _REFERENCE_COLLECTIONS:
        policies[collection] = StatusPolicy(
            entity_type=collection,
            store="reference",
            statuses=_ACTIVE_STATUSES,
            transitions=_toggle_transitions(),
        )

    # Party Roles are a reference table with their own matrix page, so their
    # status actions use the page permission before the legacy coarse code.
    policies["partyRoles"] = StatusPolicy(
        entity_type="partyRoles",
        store="reference",
        statuses=_ACTIVE_STATUSES,
        transitions=_toggle_transitions(permissions=PARTY_ROLE_WRITE),
    )

    for collection, vocabulary in _GENERIC_VOCABULARIES.items():
        # A plain Active/Inactive pair reads as activate/deactivate; the longer
        # progress vocabularies read as "Mark as <value>".
        is_toggle = {_normalize(value) for value in vocabulary} == {"ACTIVE", "INACTIVE"}
        policies[collection] = StatusPolicy(
            entity_type=collection,
            store="generic",
            statuses=vocabulary,
            transitions=_toggle_transitions(vocabulary) if is_toggle else _vocabulary_transitions(vocabulary),
        )

    for collection in ("chartOfAccounts", "financialAccounts"):
        policies[collection] = StatusPolicy(
            entity_type="chart_of_account" if collection == "chartOfAccounts" else "financial_account",
            store="account" if collection == "chartOfAccounts" else "financial_account",
            statuses=_ACTIVE_STATUSES,
            transitions=_toggle_transitions(permissions=ACCOUNT_WRITE),
        )

    policies["postingRules"] = StatusPolicy(
        entity_type="posting_rule",
        store="posting_rule",
        statuses=_ACTIVE_STATUSES,
        transitions=_toggle_transitions(permissions=POSTING_RULE_WRITE),
    )

    policies["documentSequences"] = StatusPolicy(
        entity_type="document_sequence",
        store="sequence",
        statuses=_ACTIVE_STATUSES,
        transitions=_toggle_transitions(permissions=SEQUENCE_WRITE),
    )

    policies["accountingPeriods"] = StatusPolicy(
        entity_type="accounting_period",
        store="period",
        statuses=("OPEN", "CLOSED", "REOPENED"),
        transitions=_PERIOD_TRANSITIONS,
    )

    policies["jobs"] = StatusPolicy(
        entity_type="service_order",
        store="order",
        statuses=("ACTIVE", "INACTIVE", "FINISHED"),
        transitions=_ORDER_TRANSITIONS,
    )

    policies["jobCharges"] = StatusPolicy(
        entity_type="service_charge",
        store="charge",
        statuses=("DRAFT", "ISSUED"),
        transitions={
            "DRAFT": (StatusTransition(to="ISSUED", action="issue", permissions=CHARGE_WRITE, kind="command", confirm=True),),
        },
    )

    for collection in ("debitNotes", "customerPayments", "supplierCosts", "supplierPayments"):
        # The payments and cost pages are financial documents too; the same
        # posting and reversal engine serves them.
        policies[collection] = StatusPolicy(
            entity_type="financial_document",
            store="document",
            statuses=("DRAFT", "POSTED", "REVERSED"),
            transitions=_FINANCIAL_DOCUMENT_TRANSITIONS,
        )

    policies["journals"] = StatusPolicy(
        entity_type="journal_entry",
        store="journal",
        statuses=("DRAFT", "POSTED"),
        transitions={
            "DRAFT": (StatusTransition(to="POSTED", action="post", permissions=JOURNAL_POST, kind="command", confirm=True),),
        },
    )

    policies["quotations"] = StatusPolicy(
        entity_type="quotation_revision",
        store="quotation",
        # The vocabulary a revision can hold, including the two the workflow
        # writes itself: SUPERSEDED when a competing revision is accepted and
        # CANCELLED when the offer is withdrawn.
        statuses=("DRAFT", "SENT", "ACCEPTED", "REJECTED", "CONVERTED", "SUPERSEDED", "CANCELLED"),
        transitions=_QUOTATION_TRANSITIONS,
    )

    policies["users"] = StatusPolicy(
        entity_type="user",
        store="user",
        statuses=_ACTIVE_STATUSES,
        transitions={
            "ACTIVE": (StatusTransition(to="INACTIVE", action="deactivate", permissions=USER_WRITE, event_type="USER_UPDATED"),),
            "INACTIVE": (StatusTransition(to="ACTIVE", action="activate", permissions=USER_WRITE, event_type="USER_UPDATED"),),
        },
    )

    policies["roles"] = StatusPolicy(
        entity_type="role",
        store="role",
        statuses=_ACTIVE_STATUSES,
        transitions={
            "ACTIVE": (StatusTransition(to="INACTIVE", action="deactivate", permissions=ROLE_WRITE, event_type="ROLE_UPDATED"),),
            "INACTIVE": (StatusTransition(to="ACTIVE", action="activate", permissions=ROLE_WRITE, event_type="ROLE_UPDATED"),),
        },
    )

    return policies


#: collection slug -> policy. The slug is the one the frontend module declares,
#: which is also the slug the generic master-data routes accept.
STATUS_POLICIES: dict[str, StatusPolicy] = _policies()
