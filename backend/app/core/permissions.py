"""Permission catalog, role-matrix metadata and the role seed definitions.

A permission code is ``<module>.<action>`` or ``<module>.<resource>.<action>``.
Casbin stores it split at the last dot as ``obj = <module>[.<resource>]`` and
``act = <action>``; this module only owns the *vocabulary* — it never decides
whether a subject holds a code. Casbin is the single authorization engine (see
``app/core/authorization``).

Three groups of codes exist:

* **Source permissions** — what an API route guard checks (``quotation.read``).
* **Matrix page permissions** — what the Roles & Permissions screen stores for a
  page checkbox (``sales.quotations.view``).
* **Legacy page permissions** — codes written by earlier releases; kept in the
  catalog so existing role rows still validate, and mapped onto their modern
  action at write time.

``PAGE_PERMISSION_GRANTS`` is a *write-time compile* map: granting a page
checkbox also grants the API capabilities that page needs. It is applied once
when a role is saved (``compile_role_permissions``), never during a request —
so no request ever walks an implication graph.
"""

from __future__ import annotations

# --- Source (API) permissions -------------------------------------------------
# (code, resource, action)
SOURCE_PERMISSIONS: tuple[tuple[str, str, str], ...] = (
    ("user.read", "user", "read"),
    ("user.manage", "user", "manage"),
    ("role.read", "role", "read"),
    ("role.manage", "role", "manage"),
    ("quotation.read", "quotation", "read"),
    ("quotation.create", "quotation", "create"),
    ("quotation.update_draft", "quotation", "update_draft"),
    ("quotation.send", "quotation", "send"),
    ("quotation.accept", "quotation", "accept"),
    ("quotation.convert", "quotation", "convert"),
    ("quotation.update", "quotation", "update"),
    ("quotation.delete", "quotation", "delete"),
    ("quotation.submit", "quotation", "submit"),
    ("quotation.revise", "quotation", "revise"),
    ("service_order.read", "service_order", "read"),
    ("service_order.create", "service_order", "create"),
    ("service_order.update", "service_order", "update"),
    ("service_order.complete", "service_order", "complete"),
    ("service_order.delete", "service_order", "delete"),
    ("service_order.submit", "service_order", "submit"),
    ("service_order_config.view", "service_order_config", "view"),
    ("service_order_config.create", "service_order_config", "create"),
    ("service_order_config.update", "service_order_config", "update"),
    ("service_order_config.delete", "service_order_config", "delete"),
    ("service_order_config.publish", "service_order_config", "publish"),
    ("configuration.read", "configuration", "read"),
    ("configuration.manage", "configuration", "manage"),
    ("configuration.publish", "configuration", "publish"),
    ("configuration.activate", "configuration", "activate"),
    ("configuration.rollback", "configuration", "rollback"),
    ("configuration.compare", "configuration", "compare"),
    ("service_charge.read", "service_charge", "read"),
    ("service_charge.create", "service_charge", "create"),
    ("service_charge.issue", "service_charge", "issue"),
    ("service_charge.convert_to_invoice", "service_charge", "convert_to_invoice"),
    ("service_charge.update", "service_charge", "update"),
    ("service_charge.delete", "service_charge", "delete"),
    ("service_charge.submit", "service_charge", "submit"),
    ("financial_document.read", "financial_document", "read"),
    ("financial_document.create", "financial_document", "create"),
    ("financial_document.update_draft", "financial_document", "update_draft"),
    ("financial_document.post", "financial_document", "post"),
    ("financial_document.reverse", "financial_document", "reverse"),
    ("financial_document.allocate", "financial_document", "allocate"),
    ("financial_document.update", "financial_document", "update"),
    ("financial_document.delete", "financial_document", "delete"),
    ("financial_document.submit", "financial_document", "submit"),
    ("journal_entry.read", "journal_entry", "read"),
    ("journal_entry.create", "journal_entry", "create"),
    ("journal_entry.post", "journal_entry", "post"),
    ("journal_entry.update", "journal_entry", "update"),
    ("journal_entry.delete", "journal_entry", "delete"),
    ("accounting_period.read", "accounting_period", "read"),
    ("accounting_period.close", "accounting_period", "close"),
    ("accounting_period.update", "accounting_period", "update"),
    ("chart_of_accounts.manage", "chart_of_accounts", "manage"),
    ("chart_of_accounts.read", "chart_of_accounts", "read"),
    ("chart_of_accounts.create", "chart_of_accounts", "create"),
    ("chart_of_accounts.update", "chart_of_accounts", "update"),
    ("chart_of_accounts.delete", "chart_of_accounts", "delete"),
    ("financial_account.read", "financial_account", "read"),
    ("financial_account.create", "financial_account", "create"),
    ("financial_account.update", "financial_account", "update"),
    ("financial_account.delete", "financial_account", "delete"),
    ("posting_rule.read", "posting_rule", "read"),
    ("posting_rule.manage", "posting_rule", "manage"),
    ("posting_rule.create", "posting_rule", "create"),
    ("posting_rule.update", "posting_rule", "update"),
    ("posting_rule.delete", "posting_rule", "delete"),
    ("customs_credential.retrieve", "customs_credential", "retrieve"),
    ("attachment.read", "attachment", "read"),
    ("attachment.upload", "attachment", "upload"),
    ("attachment.delete", "attachment", "delete"),
    ("audit_log.read", "audit_log", "read"),
    ("archive.view", "archive", "view"),
    ("archive.restore", "archive", "restore"),
    ("archive.hard_delete", "archive", "hard_delete"),
    ("report.read", "report", "read"),
    ("report.export", "report", "export"),
    ("dashboard.summary", "dashboard", "summary"),
    ("document_sequence.read", "document_sequence", "read"),
    ("document_sequence.create", "document_sequence", "create"),
    ("document_sequence.update", "document_sequence", "update"),
    ("document_sequence.delete", "document_sequence", "delete"),
    ("master.reference.view", "master", "view"),
    ("master.reference.manage", "master", "manage"),
    ("settings.manage", "settings", "manage"),
    ("backup.read", "backup", "read"),
    ("backup.manage", "backup", "manage"),
)

