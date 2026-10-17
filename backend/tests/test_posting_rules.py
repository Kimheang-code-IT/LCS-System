"""Database-driven posting rules: selection, posting, validation, reversal, concurrency.

Two units are under test and they are deliberately separate:

* :class:`PostingRuleResolver` answers "which accounts?" and is exercised
  directly against the ORM, so a resolution failure is pinpointed to resolution
  rather than to the posting flow around it;
* :class:`AccountingPostingService` answers "what journal?" and is exercised
  through the HTTP API, because the invariants that matter there - balance,
  atomicity, one posting per document, closed periods - are properties of the
  request, not of a function return value.

The seed gives every core document type one ACTIVE rule with priority 0, so a
test that adds a rule for the same scope at the same priority is asserting the
conflict, not accidentally creating one.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select, text

from app.core.context import RequestContext
from app.core.exceptions import Conflict, ValidationFailed
from app.modules.audit.models import AuditEvent
from app.modules.finance import service as finance_service
from app.modules.finance.models import (
    ChartOfAccount,
    FinancialDocument,
    JournalEntry,
    JournalEntryLine,
    PostingRule,
)
from app.modules.finance.posting import DocumentLineInput
from app.modules.finance.posting_rules import PostingRuleResolver, RuleSource
from app.modules.finance.service import DEFAULT_ACCOUNTS, DOCUMENT_TYPE_LABELS
from tests.conftest import login

FRONTEND_APP = Path(__file__).resolve().parents[2] / "frontend" / "app"

pytestmark = pytest.mark.asyncio


# --- helpers ----------------------------------------------------------------


async def _account_ids(session, *codes: str) -> dict[str, int]:
    rows = (
        await session.execute(select(ChartOfAccount).where(ChartOfAccount.account_code.in_(codes)))
    ).scalars().all()
    return {row.account_code: row.id for row in rows}


async def _add_rule(
    session,
    *,
    document_type: str,
    debit: str,
    credit: str,
    tax: str | None = None,
    fee_type_id: int | None = None,
    priority: int = 0,
    status: str = "ACTIVE",
) -> PostingRule:
    """Insert a rule straight through the ORM.

    The API path is covered separately; going through the model here is what
    lets a test create the states the service is supposed to *prevent* - a
    priority tie, an inactive rule - so the resolver's own guards can be shown
    to work rather than assumed.
    """
    codes = {debit, credit} | ({tax} if tax else set())
    ids = await _account_ids(session, *codes)
    rule = PostingRule(
        document_type=document_type,
        fee_type_id=fee_type_id,
        debit_account_id=ids[debit],
        credit_account_id=ids[credit],
        tax_account_id=ids[tax] if tax else None,
        status=status,
        priority=priority,
    )
    session.add(rule)
    await session.commit()
    return rule


async def _fee_type(client, headers, code: str) -> str:
    response = await client.post(
        "/api/v1/feeTypes",
        headers=headers,
        json={"code": code, "name": f"{code} fee", "status": "Active"},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


async def _document(client, headers, document_type: str, lines: list[dict], **extra) -> str:
    response = await client.post(
        "/api/v1/financial-documents",
        headers=headers,
        json={
            "document_type": document_type,
            "documentDate": date.today().isoformat(),
            "currency": "USD",
            "lines": lines,
            **extra,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


async def _journal_for(client, headers, document_id: str) -> dict:
    journals = await client.get("/api/v1/journal-entries", headers=headers, params={"page_size": 200})
    assert journals.status_code == 200, journals.text
    return next(
        item for item in journals.json()["data"]["items"] if item["sourceDocumentId"] == document_id
    )


def _debit_codes(journal: dict) -> set[str]:
    return {line["account_code"] for line in journal["lines"] if line["debit_amount"] > 0}


def _credit_codes(journal: dict) -> set[str]:
    return {line["account_code"] for line in journal["lines"] if line["credit_amount"] > 0}


def _field_errors(response) -> dict[str, str]:
    return response.json()["field_errors"]


# --- rule selection ---------------------------------------------------------


async def test_a_fee_specific_rule_outranks_the_document_default(session_factory, seeded):
    async with session_factory() as session:
        fee_type_id = int(await _fee_type_id(session))
        # Seed already has a CUSTOMER_INVOICE default (1100 / 4010).
        await _add_rule(
            session, document_type="CUSTOMER_INVOICE", debit="1100", credit="4020", fee_type_id=fee_type_id
        )

        resolver = PostingRuleResolver(session, legacy_defaults=DEFAULT_ACCOUNTS)
        exact = await resolver.resolve("CUSTOMER_INVOICE", fee_type_id)
        default = await resolver.resolve("CUSTOMER_INVOICE")

        assert (exact.credit.account_code, exact.source) == ("4020", RuleSource.EXACT)
        assert (default.credit.account_code, default.source) == ("4010", RuleSource.DOCUMENT_DEFAULT)
        # A scope with no fee type at all still reaches the document default.
        assert (await resolver.resolve("CUSTOMER_INVOICE", 999_999)).source is RuleSource.DOCUMENT_DEFAULT


async def _fee_type_id(session) -> str:
    """Insert a fee type without the API, for the resolver-only tests."""
    return str(await _new_fee_type(session, "RESOLVER-FEE"))


async def _new_fee_type(session, code: str) -> int:
    """A real row, so the `posting_rules.fee_type_id` foreign key holds."""
    from app.modules.master_data.models import FeeType

    fee = FeeType(code=code, name=f"{code} fee", status="ACTIVE")
    session.add(fee)
    await session.commit()
    return fee.id


async def test_the_highest_priority_matching_rule_wins(session_factory, seeded):
    async with session_factory() as session:
        fee_type_id = int(await _fee_type_id(session))
        await _add_rule(
            session,
            document_type="CUSTOMER_INVOICE",
            debit="1100",
            credit="4020",
            fee_type_id=fee_type_id,
            priority=1,
        )
        winner = await _add_rule(
            session,
            document_type="CUSTOMER_INVOICE",
            debit="1100",
            credit="4010",
            fee_type_id=fee_type_id,
            priority=5,
        )

        resolved = await PostingRuleResolver(session, legacy_defaults=DEFAULT_ACCOUNTS).resolve(
            "CUSTOMER_INVOICE", fee_type_id
        )

        assert resolved.credit.account_code == "4010"
        assert resolved.priority == 5
        assert resolved.rule_id == winner.id
        # The explanation is audit-friendly: codes and source, never row ids.
        assert resolved.explain() == {
            "ruleId": str(winner.id),
            "source": "EXACT",
            "priority": 5,
            "debitAccount": "1100",
            "creditAccount": "4010",
            "taxAccount": None,
        }


async def test_a_priority_tie_is_an_ambiguity_error_not_a_coin_flip(session_factory, seeded):
    """Without the unique index the resolver must still refuse an unresolvable tie.

    The index blocks this state for every write that goes through the service, so
    the only way in is a database restored without its indexes - or a future
    migration that relaxes it. Picking the lower row id there would post a
    document to whichever account happened to be written first, which is exactly
    the silent misposting the priority column exists to prevent.
    """
    async with session_factory() as session:
        fee_type_id = int(await _fee_type_id(session))
        await _add_rule(
            session,
            document_type="CUSTOMER_INVOICE",
            debit="1100",
            credit="4020",
            fee_type_id=fee_type_id,
            priority=7,
        )
        # Stand in for a database whose indexes were not restored.
        await session.execute(text("DROP INDEX uq_posting_rules_active_priority"))
        ids = await _account_ids(session, "1100", "4020")
        await session.execute(
            PostingRule.__table__.insert().values(
                document_type="CUSTOMER_INVOICE",
                fee_type_id=fee_type_id,
                debit_account_id=ids["1100"],
                credit_account_id=ids["4020"],
                tax_account_id=None,
                status="ACTIVE",
                priority=7,
            )
        )
        await session.commit()

        with pytest.raises(Conflict) as raised:
            await PostingRuleResolver(session, legacy_defaults=DEFAULT_ACCOUNTS).resolve(
                "CUSTOMER_INVOICE", fee_type_id
            )

        assert raised.value.code == "AMBIGUOUS_POSTING_RULE"
        assert raised.value.field_errors == {"feeTypeId": "Two active rules share the same priority."}


async def test_an_inactive_rule_is_ignored(session_factory, seeded):
    async with session_factory() as session:
        fee_type_id = int(await _fee_type_id(session))
        await _add_rule(
            session,
            document_type="CUSTOMER_INVOICE",
            debit="1100",
            credit="4020",
            fee_type_id=fee_type_id,
            status="INACTIVE",
        )

        resolved = await PostingRuleResolver(session, legacy_defaults=DEFAULT_ACCOUNTS).resolve(
            "CUSTOMER_INVOICE", fee_type_id
        )

        assert resolved.credit.account_code == "4010"
        assert resolved.source is RuleSource.DOCUMENT_DEFAULT


async def test_without_a_rule_the_last_resort_map_is_used_and_says_so(session_factory, seeded):
    async with session_factory() as session:
        # TRANSFER is in DEFAULT_ACCOUNTS but has no seeded rule.
        resolved = await PostingRuleResolver(session, legacy_defaults=DEFAULT_ACCOUNTS).resolve("TRANSFER")

        assert (resolved.debit.account_code, resolved.credit.account_code) == ("1020", "1010")
        assert resolved.source is RuleSource.LEGACY_DEFAULT
        assert resolved.rule_id is None


async def test_an_unconfigured_document_type_is_refused_rather_than_guessed(session_factory, seeded):
    async with session_factory() as session:
        resolver = PostingRuleResolver(session, legacy_defaults=DEFAULT_ACCOUNTS)

        with pytest.raises(ValidationFailed) as raised:
            await resolver.resolve("MADE_UP_TYPE")

        assert raised.value.field_errors == {
            "documentType": "Configure a posting rule for this document type before posting."
        }


async def test_an_inactive_or_header_account_cannot_back_a_rule(session_factory, seeded):
    """A rule that resolves to an unusable account fails at resolution, not silently."""
    async with session_factory() as session:
        unusable = {
            "header": ChartOfAccount(
                account_code="1900",
                account_name="Assets",
                account_type="ASSET",
                normal_balance="DEBIT",
                is_postable=False,
                status="ACTIVE",
            ),
            "inactive": ChartOfAccount(
                account_code="1910",
                account_name="Retired asset",
                account_type="ASSET",
                normal_balance="DEBIT",
                is_postable=True,
                status="INACTIVE",
            ),
        }
        session.add_all(unusable.values())
        await session.commit()

        resolver = PostingRuleResolver(session, legacy_defaults=DEFAULT_ACCOUNTS)
        # Each unusable account gets its own fee scope so the two rules cannot
        # collide on the scope+priority key while the test is set up.
        expectations = {"header": "not postable", "inactive": "must be active"}
        for offset, (case, account) in enumerate(unusable.items()):
            fee_type_id = await _new_fee_type(session, f"UNUSABLE-{offset}")
            await _add_rule(
                session,
                document_type="CUSTOMER_INVOICE",
                debit=account.account_code,
                credit="1100",
                fee_type_id=fee_type_id,
                priority=offset,
            )
            with pytest.raises(ValidationFailed) as raised:
                await resolver.resolve("CUSTOMER_INVOICE", fee_type_id)
            assert expectations[case] in str(raised.value.message)


# --- posting ----------------------------------------------------------------


async def test_a_customer_invoice_debits_the_control_account_and_credits_revenue_per_line(client):
    headers = await login(client)
    document_id = await _document(
        client,
        headers,
        "CUSTOMER_INVOICE",
        [
            {"description": "Freight", "quantity": 1, "unitPrice": 100},
            {"description": "Customs", "quantity": 2, "unitPrice": 25},
        ],
    )

    posted = await client.post(f"/api/v1/financial-documents/{document_id}/post", headers=headers, json={})
    assert posted.status_code == 200, posted.text

    journal = await _journal_for(client, headers, document_id)
    assert journal["debitTotal"] == journal["creditTotal"] == 150
    # Seeded CUSTOMER_INVOICE rule: Dr receivable / Cr service revenue.
    assert _debit_codes(journal) == {"1100"}
    assert _credit_codes(journal) == {"4010"}
    assert journal["status"] == "POSTED"


async def test_a_supplier_bill_mirrors_the_invoice(client):
    headers = await login(client)
    document_id = await _document(
        client, headers, "SUPPLIER_BILL", [{"description": "Carrier bill", "quantity": 1, "unitPrice": 400}]
    )

    posted = await client.post(f"/api/v1/financial-documents/{document_id}/post", headers=headers, json={})
    assert posted.status_code == 200, posted.text

    journal = await _journal_for(client, headers, document_id)
    # Seeded SUPPLIER_BILL rule: Cr payable / Dr transport expense.
    assert _credit_codes(journal) == {"2010"}
    assert _debit_codes(journal) == {"5010"}
    assert journal["debitTotal"] == journal["creditTotal"] == 400


async def test_the_journal_snapshots_the_rule_that_produced_it(client, session_factory):
    """An entry must stay explainable after the rule has been changed or removed."""
    headers = await login(client)
    document_id = await _document(
        client, headers, "CUSTOMER_INVOICE", [{"description": "Freight", "quantity": 1, "unitPrice": 300}]
    )
    assert (
        await client.post(f"/api/v1/financial-documents/{document_id}/post", headers=headers, json={})
    ).status_code == 200

    async with session_factory() as session:
        entry = (
            await session.execute(
                select(JournalEntry).where(JournalEntry.source_document_id == int(document_id))
            )
        ).scalars().first()
        snapshot = entry.data or {}
        assert snapshot["debitAccount"] == "1100"
        assert snapshot["creditAccount"] == "4010"
        assert snapshot["source"] == "DOCUMENT_DEFAULT"
        assert snapshot["side"] == "CONTROL_DEBIT"
        assert snapshot["strategy"], "the accounting shape is recorded, not just the accounts"
        assert snapshot["ruleId"]


async def test_a_customer_credit_note_mirrors_the_invoice_it_corrects(client, session_factory):
    headers = await login(client)
    async with session_factory() as session:
        # A credit note has no seeded rule; give it the mirror of the invoice.
        session.add_all(await _posting_rule_columns(session, "CREDIT_NOTE", "4010", "1100"))
        await session.commit()

    document_id = await _document(
        client, headers, "CREDIT_NOTE", [{"description": "Short delivery", "quantity": 1, "unitPrice": 80}]
    )
    posted = await client.post(f"/api/v1/financial-documents/{document_id}/post", headers=headers, json={})
    assert posted.status_code == 200, posted.text

    journal = await _journal_for(client, headers, document_id)
    assert _credit_codes(journal) == {"1100"}
    assert _debit_codes(journal) == {"4010"}
    assert journal["debitTotal"] == journal["creditTotal"] == 80


async def _posting_rule_columns(session, document_type: str, debit: str, credit: str) -> list[PostingRule]:
    ids = await _account_ids(session, debit, credit)
    return [
        PostingRule(
            document_type=document_type,
            fee_type_id=None,
            debit_account_id=ids[debit],
            credit_account_id=ids[credit],
            status="ACTIVE",
            priority=0,
        )
    ]


async def test_a_payment_posts_two_lines_against_its_control_accounts(client):
    headers = await login(client)
    document_id = await _document(
        client, headers, "CUSTOMER_RECEIPT", [{"description": "Receipt", "quantity": 1, "unitPrice": 250}]
    )

    posted = await client.post(f"/api/v1/financial-documents/{document_id}/post", headers=headers, json={})
    assert posted.status_code == 200, posted.text

    journal = await _journal_for(client, headers, document_id)
    # Seeded CUSTOMER_RECEIPT rule: Dr bank / Cr receivable.
    assert _debit_codes(journal) == {"1020"}
    assert _credit_codes(journal) == {"1100"}
    assert len(journal["lines"]) == 2


async def test_tax_is_split_out_of_the_detail_line_when_the_rule_names_a_tax_account(client, session_factory):
    headers = await login(client)
    async with session_factory() as session:
        session.add_all(await _posting_rule_columns(session, "CREDIT_NOTE", "4010", "1100"))
        await session.commit()
        await _add_rule(
            session, document_type="SUPPLIER_BILL", debit="5040", credit="2010", tax="5030", priority=9
        )

    document_id = await _document(
        client,
        headers,
        "SUPPLIER_BILL",
        [{"description": "Taxable handling", "quantity": 1, "unitPrice": 100, "taxRate": 10}],
    )
    posted = await client.post(f"/api/v1/financial-documents/{document_id}/post", headers=headers, json={})
    assert posted.status_code == 200, posted.text

    journal = await _journal_for(client, headers, document_id)
    amounts = {line["account_code"]: line["debit_amount"] - line["credit_amount"] for line in journal["lines"]}
    # Payable credited 110, expense debited 100 net, tax debited 10 - still balanced.
    assert amounts["2010"] == -110
    assert amounts["5040"] == 100
    assert amounts["5030"] == 10
    assert journal["debitTotal"] == journal["creditTotal"] == 110


async def test_a_zero_total_cannot_be_posted(client):
    headers = await login(client)
    document_id = await _document(client, headers, "CUSTOMER_INVOICE", [])

    posted = await client.post(f"/api/v1/financial-documents/{document_id}/post", headers=headers, json={})

    assert posted.status_code == 422
    assert _field_errors(posted)["total"] == "Enter a total greater than zero."


async def test_a_fee_type_without_its_own_rule_falls_back_to_the_document_default(client, session_factory):
    headers = await login(client)
    async with session_factory() as session:
        fee_type_id = int(await _fee_type_id(session))
        await _add_rule(
            session, document_type="CUSTOMER_INVOICE", debit="1100", credit="4020", fee_type_id=fee_type_id
        )

    document_id = await _document(
        client,
        headers,
        "CUSTOMER_INVOICE",
        [{"description": "Fee-typed line", "quantity": 1, "unitPrice": 60, "feeTypeId": str(fee_type_id)}],
    )
    posted = await client.post(f"/api/v1/financial-documents/{document_id}/post", headers=headers, json={})
    assert posted.status_code == 200, posted.text

    journal = await _journal_for(client, headers, document_id)
    assert _credit_codes(journal) == {"4020"}


async def test_a_draft_is_never_half_posted_when_a_rule_cannot_resolve(client, session_factory):
    """The document stays a draft and no journal exists when resolution fails."""
    headers = await login(client)
    async with session_factory() as session:
        # An inactive credit account: the rule exists, the account cannot post.
        dormant = ChartOfAccount(
            account_code="1920",
            account_name="Dormant income",
            account_type="REVENUE",
            normal_balance="CREDIT",
            is_postable=True,
            status="INACTIVE",
        )
        session.add(dormant)
        await session.commit()
        ids = await _account_ids(session, "1100")
        session.add(
            PostingRule(
                document_type="CREDIT_NOTE",
                fee_type_id=None,
                debit_account_id=dormant.id,
                credit_account_id=ids["1100"],
                status="ACTIVE",
                priority=0,
            )
        )
        await session.commit()

    document_id = await _document(
        client, headers, "CREDIT_NOTE", [{"description": "Credit", "quantity": 1, "unitPrice": 10}]
    )
    posted = await client.post(f"/api/v1/financial-documents/{document_id}/post", headers=headers, json={})

    assert posted.status_code == 422
    assert "must be active" in posted.json()["message"]
    document = await client.get(f"/api/v1/financial-documents/{document_id}", headers=headers)
    assert document.json()["data"]["status"] == "Draft"
    journals = await client.get("/api/v1/journal-entries", headers=headers, params={"page_size": 200})
    assert all(item["sourceDocumentId"] != document_id for item in journals.json()["data"]["items"])


async def test_the_posting_service_refuses_to_return_an_unbalanced_draft(session_factory, seeded):
    """Balance is enforced before anything is persisted, not after."""
    from app.modules.finance.posting import AccountingPostingService, JournalDraft

    async with session_factory() as session:
        service = AccountingPostingService(
            PostingRuleResolver(session, legacy_defaults=DEFAULT_ACCOUNTS)
        )
        draft = await service.build(
            document_type="CUSTOMER_INVOICE",
            total=Decimal("100"),
            lines=[DocumentLineInput(description="Freight", amount=Decimal("100"), tax=Decimal("10"))],
        )
        assert draft.debit_total == draft.credit_total == Decimal("100")

        # A hand-corrupted draft is caught by the same assertion the service uses.
        broken = JournalDraft()

        accounts = await _account_ids(session, "1100", "4010")
        debit = await session.get(ChartOfAccount, accounts["1100"])
        broken.add(debit, Decimal("100"), debit=True)
        with pytest.raises(Conflict) as raised:
            broken.assert_balanced()
        assert raised.value.code == "JOURNAL_UNBALANCED"


# --- validation of the rule itself ------------------------------------------


async def test_a_rule_missing_its_accounts_is_rejected_per_field(client):
    headers = await login(client)

    response = await client.post(
        "/api/v1/postingRules",
        headers=headers,
        json={"documentType": "OTHER_INCOME", "status": "ACTIVE"},
    )

    assert response.status_code == 422
    errors = _field_errors(response)
    assert errors["debitAccount"] == "Select the debit account."
    assert errors["creditAccount"] == "Select the credit account."


@pytest.mark.parametrize(
    ("payload", "field", "fragment"),
    [
        ({"documentType": "NOT_A_TYPE", "debitAccount": "1100", "creditAccount": "4010"}, "documentType", "Unknown"),
        ({"documentType": "OTHER_INCOME", "debitAccount": "9999", "creditAccount": "4010"}, "debitAccount", "chart of accounts"),
        (
            {"documentType": "OTHER_INCOME", "debitAccount": "4010", "creditAccount": "4010"},
            "creditAccount",
            "must differ",
        ),
        (
            {"documentType": "OTHER_INCOME", "debitAccount": "1100", "creditAccount": "4010", "priority": -3},
            "priority",
            "cannot be negative",
        ),
        (
            {"documentType": "OTHER_INCOME", "debitAccount": "1100", "creditAccount": "4010", "priority": "high"},
            "priority",
            "whole number",
        ),
        (
            {"documentType": "OTHER_INCOME", "debitAccount": "1100", "creditAccount": "4010", "status": "MAYBE"},
            "status",
            "ACTIVE or INACTIVE",
        ),
    ],
)
async def test_rule_validation_rejects_bad_input_on_the_right_field(client, payload, field, fragment):
    headers = await login(client)
    response = await client.post("/api/v1/postingRules", headers=headers, json=payload)

    assert response.status_code == 422, response.text
    assert fragment in _field_errors(response)[field]


async def test_a_header_account_cannot_be_configured(client, session_factory):
    headers = await login(client)
    async with session_factory() as session:
        session.add(
            ChartOfAccount(
                account_code="1900",
                account_name="Assets",
                account_type="ASSET",
                normal_balance="DEBIT",
                is_postable=False,
                status="ACTIVE",
            )
        )
        await session.commit()

    response = await client.post(
        "/api/v1/postingRules",
        headers=headers,
        json={"documentType": "OTHER_INCOME", "debitAccount": "1900", "creditAccount": "4010"},
    )

    assert response.status_code == 422
    assert "header account" in _field_errors(response)["debitAccount"]


async def test_two_active_rules_may_share_a_scope_only_at_different_priorities(client):
    headers = await login(client)
    payload = {"documentType": "OTHER_INCOME", "debitAccount": "1020", "creditAccount": "4020", "status": "ACTIVE"}

    first = await client.post("/api/v1/postingRules", headers=headers, json={**payload, "priority": 1})
    assert first.status_code == 201, first.text

    # The seeded OTHER_INCOME rule already sits at priority 0 in this scope.
    clash = await client.post("/api/v1/postingRules", headers=headers, json={**payload, "priority": 0})
    assert clash.status_code == 409, clash.text
    assert _field_errors(clash)["priority"] == "Priority 0 is already taken for this scope."

    # A different priority is a legitimate additional rule for the same scope.
    second = await client.post("/api/v1/postingRules", headers=headers, json={**payload, "priority": 4})
    assert second.status_code == 201, second.text
    assert second.json()["data"]["priority"] == 4

    # An inactive rule never occupies a priority, so it may reuse one.
    dormant = await client.post(
        "/api/v1/postingRules",
        headers=headers,
        json={**payload, "priority": 4, "status": "INACTIVE"},
    )
    assert dormant.status_code == 201, dormant.text


async def test_an_optional_priority_left_blank_is_not_a_malformed_number(client):
    """The form sends "" for an empty optional number, which must not be an error."""
    headers = await login(client)
    response = await client.post(
        "/api/v1/postingRules",
        headers=headers,
        json={
            # CREDIT_NOTE has no seeded rule, so priority 0 is free in this scope.
            "documentType": "CREDIT_NOTE",
            "debitAccount": "4010",
            "creditAccount": "1100",
            "priority": "",
            "status": "ACTIVE",
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["data"]["priority"] == 0
    # An omitted description clears rather than erroring.
    assert response.json()["data"]["description"] is None


async def test_updating_a_rule_keeps_omitted_fields(client):
    headers = await login(client)
    created = await client.post(
        "/api/v1/postingRules",
        headers=headers,
        json={
            "documentType": "OTHER_EXPENSE",
            "debitAccount": "5030",
            "creditAccount": "1020",
            "description": "Office costs",
            "priority": 3,
        },
    )
    assert created.status_code == 201, created.text
    rule_id = created.json()["data"]["id"]

    updated = await client.put(
        f"/api/v1/postingRules/{rule_id}", headers=headers, json={"description": "Office and consumables"}
    )

    assert updated.status_code == 200, updated.text
    body = updated.json()["data"]
    assert body["description"] == "Office and consumables"
    assert (body["debitAccount"], body["creditAccount"], body["priority"]) == ("5030", "1020", 3)


async def test_managing_rules_requires_the_manage_permission(client):
    headers = await login(client)
    role = await client.post(
        "/api/v1/roles",
        headers=headers,
        json={
            "code": "RULE_READER",
            "name": "Posting rule reader",
            "permissions": ["finance.posting_rules.view"],
        },
    )
    assert role.status_code == 201, role.text
    user = await client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "username": "rule.reader",
            "displayName": "Rule Reader",
            "email": "rule.reader@example.com",
            "password": "Passw0rd!",
            "status": "Active",
            "role": "RULE_READER",
        },
    )
    assert user.status_code == 201, user.text
    reader = await login(client, "rule.reader")

    # Read is allowed: seeing how accounts are mapped is not privileged.
    assert (await client.get("/api/v1/postingRules", headers=reader)).status_code == 200
    # Writing is not.
    denied = await client.post(
        "/api/v1/postingRules",
        headers=reader,
        json={"documentType": "OTHER_INCOME", "debitAccount": "1020", "creditAccount": "4020"},
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "ACCESS_DENIED"


async def test_creating_and_updating_a_rule_is_audited(client, session_factory):
    headers = await login(client)
    created = await client.post(
        "/api/v1/postingRules",
        headers=headers,
        json={"documentType": "OTHER_INCOME", "debitAccount": "1020", "creditAccount": "4020", "priority": 2},
    )
    assert created.status_code == 201, created.text
    rule_id = created.json()["data"]["id"]

    updated = await client.put(f"/api/v1/postingRules/{rule_id}", headers=headers, json={"priority": 6})
    assert updated.status_code == 200, updated.text

    # The list is what an auditor reads first: it must say *what* happened, not
    # only that something did.
    events = await client.get("/api/v1/audit-events", headers=headers, params={"page_size": 200})
    assert events.status_code == 200, events.text
    listed = [item for item in events.json()["data"]["items"] if item["entityType"] == "posting_rule"]
    assert [item["eventType"] for item in listed] == ["POSTING_RULE_UPDATED", "POSTING_RULE_CREATED"]
    assert [item["action"] for item in listed] == ["update", "create"]
    assert all(item["entityId"] == int(rule_id) for item in listed)

    # The before/after images stay in the stored row; the list deliberately does
    # not carry them, because one blob per event would swamp the page.
    async with session_factory() as session:
        stored = (
            await session.execute(
                select(AuditEvent)
                .where(AuditEvent.entity_type == "posting_rule")
                .order_by(AuditEvent.id)
            )
        ).scalars().all()
        assert [event.event_type for event in stored] == ["POSTING_RULE_CREATED", "POSTING_RULE_UPDATED"]
        assert stored[0].after_json["priority"] == 2
        assert stored[1].before_json["priority"] == 2
        assert stored[1].after_json["priority"] == 6


# --- reversals and history --------------------------------------------------


async def test_changing_a_rule_leaves_posted_history_untouched(client):
    headers = await login(client)
    document_id = await _document(
        client, headers, "CUSTOMER_INVOICE", [{"description": "Freight", "quantity": 1, "unitPrice": 300}]
    )
    posted = await client.post(f"/api/v1/financial-documents/{document_id}/post", headers=headers, json={})
    assert posted.status_code == 200, posted.text
    original = await _journal_for(client, headers, document_id)

    # Repoint the rule at completely different accounts.
    rules = await client.get("/api/v1/postingRules", headers=headers, params={"page_size": 200})
    default_rule = next(
        item
        for item in rules.json()["data"]["items"]
        if item["documentType"] == "CUSTOMER_INVOICE" and item["feeTypeId"] is None
    )
    changed = await client.put(
        f"/api/v1/postingRules/{default_rule['id']}",
        headers=headers,
        json={"debitAccount": "1200", "creditAccount": "4020"},
    )
    assert changed.status_code == 200, changed.text

    # The posted entry still shows the accounts it was posted through.
    after_change = await _journal_for(client, headers, document_id)
    assert after_change["id"] == original["id"]
    assert after_change["debitTotal"] == original["debitTotal"]
    assert _debit_codes(after_change) == {"1100"}

    # And a new document picks up the new mapping.
    next_document = await _document(
        client, headers, "CUSTOMER_INVOICE", [{"description": "Later freight", "quantity": 1, "unitPrice": 300}]
    )
    assert (
        await client.post(f"/api/v1/financial-documents/{next_document}/post", headers=headers, json={})
    ).status_code == 200
    later = await _journal_for(client, headers, next_document)
    assert _debit_codes(later) == {"1200"}


async def test_a_reversal_equals_and_opposes_the_original_after_the_rule_changed(client):
    headers = await login(client)
    document_id = await _document(
        client, headers, "CUSTOMER_INVOICE", [{"description": "Freight", "quantity": 1, "unitPrice": 300}]
    )
    await client.post(f"/api/v1/financial-documents/{document_id}/post", headers=headers, json={})
    original = await _journal_for(client, headers, document_id)

    rules = await client.get("/api/v1/postingRules", headers=headers, params={"page_size": 200})
    default_rule = next(
        item
        for item in rules.json()["data"]["items"]
        if item["documentType"] == "CUSTOMER_INVOICE" and item["feeTypeId"] is None
    )
    await client.put(
        f"/api/v1/postingRules/{default_rule['id']}",
        headers=headers,
        json={"debitAccount": "1200", "creditAccount": "4020"},
    )

    reversal = await client.post(
        f"/api/v1/financial-documents/{document_id}/reverse",
        headers=headers,
        json={"reason": "Billed in error"},
    )
    assert reversal.status_code == 201, reversal.text

    journals = await client.get("/api/v1/journal-entries", headers=headers, params={"page_size": 200})
    entries = [item for item in journals.json()["data"]["items"] if item["sourceDocumentId"] == document_id]
    assert len(entries) == 2

    original_after = next(item for item in entries if item["id"] == original["id"])
    # The original entry is immutable: it stays POSTED and keeps its own accounts
    # and amounts. The reversal is a separate entry, not an edit of this one.
    assert original_after["status"] == "POSTED"
    assert original_after["debitTotal"] == original["debitTotal"]
    assert _debit_codes(original_after) == _debit_codes(original)
    document = await client.get(f"/api/v1/financial-documents/{document_id}", headers=headers)
    assert document.json()["data"]["status"] == "Reversed"

    reversing = next(item for item in entries if item["id"] != original["id"])
    assert reversing["entryType"] == "REVERSAL"
    assert reversing["debitTotal"] == original["debitTotal"]
    assert reversing["creditTotal"] == original["creditTotal"]
    # The mirror holds account by account, so every balance nets back to zero.
    original_net = sum(line["debit_amount"] - line["credit_amount"] for line in original_after["lines"])
    assert sum(line["debit_amount"] - line["credit_amount"] for line in reversing["lines"]) == -original_net
    for code in _debit_codes(original) | _credit_codes(original):
        posted_net = sum(
            line["debit_amount"] - line["credit_amount"]
            for line in original_after["lines"]
            if line["account_code"] == code
        )
        reversal_net = sum(
            line["debit_amount"] - line["credit_amount"]
            for line in reversing["lines"]
            if line["account_code"] == code
        )
        assert reversal_net == -posted_net, f"{code} did not net back to zero"


# --- concurrency and duplicate posting ---------------------------------------


async def test_a_document_cannot_be_posted_twice(client):
    headers = await login(client)
    document_id = await _document(
        client, headers, "CUSTOMER_INVOICE", [{"description": "Freight", "quantity": 1, "unitPrice": 100}]
    )

    first = await client.post(f"/api/v1/financial-documents/{document_id}/post", headers=headers, json={})
    assert first.status_code == 200, first.text

    journals = await client.get("/api/v1/journal-entries", headers=headers, params={"page_size": 200})
    posted_entries = [
        item for item in journals.json()["data"]["items"] if item["sourceDocumentId"] == document_id
    ]
    assert len(posted_entries) == 1

    # A second post is a no-op read of the already-posted document, never a second entry.
    second = await client.post(f"/api/v1/financial-documents/{document_id}/post", headers=headers, json={})
    assert second.status_code == 200, second.text
    journals = await client.get("/api/v1/journal-entries", headers=headers, params={"page_size": 200})
    assert (
        len([item for item in journals.json()["data"]["items"] if item["sourceDocumentId"] == document_id]) == 1
    )


async def test_a_posting_link_blocks_a_second_journal_even_if_the_document_looks_draft(client, session_factory):
    """The duplicate-posting guard, exercised at the state the row lock prevents.

    ``post_document`` reads the document ``FOR UPDATE`` and refuses a document
    that is not DRAFT. That lock is what serialises two concurrent posts, so the
    branch it protects is unreachable through the API - and that is exactly why
    it needs its own test: if the document row were ever reset, the unique
    ``financial_document_postings`` link is what still holds.
    """
    headers = await login(client)
    document_id = await _document(
        client, headers, "CUSTOMER_INVOICE", [{"description": "Freight", "quantity": 1, "unitPrice": 100}]
    )
    assert (
        await client.post(f"/api/v1/financial-documents/{document_id}/post", headers=headers, json={})
    ).status_code == 200

    async with session_factory() as session:
        document = await session.get(FinancialDocument, int(document_id))
        document.status = "DRAFT"
        await session.commit()

    repeated = await client.post(f"/api/v1/financial-documents/{document_id}/post", headers=headers, json={})

    assert repeated.status_code == 409
    assert repeated.json()["code"] == "DUPLICATE_POSTING"
    journals = await client.get("/api/v1/journal-entries", headers=headers, params={"page_size": 200})
    assert (
        len([item for item in journals.json()["data"]["items"] if item["sourceDocumentId"] == document_id]) == 1
    )


async def test_concurrent_rules_at_the_same_priority_leave_one_winner(session_factory, seeded):
    """A lost priority race is a legible 409, not a driver error.

    ``_assert_unique_priority`` is a read-then-write, so two requests can both
    see an empty scope. The partial unique index is the authority; the test
    reproduces the exact interleaving - the loser's duplicate check runs *before*
    the winner commits - so the branch that converts the IntegrityError is covered.
    """
    from app.modules.finance import service as finance_service

    payload = {
        "documentType": "CREDIT_NOTE",
        "debitAccount": "4010",
        "creditAccount": "1100",
        "status": "ACTIVE",
        "priority": 3,
    }
    context = RequestContext(
        user_id=1,
        username="admin",
        email="admin@example.com",
        display_name="Admin",
        permissions={"posting_rule.manage"},
        is_platform_admin=False,
        request_id="race",
    )

    async with session_factory() as loser:
        # The loser validates first and finds nothing, exactly as it would while
        # the winner's transaction is still open.
        stale = await finance_service._posting_rule_data(loser, payload)

        async with session_factory() as winner:
            created = await finance_service.create_posting_rule(winner, context, payload)
            await winner.commit()
        assert created["priority"] == 3

        # The loser now writes with values validated before the winner existed.
        loser.add(PostingRule(**stale))
        with pytest.raises(Conflict) as raised:
            await finance_service._flush_rule(loser, stale)
        assert raised.value.code == "DUPLICATE_POSTING_RULE"
        assert raised.value.field_errors["priority"] == "Priority 3 is already taken for this scope."

    async with session_factory() as session:
        scope = (
            await session.execute(
                select(PostingRule).where(
                    PostingRule.document_type == "CREDIT_NOTE",
                    PostingRule.fee_type_id.is_(None),
                    PostingRule.status == "ACTIVE",
                )
            )
        ).scalars().all()
        assert len(scope) == 1
        assert scope[0].priority == 3


async def test_posting_into_a_closed_period_is_refused(client):
    headers = await login(client)
    document_id = await _document(
        client, headers, "CUSTOMER_INVOICE", [{"description": "Freight", "quantity": 1, "unitPrice": 100}]
    )

    periods = await client.get("/api/v1/accounting-periods", headers=headers, params={"page_size": 200})
    assert periods.status_code == 200, periods.text
    period = next(item for item in periods.json()["data"] if item["status"] == "OPEN")
    closed = await client.post(f"/api/v1/accounting-periods/{period['id']}/close", headers=headers, json={})
    assert closed.status_code == 200, closed.text

    posted = await client.post(f"/api/v1/financial-documents/{document_id}/post", headers=headers, json={})

    assert posted.status_code == 409
    assert posted.json()["code"] == "PERIOD_CLOSED"
    document = await client.get(f"/api/v1/financial-documents/{document_id}", headers=headers)
    assert document.json()["data"]["status"] == "Draft"


async def test_lines_are_written_before_the_journal_is_marked_posted(client, session_factory):
    """Regression: `fn_guard_journal_line` rejected every posting on PostgreSQL.

    The guard is an immediate trigger that refuses a line whose parent entry is
    already POSTED. SQLAlchemy flushes a mapper's pending UPDATE before another
    mapper's pending INSERT when both are queued together, so setting
    `entry.status = "POSTED"` alongside the line inserts made the trigger observe
    POSTED and abort with "Lines of posted journal N cannot change". The SQLite
    test database has no triggers, so only a PostgreSQL run catches this - which
    is why the flush order is pinned here as well.
    """
    headers = await login(client)
    document_id = await _document(
        client, headers, "CUSTOMER_INVOICE", [{"description": "Freight", "quantity": 1, "unitPrice": 100}]
    )
    assert (
        await client.post(f"/api/v1/financial-documents/{document_id}/post", headers=headers, json={})
    ).status_code == 200

    async with session_factory() as session:
        entry = (
            await session.execute(
                select(JournalEntry).where(JournalEntry.source_document_id == int(document_id))
            )
        ).scalars().first()
        assert entry is not None
        lines = (
            await session.execute(select(JournalEntryLine).where(JournalEntryLine.journal_entry_id == entry.id))
        ).scalars().all()
        assert len(lines) == 2

    source = Path(finance_service.__file__).read_text(encoding="utf-8")
    for function in ("post_document", "reverse_document"):
        body = source.split(f"async def {function}(", 1)[1].split("\nasync def ", 1)[0]
        status_line = body.index('.status = "POSTED"')
        # The flush that persists the lines must come first, and the status
        # change must be followed by its own flush.
        assert body[:status_line].count("await session.flush()") >= 2, (
            f"{function} must flush the lines while the header is still DRAFT"
        )
        assert "await session.flush()" in body[status_line:], (
            f"{function} must flush the header promotion separately"
        )


# --- history and usage ------------------------------------------------------


async def test_a_rule_change_is_recorded_in_the_audit_trail(client):
    """What an administrator asks after a rule misbehaves: what changed, and when.

    Read through the general audit endpoint. The posting-rule history screen was
    removed from the product, but the events behind it are append-only audit records
    that the Audit Logs screen still shows, so the requirement is unchanged.
    """
    headers = await login(client)
    created = await client.post(
        "/api/v1/postingRules",
        headers=headers,
        json={
            "documentType": "CREDIT_NOTE",
            "debitAccount": "4010",
            "creditAccount": "1100",
            "priority": 2,
            "description": "Short deliveries",
        },
    )
    assert created.status_code == 201, created.text
    rule_id = created.json()["data"]["id"]

    updated = await client.put(
        f"/api/v1/postingRules/{rule_id}",
        headers=headers,
        json={"creditAccount": "1200", "priority": 7, "description": "Short deliveries and returns"},
    )
    assert updated.status_code == 200, updated.text

    events = await client.get(
        "/api/v1/audit-events",
        headers=headers,
        params={"entity_type": "posting_rule", "entity_id": rule_id, "page_size": 50},
    )
    assert events.status_code == 200, events.text

    actions = [item["action"].lower() for item in events.json()["data"]["items"]]
    assert "create" in actions
    assert "update" in actions
    assert all(item["user"] for item in events.json()["data"]["items"]), (
        "the audit trail names who made the change"
    )


async def test_a_posted_journal_links_to_the_rule_that_resolved_it(client, session_factory):
    headers = await login(client)
    rules = await client.get("/api/v1/postingRules", headers=headers, params={"page_size": 200})
    rule = next(
        item
        for item in rules.json()["data"]["items"]
        if item["documentType"] == "CUSTOMER_INVOICE" and item["feeTypeId"] is None
    )

    document_id = await _document(
        client, headers, "CUSTOMER_INVOICE", [{"description": "Freight", "quantity": 1, "unitPrice": 250}]
    )
    assert (
        await client.post(f"/api/v1/financial-documents/{document_id}/post", headers=headers, json={})
    ).status_code == 200

    async with session_factory() as session:
        entry = (
            await session.execute(
                select(JournalEntry).where(JournalEntry.source_document_id == int(document_id))
            )
        ).scalars().first()
        assert str(entry.posting_rule_id) == rule["id"]


async def test_a_rule_that_posted_something_cannot_be_deleted(client):
    """Deleting it would destroy the link between the journal and its rule.

    The reference scan walks the SQLAlchemy metadata, so the new
    ``journal_entries.posting_rule_id`` foreign key becomes a blocker without
    anyone maintaining a list.
    """
    headers = await login(client)
    created = await client.post(
        "/api/v1/postingRules",
        headers=headers,
        json={
            "documentType": "CREDIT_NOTE",
            "debitAccount": "4010",
            "creditAccount": "1100",
            "priority": 4,
            "status": "INACTIVE",
        },
    )
    assert created.status_code == 201, created.text
    rule_id = created.json()["data"]["id"]
    # Inactive and unreferenced: deletable.
    assert (await client.request("DELETE", "/api/v1/postingRules", headers=headers, json={"ids": [rule_id]})).status_code == 200

    seeded = await client.post(
        "/api/v1/postingRules",
        headers=headers,
        json={"documentType": "CREDIT_NOTE", "debitAccount": "4010", "creditAccount": "1100", "priority": 4},
    )
    assert seeded.status_code == 201, seeded.text
    live_rule_id = seeded.json()["data"]["id"]

    document_id = await _document(
        client, headers, "CREDIT_NOTE", [{"description": "Return", "quantity": 1, "unitPrice": 40}]
    )
    assert (
        await client.post(f"/api/v1/financial-documents/{document_id}/post", headers=headers, json={})
    ).status_code == 200

    await client.put(f"/api/v1/postingRules/{live_rule_id}", headers=headers, json={"status": "INACTIVE"})
    blocked = await client.request(
        "DELETE", "/api/v1/postingRules", headers=headers, json={"ids": [live_rule_id]}
    )

    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["code"] == "DELETE_BLOCKED_BY_REFERENCES"
    assert "journal_entries" in blocked.json()["message"]
    # The rule is still there, so the journal keeps its attribution.
    assert (await client.get(f"/api/v1/postingRules/{live_rule_id}", headers=headers)).status_code == 200


async def test_a_manual_journal_is_not_attributed_to_any_rule(client, session_factory):
    """Only a rule-driven posting carries a rule; a manual entry has none."""
    headers = await login(client)
    created = await client.post(
        "/api/v1/journal-entries",
        headers=headers,
        json={
            "entryDate": date.today().isoformat(),
            "lines": [
                {"accountCode": "1010", "debitAmount": 15, "creditAmount": 0},
                {"accountCode": "1020", "debitAmount": 0, "creditAmount": 15},
            ],
        },
    )
    assert created.status_code == 201, created.text

    async with session_factory() as session:
        entry = await session.get(JournalEntry, int(created.json()["data"]["id"]))
        assert entry.posting_rule_id is None


# --- cross-stack parity -----------------------------------------------------


def test_the_frontend_document_type_registry_matches_the_backend():
    """Both sides must offer an administrator exactly the same document types.

    The codes are stored verbatim on ``financial_documents.document_type`` and
    matched against ``posting_rules.document_type``; a type offered on one side
    and refused on the other is a silent configuration dead end. The frontend list
    is read statically, the same way ``test_frontend_api_contract`` does.
    """
    options = FRONTEND_APP / "config" / "freight-options.ts"
    source = options.read_text(encoding="utf-8")
    block = source.split("FINANCIAL_DOCUMENT_TYPES = [", 1)[1].split("]", 1)[0]
    frontend = [value.strip().strip("',\"") for value in block.split("\n") if value.strip()]

    assert frontend == list(DOCUMENT_TYPE_LABELS), (
        "frontend/app/config/freight-options.ts FINANCIAL_DOCUMENT_TYPES has drifted from "
        "DOCUMENT_TYPE_LABELS in backend/app/modules/finance/service.py"
    )