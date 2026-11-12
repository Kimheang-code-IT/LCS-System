"""Accounting bootstrap data: chart of accounts, financial accounts, posting rules.

Insert-missing only, like the rest of the seeder. The chart is the small,
standard freight-forwarding set the posting engine's legacy defaults expect
(1010, 1020, 1100, 2010, 4010, 4020, 5010, 5030), plus the tax and equity
accounts needed for a complete set of books. Administrators may rename, add or
deactivate rows afterwards; a re-run never overwrites them.

Posting rules are seeded only when a document type has no active
document-default rule (``fee_type_id IS NULL``). A rule the administrator
configured is therefore never replaced.
"""

from __future__ import annotations

CHART_OF_ACCOUNTS: tuple[dict[str, object], ...] = (
    # Assets
    {"account_code": "1000", "account_name": "Current Assets", "account_type": "ASSET", "normal_balance": "DEBIT", "postable": False, "parent_code": None},
    {"account_code": "1010", "account_name": "Cash on Hand", "account_type": "ASSET", "normal_balance": "DEBIT", "postable": True, "parent_code": "1000"},
    {"account_code": "1020", "account_name": "Bank - Operating", "account_type": "ASSET", "normal_balance": "DEBIT", "postable": True, "parent_code": "1000"},
    {"account_code": "1030", "account_name": "Bank - Savings", "account_type": "ASSET", "normal_balance": "DEBIT", "postable": True, "parent_code": "1000"},
    {"account_code": "1100", "account_name": "Accounts Receivable", "account_type": "ASSET", "normal_balance": "DEBIT", "postable": True, "parent_code": "1000"},
    {"account_code": "1200", "account_name": "Prepaid Expenses", "account_type": "ASSET", "normal_balance": "DEBIT", "postable": True, "parent_code": "1000"},
    {"account_code": "1300", "account_name": "VAT Input", "account_type": "ASSET", "normal_balance": "DEBIT", "postable": True, "parent_code": "1000"},
    {"account_code": "1400", "account_name": "Employee Advances", "account_type": "ASSET", "normal_balance": "DEBIT", "postable": True, "parent_code": "1000"},
    {"account_code": "1500", "account_name": "Fixed Assets", "account_type": "ASSET", "normal_balance": "DEBIT", "postable": False, "parent_code": "1000"},
    {"account_code": "1510", "account_name": "Equipment", "account_type": "ASSET", "normal_balance": "DEBIT", "postable": True, "parent_code": "1500"},
    # Liabilities
    {"account_code": "2000", "account_name": "Current Liabilities", "account_type": "LIABILITY", "normal_balance": "CREDIT", "postable": False, "parent_code": None},
    {"account_code": "2010", "account_name": "Accounts Payable", "account_type": "LIABILITY", "normal_balance": "CREDIT", "postable": True, "parent_code": "2000"},
    {"account_code": "2100", "account_name": "Accrued Expenses", "account_type": "LIABILITY", "normal_balance": "CREDIT", "postable": True, "parent_code": "2000"},
    {"account_code": "2200", "account_name": "VAT Output", "account_type": "LIABILITY", "normal_balance": "CREDIT", "postable": True, "parent_code": "2000"},
    {"account_code": "2300", "account_name": "Customer Advances", "account_type": "LIABILITY", "normal_balance": "CREDIT", "postable": True, "parent_code": "2000"},
    {"account_code": "2400", "account_name": "Payroll Liabilities", "account_type": "LIABILITY", "normal_balance": "CREDIT", "postable": True, "parent_code": "2000"},
    # Equity
    {"account_code": "3000", "account_name": "Equity", "account_type": "EQUITY", "normal_balance": "CREDIT", "postable": False, "parent_code": None},
    {"account_code": "3100", "account_name": "Owner's Capital", "account_type": "EQUITY", "normal_balance": "CREDIT", "postable": True, "parent_code": "3000"},
    {"account_code": "3200", "account_name": "Retained Earnings", "account_type": "EQUITY", "normal_balance": "CREDIT", "postable": True, "parent_code": "3000"},
    # Revenue
    {"account_code": "4000", "account_name": "Revenue", "account_type": "REVENUE", "normal_balance": "CREDIT", "postable": False, "parent_code": None},
    {"account_code": "4010", "account_name": "Freight and Service Revenue", "account_type": "REVENUE", "normal_balance": "CREDIT", "postable": True, "parent_code": "4000"},
    {"account_code": "4020", "account_name": "Other Income", "account_type": "REVENUE", "normal_balance": "CREDIT", "postable": True, "parent_code": "4000"},
    # Expenses
    {"account_code": "5000", "account_name": "Expenses", "account_type": "EXPENSE", "normal_balance": "DEBIT", "postable": False, "parent_code": None},
    {"account_code": "5010", "account_name": "Cost of Services", "account_type": "EXPENSE", "normal_balance": "DEBIT", "postable": True, "parent_code": "5000"},
    {"account_code": "5020", "account_name": "Salaries and Wages", "account_type": "EXPENSE", "normal_balance": "DEBIT", "postable": True, "parent_code": "5000"},
    {"account_code": "5030", "account_name": "Other Expenses", "account_type": "EXPENSE", "normal_balance": "DEBIT", "postable": True, "parent_code": "5000"},
    {"account_code": "5040", "account_name": "Bank Charges", "account_type": "EXPENSE", "normal_balance": "DEBIT", "postable": True, "parent_code": "5000"},
    {"account_code": "5050", "account_name": "Rent and Utilities", "account_type": "EXPENSE", "normal_balance": "DEBIT", "postable": True, "parent_code": "5000"},
    {"account_code": "5060", "account_name": "Professional Fees", "account_type": "EXPENSE", "normal_balance": "DEBIT", "postable": True, "parent_code": "5000"},
    {"account_code": "5070", "account_name": "Travel and Transport", "account_type": "EXPENSE", "normal_balance": "DEBIT", "postable": True, "parent_code": "5000"},
    {"account_code": "5080", "account_name": "Depreciation", "account_type": "EXPENSE", "normal_balance": "DEBIT", "postable": True, "parent_code": "5000"},
    {"account_code": "5090", "account_name": "Taxes and Licenses", "account_type": "EXPENSE", "normal_balance": "DEBIT", "postable": True, "parent_code": "5000"},
)

