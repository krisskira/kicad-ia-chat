from kicad_ia.agent.pcb_review import PcbReviewer
from kicad_ia.kicad.ipc import audit_placement, place_ipc, profile, safe_fixes
from kicad_ia.kicad.pcb_metrics import BoardSnapshot, better_than, score_routing


def test_profile_disclaimer():
    data = profile("2")
    assert "pre-chequeo" in data["disclaimer"].lower() or "Pre-chequeo" in data["disclaimer"]
    assert data["body_clearance_mm"] > 0


def test_audit_detects_overlap_and_edge():
    footprints = [
        {"reference": "R1", "x_mm": 10, "y_mm": 10, "width_mm": 4, "height_mm": 2},
        {"reference": "R2", "x_mm": 11, "y_mm": 10, "width_mm": 4, "height_mm": 2},
        {"reference": "U1", "x_mm": 0.2, "y_mm": 5, "width_mm": 5, "height_mm": 5},
    ]
    outline = (0, 0, 50, 40)
    findings = audit_placement(footprints, outline)
    codes = {item.code for item in findings}
    assert "ipc.overlap" in codes or "ipc.body_clearance" in codes
    assert "ipc.edge_clearance" in codes or "ipc.outside_board" in codes


def test_place_ipc_respects_locked():
    footprints = [
        {"reference": "U1", "x_mm": 20, "y_mm": 20, "width_mm": 8, "height_mm": 8, "locked": True},
        {"reference": "C1", "x_mm": 40, "y_mm": 40, "width_mm": 2, "height_mm": 1.2},
        {"reference": "R1", "x_mm": 45, "y_mm": 40, "width_mm": 2, "height_mm": 1},
    ]
    plan, findings = place_ipc(
        footprints,
        [{"name": "MCU", "references": ["U1", "C1", "R1"]}],
        (0, 0, 80, 60),
    )
    refs = {item["reference"] for item in plan}
    assert "U1" not in refs
    assert "C1" in refs
    assert any(item.code == "ipc.locked_kept" for item in findings)


def test_safe_fixes_push_from_edge():
    footprints = [{"reference": "R1", "x_mm": 1.2, "y_mm": 10, "width_mm": 2, "height_mm": 1}]
    findings = audit_placement(footprints, (0, 0, 40, 30))
    moves = safe_fixes(findings, footprints, (0, 0, 40, 30))
    assert moves
    assert moves[0]["x_mm"] > footprints[0]["x_mm"]


def test_score_routing_prefers_fewer_errors():
    before = score_routing({"error_count": 2, "warning_count": 1, "unconnected": 3}, BoardSnapshot(tracks=0))
    after = score_routing({"error_count": 0, "warning_count": 1, "unconnected": 0}, BoardSnapshot(tracks=12))
    assert better_than(after, before)


def test_pcb_reviewer_hard_blocks_drc_errors():
    reviewer = PcbReviewer(client=None)
    blocked = reviewer.gate(
        {
            "operation": "autoroute",
            "drc": {"error_count": 2, "unconnected": 0, "problems": ["error: clearance"]},
            "better_than": True,
            "ipc_findings": [],
        }
    )
    assert blocked is not None
    assert blocked["review"] == "rejected"


def test_pcb_reviewer_allows_clean_candidate():
    reviewer = PcbReviewer(client=None)
    blocked = reviewer.gate(
        {
            "operation": "autoroute",
            "drc": {"error_count": 0, "unconnected": 0, "problems": []},
            "better_than": True,
            "score": {"score": 1100},
            "baseline_score": {"score": 900},
            "ipc_findings": [],
        }
    )
    assert blocked is None
    assert reviewer.note.get("review") == "approved"
