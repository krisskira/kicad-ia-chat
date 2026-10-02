from pathlib import Path

import pytest

from kicad_ia.kicad.libraries import KicadPaths, LibraryIndex

SYMBOLS = """(kicad_symbol_lib
\t(version 20251024)
\t(generator "kicad_symbol_editor")
\t(symbol "LDO_Base"
\t\t(exclude_from_sim no)
\t\t(in_bom yes)
\t\t(on_board yes)
\t\t(property "Reference" "U"
\t\t\t(at 0 5.08 0)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t)
\t\t(property "Value" "LDO_Base"
\t\t\t(at 0 -5.08 0)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t)
\t\t(property "Footprint" "Test:SOT-23-5"
\t\t\t(at 0 0 0)
\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t)
\t\t(property "Description" "Regulador lineal de prueba"
\t\t\t(at 0 0 0)
\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t)
\t\t(symbol "LDO_Base_0_1"
\t\t\t(rectangle (start -5.08 2.54) (end 5.08 -2.54)
\t\t\t\t(stroke (width 0.254) (type default))
\t\t\t\t(fill (type background))
\t\t\t)
\t\t)
\t\t(symbol "LDO_Base_1_1"
\t\t\t(pin power_in line (at -7.62 0 0) (length 2.54) (name "VIN" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
\t\t\t(pin power_in line (at 0 -5.08 90) (length 2.54) (name "GND" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))
\t\t\t(pin power_out line (at 7.62 0 180) (length 2.54) (name "VOUT" (effects (font (size 1.27 1.27)))) (number "5" (effects (font (size 1.27 1.27)))))
\t\t)
\t\t(embedded_fonts no)
\t)
\t(symbol "LDO-3.3"
\t\t(extends "LDO_Base")
\t\t(property "Reference" "U"
\t\t\t(at 0 5.08 0)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t)
\t\t(property "Value" "LDO-3.3"
\t\t\t(at 0 -5.08 0)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t)
\t\t(property "Description" "Regulador 3,3 V de prueba"
\t\t\t(at 0 0 0)
\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t)
\t\t(embedded_fonts no)
\t)
\t(symbol "Bare"
\t\t(property "Reference" "U"
\t\t\t(at 0 2.54 0)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t)
\t\t(property "Value" "Bare"
\t\t\t(at 0 -2.54 0)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t)
\t\t(property "Footprint" ""
\t\t\t(at 0 0 0)
\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t)
\t\t(symbol "Bare_1_1"
\t\t\t(pin passive line (at -5.08 0 0) (length 2.54)
\t\t\t\t(name "A" (effects (font (size 1.27 1.27))))
\t\t\t\t(number "1" (effects (font (size 1.27 1.27))))
\t\t\t)
\t\t)
\t\t(embedded_fonts no)
\t)
)
"""

FOOTPRINT = """(footprint "SOT-23-5"
\t(version 20241229)
\t(generator "pcbnew")
\t(layer "F.Cu")
\t(descr "SOT-23 de 5 pines")
\t(attr smd)
\t(pad "1" smd roundrect (at -1.1 -0.95) (size 1 0.6) (layers "F.Cu"))
\t(pad "2" smd roundrect (at -1.1 0) (size 1 0.6) (layers "F.Cu"))
\t(pad "5" smd roundrect (at 1.1 -0.95) (size 1 0.6) (layers "F.Cu"))
\t(model "${KIPRJMOD}/models/SOT-23-5.step"
\t\t(offset (xyz 0 0 0))
\t\t(scale (xyz 1 1 1))
\t\t(rotate (xyz 0 0 0))
\t)
)
"""

SCHEMATIC = """(kicad_sch
\t(version 20260306)
\t(generator "eeschema")
\t(generator_version "10.0")
\t(uuid "5e40073c-0f26-4cc6-b943-88e60c0a7e82")
\t(paper "A4")
\t(lib_symbols)
\t(sheet_instances
\t\t(path "/"
\t\t\t(page "1")
\t\t)
\t)
\t(embedded_fonts no)
)
"""


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("KICAD_IA_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("KICAD_IA_CONFIG", str(tmp_path / "config"))


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "demo"
    (root / "Test.pretty").mkdir(parents=True)
    (root / "models").mkdir()
    (root / "models" / "SOT-23-5.step").write_text("ISO-10303-21;", encoding="utf-8")
    (root / "Test.kicad_sym").write_text(SYMBOLS, encoding="utf-8")
    (root / "Test.pretty" / "SOT-23-5.kicad_mod").write_text(FOOTPRINT, encoding="utf-8")
    (root / "demo.kicad_sch").write_text(SCHEMATIC, encoding="utf-8")
    (root / "demo.kicad_pro").write_text("{}", encoding="utf-8")
    (root / "sym-lib-table").write_text(
        '(sym_lib_table (version 7) (lib (name "Test")(type "KiCad")(uri "${KIPRJMOD}/Test.kicad_sym")(options "")(descr "")))',
        encoding="utf-8",
    )
    (root / "fp-lib-table").write_text(
        '(fp_lib_table (version 7) (lib (name "Test")(type "KiCad")(uri "${KIPRJMOD}/Test.pretty")(options "")(descr "")))',
        encoding="utf-8",
    )
    return root


@pytest.fixture
def index(project: Path) -> LibraryIndex:
    paths = KicadPaths(config_dir=None, share_dir=None, major=10, variables={"KIPRJMOD": str(project)})
    return LibraryIndex(paths, project)