# --- Matrix pages -------------------------------------------------------------
# One row per screen in the Roles & Permissions matrix. ``value`` is the stable
# document-type id the frontend used historically; ``prefix`` builds the page
# permission codes. ``label_key`` points at the existing i18n key so the matrix
# keeps its translations.
CRUD_ACTIONS = ("view", "create", "update", "delete", "export")
READ_ACTIONS = ("view", "export")
DOCUMENT_ACTIONS = ("view", "create", "update", "delete", "submit", "export")
QUOTATION_ACTIONS = ("view", "create", "update", "delete", "submit", "re_quotation", "quotation", "export")

PageDefinition = tuple[str, str, str, str, tuple[str, ...]]  # value, group, prefix, label_key, actions

MATRIX_PAGES: tuple[PageDefinition, ...] = (
    ("dashboard", "dashboard", "dashboard", "freight.pages.dashboard", ("view", "export", "summary")),
    ("sales_quotations", "sales", "sales.quotations", "freight.pages.quotations", QUOTATION_ACTIONS),
    ("operations_service_orders", "operations", "operations.service_orders", "freight.pages.serviceOrders", DOCUMENT_ACTIONS),
    ("reports_service_order_register", "operations", "reports.service_order_register", "freight.reportCatalog.reports.service-orders.title", READ_ACTIONS),
    ("reports_service_order_status", "operations", "reports.service_order_status", "freight.reportCatalog.reports.service-order-status.title", READ_ACTIONS),
    ("reports_service_order_containers", "operations", "reports.service_order_containers", "freight.reportCatalog.reports.containers.title", READ_ACTIONS),
    ("reports_service_order_profitability", "operations", "reports.service_order_profitability", "freight.reportCatalog.reports.profitability.title", READ_ACTIONS),
    ("finance_service_charges", "finance", "finance.service_charges", "freight.pages.serviceCharges", DOCUMENT_ACTIONS),
    ("finance_financial_documents", "finance", "finance.financial_documents", "freight.pages.financialDocuments", DOCUMENT_ACTIONS),
    ("finance_chart_of_accounts", "finance", "finance.chart_of_accounts", "freight.pages.chartOfAccounts", CRUD_ACTIONS),
    ("finance_financial_accounts", "finance", "finance.financial_accounts", "freight.pages.financialAccounts", CRUD_ACTIONS),
    ("finance_journal_entries", "finance", "finance.journal_entries", "freight.pages.journals", CRUD_ACTIONS),
    ("finance_accounting_periods", "finance", "finance.accounting_periods", "freight.pages.accountingPeriods", ("view", "update", "export")),
    ("finance_posting_rules", "finance", "finance.posting_rules", "freight.pages.postingRules", CRUD_ACTIONS),
    ("reports_revenue_expense", "reports", "reports.revenue_expense", "freight.reportCatalog.reports.revenue-expense.title", READ_ACTIONS),
    ("reports_accounts_receivable", "reports", "reports.accounts_receivable", "freight.reportCatalog.reports.accounts-receivable.title", READ_ACTIONS),
    ("reports_accounts_payable", "reports", "reports.accounts_payable", "freight.reportCatalog.reports.accounts-payable.title", READ_ACTIONS),
    ("reports_general_ledger", "reports", "reports.general_ledger", "freight.reportCatalog.reports.general-ledger.title", READ_ACTIONS),
    ("reports_trial_balance", "reports", "reports.trial_balance", "freight.reportCatalog.reports.trial-balance.title", READ_ACTIONS),
    ("reports_profit_loss", "reports", "reports.profit_loss", "freight.reportCatalog.reports.profit-loss.title", READ_ACTIONS),
    ("reports_balance_sheet", "reports", "reports.balance_sheet", "freight.reportCatalog.reports.balance-sheet.title", READ_ACTIONS),
    ("reports_cash_flow", "reports", "reports.cash_flow", "freight.reportCatalog.reports.cash-flow.title", READ_ACTIONS),
    ("master_business_parties", "master", "master.business_parties", "freight.pages.businessParties", CRUD_ACTIONS),
    ("master_party_roles", "master", "master.party_roles", "freight.pages.partyRoles", CRUD_ACTIONS),
    ("master_place_roles", "master", "master.place_roles", "freight.pages.placeRoles", CRUD_ACTIONS),
    ("master_trade_directions", "master", "master.trade_directions", "freight.pages.tradeDirections", CRUD_ACTIONS),
    ("master_container_types", "master", "master.container_types", "freight.pages.containerTypes", CRUD_ACTIONS),
    ("master_transport_types", "master", "master.transport_types", "freight.pages.transportTypes", CRUD_ACTIONS),
    ("master_transport_assets", "master", "master.transport_assets", "freight.pages.transportAssets", CRUD_ACTIONS),
    ("master_fee_types", "master", "master.fee_types", "freight.pages.feeTypes", CRUD_ACTIONS),
    ("master_currencies", "master", "master.currencies", "freight.pages.currencies", CRUD_ACTIONS),
    ("configuration", "configuration", "configuration", "freight.nav.configuration", ("view", "create", "update", "delete", "export")),
    ("admin_document_sequences", "admin", "admin.document_sequences", "freight.pages.documentSequences", CRUD_ACTIONS),
    ("admin_users", "admin", "admin.users", "freight.pages.users", CRUD_ACTIONS),
    ("admin_roles", "admin", "admin.roles", "freight.pages.roles", CRUD_ACTIONS),
    ("admin_audit_logs", "admin", "admin.audit_logs", "freight.pages.auditLogs", READ_ACTIONS),
    ("admin_archive", "admin", "admin.archive", "freight.pages.archive", ("view", "export", "restore")),
    ("settings_app_config", "settings", "settings.app_config", "freight.pages.settings", ("view", "update")),
    ("settings_backup", "settings", "settings.backup", "freight.pages.backup", ("view", "create", "update")),
)

