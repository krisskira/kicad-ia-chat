import json
from pathlib import Path

from kicad_ia.config import Settings
from kicad_ia.kicad.candidates import STORE
from kicad_ia.agent.pcb_review import _hard_block
from kicad_ia.kicad.cli import run_drc
from kicad_ia.kicad.copper_apply import apply_copper_to_board, parse_copper
from kicad_ia.kicad.fake import FakeGateway
from kicad_ia.kicad.freerouting import ensure_jar, run_freerouting
from kicad_ia.kicad.pcbnew_bridge import find_pcbnew_python
from kicad_ia.tools.registry import build_registry


def test_ensure_jar_uses_cached_file(tmp_path, monkeypatch):
    monkeypatch.setenv("KICAD_IA_CACHE", str(tmp_path))
    jar = tmp_path / "freerouting" / "freerouting-2.0.1.jar"
    jar.parent.mkdir(parents=True)
    jar.write_bytes(b"not-a-real-jar-but-hashed")
    digest = __import__("hashlib").sha256(jar.read_bytes()).hexdigest()
    monkeypatch.setenv("FREEROUTING_SHA256", digest)
    # Recargar constante leída al import — pasar expected_sha evita la global vieja
    result = ensure_jar(expected_sha=digest, allow_download=False)
    assert result["ok"] is True
    assert result["downloaded"] is False


def test_run_freerouting_mocked(tmp_path, monkeypatch):
    dsn = tmp_path / "board.dsn"
    ses = tmp_path / "board.ses"
    dsn.write_text("(pcb dummy)", encoding="utf-8")
    jar = tmp_path / "fr.jar"
    jar.write_bytes(b"jar")

    def fake_run(args, **kwargs):
        ses.write_text("(session routed)", encoding="utf-8")

        class Proc:
            returncode = 0
            stdout = "done"
            stderr = ""

        return Proc()

    monkeypatch.setattr("kicad_ia.kicad.freerouting.subprocess.run", fake_run)
    monkeypatch.setattr("kicad_ia.kicad.freerouting.find_java", lambda configured="": "/usr/bin/java")
    monkeypatch.setattr("kicad_ia.kicad.freerouting.java_version", lambda _java: (21, 'openjdk version "21"'))
    result = run_freerouting(dsn, ses, jar=str(jar), timeout_s=10)
    assert result["ok"] is True
    assert Path(result["ses"]).is_file()


def test_parse_copper_from_minimal_board(tmp_path):
    board = tmp_path / "x.kicad_pcb"
    board.write_text(
        """(kicad_pcb
  (net 0 "")
  (net 1 "+5V")
  (net 2 "GND")
  (segment (start 1 2) (end 3 4) (width 0.25) (layer "F.Cu") (net 1))
  (via (at 5 6) (size 0.8) (drill 0.4) (layers "F.Cu" "B.Cu") (net 2))
)
""",
        encoding="utf-8",
    )
    copper = parse_copper(board)
    assert len(copper["segments"]) == 1
    assert copper["segments"][0]["net_name"] == "+5V"
    assert len(copper["vias"]) == 1
    assert copper["vias"][0]["net_name"] == "GND"


def test_parse_copper_kicad10_names_nets_inline(tmp_path):
    board = tmp_path / "x.kicad_pcb"
    board.write_text(
        """(kicad_pcb
  (segment (start 1 2) (end 3 4) (width 0.2) (layer "B.Cu") (net "/NET2"))
  (via (at 5 6) (size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu") (net "/GND"))
)
""",
        encoding="utf-8",
    )
    copper = parse_copper(board)
    assert copper["segments"][0]["net_name"] == "/NET2"
    assert copper["vias"][0]["net_name"] == "/GND"


class _Net:
    def __init__(self, name):
        self.name = name


class _RecordingBoard:
    def __init__(self, nets, tracks=()):
        self._nets = [_Net(name) for name in nets]
        self._tracks = list(tracks)
        self.removed = []
        self.created = []

    def get_nets(self):
        return self._nets

    def get_tracks(self):
        return self._tracks

    def get_vias(self):
        return []

    def remove_items(self, items):
        self.removed.extend(items)

    def create_items(self, items):
        self.created.extend(items)


def test_apply_copper_keeps_board_when_a_net_is_missing(tmp_path):
    board = tmp_path / "x.kicad_pcb"
    board.write_text(
        '(kicad_pcb (segment (start 1 2) (end 3 4) (width 0.2) (layer "F.Cu") (net "/OTRA")))',
        encoding="utf-8",
    )
    live = _RecordingBoard(["/GND"], tracks=["pista vieja"])
    result = apply_copper_to_board(live, board)
    assert result["ok"] is False
    assert result["missing_nets"] == ["/OTRA"]
    assert live.removed == [] and live.created == []


def test_drc_counts_kicad10_unconnected_items(tmp_path, monkeypatch):
    report = {
        "violations": [{"type": "invalid_outline", "severity": "error", "items": []}],
        "unconnected_items": [{"items": [{"description": "Pad 1 [/GND]"}]}, {"items": []}],
    }

    def fake_run(args, **_kwargs):
        Path(args[args.index("-o") + 1]).write_text(json.dumps(report), encoding="utf-8")

    monkeypatch.setattr("kicad_ia.kicad.cli.subprocess.run", fake_run)
    drc = run_drc("kicad-cli", tmp_path / "x.kicad_pcb")
    assert drc["error_count"] == 1
    assert drc["unconnected"] == 2


def test_pcb_review_ignores_drc_errors_already_in_baseline():
    drc = {"error_count": 1, "unconnected": 0, "problems": ["error: invalid_outline"]}
    report = {"operation": "autoroute", "drc": drc, "better_than": True, "baseline_drc_errors": 1}
    assert _hard_block(report) is None
    assert _hard_block({**report, "baseline_drc_errors": 0})


def test_fake_gateway_ipc_and_autoroute_flow():
    gateway = FakeGateway()
    gateway.sync_board()
    # sync may create nothing without symbols; plant footprints
    from kicad_ia.kicad.circuit import PlacedFootprint

    gateway.footprints["U1"] = PlacedFootprint(reference="U1", footprint="Pkg:SOIC", value="NE555", x_mm=10, y_mm=10, model="")
    gateway.footprints["C1"] = PlacedFootprint(reference="C1", footprint="C_0603", value="100n", x_mm=20, y_mm=10, model="")
    registry = build_registry()
    place = registry.call("ipc_place_components", {"apply": False}, gateway)
    assert place["ok"] is True
    assert place["candidate_id"]
    applied = registry.call(
        "ipc_place_components",
        {"apply": True, "candidate_id": place["candidate_id"]},
        gateway,
    )
    assert applied["applied"] is True

    route = registry.call("autoroute_board", {}, gateway)
    assert route["ok"] is True
    assert route["candidate_id"]
    done = registry.call("autoroute_board", {"apply": True, "candidate_id": route["candidate_id"]}, gateway)
    assert done["applied"] is True

    report = registry.call("ipc_validate_correct", {}, gateway)
    assert report["ok"] is True
    assert "disclaimer" in report


def test_pcbnew_python_detection():
    # En este Mac de desarrollo debería existir; si no, None es aceptable.
    found = find_pcbnew_python()
    assert found is None or Path(found).is_file()
