from kicad_ia.kicad.lcsc import import_lcsc, register_project_library
from kicad_ia.kicad.libraries import KicadPaths, LibraryIndex
from kicad_ia.kicad.sexpr import child, children, parse

SYMBOL = """(kicad_symbol_lib
  (version 20251024)
  (symbol "MOD-1"
    (property "Reference" "U" (at 0 0 0) (effects (font (size 1.27 1.27))))
    (property "Value" "MOD-1" (at 0 0 0) (effects (font (size 1.27 1.27))))
    (property "Footprint" "kicad-ia:MOD-1" (at 0 0 0) (effects (font (size 1.27 1.27))))
    (property "LCSC" "C999" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (symbol "MOD-1_1_1"
      (pin passive line (at -2.54 0 0) (length 2.54) (name "VCC" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
    )
  )
)
"""


def test_registers_project_library_once(tmp_path):
    register_project_library(tmp_path)
    register_project_library(tmp_path)
    tree = parse((tmp_path / "sym-lib-table").read_text(encoding="utf-8"))[0]
    names = [str(child(lib, "name")[1]) for lib in children(tree, "lib")]
    assert names == ["kicad-ia"]
    assert "kicad-ia.pretty" in str(child(children(parse((tmp_path / "fp-lib-table").read_text(encoding="utf-8"))[0], "lib")[0], "uri")[1])


def test_import_uses_runner_and_is_searchable(tmp_path, monkeypatch):
    monkeypatch.setenv("KICAD_IA_CACHE", str(tmp_path / "cache"))

    def runner(project, lcsc_id):
        assert lcsc_id == "C999"
        (project / "kicad-ia.kicad_sym").write_text(SYMBOL, encoding="utf-8")
        (project / "kicad-ia.pretty").mkdir()
        (project / "kicad-ia.3dshapes").mkdir()
        (project / "kicad-ia.3dshapes" / "MOD-1.step").write_text("solid", encoding="utf-8")
        return 0

    result = import_lcsc(tmp_path, "c999", runner)
    assert result["ok"] is True
    assert result["lib_id"] == "kicad-ia:MOD-1"
    assert result["footprint"] == "kicad-ia:MOD-1"
    index = LibraryIndex(KicadPaths(None, None, 10, {"KIPRJMOD": str(tmp_path)}), tmp_path)
    assert index.search_symbols("MOD-1")[0]["lib_id"] == "kicad-ia:MOD-1"


def test_rejects_a_code_that_is_not_lcsc(tmp_path):
    assert import_lcsc(tmp_path, "ILI9341")["ok"] is False