PAGE_PERMISSIONS: tuple[tuple[str, str, str], ...] = tuple(
    (f"{prefix}.{action}", prefix, action)
    for _value, _group, prefix, _label, actions in MATRIX_PAGES
    for action in actions
)

#: Legacy page codes. They remain valid (an existing role row may hold them) and
#: the matrix folds them onto the modern action; they are not offered as new
#: checkboxes.
LEGACY_PAGE_PERMISSIONS: tuple[tuple[str, str, str], ...] = tuple(
    (f"{prefix}.{action}", prefix, action)
    for prefix, action in (
        ("sales.quotations", "edit"),
        ("operations.service_orders", "edit"),
        ("finance.service_charges", "edit"),
        ("finance.financial_documents", "edit"),
        ("finance.accounting", "view"),
        ("finance.accounting", "create"),
        ("finance.accounting", "edit"),
        ("finance.accounting", "delete"),
        ("finance.accounting", "export"),
        ("finance.posting_rules", "edit"),
        ("operations.reports", "view"),
        ("operations.reports", "export"),
        ("finance.reports", "view"),
        ("finance.reports", "export"),
        ("master.reference", "view"),
        ("master.reference", "create"),
        ("master.reference", "edit"),
        ("master.reference", "delete"),
        ("master.reference", "export"),
        ("configuration", "edit"),
        ("admin.document_sequences", "edit"),
        ("admin.users", "edit"),
        ("admin.roles", "edit"),
        ("admin.archive", "edit"),
        ("admin.archive", "delete"),
        ("settings.app_config", "edit"),
        ("settings.backup", "edit"),
    )
)

#: Navigation codes whose page is served by the generic record or report API.
#: A role needs them for the menu entry to resolve; the matrix grants them
#: together with the page row.
NAVIGATION_PAGE_PERMISSIONS: tuple[tuple[str, str, str], ...] = tuple(
    (code, code.rsplit(".", 1)[0], code.rsplit(".", 1)[-1])
    for code in (
        "sales.companies.view",
        "operations.jobs.view",
        "operations.shipments.view",
        "operations.customs.view",
        "operations.documents.view",
        "operations.deliveries.view",
        "finance.debit_notes.view",
        "finance.customer_payments.view",
        "finance.job_charges.view",
        "finance.supplier_costs.view",
        "finance.supplier_payments.view",
        "reports.view",
        "finance.accounts_receivable.view",
        "finance.accounts_payable.view",
        "finance.job_profitability.view",
        "settings.manage",
        "admin.user_manage",
        "admin.role_manage",
        "configuration.configure",
    )
)

