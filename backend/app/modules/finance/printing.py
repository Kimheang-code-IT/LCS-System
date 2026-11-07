"""Read-only, reconciled projections of stored financial documents for printing.

No numbering, posting, rate resolution, audit mutation or commit belongs here.
Container notes are labeled source-invoice breakdowns, never newly issued documents.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound, ValidationFailed
from app.core.fx import currency_precision
from app.modules.finance.models import FinancialAccount, FinancialDocument, FinancialDocumentLine
from app.modules.master_data.models import BusinessParty, BusinessPartyRole, ContainerType, Currency, PartyRole
from app.modules.operations.models import ServiceOrder, ServiceOrderContainer
from app.modules.settings.service import get_app_info

ZERO = Decimal("0")


def _text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _party(row: BusinessParty | None) -> dict:
    return {
        "name": row.legal_name if row else "",
        "legalName": row.legal_name if row else "",
        "nameKh": "",
        "taxIdentifier": row.vat_tin or "" if row else "",
        "address": row.address or "" if row else "",
        "phone": row.phone or "" if row else "",
        "email": row.email or "" if row else "",
        "contact": row.contact_person or "" if row else "",
    }


def _totals(lines: list[FinancialDocumentLine]) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    gross = sum((line.line_amount + line.discount_amount - line.tax_amount for line in lines), ZERO)
    discount = sum((line.discount_amount for line in lines), ZERO)
    tax = sum((line.tax_amount for line in lines), ZERO)
    total = sum((line.line_amount for line in lines), ZERO)
    if any(line.line_amount != (line.quantity * line.unit_price - line.discount_amount + line.tax_amount).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP) for line in lines):
        raise ValidationFailed("Stored invoice line totals do not reconcile. Review the source document.")
    return gross, discount, tax, total


async def _containers(session: AsyncSession, document: FinancialDocument, lines: list[FinancialDocumentLine]) -> dict:
    ids = {line.service_order_container_id for line in lines if line.service_order_container_id}
    orders = {line.service_order_id or document.service_order_id for line in lines}
    if None in orders and ids:
        raise ValidationFailed("A billed container has no reliable Service Order relationship.")
    if orders - {None}:
        rows = (await session.execute(select(ServiceOrder).where(ServiceOrder.id.in_(orders - {None})))).scalars().all()
        if {row.id for row in rows} != orders - {None} or any(row.customer_party_id != document.party_id for row in rows):
            raise ValidationFailed("Invoice lines reference a missing Service Order or a different customer.")
    rows = (await session.execute(
        select(ServiceOrderContainer, ContainerType.name)
        .join(ContainerType, ContainerType.id == ServiceOrderContainer.container_type_id)
        .where(ServiceOrderContainer.id.in_(ids))
    )).all() if ids else []
    found = {row.id: (row, label) for row, label in rows}
    if set(found) != ids:
        raise ValidationFailed("A billed container no longer has a reliable stored relationship.")
    for line in lines:
        if line.service_order_container_id:
            box, _ = found[line.service_order_container_id]
            if box.service_order_id != (line.service_order_id or document.service_order_id) or not box.container_number:
                raise ValidationFailed("The billed container does not belong to its Service Order or has no actual number.")
    return found


async def _issuer(session: AsyncSession) -> tuple[dict, list[str]]:
    # Company is shared master data, not a hardcoded legal identity or the app title.
    companies = (await session.execute(
        select(BusinessParty).join(BusinessPartyRole, BusinessPartyRole.business_party_id == BusinessParty.id)
        .join(PartyRole, PartyRole.id == BusinessPartyRole.party_role_id)
        .where(PartyRole.code == "COMPANY", PartyRole.deleted_at.is_(None), PartyRole.status == "ACTIVE",
               BusinessParty.deleted_at.is_(None), BusinessParty.status == "ACTIVE")
    )).scalars().unique().all()
    info = await get_app_info(session)
    company = companies[0] if len(companies) == 1 else None
    issuer = {
        **_party(company), "legalNameKh": "", "addressKh": "", "displayName": company.display_name or "" if company else "",
        "logoUrl": _text((info.get("branding") or {}).get("mainLogoUrl")) or "/lcs-invoice-logo.jpg",
    }
    if company and any("\u1780" <= char <= "\u17ff" for char in (company.display_name or "")):
        issuer["legalNameKh"] = company.display_name
    return issuer, [] if company else ["Configure exactly one active Company business party before printing."]


async def financial_print_data(
    session: AsyncSession, document_id: int, template: str = "tax-invoice", container_id: int | None = None
) -> dict:
    document = await session.get(FinancialDocument, document_id)
    if document is None:
        raise NotFound("Financial document not found.")
    if document.status not in {"DRAFT", "POSTED"}:
        raise ValidationFailed("Only draft previews and posted financial documents can be printed.")
    if document.document_type != "CUSTOMER_INVOICE":
        raise ValidationFailed("These invoice/container layouts require a customer invoice. Use the document's existing print workflow.")
    if template == "tax-invoice" and container_id is not None:
        raise ValidationFailed("A consolidated invoice must include its complete stored billing scope.")
    lines = (await session.execute(
        select(FinancialDocumentLine).where(FinancialDocumentLine.financial_document_id == document.id)
        .order_by(FinancialDocumentLine.line_no)
    )).scalars().all()
    if not lines:
        raise ValidationFailed("The invoice has no stored lines to print.")
    totals = _totals(lines)
    expected = (document.subtotal_amount, document.discount_amount, document.tax_amount, document.total_amount)
    if totals != expected:
        raise ValidationFailed("Stored invoice totals do not reconcile. Printing cannot change the source document.")
    if any(line.quantity < ZERO or line.unit_price < ZERO or line.discount_amount < ZERO or line.tax_amount < ZERO for line in lines):
        raise ValidationFailed("The invoice contains unsupported negative charge values.")
    # Currency has a numeric PK; look up its stable code rather than assume code is the PK.
    currency = (await session.execute(select(Currency).where(Currency.code == document.currency_code))).scalars().first()
    if currency is None:
        raise ValidationFailed("The stored invoice currency is missing.")
    precision = currency_precision(currency.decimal_places)
    base_currency = (await session.execute(select(Currency).where(Currency.code == document.base_currency_code))).scalars().first() if document.base_currency_code else currency
    if base_currency is None:
        raise ValidationFailed("The stored base currency is missing.")
    # Existing layouts use JS numbers for presentation only. Refuse an amount they cannot display faithfully.
    if any(abs(value) * (10 ** precision) > Decimal("9007199254740991") for value in totals):
        raise ValidationFailed("This amount exceeds the printable precision supported by the current renderer.")
    party = await session.get(BusinessParty, document.party_id) if document.party_id else None
    if party is None:
        raise ValidationFailed("The invoice customer is missing.")
    boxes = await _containers(session, document, lines)
    options = [{"id": str(box.id), "number": box.container_number, "type": label} for box, label in boxes.values()]
    options.sort(key=lambda row: (row["number"], row["id"]))
    selected = boxes.get(container_id) if container_id else None
    if template == "debit-note":
        if container_id is None and len(boxes) == 1:
            selected = next(iter(boxes.values()))
        if selected is None:
            raise ValidationFailed("Select one billed actual container by its ID; container type alone is not sufficient.")
        lines = [line for line in lines if line.service_order_container_id == selected[0].id]
        totals = _totals(lines)
    gross, discount, tax, total = totals
    order_ids = {line.service_order_id or document.service_order_id for line in lines} - {None}
    order = await session.get(ServiceOrder, next(iter(order_ids))) if len(order_ids) == 1 else None
    shipment_data = order.data or {} if order else {}
    keys = {
        "houseNo": "houseNo", "masterNo": "masterNo", "blNo": "blNo", "loadingPort": "loadingPort",
        "dischargePort": "dischargePort", "etd": "etd", "eta": "eta", "vessel": "vessel", "voyage": "voyage",
        "shipper": "shipper", "consignee": "consignee", "notifyParty": "notifyParty",
    }
    shipment = {key: _text(shipment_data.get(raw)) for key, raw in keys.items()}
    shipment.update({
        "workNo": order.service_order_no if order else "", "containerNo": selected[0].container_number if selected else "",
        "containerType": selected[1] if selected else "", "packageQty": "", "packageUnit": "",
    })
    issuer, warnings = await _issuer(session)
    account = await session.get(FinancialAccount, document.financial_account_id) if document.financial_account_id else None
    if account is None:
        accounts = (await session.execute(select(FinancialAccount).where(
            FinancialAccount.status == "ACTIVE", FinancialAccount.account_type == "BANK",
            FinancialAccount.currency_code == document.currency_code,
        ))).scalars().all()
        account = accounts[0] if len(accounts) == 1 else None
    rates = {line.tax_rate for line in lines}
    tax_rate = next(iter(rates)) if len(rates) == 1 else ZERO
    tax_invoice = (document.data or {}).get("documentTypeCode") == "TAX_INVOICE"
    return {
        "containers": options, "selectedContainerId": str(selected[0].id) if selected else "",
        "taxInvoiceEligible": tax_invoice, "warnings": warnings,
        "model": {
            "templateId": template, "precision": precision, "isContainerBreakdown": selected is not None,
            "issuer": issuer, "party": _party(party),
            "document": {
                "number": document.document_no, "documentType": document.document_type,
                "titleKey": "freight.print.title.taxInvoice" if tax_invoice else "freight.print.title.invoice",
                "issueDate": document.document_date.isoformat(), "dueDate": document.due_date.isoformat() if document.due_date else "",
                "currency": document.currency_code, "status": document.status, "remarks": document.description or "",
                "personInCharge": "", "exchangeRate": str(document.exchange_rate),
            },
            "shipment": shipment,
            "lines": [{
                "no": n + 1, "reference": shipment["blNo"] or shipment["workNo"], "description": line.description or "",
                "descriptionKh": "", "quantity": str(line.quantity), "unit": "", "unitPrice": str(line.unit_price),
                "currency": document.currency_code, "debit": str(line.line_amount), "credit": "0",
                "amount": str(line.line_amount + line.discount_amount - line.tax_amount),
            } for n, line in enumerate(lines)],
            "totals": {
                "currency": document.currency_code, "subtotal": str(gross), "discount": str(discount),
                "taxableAmount": str(gross - discount), "taxRate": str(tax_rate), "taxAmount": str(tax),
                "grandTotal": str(total), "totalDebit": str(total), "totalCredit": "0", "balance": str(total),
                # Never reinterpret the stored base conversion as today's local/KHR exchange rate.
                "localCurrency": document.base_currency_code or document.currency_code,
                "localPrecision": currency_precision(base_currency.decimal_places),
                "exchangeRate": str(document.exchange_rate),
                "grandTotalLocal": str(document.base_total_amount or ZERO) if not selected else "0",
                "outstanding": str(document.total_amount - document.paid_amount),
            },
            "settlement": {
                "accountName": account.account_name if account else "", "accountAddress": "",
                "bankName": account.bank_name or "" if account else "",
                "accountNumber": account.account_number_masked or "" if account else "", "swiftCode": "",
            },
            "signatures": {key: _text((document.data or {}).get(key)) for key in ("customerSignatureUrl", "customerStampUrl", "sellerSignatureUrl", "sellerStampUrl")},
            "watermark": "DRAFT" if document.status == "DRAFT" else None, "amountInWords": "",
        },
    }