#: One settlement account per ledger account (unique ledger link). The base
#: currency follows the application default; more accounts can be added in
#: Financial Accounts when the company banks in other currencies.
FINANCIAL_ACCOUNTS: tuple[dict[str, object], ...] = (
    {
        "ledger_code": "1020",
        "account_name": "Bank - Operating (USD)",
        "account_type": "BANK",
        "currency": "USD",
        "bank_name": "Main Bank",
        "account_number_masked": "**** 0001",
    },
    {
        "ledger_code": "1010",
        "account_name": "Cash on Hand (USD)",
        "account_type": "CASH",
        "currency": "USD",
        "bank_name": None,
        "account_number_masked": None,
    },
)

#: One document-default rule per financial document type. The posting engine
#: resolves the control rule by document type, then each detail line falls back
#: to this same rule when no fee-specific rule exists.
POSTING_RULES: tuple[dict[str, object], ...] = (
    {
        "document_type": "CUSTOMER_INVOICE",
        "debit_code": "1100",
        "credit_code": "4010",
        "tax_code": "2200",
        "description": "Customer invoice: receivable control, freight/service revenue, output VAT.",
    },
    {
        "document_type": "CREDIT_NOTE",
        "debit_code": "4010",
        "credit_code": "1100",
        "tax_code": "2200",
        "description": "Customer credit note: mirrors the invoice.",
    },
    {
        "document_type": "SUPPLIER_BILL",
        "debit_code": "5010",
        "credit_code": "2010",
        "tax_code": "1300",
        "description": "Supplier bill: cost of services, payable control, input VAT.",
    },
    {
        "document_type": "SUPPLIER_CREDIT_NOTE",
        "debit_code": "2010",
        "credit_code": "5010",
        "tax_code": "1300",
        "description": "Supplier credit note: mirrors the bill.",
    },
    {
        "document_type": "CUSTOMER_RECEIPT",
        "debit_code": "1020",
        "credit_code": "1100",
        "tax_code": None,
        "description": "Customer receipt: bank, receivable control.",
    },
    {
        "document_type": "SUPPLIER_PAYMENT",
        "debit_code": "2010",
        "credit_code": "1020",
        "tax_code": None,
        "description": "Supplier payment: payable control, bank.",
    },
    {
        "document_type": "OTHER_INCOME",
        "debit_code": "1020",
        "credit_code": "4020",
        "tax_code": None,
        "description": "Other income: bank, other income.",
    },
    {
        "document_type": "OTHER_EXPENSE",
        "debit_code": "5030",
        "credit_code": "1020",
        "tax_code": None,
        "description": "Other expense: other expenses, bank.",
    },
    {
        "document_type": "TRANSFER",
        "debit_code": "1020",
        "credit_code": "1010",
        "tax_code": None,
        "description": "Transfer between own cash and bank accounts.",
    },
    {
        "document_type": "ADJUSTMENT",
        "debit_code": "5030",
        "credit_code": "1020",
        "tax_code": None,
        "description": "Manual adjustment: other expenses, bank.",
    },
)