# --- Page -> API capability grants (write-time compile only) ------------------
# An empty tuple means the page code is itself the capability.
PAGE_PERMISSION_GRANTS: dict[str, tuple[str, ...]] = {
    "dashboard.view": (),
    "dashboard.export": ("report.export",),
    "dashboard.summary": (),

    "sales.quotations.view": ("quotation.read",),
    "sales.quotations.create": ("quotation.create",),
    "sales.quotations.update": ("quotation.update", "quotation.update_draft", "quotation.accept", "quotation.convert"),
    "sales.quotations.delete": ("quotation.delete",),
    "sales.quotations.submit": ("quotation.submit", "quotation.send"),
    "sales.quotations.re_quotation": ("quotation.revise",),
    "sales.quotations.quotation": ("quotation.send",),
    "sales.quotations.export": ("report.export",),

    "operations.service_orders.view": ("service_order.read",),
    "operations.service_orders.create": ("service_order.create",),
    "operations.service_orders.update": ("service_order.update", "service_order.complete"),
    "operations.service_orders.delete": ("service_order.delete",),
    "operations.service_orders.submit": ("service_order.submit",),
    "operations.service_orders.export": ("report.export",),

    "finance.service_charges.view": ("service_charge.read", "financial_document.read"),
    "finance.service_charges.create": ("service_charge.create", "financial_document.create"),
    "finance.service_charges.update": (
        "service_charge.update",
        "service_charge.convert_to_invoice",
        "financial_document.update",
        "financial_document.update_draft",
        "financial_document.allocate",
    ),
    "finance.service_charges.delete": ("service_charge.delete", "financial_document.delete"),
    "finance.service_charges.submit": (
        "service_charge.submit",
        "service_charge.issue",
        "financial_document.submit",
        "financial_document.post",
        "financial_document.reverse",
    ),
    "finance.service_charges.export": ("report.export",),

    "finance.financial_documents.view": ("financial_document.read",),
    "finance.financial_documents.create": ("financial_document.create",),
    "finance.financial_documents.update": (
        "financial_document.update",
        "financial_document.update_draft",
        "financial_document.allocate",
        "financial_document.reverse",
    ),
    "finance.financial_documents.delete": ("financial_document.delete",),
    "finance.financial_documents.submit": ("financial_document.submit", "financial_document.post"),
    "finance.financial_documents.export": ("report.export",),

    "finance.chart_of_accounts.view": ("chart_of_accounts.read",),
    "finance.chart_of_accounts.create": ("chart_of_accounts.create", "chart_of_accounts.manage"),
    "finance.chart_of_accounts.update": ("chart_of_accounts.update", "chart_of_accounts.manage"),
    "finance.chart_of_accounts.delete": ("chart_of_accounts.delete", "chart_of_accounts.manage"),
    "finance.chart_of_accounts.export": ("report.export",),

    "finance.financial_accounts.view": ("financial_account.read",),
    "finance.financial_accounts.create": ("financial_account.create",),
    "finance.financial_accounts.update": ("financial_account.update",),
    "finance.financial_accounts.delete": ("financial_account.delete",),
    "finance.financial_accounts.export": ("report.export",),

    "finance.journal_entries.view": ("journal_entry.read",),
    "finance.journal_entries.create": ("journal_entry.create",),
    "finance.journal_entries.update": ("journal_entry.update", "journal_entry.post"),
    "finance.journal_entries.delete": ("journal_entry.delete",),
    "finance.journal_entries.export": ("report.export",),

    "finance.accounting_periods.view": ("accounting_period.read",),
    "finance.accounting_periods.update": ("accounting_period.update", "accounting_period.close"),
    "finance.accounting_periods.export": ("report.export",),

    "finance.posting_rules.view": ("posting_rule.read",),
    "finance.posting_rules.create": ("posting_rule.create", "posting_rule.manage"),
    "finance.posting_rules.update": ("posting_rule.update", "posting_rule.manage"),
    "finance.posting_rules.delete": ("posting_rule.delete", "posting_rule.manage"),
    "finance.posting_rules.export": ("report.export",),

    "master.business_parties.view": (),
    "master.business_parties.create": (),
    "master.business_parties.update": (),
    "master.business_parties.delete": (),
    "master.business_parties.export": ("report.export",),
    "master.place_roles.view": (),
    "master.place_roles.create": (),
    "master.place_roles.update": (),
    "master.place_roles.delete": (),
    "master.place_roles.export": ("report.export",),
    "master.party_roles.view": (),
    "master.party_roles.create": (),
    "master.party_roles.update": (),
    "master.party_roles.delete": (),
    "master.party_roles.export": ("report.export",),
    "master.trade_directions.view": (),
    "master.trade_directions.create": (),
    "master.trade_directions.update": (),
    "master.trade_directions.delete": (),
    "master.trade_directions.export": ("report.export",),
    "master.container_types.view": (),
    "master.container_types.create": (),
    "master.container_types.update": (),
    "master.container_types.delete": (),
    "master.container_types.export": ("report.export",),
    "master.transport_types.view": (),
    "master.transport_types.create": (),
    "master.transport_types.update": (),
    "master.transport_types.delete": (),
    "master.transport_types.export": ("report.export",),
    "master.transport_assets.view": (),
    "master.transport_assets.create": (),
    "master.transport_assets.update": (),
    "master.transport_assets.delete": (),
    "master.transport_assets.export": ("report.export",),
    "master.fee_types.view": (),
    "master.fee_types.create": (),
    "master.fee_types.update": (),
    "master.fee_types.delete": (),
    "master.fee_types.export": ("report.export",),
    "master.currencies.view": (),
    "master.currencies.create": (),
    "master.currencies.update": (),
    "master.currencies.delete": (),
    "master.currencies.export": ("report.export",),

    "configuration.view": ("configuration.read", "configuration.compare", "service_order_config.view"),
    # Each page action grants only the form-config capabilities it needs. None of
    # them grants ``configuration.manage``: that coarse code also opens every
    # generic master-data collection, the document sequences and the app-config
    # recovery screen, which is a different job from editing the form config.
    "configuration.create": ("service_order_config.create",),
    "configuration.update": (
        "configuration.configure",
        "configuration.publish",
        "configuration.activate",
        "configuration.rollback",
        "service_order_config.update",
        "service_order_config.publish",
    ),
    "configuration.delete": ("service_order_config.delete",),
    "configuration.export": ("report.export",),
    "configuration.edit": (
        "configuration.configure",
        "configuration.publish",
        "configuration.activate",
        "configuration.rollback",
        "service_order_config.create",
        "service_order_config.update",
        "service_order_config.delete",
        "service_order_config.publish",
    ),

    "admin.users.view": ("user.read",),
    "admin.users.create": ("user.manage",),
    "admin.users.update": ("user.manage",),
    "admin.users.delete": ("user.manage",),
    "admin.users.export": ("report.export",),
    "admin.users.edit": ("user.manage",),

    "admin.roles.view": ("role.read",),
    "admin.roles.create": ("role.manage",),
    "admin.roles.update": ("role.manage",),
    "admin.roles.delete": ("role.manage",),
    "admin.roles.export": ("report.export",),
    "admin.roles.edit": ("role.manage",),

    "admin.document_sequences.view": ("document_sequence.read",),
    "admin.document_sequences.create": ("document_sequence.create",),
    "admin.document_sequences.update": ("document_sequence.update",),
    "admin.document_sequences.delete": ("document_sequence.delete",),
    "admin.document_sequences.export": ("report.export",),
    "admin.document_sequences.edit": ("document_sequence.update",),

    "admin.audit_logs.view": ("audit_log.read",),
    "admin.audit_logs.export": ("report.export",),

    "admin.archive.view": ("archive.view",),
    "admin.archive.export": ("report.export",),
    "admin.archive.restore": ("archive.restore",),
    "admin.archive.edit": ("archive.restore",),
    "admin.archive.delete": ("archive.hard_delete",),

    "settings.app_config.view": (),
    "settings.app_config.update": (),
    "settings.app_config.edit": (),
    "settings.backup.view": ("backup.read",),
    "settings.backup.create": ("backup.manage",),
    "settings.backup.update": ("backup.manage",),
    "settings.backup.edit": ("backup.manage",),
}

