"""KiCad real: placa por la API IPC (kipy) y esquemático por archivo.

KiCad 10 solo expone la placa por IPC. Las bibliotecas se leen de las mismas
tablas que usa KiCad y el esquemático se escribe en el .kicad_sch del proyecto.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path

from kicad_ia.config import Settings
from kicad_ia.kicad.candidates import STORE
from kicad_ia.kicad.cli import export_netlist, find_kicad_cli, read_netlist, run_drc, run_erc
from kicad_ia.kicad.copper_apply import apply_copper_to_board
from kicad_ia.kicad.freerouting import ensure_jar, probe_java, route_board_files
from kicad_ia.kicad.gateway import Gateway, GatewayError
from kicad_ia.kicad.ipc import audit_placement, place_ipc, profile, safe_fixes
from kicad_ia.kicad.layout import auto_groups, group_layout, normalize_groups
from kicad_ia.kicad.lcsc import import_lcsc, search_lcsc
from kicad_ia.kicad.pcb_metrics import BoardSnapshot, better_than, compare_snapshots, score_routing
from kicad_ia.kicad.pcbnew_bridge import find_pcbnew_python
from kicad_ia.kicad.render import VIEWS, render_board, render_schematic
from kicad_ia.kicad.libraries import LibraryIndex, detect_paths
from kicad_ia.kicad.normalize import lib_id_text, normalize_item, text_value
from kicad_ia.kicad.sch_writer import SchematicLocked, lock_file, nets_from_connections, read_symbols, set_footprint, write_circuit

DOCTYPE_SCHEMATIC = 1
DOCTYPE_PCB = 3


class KipyGateway(Gateway):
    def __init__(self, settings: Settings) -> None:
        try:
            from kipy import KiCad
        except ImportError as exc:
            raise GatewayError("Falta kicad-python. Instálalo con pip install -e '.[kicad]'.") from exc
        self._kicad = _connect_kicad(KiCad)
        self._settings = settings
        self._version = _version_text(self._kicad)
        self._major = _major(self._version)
        self._index: LibraryIndex | None = None
        self._index_project: Path | None = None

    def alive(self) -> bool:
        try:
            self._kicad.ping()
            return True
        except Exception:
            return False

    def capabilities(self) -> dict:
        if not self.alive():
            return {
                "connected": False,
                "backend": "kipy",
                "kicad_version": self._version,
                "project": "",
                "board_open": False,
                "notes": ["KiCad dejó de responder. Ábrelo con la API activada; me reconecto solo."],
            }
        project = self._project()
        schematic = self._schematic_path(project)
        board = _try(self._board)
        cli = find_kicad_cli(self._settings.kicad_cli)
        index = self._library_index()
        schematic_open = bool(schematic and lock_file(schematic).exists())
        notes = [
            "KiCad 10 no expone el esquemático por API. El plugin escribe el .kicad_sch del proyecto y hace copia en .kicad-ia-backup.",
            "Las piezas salen de sym-lib-table y fp-lib-table: las mismas bibliotecas que ves en KiCad.",
        ]
        if schematic_open:
            notes.append("El editor de esquemáticos tiene el archivo abierto: hay que cerrarlo antes de escribir.")
        if board is None:
            notes.append("No hay placa abierta en el editor de PCB: huellas, selección y ruteo no están disponibles.")
        notes.append("Para pasar a la PCB: en el editor de PCB, Herramientas > Actualizar PCB desde esquemático (F8). kipy 0.8 no importa netlists.")
        pcbnew = bool(find_pcbnew_python(self._settings.kicad_python))
        freerouting_ready = False
        java = probe_java(self._settings.java_bin)
        if self._settings.freerouting_jar:
            freerouting_ready = Path(self._settings.freerouting_jar).is_file()
        else:
            freerouting_ready = ensure_jar(allow_download=False).get("ok", False)
        if not pcbnew:
            notes.append("Sin Python de KiCad (pcbnew) no puedo exportar DSN/SES para autoruteo. Define KICAD_PYTHON.")
        if not freerouting_ready:
            notes.append("FreeRouting aún no está en caché; se descargará al primer autoruteo si FREEROUTING_DOWNLOAD=1.")
        if not self._settings.autoroute_enabled:
            notes.append("Autoruteo desactivado en Ajustes. Actívalo y define anchos/taladros de fabricación para usarlo.")
        elif not java.get("ok"):
            notes.append(java.get("error") or "Autoruteo activo pero Java no está listo.")
        return {
            "connected": True,
            "backend": "kipy",
            "kicad_version": self._version,
            "kicad_major": self._major,
            "project": project.get("name") if project else "",
            "schematic_file": str(schematic or ""),
            "schematic_open_in_editor": schematic_open,
            "schematic_write": bool(schematic and schematic.is_file() and not schematic_open),
            "schematic_live_api": False,
            "schematic_selection": False,
            "board_open": board is not None,
            "board_selection": board is not None,
            "library_search": bool(index.symbol_libs),
            "libraries": index.summary(),
            "erc": bool(cli),
            "drc": bool(cli),
            "pcbnew_python": pcbnew,
            "freerouting": freerouting_ready,
            "java": java,
            "autoroute_enabled": self._settings.autoroute_enabled,
            "fab": self._settings.fab_summary(),
            "ipc_class": self._settings.ipc_class,
            "netlist_import": False,
            "external_router": pcbnew and self._settings.autoroute_enabled,
            "notes": notes,
        }

    def inspect(self) -> dict:
        project = self._project()
        schematic = self._schematic_path(project)
        symbols = read_symbols(schematic) if schematic and schematic.is_file() else []
        board = _try(self._board)
        board_summary: dict = {"available": False}
        if board is not None:
            footprints = list(_call(board, "get_footprints") or [])
            board_summary = {
                "available": True,
                "name": str(getattr(board, "name", "") or ""),
                "footprint_count": len(footprints),
                "track_count": len(list(_call(board, "get_tracks") or [])),
                "via_count": len(list(_call(board, "get_vias") or [])),
                "zone_count": len(list(_call(board, "get_zones") or [])),
            }
        return {
            "ok": True,
            "project": project.get("name") if project else "",
            "selection": self._selection(),
            "schematic": {
                "available": bool(schematic and schematic.is_file()),
                "file": str(schematic or ""),
                "symbol_count": len(symbols),
                "symbols": symbols[:80],
            },
            "board": board_summary,
            "capabilities": self.capabilities(),
        }

    def search_parts(self, kind: str, query: str, limit: int) -> dict:
        index = self._library_index()
        limit = max(1, min(limit, 40))
        if kind == "symbol":
            matches = index.search_symbols(query, limit)
        elif kind == "footprint":
            matches = index.search_footprints(query, limit)
        elif kind == "model":
            matches = []
            for row in index.search_footprints(query, limit):
                detail = index.describe_footprint(row["lib_id"]) or {}
                matches.append({"footprint": row["lib_id"], "models": detail.get("models", [])})
        else:
            return {"ok": False, "error": "kind debe ser symbol, footprint o model."}
        result = {"ok": True, "kind": kind, "query": query, "matches": matches}
        if not matches:
            result["note"] = (
                "No está en las bibliotecas configuradas en KiCad. Prueba con menos palabras o con la familia del componente; "
                "si no existe, pregunta al usuario si quiere crearlo."
            )
        return result

    def search_lcsc(self, query: str, limit: int) -> dict:
        return search_lcsc(query, limit)

    def import_lcsc(self, lcsc_id: str) -> dict:
        project = self._project()
        if project is None:
            return {"ok": False, "error": "No hay un proyecto abierto en KiCad."}
        result = import_lcsc(project["path"], lcsc_id)
        self._index = None
        self._index_project = None
        return result

    def describe_part(self, lib_id: str) -> dict:
        summary = self._library_index().describe_symbol(lib_id)
        if summary is None:
            return {"ok": False, "error": f"No está en las bibliotecas de KiCad: {lib_id}. Busca con search_parts."}
        footprint = summary.get("footprint") or ""
        if footprint:
            detail = self._library_index().describe_footprint(footprint)
            if detail:
                summary["footprint_detail"] = detail
        return {"ok": True, "part": summary}

    def describe_footprint(self, lib_id: str) -> dict:
        detail = self._library_index().describe_footprint(lib_id)
        if detail is None:
            return {"ok": False, "error": f"No está en las bibliotecas de huellas de KiCad: {lib_id}."}
        return {"ok": True, "footprint": detail}

    def place_circuit(self, symbols: list[dict], nets: list[dict], connections: list[dict], replace: bool = False) -> dict:
        schematic = self._schematic_path(self._project())
        if schematic is None or not schematic.is_file():
            return {"ok": False, "error": "No encuentro el .kicad_sch del proyecto abierto en KiCad."}
        all_nets = list(nets) + nets_from_connections(connections)
        try:
            result = write_circuit(schematic, self._library_index(), symbols, all_nets, replace)
        except SchematicLocked as exc:
            return {"ok": False, "error": str(exc)}
        cli = find_kicad_cli(self._settings.kicad_cli)
        if result.get("written") and cli:
            result["erc"] = run_erc(cli, schematic)
        result["next"] = "Abre el esquemático en KiCad para verlo. Para la PCB: F8 en el editor de PCB."
        return result

    def assign_footprint(self, reference: str, footprint: str) -> dict:
        if self._library_index().describe_footprint(footprint) is None:
            return {"ok": False, "error": f"La huella {footprint} no está en las bibliotecas de KiCad."}
        schematic = self._schematic_path(self._project())
        if schematic is None or not schematic.is_file():
            return {"ok": False, "error": "No encuentro el .kicad_sch del proyecto."}
        try:
            return set_footprint(schematic, reference, footprint)
        except SchematicLocked as exc:
            return {"ok": False, "error": str(exc)}

    def sync_board(self) -> dict:
        schematic = self._schematic_path(self._project())
        cli = find_kicad_cli(self._settings.kicad_cli)
        if schematic is None or not schematic.is_file():
            return {"ok": False, "error": "No encuentro el .kicad_sch del proyecto."}
        if cli is None:
            return {"ok": False, "error": "No encuentro kicad-cli. Define KICAD_CLI en .env."}
        erc = run_erc(cli, schematic)
        with tempfile.TemporaryDirectory() as tmp:
            netlist = export_netlist(cli, schematic, Path(tmp) / "kicad-ia.net")
        netlist.pop("netlist", None)
        missing = [row["reference"] for row in read_symbols(schematic) if not row["footprint"] and not row["reference"].startswith("#")]
        return {
            "ok": netlist.get("ok", False),
            "erc": erc,
            "netlist": netlist,
            "symbols_without_footprint": missing,
            "imported": False,
            "next": "En el editor de PCB: Herramientas > Actualizar PCB desde esquemático (F8). Luego usa board_state.",
        }

    def board_state(self) -> dict:
        board = self._board()
        footprints = [_footprint_brief(item) for item in list(_call(board, "get_footprints") or [])]
        return {
            "ok": True,
            "name": str(getattr(board, "name", "") or ""),
            "footprints": footprints[:120],
            "tracks": len(list(_call(board, "get_tracks") or [])),
            "vias": len(list(_call(board, "get_vias") or [])),
            "zones": len(list(_call(board, "get_zones") or [])),
        }

    def move_footprints(self, placements: list[dict]) -> dict:
        board = self._board()
        by_reference = {_footprint_reference(item): item for item in list(_call(board, "get_footprints") or [])}
        moved, errors, changed = [], [], []
        for placement in placements:
            reference = str(placement.get("reference") or "")
            footprint = by_reference.get(reference)
            if footprint is None:
                errors.append(f"No está en la placa: {reference}.")
                continue
            footprint.position = _mm_vector(float(placement["x_mm"]), float(placement["y_mm"]))
            changed.append(footprint)
            moved.append(reference)
        if changed:
            board.update_items(changed)
        return {"ok": not errors, "moved": moved, "errors": errors}

    def list_models(self, reference: str | None) -> dict:
        board = _try(self._board)
        if board is None:
            return {"ok": False, "error": "No hay placa abierta. Para una huella de biblioteca usa search_parts kind=model o describe_footprint."}
        selected = {item.get("reference") for item in self._selection() if item.get("reference")}
        rows = []
        for footprint in list(_call(board, "get_footprints") or []):
            ref = _footprint_reference(footprint)
            if reference and ref != reference:
                continue
            if reference is None and selected and ref not in selected:
                continue
            rows.append(
                {
                    "reference": ref,
                    "footprint": lib_id_text(getattr(getattr(footprint, "definition", None), "id", "")),
                    "models": normalize_item(footprint, "pcb")["models"],
                }
            )
        if reference and not rows:
            return {"ok": False, "error": f"No está en la placa: {reference}."}
        return {"ok": True, "items": rows[:80]}

    def routing(self, mode: str, action: str | None) -> dict:
        board = self._board()
        if mode == "status":
            return {
                "ok": True,
                "mode": "status",
                "tracks": len(list(_call(board, "get_tracks") or [])),
                "vias": len(list(_call(board, "get_vias") or [])),
                "footprints": len(list(_call(board, "get_footprints") or [])),
                "zones": len(list(_call(board, "get_zones") or [])),
            }
        if mode == "interactive":
            if not action:
                return {"ok": False, "error": "Indica el nombre de la acción de KiCad. run_action es inestable y no se lanza a ciegas."}
            status = self._kicad.run_action(action)
            return {"ok": True, "action": action, "status": str(status)}
        if mode == "external":
            return {
                "ok": False,
                "error": "kicad-cli de KiCad 10 no exporta Specctra DSN. Exporta el DSN desde Archivo > Exportar en el editor de PCB.",
            }
        return {"ok": False, "error": "mode debe ser status, interactive o external."}

    def selection(self) -> list[dict]:
        return self._selection()

    def render_view(self, view: str) -> dict:
        if view not in VIEWS:
            return {"ok": False, "error": f"view debe ser uno de: {', '.join(VIEWS)}."}
        cli = find_kicad_cli(self._settings.kicad_cli)
        if cli is None:
            return {"ok": False, "error": "No encuentro kicad-cli. Define KICAD_CLI en .env."}
        project = self._project()
        if project is None:
            return {"ok": False, "error": "No hay un proyecto abierto en KiCad."}
        if view == "schematic":
            schematic = self._schematic_path(project)
            if schematic is None or not schematic.is_file():
                return {"ok": False, "error": "No encuentro el .kicad_sch del proyecto."}
            result = render_schematic(cli, schematic)
            if result.get("ok") and lock_file(schematic).exists():
                result["note"] = "Es el archivo guardado. Si tienes cambios sin guardar en el editor, no salen en la imagen."
            return result
        board = self._board()
        # Una copia junto al proyecto para que ${KIPRJMOD} resuelva los modelos 3D.
        copy = project["path"] / ".kicad-ia-render.kicad_pcb"
        try:
            copy.write_text(board.get_as_string(), encoding="utf-8")
            result = render_board(cli, copy, view)
        finally:
            copy.unlink(missing_ok=True)
            copy.with_suffix(".kicad_prl").unlink(missing_ok=True)
        return result

    def organize_layout(self, target: str, groups: list[dict] | None, apply: bool = True) -> dict:
        if target not in ("schematic", "pcb", "both"):
            return {"ok": False, "error": "target debe ser schematic, pcb o both."}
        project = self._project()
        schematic = self._schematic_path(project)
        cli = find_kicad_cli(self._settings.kicad_cli)
        netlist = None
        if schematic and schematic.is_file() and cli:
            netlist = read_netlist(cli, schematic)
        result: dict = {"ok": True, "target": target}
        if groups:
            plan = groups
        elif netlist and netlist.get("ok"):
            plan = auto_groups(
                [comp for comp in netlist["components"] if not comp["reference"].startswith("#")],
                netlist["nets"],
            )
            result["auto_groups"] = True
        else:
            board = _try(self._board)
            refs = [_footprint_reference(item) for item in list(_call(board, "get_footprints") or [])] if board else []
            plan = [{"name": "Circuito", "references": refs}]
        result["groups"] = plan
        if target in ("schematic", "both"):
            result["schematic"] = self._organize_schematic(schematic, netlist, plan, apply, cli)
        if target in ("pcb", "both"):
            result["pcb"] = self._organize_board(plan, apply)
        parts = [result.get(key) for key in ("schematic", "pcb") if key in result]
        result["ok"] = all(part.get("ok") for part in parts)
        return result

    def _organize_schematic(self, schematic: Path | None, netlist: dict | None, groups: list[dict], apply: bool, cli: str | None) -> dict:
        if schematic is None or not schematic.is_file():
            return {"ok": False, "error": "No encuentro el .kicad_sch del proyecto."}
        if not netlist or not netlist.get("ok"):
            return {"ok": False, "error": (netlist or {}).get("error") or "No pude leer el netlist con kicad-cli."}
        symbols = [
            {"lib_id": comp["lib_id"], "reference": comp["reference"], "value": comp["value"], "footprint": comp["footprint"]}
            for comp in netlist["components"]
            if comp["lib_id"] and not comp["reference"].startswith("#")
        ]
        refs = {spec["reference"] for spec in symbols}
        nets = []
        for net in netlist["nets"]:
            pins = [{"reference": node["ref"], "pin": node["pin"]} for node in net["nodes"] if node["ref"] in refs]
            if len(pins) >= 2:
                nets.append({"name": net["name"], "pins": pins})
        if not apply:
            return {"ok": True, "applied": False, "symbols": len(symbols), "nets": len(nets)}
        try:
            written = write_circuit(schematic, self._library_index(), symbols, nets, replace=True, groups=groups, check_power=False)
        except SchematicLocked as exc:
            return {"ok": False, "error": str(exc)}
        written["warning"] = (
            "El esquemático se rehizo con etiquetas de red por pin. Se pierden cables, textos y símbolos de alimentación dibujados a mano; "
            f"la versión anterior está en {written.get('backup') or '.kicad-ia-backup'}."
        )
        if written.get("written") and cli:
            written["erc"] = run_erc(cli, schematic)
        return written

    def _organize_board(self, groups: list[dict], apply: bool) -> dict:
        board = _try(self._board)
        if board is None:
            return {"ok": False, "error": "No hay placa abierta en el editor de PCB."}
        footprints = list(_call(board, "get_footprints") or [])
        if not footprints:
            return {"ok": False, "error": "La placa no tiene huellas. Primero F8 en el editor de PCB."}
        refs = [_footprint_reference(item) for item in footprints]
        by_ref = dict(zip(refs, footprints))
        boxes = board.get_item_bounding_box(footprints)
        sizes, offsets = {}, {}
        for ref, footprint, box in zip(refs, footprints, boxes):
            if box is None or ref in sizes:
                continue
            x, y = _vec_mm(box.pos)
            w, h = _vec_mm(box.size)
            px, py = _vec_mm(footprint.position)
            sizes[ref] = (w + 1.0, h + 1.0)
            offsets[ref] = (px - (x + w / 2), py - (y + h / 2))
        clean, unknown = normalize_groups(groups, list(sizes))
        outline = _board_outline(board)
        margin = 3.0
        if outline:
            ox, oy, ow, oh = outline
            origin = (ox + margin, oy + margin)
            max_width = ow - 2 * margin
        else:
            starts = [_vec_mm(by_ref[ref].position) for ref in sizes]
            origin = (min(x for x, _ in starts), min(y for _, y in starts))
            max_width = None
        centers, blocks, (used_w, used_h) = group_layout(sizes, clean, max_width, item_gap=1.5, group_gap=5.0, padding=1.0)
        plan = []
        for ref, (cx, cy) in centers.items():
            dx, dy = offsets[ref]
            plan.append({"reference": ref, "x_mm": round(origin[0] + cx + dx, 3), "y_mm": round(origin[1] + cy + dy, 3)})
        result = {
            "ok": True,
            "applied": False,
            "groups": [
                {"name": block.key, "x_mm": round(origin[0] + block.x, 2), "y_mm": round(origin[1] + block.y, 2),
                 "width_mm": round(block.width, 2), "height_mm": round(block.height, 2)}
                for block in blocks
            ],
            "area_mm": [round(used_w, 1), round(used_h, 1)],
            "unknown_references": unknown,
        }
        if outline and used_h > outline[3] - 2 * margin:
            result["warning"] = f"Los grupos ocupan {used_h:.1f} mm de alto y la placa mide {outline[3]:.1f} mm. Agranda el contorno o reparte en dos caras."
        if not outline:
            result["note"] = "La placa no tiene contorno en Edge.Cuts; reparto alrededor de las huellas actuales."
        if apply:
            moved = self.move_footprints(plan)
            result.update(applied=True, moved=moved["moved"], errors=moved["errors"])
            result["next"] = "Las pistas existentes no se mueven con las huellas: revísalas o bórralas y vuelve a rutear."
        else:
            result["placements"] = plan
        return result

    def ipc_place_components(
        self, groups: list[dict] | None, apply: bool = False, candidate_id: str | None = None, class_id: str = "2"
    ) -> dict:
        if apply and candidate_id:
            return self._apply_place_candidate(candidate_id)
        board = _try(self._board)
        if board is None:
            return {"ok": False, "error": "No hay placa abierta en el editor de PCB."}
        footprints = self._ipc_footprints(board)
        if not footprints:
            return {"ok": False, "error": "La placa no tiene huellas. Primero F8 en el editor de PCB."}
        outline = _board_outline(board)
        nets = self._board_nets_for_ipc()
        plan_groups = groups
        if not plan_groups:
            plan_groups = auto_groups(
                [{"reference": fp["reference"], "value": fp.get("value") or ""} for fp in footprints],
                nets or [],
            )
        plan, findings = place_ipc(footprints, plan_groups, outline, class_id or self._settings.ipc_class)
        tracks = list(_call(board, "get_tracks") or [])
        result = {
            "ok": True,
            "applied": False,
            "profile": profile(class_id or self._settings.ipc_class),
            "placements": plan,
            "groups": plan_groups,
            "ipc_findings": [item.as_dict() for item in findings],
            "copper_tracks": len(tracks),
        }
        if tracks:
            result["warning"] = (
                "Hay pistas en la placa. Mover huellas las dejará desconectadas de los pads. "
                "Tras aplicar, borra el cobre o vuelve a autorutear."
            )
        project = self._project() or {"name": "board", "path": Path(tempfile.gettempdir())}
        job = STORE.put(
            "place",
            project["name"],
            placements=plan,
            report={"ipc_findings": result["ipc_findings"], "groups": plan_groups},
            approved=not any(f.severity == "error" for f in findings),
        )
        result["candidate_id"] = job.id
        result["next"] = (
            "Vista previa lista. Si te parece bien, vuelve a llamar ipc_place_components "
            f"con apply=true y candidate_id={job.id}."
        )
        # Render preview on a temp board file with moved footprints (sexpr edit)
        preview = self._preview_place_image(board, plan)
        if preview:
            result.update(preview)
        return result

    def autoroute_board(
        self,
        apply: bool = False,
        candidate_id: str | None = None,
        ignore_net_classes: list[str] | None = None,
        max_passes: int = 100,
    ) -> dict:
        if not self._settings.autoroute_enabled:
            return {
                "ok": False,
                "error": (
                    "El autoruteo está desactivado. Ábrelo en Ajustes, indica anchos mínimos de pista, "
                    "clearance, vías y taladros, y vuelve a intentarlo."
                ),
            }
        if apply and candidate_id:
            return self._apply_route_candidate(candidate_id)
        board = _try(self._board)
        if board is None:
            return {"ok": False, "error": "No hay placa abierta en el editor de PCB."}
        if not find_pcbnew_python(self._settings.kicad_python):
            return {"ok": False, "error": "No encuentro el Python de KiCad (pcbnew). Define KICAD_PYTHON."}
        java = probe_java(self._settings.java_bin)
        if not java.get("ok"):
            return {"ok": False, "error": java.get("error") or "Java no está listo para FreeRouting."}
        jar = ensure_jar(allow_download=self._settings.freerouting_download)
        if not jar.get("ok"):
            return jar
        project = self._project()
        if project is None:
            return {"ok": False, "error": "No hay un proyecto abierto en KiCad."}
        work = Path(tempfile.mkdtemp(prefix="kicad-ia-route-", dir=str(project["path"])))
        source = work / "live.kicad_pcb"
        source.write_text(board.get_as_string(), encoding="utf-8")
        before_snap = self._snapshot(board)
        cli = find_kicad_cli(self._settings.kicad_cli)
        before_drc = run_drc(cli, source) if cli else {"ok": False, "error": "sin kicad-cli"}
        baseline = score_routing(before_drc if before_drc.get("ok") else {}, before_snap)
        try:
            routed = route_board_files(
                source,
                work_dir=work,
                timeout_s=self._settings.freerouting_timeout_s,
                max_passes=max_passes,
                ignore_net_classes=ignore_net_classes,
                java_bin=java.get("java") or self._settings.java_bin or None,
                fab=self._settings.fab_summary(),
            )
        except Exception as exc:
            return {"ok": False, "error": str(exc), "work_dir": str(work)}
        if not routed.get("ok"):
            return routed
        candidate = Path(routed["candidate"])
        after_drc = run_drc(cli, candidate) if cli else {"ok": False, "error": "sin kicad-cli"}
        from kicad_ia.kicad.pcbnew_bridge import board_stats

        stats = board_stats(candidate, self._settings.kicad_python or None)
        after_snap = BoardSnapshot(
            footprints=int(stats.get("footprints") or before_snap.footprints),
            tracks=int(stats.get("tracks") or 0),
            vias=int(stats.get("vias") or 0),
            track_length_mm=float(stats.get("track_length_mm") or 0),
            references=before_snap.references,
        )
        cand_score = score_routing(after_drc if after_drc.get("ok") else {}, after_snap)
        improved = better_than(cand_score, baseline)
        baseline_errors = int(before_drc.get("error_count") or 0) if before_drc.get("ok") else 0
        new_errors = int(after_drc.get("error_count") or 0) - baseline_errors
        preexisting = [
            kind for kind in (before_drc.get("by_type") or {})
            if kind != "unconnected_items" and kind in (after_drc.get("by_type") or {})
        ]
        before_img = render_board(cli, source, "pcb") if cli else {"ok": False}
        after_img = render_board(cli, candidate, "pcb") if cli else {"ok": False}
        report = {
            "operation": "autoroute",
            "drc": after_drc,
            "baseline_drc": before_drc,
            "score": cand_score,
            "baseline_score": baseline,
            "better_than": improved,
            "delta": compare_snapshots(before_snap, after_snap),
            "profile": profile(self._settings.ipc_class),
            "fab": self._settings.fab_summary(),
        }
        job = STORE.put(
            "route",
            project["name"],
            files={"candidate": str(candidate), "source": str(source), "ses": routed.get("ses", ""), "work_dir": str(work)},
            report=report,
            approved=bool(
                improved
                and after_drc.get("ok")
                and new_errors <= 0
                and int(after_drc.get("unconnected") or 0) == 0
            ),
        )
        result = {
            "ok": True,
            "applied": False,
            "candidate_id": job.id,
            "approved_heuristics": job.approved,
            "freerouting": {"jar": jar.get("jar"), "downloaded": jar.get("downloaded"), "ses": routed.get("ses"), "java": java},
            "fab": self._settings.fab_summary(),
            "drc": after_drc,
            "baseline_drc": before_drc,
            "score": cand_score,
            "baseline_score": baseline,
            "better_than": improved,
            "delta": report["delta"],
            "profile": report["profile"],
            "disclaimer": report["profile"]["disclaimer"],
            "before_image": before_img.get("image"),
            "image": after_img.get("image"),
            "next": (
                "Candidato listo. El revisor del chat debe mirar drc/score. "
                f"Si el usuario confirma, autoroute_board apply=true candidate_id={job.id}."
            ),
        }
        if preexisting:
            result["preexisting_drc"] = preexisting
            result["preexisting_note"] = (
                "Estos errores DRC ya estaban antes de rutear y no los causa el autoruteo: "
                + ", ".join(preexisting)
                + (". Falta el contorno de la placa (Edge.Cuts)." if "invalid_outline" in preexisting else ".")
            )
        if not improved:
            result["warning"] = "El autoruteo no mejora el baseline; no recomiendo aplicarlo."
        return result

    def ipc_validate_correct(self, apply: bool = False, class_id: str = "2") -> dict:
        board = _try(self._board)
        if board is None:
            return {"ok": False, "error": "No hay placa abierta en el editor de PCB."}
        footprints = self._ipc_footprints(board)
        outline = _board_outline(board)
        nets = self._board_nets_for_ipc()
        findings = audit_placement(footprints, outline, nets, class_id or self._settings.ipc_class)
        cli = find_kicad_cli(self._settings.kicad_cli)
        project = self._project()
        drc = {"ok": False, "error": "sin kicad-cli"}
        if cli and project:
            with tempfile.TemporaryDirectory(dir=str(project["path"])) as tmp:
                path = Path(tmp) / "drc-live.kicad_pcb"
                path.write_text(board.get_as_string(), encoding="utf-8")
                drc = run_drc(cli, path)
        fixes = safe_fixes(findings, footprints, outline)
        result = {
            "ok": True,
            "applied": False,
            "profile": profile(class_id or self._settings.ipc_class),
            "disclaimer": profile(class_id or self._settings.ipc_class)["disclaimer"],
            "drc": drc,
            "ipc_findings": [item.as_dict() for item in findings],
            "safe_fixes": fixes,
            "recommendations": [item.as_dict() for item in findings if not item.auto_fixable],
            "snapshot": self._snapshot(board).as_dict(),
        }
        if apply and fixes:
            backup = self._backup_board(board)
            moved = self.move_footprints(fixes)
            result.update(applied=True, moved=moved.get("moved") or [], errors=moved.get("errors") or [], backup=backup)
            result["note"] = "Solo apliqué correcciones seguras de colocación. El resto queda en recommendations."
        elif apply and not fixes:
            result["note"] = "No hay correcciones seguras automáticas; revisa recommendations."
        else:
            result["next"] = "Para aplicar solo los movimientos seguros: ipc_validate_correct apply=true."
        return result

    def _apply_place_candidate(self, candidate_id: str) -> dict:
        job = STORE.get(candidate_id)
        if job is None or job.kind != "place":
            return {"ok": False, "error": f"No hay un candidato de colocación {candidate_id}. Genera la vista previa antes."}
        board = self._board()
        backup = self._backup_board(board)
        tracks = list(_call(board, "get_tracks") or [])
        moved = self.move_footprints(job.placements)
        result = {
            "ok": not moved.get("errors"),
            "applied": True,
            "candidate_id": candidate_id,
            "moved": moved.get("moved") or [],
            "errors": moved.get("errors") or [],
            "backup": backup,
            "profile": profile(self._settings.ipc_class),
        }
        if tracks:
            result["warning"] = "Las pistas antiguas no se movieron con las huellas. Usa autoroute_board o bórralas."
        STORE.drop(candidate_id)
        return result

    def _apply_route_candidate(self, candidate_id: str) -> dict:
        job = STORE.get(candidate_id)
        if job is None or job.kind != "route":
            return {"ok": False, "error": f"No hay un candidato de autoruteo {candidate_id}. Genera la vista previa antes."}
        candidate = Path(job.files.get("candidate") or "")
        if not candidate.is_file():
            return {"ok": False, "error": "Se perdió el archivo candidato. Vuelve a autorutear."}
        board = self._board()
        backup = self._backup_board(board)
        before = self._snapshot(board)
        try:
            applied = apply_copper_to_board(board, candidate)
        except Exception as exc:
            return {"ok": False, "error": f"No pude aplicar el cobre: {exc}", "backup": backup}
        after = self._snapshot(board)
        result = {
            "ok": applied.get("ok", False),
            "applied": True,
            "candidate_id": candidate_id,
            "copper": applied,
            "backup": backup,
            "delta": compare_snapshots(before, after),
            "disclaimer": profile(self._settings.ipc_class)["disclaimer"],
        }
        if not applied.get("ok"):
            result["error"] = applied.get("error") or "No pude aplicar el cobre."
            if applied.get("missing_nets"):
                result["warning"] = f"Redes no encontradas en la placa viva: {', '.join(applied['missing_nets'])}."
            return result
        STORE.drop(candidate_id)
        return result

    def _ipc_footprints(self, board) -> list[dict]:
        footprints = list(_call(board, "get_footprints") or [])
        if not footprints:
            return []
        boxes = board.get_item_bounding_box(footprints)
        rows = []
        for footprint, box in zip(footprints, boxes):
            ref = _footprint_reference(footprint)
            px, py = _vec_mm(getattr(footprint, "position", None))
            if box is None:
                w = h = 2.0
                ox = oy = 0.0
            else:
                x, y = _vec_mm(box.pos)
                w, h = _vec_mm(box.size)
                ox = px - (x + w / 2)
                oy = py - (y + h / 2)
            locked = bool(getattr(footprint, "locked", False))
            angle = float(getattr(getattr(footprint, "orientation", None), "degrees", 0) or 0)
            rows.append(
                {
                    "reference": ref,
                    "value": text_value(getattr(footprint, "value_field", None)),
                    "x_mm": round(px, 3),
                    "y_mm": round(py, 3),
                    "width_mm": round(w, 3),
                    "height_mm": round(h, 3),
                    "origin_offset_x_mm": round(ox, 3),
                    "origin_offset_y_mm": round(oy, 3),
                    "angle": angle,
                    "locked": locked,
                }
            )
        return rows

    def _board_nets_for_ipc(self) -> list[dict]:
        project = self._project()
        schematic = self._schematic_path(project)
        cli = find_kicad_cli(self._settings.kicad_cli)
        if not schematic or not schematic.is_file() or not cli:
            return []
        data = read_netlist(cli, schematic)
        return data.get("nets") or [] if data.get("ok") else []

    def _snapshot(self, board) -> BoardSnapshot:
        footprints = list(_call(board, "get_footprints") or [])
        tracks = list(_call(board, "get_tracks") or [])
        vias = list(_call(board, "get_vias") or [])
        length = 0.0
        for track in tracks:
            try:
                length += float(track.length()) / 1_000_000
            except Exception:
                pass
        return BoardSnapshot(
            footprints=len(footprints),
            tracks=len(tracks),
            vias=len(vias),
            zones=len(list(_call(board, "get_zones") or [])),
            track_length_mm=round(length, 2),
            locked_footprints=sum(1 for fp in footprints if getattr(fp, "locked", False)),
            references=[_footprint_reference(fp) for fp in footprints],
        )

    def _backup_board(self, board) -> str:
        project = self._project()
        root = (project["path"] / ".kicad-ia-backup") if project else Path(tempfile.gettempdir()) / "kicad-ia-backup"
        root.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        path = root / f"board-{stamp}.kicad_pcb"
        path.write_text(board.get_as_string(), encoding="utf-8")
        return str(path)

    def _preview_place_image(self, board, plan: list[dict]) -> dict:
        cli = find_kicad_cli(self._settings.kicad_cli)
        project = self._project()
        if not cli or not project or not plan:
            return {}
        from kicad_ia.kicad.sexpr import child, children, dumps, parse

        text = board.get_as_string()
        root = parse(text)[0]
        by_ref = {p["reference"]: p for p in plan}
        for fp in children(root, "footprint"):
            ref = next((str(prop[2]) for prop in children(fp, "property") if str(prop[1]) == "Reference"), "")
            if ref not in by_ref:
                continue
            at = child(fp, "at")
            if at and len(at) >= 3:
                at[1], at[2] = by_ref[ref]["x_mm"], by_ref[ref]["y_mm"]
        preview = project["path"] / ".kicad-ia-place-preview.kicad_pcb"
        try:
            preview.write_text(dumps(root), encoding="utf-8")
            image = render_board(cli, preview, "pcb")
            return {"image": image.get("image"), "preview_format": image.get("format")} if image.get("ok") else {}
        finally:
            preview.unlink(missing_ok=True)
            preview.with_suffix(".kicad_prl").unlink(missing_ok=True)

    def _project(self) -> dict | None:
        for doc_type in (DOCTYPE_PCB, DOCTYPE_SCHEMATIC):
            try:
                documents = self._kicad.get_open_documents(doc_type)
            except Exception:
                continue
            for document in documents:
                project = getattr(document, "project", None)
                path = str(getattr(project, "path", "") or "")
                name = str(getattr(project, "name", "") or "")
                if path:
                    return {"name": name or Path(path).name, "path": Path(path)}
        return None

    def _schematic_path(self, project: dict | None) -> Path | None:
        if not project:
            return None
        return project["path"] / f"{project['name']}.kicad_sch"

    def _library_index(self) -> LibraryIndex:
        project = self._project()
        project_dir = project["path"] if project else None
        if self._index is None or self._index_project != project_dir:
            self._index = LibraryIndex(detect_paths(self._major, project_dir), project_dir)
            self._index_project = project_dir
        return self._index

    def _selection(self) -> list[dict]:
        board = _try(self._board)
        if board is None:
            return []
        try:
            return [normalize_item(item, "pcb") for item in board.get_selection()]
        except Exception as exc:
            return [{"editor": "pcb", "kind": "error", "reference": "", "error": str(exc)}]

    def _board(self):
        try:
            return self._kicad.get_board()
        except Exception as exc:
            raise GatewayError(f"No hay una placa abierta en el editor de PCB: {exc}") from exc


def _try(func):
    try:
        return func()
    except Exception:
        return None


def _call(target, name: str, *args):
    method = getattr(target, name, None)
    if method is None:
        return None
    try:
        return method(*args)
    except Exception:
        return None


def _connect_kicad(kicad_cls):
    # KICAD_API_TOKEN es de la instancia que lanzó el plugin. Si KiCad se
    # reinicia, la nueva rechaza ese token: hay que reintentar sin él.
    tokens = [None, ""] if os.environ.get("KICAD_API_TOKEN") else [None]
    error: Exception | None = None
    for token in tokens:
        try:
            kicad = kicad_cls(client_name="kicad-ia", kicad_token=token, timeout_ms=3000)
            kicad.ping()
            return kicad
        except Exception as exc:
            error = exc
    raise GatewayError(f"No hay un KiCad escuchando la API: {error}") from error


def _version_text(kicad) -> str:
    try:
        version = kicad.get_version()
    except Exception:
        return ""
    for attr in ("full_string", "version", "name"):
        value = getattr(version, attr, None)
        if isinstance(value, str) and value:
            return value
    return str(version)


def _major(version: str) -> int | None:
    digits = ""
    for char in version:
        if char.isdigit():
            digits += char
        elif digits:
            break
    return int(digits) if digits else None


def _mm_vector(x_mm: float, y_mm: float):
    from kipy.geometry import Vector2

    if hasattr(Vector2, "from_xy_mm"):
        return Vector2.from_xy_mm(float(x_mm), float(y_mm))
    return Vector2.from_xy(int(round(float(x_mm) * 1_000_000)), int(round(float(y_mm) * 1_000_000)))


def _vec_mm(vector) -> tuple[float, float]:
    if vector is None:
        return 0.0, 0.0
    x = float(getattr(vector, "x", 0) or 0)
    y = float(getattr(vector, "y", 0) or 0)
    return x / 1_000_000, y / 1_000_000


def _board_outline(board) -> tuple[float, float, float, float] | None:
    try:
        from kipy.proto.board.board_types_pb2 import BoardLayer

        edges = [shape for shape in board.get_shapes() if shape.layer == BoardLayer.BL_Edge_Cuts]
        if not edges:
            return None
        boxes = [box for box in board.get_item_bounding_box(edges) if box is not None]
    except Exception:
        return None
    if not boxes:
        return None
    total = boxes[0]
    for box in boxes[1:]:
        total.merge(box)
    x, y = _vec_mm(total.pos)
    w, h = _vec_mm(total.size)
    return x, y, w, h


def _footprint_reference(footprint) -> str:
    return text_value(getattr(footprint, "reference_field", None))


def _footprint_brief(footprint) -> dict:
    x_mm, y_mm = _vec_mm(getattr(footprint, "position", None))
    return {
        "reference": _footprint_reference(footprint),
        "value": text_value(getattr(footprint, "value_field", None)),
        "footprint": lib_id_text(getattr(getattr(footprint, "definition", None), "id", "")),
        "x_mm": round(x_mm, 3),
        "y_mm": round(y_mm, 3),
        "models": normalize_item(footprint, "pcb")["models"],
    }
