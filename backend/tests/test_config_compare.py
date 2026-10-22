"""Pure snapshot comparison rules used by the version-history screen.

Identity is the stable id, so a reordered group must not be reported as a
removal plus an addition. The endpoint test covers the wiring; this module pins
the detailed change categories.
"""

from __future__ import annotations

from app.modules.master_data.config_compare import compare_snapshots


def _attribute(code: str, **overrides) -> dict:
    return {
        "id": f"attr-{code}",
        "code": code,
        "label": code.replace("_", " ").title(),
        "dataType": "text",
        "isRequired": False,
        "isVisible": True,
        "displayOrder": 10,
        **overrides,
    }


def _group(code: str, attributes: list[dict], **overrides) -> dict:
    return {
        "id": f"group-{code}",
        "code": code,
        "name": code.title(),
        "renderMode": "table",
        "displayOrder": 10,
        "attributes": attributes,
        "displayMode": "table_only",
        "dataCardinality": "multiple",
        "formColumns": 3,
        "showGroupTitle": True,
        "editable": True,
        "collapsible": False,
        "defaultExpanded": True,
        **overrides,
    }


def _snapshot(tabs: list[dict]) -> dict:
    return {"tabs": tabs}


def test_compare_matches_objects_by_stable_id_not_position() -> None:
    first = _group("first", [_attribute("seal_no"), _attribute("marks")])
    second = _group("second", [_attribute("weight", dataType="decimal")])
    before = _snapshot([{
        "id": "tab-1",
        "code": "CUSTOMS",
        "name": "Customs",
        "displayOrder": 10,
        "groups": [first, second],
    }])
    after = _snapshot([{
        "id": "tab-1",
        "code": "CUSTOMS",
        "name": "Customs",
        "displayOrder": 10,
        "groups": [second, first],
    }])

    changes = compare_snapshots(before, after)
    assert changes["summary"]["addedGroups"] == 0
    assert changes["summary"]["removedGroups"] == 0
    assert changes["summary"]["changedGroupOrdering"] == 1
    assert changes["unchanged"] is False


def test_compare_reports_renames_types_rules_and_layout_changes() -> None:
    before = _snapshot([{
        "id": "tab-1",
        "code": "CUSTOMS",
        "name": "Customs",
        "displayOrder": 10,
        "groups": [_group("customs", [_attribute("declaration_no")])],
    }])
    after = _snapshot([{
        "id": "tab-1",
        "code": "CUSTOMS",
        "name": "Customs Desk",
        "displayOrder": 10,
        "groups": [_group(
            "customs",
            [_attribute("declaration_no", label="Declaration Number", dataType="number", isRequired=True, isVisible=False)],
            name="Customs Group",
            displayMode="form_and_table",
            dataCardinality="single",
            formColumns=2,
        )],
    }])

    changes = compare_snapshots(before, after)
    summary = changes["summary"]
    assert summary["renamedTabs"] == 1
    assert summary["renamedGroups"] == 1
    assert summary["renamedAttributes"] == 1
    assert summary["changedFieldTypes"] == 1
    assert summary["changedRequiredRules"] == 1
    assert summary["changedDisplayModes"] == 1
    # formColumns, dataCardinality and isVisible each differ.
    assert summary["changedLayouts"] == 3

    assert changes["tabs"]["renamed"][0]["after"]["name"] == "Customs Desk"
    assert changes["attributes"]["changedFieldTypes"][0]["after"] == "number"
    assert changes["attributes"]["changedRequiredRules"][0]["after"] is True
    assert changes["layouts"]["changedDisplayModes"][0]["after"] == "form_and_table"


def test_identical_snapshots_compare_as_unchanged() -> None:
    snapshot = _snapshot([{
        "id": "tab-1",
        "code": "CUSTOMS",
        "name": "Customs",
        "displayOrder": 10,
        "groups": [_group("customs", [_attribute("declaration_no")])],
    }])
    changes = compare_snapshots(snapshot, snapshot)
    assert changes["unchanged"] is True
    assert all(value == 0 for value in changes["summary"].values())