_REPORT_PREFIXES = tuple(
    prefix for _value, _group, prefix, _label, _actions in MATRIX_PAGES if prefix.startswith("reports.")
)
_MASTER_PREFIXES = tuple(
    prefix for _value, _group, prefix, _label, _actions in MATRIX_PAGES if prefix.startswith("master.")
)

# Aggregate page rows: one checkbox that unlocks a whole family, kept for
# compatibility with roles saved by earlier releases.
PAGE_PERMISSION_GRANTS.update(
    {
        f"{prefix}.view": () for prefix in _REPORT_PREFIXES
    }
)
PAGE_PERMISSION_GRANTS.update(
    {
        **{f"{prefix}.export": ("report.export",) for prefix in _REPORT_PREFIXES},
        **{f"{prefix}.view": () for prefix in _MASTER_PREFIXES},
        **{f"{prefix}.create": () for prefix in _MASTER_PREFIXES},
        **{f"{prefix}.update": () for prefix in _MASTER_PREFIXES},
        **{f"{prefix}.delete": () for prefix in _MASTER_PREFIXES},
        **{f"{prefix}.export": ("report.export",) for prefix in _MASTER_PREFIXES},
        "master.reference.view": ("master.reference.view", *(f"{prefix}.view" for prefix in _MASTER_PREFIXES)),
        "master.reference.manage": (
            "master.reference.manage",
            *(
                f"{prefix}.{action}"
                for prefix in _MASTER_PREFIXES
                for action in ("create", "update", "delete")
            ),
        ),
        "operations.reports.view": tuple(f"{prefix}.view" for prefix in _REPORT_PREFIXES[:4]),
        "operations.reports.export": tuple(f"{prefix}.export" for prefix in _REPORT_PREFIXES[:4]),
        "finance.reports.view": tuple(f"{prefix}.view" for prefix in _REPORT_PREFIXES[4:]),
        "finance.reports.export": tuple(f"{prefix}.export" for prefix in _REPORT_PREFIXES[4:]),
        "finance.accounting.view": (
            "finance.chart_of_accounts.view",
            "finance.financial_accounts.view",
            "finance.journal_entries.view",
            "finance.accounting_periods.view",
        ),
        "finance.accounting.create": (
            "finance.chart_of_accounts.create",
            "finance.financial_accounts.create",
            "finance.journal_entries.create",
        ),
        "finance.accounting.edit": (
            "finance.chart_of_accounts.update",
            "finance.financial_accounts.update",
            "finance.journal_entries.update",
            "finance.accounting_periods.update",
        ),
        "finance.accounting.delete": (
            "finance.chart_of_accounts.delete",
            "finance.financial_accounts.delete",
            "finance.journal_entries.delete",
        ),
        "admin.user_manage": ("user.read", "user.manage", "admin.users.view", "admin.users.create", "admin.users.update", "admin.users.delete", "admin.users.edit"),
        "admin.role_manage": ("role.read", "role.manage", "admin.roles.view", "admin.roles.create", "admin.roles.update", "admin.roles.delete", "admin.roles.edit"),
        "configuration.configure": (
            "configuration.read",
            "configuration.compare",
            "configuration.publish",
            "configuration.activate",
            "configuration.rollback",
            "service_order_config.view",
            "service_order_config.update",
            "service_order_config.publish",
        ),
        "settings.manage": (
            "settings.app_config.view",
            "settings.app_config.update",
            "settings.app_config.edit",
            "settings.backup.view",
            "settings.backup.create",
            "settings.backup.update",
            "settings.backup.edit",
            "backup.read",
            "backup.manage",
        ),
        "reports.view": ("report.read", *(f"{prefix}.view" for prefix in _REPORT_PREFIXES)),
        "finance.accounts_receivable.view": ("reports.accounts_receivable.view",),
        "finance.accounts_payable.view": ("reports.accounts_payable.view",),
        "finance.job_profitability.view": ("reports.service_order_profitability.view",),
        "sales.companies.view": ("master.reference.view",),
        "operations.jobs.view": ("master.reference.view",),
        "operations.shipments.view": ("master.reference.view",),
        "operations.customs.view": ("master.reference.view",),
        "operations.documents.view": ("master.reference.view",),
        "operations.deliveries.view": ("master.reference.view",),
        "finance.debit_notes.view": ("master.reference.view",),
        "finance.customer_payments.view": ("master.reference.view",),
        "finance.job_charges.view": ("master.reference.view",),
        "finance.supplier_costs.view": ("master.reference.view",),
        "finance.supplier_payments.view": ("master.reference.view",),
    }
)

#: ``report.read`` / ``report.export`` are coarse capabilities that open the whole
#: report family. Applied at write time like every other grant.
PAGE_PERMISSION_GRANTS["report.read"] = tuple(f"{prefix}.view" for prefix in _REPORT_PREFIXES) + ("reports.view",)
PAGE_PERMISSION_GRANTS["report.export"] = tuple(f"{prefix}.export" for prefix in _REPORT_PREFIXES)

#: A document page carries the Files tab. Reading the record reads its files,
#: editing it lets an attachment be added, and deleting it lets one be removed.
#: Without this the attachment capabilities were reachable only from ADMIN.
for _document_prefix in (
    "sales.quotations",
    "operations.service_orders",
    "finance.service_charges",
    "finance.financial_documents",
):
    for _action, _capability in (
        ("view", "attachment.read"),
        ("update", "attachment.upload"),
        ("delete", "attachment.delete"),
    ):
        _page = f"{_document_prefix}.{_action}"
        if _page in PAGE_PERMISSION_GRANTS:
            PAGE_PERMISSION_GRANTS[_page] = (*PAGE_PERMISSION_GRANTS[_page], _capability)

# --- Catalog ------------------------------------------------------------------
def _dedupe(catalog: tuple[tuple[str, str, str], ...]) -> tuple[tuple[str, str, str], ...]:
    seen: set[str] = set()
    unique: list[tuple[str, str, str]] = []
    for item in catalog:
        if item[0] in seen:
            continue
        seen.add(item[0])
        unique.append(item)
    return tuple(unique)


PERMISSION_CATALOG: tuple[tuple[str, str, str], ...] = _dedupe(
    SOURCE_PERMISSIONS + PAGE_PERMISSIONS + LEGACY_PAGE_PERMISSIONS + NAVIGATION_PAGE_PERMISSIONS
)

ALL_PERMISSION_CODES = tuple(code for code, _, _ in PERMISSION_CATALOG)
SOURCE_PERMISSION_CODES = frozenset(code for code, _, _ in SOURCE_PERMISSIONS)
PAGE_PERMISSION_CODES = frozenset(
    code
    for code, _, _ in PAGE_PERMISSIONS + LEGACY_PAGE_PERMISSIONS + NAVIGATION_PAGE_PERMISSIONS
)


def permission_module(code: str) -> str:
    """Administration grouping key. Purely descriptive — never used to decide access."""
    return code.split(".", 1)[0]


def permission_name(code: str) -> str:
    return code.replace(".", " ").replace("_", " ").title()


#: Reverse of ``PAGE_PERMISSION_GRANTS``, used only when compiling a role so a
#: legacy source-only grant still renders as the page checkbox it used to unlock.
PAGE_CODES_BY_GRANTED: dict[str, tuple[str, ...]] = {}
for _page_code, _granted in PAGE_PERMISSION_GRANTS.items():
    for _source in _granted:
        if _page_code not in PAGE_CODES_BY_GRANTED.get(_source, ()):
            PAGE_CODES_BY_GRANTED[_source] = (*PAGE_CODES_BY_GRANTED.get(_source, ()), _page_code)


def compile_role_permissions(codes: tuple[str, ...] | list[str] | set[str]) -> frozenset[str]:
    """Close a set of role permissions over the page/capability graph.

    This runs **once when a role is saved**; Casbin then evaluates the resulting
    concrete codes. Nothing here is consulted on a request path.

    Expansion is one-directional and bounded:

    1. each selected page (or legacy aggregate) contributes the codes it declares;
    2. a declared page code contributes *its* codes — the legacy aggregates point
       at pages, so this second forward hop is needed, and it stops there;
    3. a capability contributes the page code that renders it in the matrix, but
       **only when that page grants nothing that is not already granted**.

    Rule 3 is what keeps a grant from widening an independent permission: adding
    the page for `quotation.read` would also have granted `attachment.read`, so the
    page is not added. It also makes the function idempotent — saving the same
    selection twice produces the same policy set.

    Nothing ever goes capability → page → capability. That loop let one read
    capability inherit the write capabilities of every page that also grants it: a
    read-only configuration viewer used to end up with full configuration write
    access, and a settings viewer with `backup.manage`.
    """
    granted: set[str] = {str(code) for code in codes if str(code).strip()}
    declared: set[str] = set()
    for code in granted:
        declared.update(PAGE_PERMISSION_GRANTS.get(code, ()))
    capabilities = set(declared)
    for code in declared & PAGE_PERMISSION_CODES:
        capabilities.update(PAGE_PERMISSION_GRANTS.get(code, ()))
    covered = granted | capabilities
    implied_pages: set[str] = set()
    for code in covered - PAGE_PERMISSION_CODES:
        for page in PAGE_CODES_BY_GRANTED.get(code, ()):
            if set(PAGE_PERMISSION_GRANTS.get(page, ())) <= covered:
                implied_pages.add(page)
                break
    return frozenset(covered | implied_pages)


#: Codes some page checkbox produces. A save therefore cannot tell a compiled code
#: from a chosen one unless it filters them out first.
#:
#: A code a page lists as *itself* is not counted: the legacy aggregates name their
#: own capability (`master.reference.manage`), and that capability has to survive a
#: rebuild as a deliberate grant.
DERIVED_PERMISSION_CODES = frozenset(
    granted
    for page_code, values in PAGE_PERMISSION_GRANTS.items()
    for granted in values
    if granted != page_code
)


def resolve_role_codes(codes: tuple[str, ...] | list[str] | set[str]) -> frozenset[str]:
    """Turn what an administrator submitted into the role's stored code set.

    A code compiled from a *selected* page is dropped and re-derived, otherwise
    unticking that page would leave its API capabilities behind. A code with no
    page behind it stays a deliberate grant.
    """
    submitted = {str(code).strip() for code in codes if str(code).strip()}
    if "*" in submitted:
        return frozenset({"*"})
    page_codes = submitted & PAGE_PERMISSION_CODES
    granted_by_pages = {
        code for page in page_codes for code in PAGE_PERMISSION_GRANTS.get(page, ())
    }
    explicit = submitted - page_codes - granted_by_pages
    return compile_role_permissions(page_codes | explicit)


# --- Roles --------------------------------------------------------------------
SUPER_ADMIN_ROLE = "SUPER_ADMIN"
SUPER_ADMIN_WILDCARD = ("*", "*")

PAGE_CODES_BY_PREFIX = {
    prefix: tuple(f"{prefix}.{action}" for action in actions)
    for _value, _group, prefix, _label, actions in MATRIX_PAGES
}


def _page_codes(*prefixes: str, actions: tuple[str, ...] | None = None) -> tuple[str, ...]:
    codes: list[str] = []
    for prefix in prefixes:
        allowed = PAGE_CODES_BY_PREFIX.get(prefix, ())
        for code in allowed:
            if actions is None or code.rsplit(".", 1)[-1] in actions:
                codes.append(code)
    return tuple(codes)


_OPERATIONS_REPORT_PREFIXES = tuple(prefix for prefix in _REPORT_PREFIXES[:4])
_FINANCE_REPORT_PREFIXES = tuple(prefix for prefix in _REPORT_PREFIXES[4:])
_MASTER_READ = _page_codes(*_MASTER_PREFIXES, actions=("view",))

ROLE_DEFINITIONS: dict[str, dict[str, object]] = {
    SUPER_ADMIN_ROLE: {
        "name": "Super Administrator",
        "description": "Unrestricted platform administration. Protected system role.",
        "permissions": (),  # wildcard, seeded directly as a Casbin policy
        "protects": True,
    },
    "ADMIN": {
        "name": "Administrator",
        "description": "System administration with the full permission catalog.",
        "permissions": ALL_PERMISSION_CODES,
    },
    "MANAGER": {
        "name": "Manager",
        "description": "Branch manager: operations, sales and finance visibility.",
        "permissions": (
            *_page_codes("dashboard"),
            *_page_codes("sales.quotations"),
            *_page_codes("operations.service_orders"),
            *_page_codes("finance.service_charges", "finance.financial_documents", actions=("view", "export")),
            *_page_codes("finance.chart_of_accounts", "finance.financial_accounts", "finance.journal_entries", "finance.accounting_periods", "finance.posting_rules", actions=("view", "export")),
            *_page_codes(*_REPORT_PREFIXES),
            "report.read",
            *_MASTER_READ,
            *_page_codes("admin.users", "admin.roles", actions=("view",)),
        ),
    },
    "SALES": {
        "name": "Sales Officer",
        "description": "Owns quotations and customer pricing.",
        "permissions": (
            *_page_codes("dashboard"),
            *_page_codes("sales.quotations"),
            *_page_codes("operations.service_orders", actions=("view",)),
            *_page_codes(*_REPORT_PREFIXES, actions=("view",)),
            *_MASTER_READ,
        ),
    },
    "OPERATIONS": {
        "name": "Operations Officer",
        "description": "Runs service orders, shipments and milestone updates.",
        "permissions": (
            *_page_codes("dashboard"),
            *_page_codes("operations.service_orders"),
            *_page_codes("sales.quotations", actions=("view",)),
            *_page_codes(*_OPERATIONS_REPORT_PREFIXES),
            *_MASTER_READ,
            "master.reference.view",
        ),
    },
    "ACCOUNTANT": {
        "name": "Accountant",
        "description": "Finance documents, journals, periods and financial reports.",
        "permissions": (
            *_page_codes("dashboard"),
            *_page_codes(
                "finance.service_charges",
                "finance.financial_documents",
                "finance.chart_of_accounts",
                "finance.financial_accounts",
                "finance.journal_entries",
                "finance.accounting_periods",
                "finance.posting_rules",
            ),
            *_page_codes(*_FINANCE_REPORT_PREFIXES),
            *_page_codes("operations.service_orders", actions=("view",)),
            *_page_codes("sales.quotations", actions=("view",)),
            *_MASTER_READ,
            "master.reference.view",
        ),
    },
    "VIEWER": {
        "name": "Viewer",
        "description": "Read-only access to business data and reports.",
        "permissions": (
            *_page_codes("dashboard", actions=("view",)),
            *_page_codes("sales.quotations", actions=("view",)),
            *_page_codes("operations.service_orders", actions=("view",)),
            *_page_codes(
                "finance.service_charges",
                "finance.financial_documents",
                "finance.chart_of_accounts",
                "finance.financial_accounts",
                "finance.journal_entries",
                "finance.accounting_periods",
                "finance.posting_rules",
                actions=("view",),
            ),
            *_page_codes(*_REPORT_PREFIXES, actions=("view",)),
            "report.read",
            *_MASTER_READ,
            "master.reference.view",
        ),
    },
}

BUILTIN_ROLE_CODES: tuple[str, ...] = tuple(ROLE_DEFINITIONS)
#: Roles a non-super administrator may never create, rename, modify or delete.
PROTECTED_ROLE_CODES = frozenset({SUPER_ADMIN_ROLE})
#: Every role is provisioned on startup so a fresh install has a usable matrix.
SEEDED_ROLE_CODES = tuple(code for code in ROLE_DEFINITIONS if code != SUPER_ADMIN_ROLE)

ALL_PAGES = ("ALL_PAGES",)
