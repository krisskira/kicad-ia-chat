"""KiCad de mentira: mismo contrato que la API, sin editor abierto."""

from __future__ import annotations

import uuid
from html import escape

from kicad_ia.kicad.catalog import CATALOG, footprints
from kicad_ia.kicad.circuit import PlacedFootprint, PlacedSymbol, grid_note, snapped_symbol
from kicad_ia.kicad.gateway import Gateway
from kicad_ia.kicad.layout import auto_groups, group_layout, normalize_groups
from kicad_ia.kicad.render import VIEWS, renders_dir
from kicad_ia.kicad.sch_writer import nets_from_connections


class FakeGateway(Gateway):
    def __init__(self) -> None:
        self.symbols: dict[str, PlacedSymbol] = {}
        self.wires: list[dict] = []
        self.labels: list[dict] = []
        self.footprints: dict[str, PlacedFootprint] = {}
        self.selected: list[dict] = []
        self.fallback_reason = ""
        self.router_runs: list[dict] = []

    def capabilities(self) -> dict:
        notes = [
            "Modo de desarrollo: los cambios se quedan en memoria y no entran en KiCad.",
            "La galería de este modo es un catálogo corto de piezas habituales.",
        ]
        if self.fallback_reason:
            notes.insert(0, f"KiCad no respondió: {self.fallback_reason}")
        return {
            "connected": False,
            "backend": "fake",
            "kicad_version": None,
            "schematic_edit": True,
            "board_selection": True,
            "schematic_selection": True,
            "library_search": True,
            "netlist_sync": True,
            "models_3d": True,
            "external_router": False,
            "autoroute_enabled": False,
            "freerouting": False,
            "java": {"ok": False, "error": "Modo desarrollo"},
            "fab": {},
            "notes": notes,
        }

    def inspect(self) -> dict:
        return {
            "ok": True,
            "project": "desarrollo",
            "selection": list(self.selected),
            "schematic": {
                "symbols": [item.as_dict() for item in self.symbols.values()],
                "wire_count": len(self.wires),
                "label_count": len(self.labels),
            },
            "board": {
                "footprints": [item.as_dict() for item in self.footprints.values()],
            },
            "capabilities": self.capabilities(),
        }

    def search_lcsc(self, query: str, limit: int) -> dict:
        del query, limit
        return {"ok": False, "error": "La búsqueda LCSC no está en el modo de desarrollo."}

    def import_lcsc(self, lcsc_id: str) -> dict:
        del lcsc_id
        return {"ok": False, "error": "Importar desde LCSC necesita un proyecto de KiCad abierto."}

    def search_parts(self, kind: str, query: str, limit: int) -> dict:
        needle = query.casefold().strip()
        limit = max(1, min(limit, 40))
        if kind == "symbol":
            rows = [
                part.as_dict()
                for part in CATALOG.values()
                if not needle
                or needle in part.lib_id.casefold()
                or needle in part.description.casefold()
            ]
        elif kind == "footprint":
            rows = [
                row
                for row in footprints()
                if not needle or needle in row["lib_id"].casefold()
            ]
        elif kind == "model":
            rows = [
                {"lib_id": part.lib_id, "model": part.default_model, "footprint": part.default_footprint}
                for part in CATALOG.values()
                if part.default_model
                and (
                    not needle
                    or needle in part.default_model.casefold()
                    or needle in part.lib_id.casefold()
                )
            ]
        else:
            return {"ok": False, "error": "kind debe ser symbol, footprint o model."}
        return {"ok": True, "kind": kind, "query": query, "matches": rows[:limit]}

    def describe_part(self, lib_id: str) -> dict:
        part = CATALOG.get(lib_id)
        if part is None:
            known = ", ".join(sorted(CATALOG))
            return {
                "ok": False,
                "error": f"No está en la galería de desarrollo: {lib_id}. Piezas: {known}",
            }
        return {"ok": True, "part": part.as_dict(), "grid_mm": 1.27}

    def describe_footprint(self, lib_id: str) -> dict:
        for row in footprints():
            if row["lib_id"] == lib_id:
                return {"ok": True, "footprint": {"lib_id": lib_id, "models": [{"path": row["model"], "exists": False}]}}
        return {"ok": False, "error": f"No está en la galería de desarrollo: {lib_id}."}

    def place_circuit(self, symbols: list[dict], nets: list[dict], connections: list[dict], replace: bool = False) -> dict:
        if replace:
            self.symbols.clear()
            self.labels.clear()
        all_nets = list(nets) + nets_from_connections(connections)
        result = self._place(symbols)
        for net in all_nets:
            name = str(net.get("name") or "").strip()
            if not name:
                result["errors"].append("Una red no tiene nombre.")
                continue
            for member in net.get("pins") or []:
                symbol = self.symbols.get(str(member.get("reference") or ""))
                pin = str(member.get("pin") or "")
                if symbol is None:
                    result["errors"].append(f"Red {name}: no está {member.get('reference')}.")
                elif symbol.pin_position(pin) is None:
                    result["errors"].append(f"Red {name}: {symbol.reference} no tiene el pin {pin}.")
                else:
                    self.labels.append({"text": name, "reference": symbol.reference, "pin": pin})
        result["nets"] = [net.get("name") for net in all_nets]
        result["ok"] = not result["errors"]
        return result

    def _place(self, symbols: list[dict]) -> dict:
        placed: list[PlacedSymbol] = []
        errors: list[str] = []
        for position, spec in enumerate(symbols):
            lib_id = str(spec.get("lib_id") or "")
            part = CATALOG.get(lib_id)
            if part is None:
                errors.append(f"Símbolo desconocido: {lib_id}.")
                continue
            reference = str(spec.get("reference") or self._next_reference(part.reference_prefix))
            if reference in self.symbols or any(item.reference == reference for item in placed):
                errors.append(f"La referencia {reference} ya existe.")
                continue
            item = snapped_symbol(
                {
                    **spec,
                    "reference": reference,
                    "footprint": spec.get("footprint") or part.default_footprint,
                    "x_mm": spec.get("x_mm", 50.8 + 50.8 * position),
                    "y_mm": spec.get("y_mm", 76.2),
                },
                list(part.pins),
            )
            placed.append(item)

        for item in placed:
            self.symbols[item.reference] = item
        return {
            "ok": not errors,
            "placed": [item.as_dict() for item in placed],
            "errors": errors,
            "grid": grid_note(),
            "backend": "fake",
        }

    def assign_footprint(self, reference: str, footprint: str) -> dict:
        symbol = self.symbols.get(reference)
        if symbol is None:
            return {"ok": False, "error": f"No hay ningún símbolo {reference}."}
        symbol.footprint = footprint
        if reference in self.footprints:
            self.footprints[reference].footprint = footprint
        return {"ok": True, "reference": reference, "footprint": footprint}

    def sync_board(self) -> dict:
        created = []
        cursor = 10.0
        for symbol in self.symbols.values():
            if not symbol.footprint or symbol.reference in self.footprints:
                continue
            part = CATALOG.get(symbol.lib_id)
            model = part.default_model if part else ""
            footprint = PlacedFootprint(
                reference=symbol.reference,
                footprint=symbol.footprint,
                value=symbol.value,
                x_mm=cursor,
                y_mm=10.0,
                model=model,
            )
            self.footprints[symbol.reference] = footprint
            created.append(footprint.as_dict())
            cursor += 8.0
        return {
            "ok": True,
            "created": created,
            "footprints": [item.as_dict() for item in self.footprints.values()],
            "note": "En KiCad real esto exporta el netlist e importa la placa.",
            "board_area": self._board_area_payload(),
        }

    def _board_area_payload(self) -> dict:
        from kicad_ia.kicad.board_area import board_area_report

        boxes = [(item.x_mm - 4, item.y_mm - 4, 8, 8) for item in self.footprints.values()]
        return board_area_report(None, boxes)

    def board_state(self) -> dict:
        return {
            "ok": True,
            "board_area": self._board_area_payload(),
            "footprints": [item.as_dict() for item in self.footprints.values()],
            "tracks": 0,
            "vias": 0,
            "zones": 0,
        }

    def move_footprints(self, placements: list[dict]) -> dict:
        moved = []
        errors = []
        for placement in placements:
            reference = str(placement.get("reference") or "")
            footprint = self.footprints.get(reference)
            if footprint is None:
                errors.append(f"No está en la placa: {reference}.")
                continue
            footprint.x_mm = float(placement["x_mm"])
            footprint.y_mm = float(placement["y_mm"])
            moved.append(footprint.as_dict())
        return {"ok": not errors, "moved": moved, "errors": errors}

    def list_models(self, reference: str | None) -> dict:
        if reference:
            footprint = self.footprints.get(reference)
            symbol = self.symbols.get(reference)
            if footprint is None and symbol is None:
                return {"ok": False, "error": f"No existe {reference}."}
            model = footprint.model if footprint else ""
            if not model and symbol:
                part = CATALOG.get(symbol.lib_id)
                model = part.default_model if part else ""
            return {
                "ok": True,
                "reference": reference,
                "footprint": (footprint.footprint if footprint else symbol.footprint if symbol else ""),
                "models": [model] if model else [],
            }
        rows = []
        for item in self.footprints.values():
            rows.append(
                {
                    "reference": item.reference,
                    "footprint": item.footprint,
                    "models": [item.model] if item.model else [],
                }
            )
        if not rows and self.selected:
            return {"ok": True, "from_selection": True, "items": list(self.selected)}
        return {"ok": True, "items": rows}

    def routing(self, mode: str, action: str | None) -> dict:
        if mode == "status":
            return {
                "ok": True,
                "mode": "status",
                "tracks": 0,
                "vias": 0,
                "footprints": len(self.footprints),
                "note": "Modo de desarrollo: no hay cobre real que rutear.",
            }
        if mode == "interactive":
            return {
                "ok": False,
                "error": "El router interactivo solo existe dentro de KiCad.",
                "action": action or "",
            }
        if mode == "external":
            self.router_runs.append({"action": action or ""})
            return {
                "ok": False,
                "error": "El ruteador externo se lanza solo con KiCad conectado y ROUTER_COMMAND definido.",
            }
        return {"ok": False, "error": "mode debe ser status, interactive o external."}

    def selection(self) -> list[dict]:
        return list(self.selected)

    def render_view(self, view: str) -> dict:
        if view not in VIEWS:
            return {"ok": False, "error": f"view debe ser uno de: {', '.join(VIEWS)}."}
        items = list(self.symbols.values()) if view == "schematic" else list(self.footprints.values())
        rows = "".join(
            f'<text x="10" y="{24 + 18 * index}" font-family="monospace" font-size="14">{escape(item.reference)} {escape(item.value or "")}</text>'
            for index, item in enumerate(items)
        )
        height = 40 + 18 * len(items)
        target = renders_dir() / f"fake-{view}-{uuid.uuid4().hex[:8]}.svg"
        target.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="320" height="{height}">{rows}</svg>', encoding="utf-8")
        return {"ok": True, "image": f"/renders/{target.name}", "format": "svg", "note": "Imagen del modo de desarrollo."}

    def organize_layout(self, target: str, groups: list[dict] | None, apply: bool = True) -> dict:
        if target not in ("schematic", "pcb", "both"):
            return {"ok": False, "error": "target debe ser schematic, pcb o both."}
        nets: dict[str, list[dict]] = {}
        for label in self.labels:
            nets.setdefault(label["text"], []).append({"ref": label["reference"], "pin": label["pin"], "pintype": ""})
        components = [{"reference": ref, "value": item.value} for ref, item in self.symbols.items()]
        plan = groups or auto_groups(components, [{"name": name, "nodes": nodes} for name, nodes in nets.items()])
        result: dict = {"ok": True, "target": target, "groups": plan}
        if target in ("pcb", "both") and self.footprints:
            sizes = {ref: (6.0, 4.0) for ref in self.footprints}
            clean, _ = normalize_groups(plan, list(sizes))
            centers, _, _ = group_layout(sizes, clean, 60.0, item_gap=1.5, group_gap=5.0, padding=1.0)
            placements = [{"reference": ref, "x_mm": 10 + x, "y_mm": 10 + y} for ref, (x, y) in centers.items()]
            if apply:
                self.move_footprints(placements)
            result["pcb"] = {"ok": True, "applied": apply, "placements": placements}
        if target in ("schematic", "both"):
            result["schematic"] = {"ok": True, "applied": False, "note": "El modo de desarrollo no dibuja esquemáticos."}
        return result

    def ipc_place_components(
        self, groups: list[dict] | None, apply: bool = False, candidate_id: str | None = None, class_id: str = "2"
    ) -> dict:
        from kicad_ia.kicad.candidates import STORE
        from kicad_ia.kicad.ipc import place_ipc, profile

        if apply and candidate_id:
            job = STORE.get(candidate_id)
            if job is None:
                return {"ok": False, "error": "Candidato desconocido."}
            moved = self.move_footprints(job.placements)
            STORE.drop(candidate_id)
            return {"ok": True, "applied": True, "moved": moved.get("moved") or [], "candidate_id": candidate_id}
        fps = [
            {
                "reference": item.reference,
                "value": item.value,
                "x_mm": item.x_mm,
                "y_mm": item.y_mm,
                "width_mm": 4.0,
                "height_mm": 3.0,
                "locked": False,
            }
            for item in self.footprints.values()
        ]
        plan, findings = place_ipc(fps, groups or [{"name": "Circuito", "references": [f["reference"] for f in fps]}], None, class_id)
        job = STORE.put("place", "fake", placements=plan, report={"ipc_findings": [f.as_dict() for f in findings]}, approved=True)
        return {
            "ok": True,
            "applied": False,
            "candidate_id": job.id,
            "placements": plan,
            "ipc_findings": [f.as_dict() for f in findings],
            "profile": profile(class_id),
            "next": f"Confirma con apply=true candidate_id={job.id}.",
        }

    def autoroute_board(
        self,
        apply: bool = False,
        candidate_id: str | None = None,
        ignore_net_classes: list[str] | None = None,
        max_passes: int = 100,
    ) -> dict:
        from kicad_ia.kicad.candidates import STORE

        del ignore_net_classes, max_passes
        if apply and candidate_id:
            job = STORE.get(candidate_id)
            if job is None:
                return {"ok": False, "error": "Candidato desconocido."}
            STORE.drop(candidate_id)
            return {
                "ok": True,
                "applied": True,
                "candidate_id": candidate_id,
                "copper": {"tracks_created": 3, "vias_created": 1},
                "note": "Modo de desarrollo: cobre simulado.",
            }
        job = STORE.put(
            "route",
            "fake",
            files={},
            report={"operation": "autoroute", "drc": {"ok": True, "error_count": 0, "unconnected": 0}},
            approved=True,
        )
        return {
            "ok": True,
            "applied": False,
            "candidate_id": job.id,
            "drc": {"ok": True, "verdict": "DRC simulado limpio.", "error_count": 0, "warning_count": 0, "unconnected": 0, "problems": []},
            "score": {"score": 1100, "errors": 0, "warnings": 0, "unconnected": 0, "tracks": 3, "vias": 1},
            "baseline_score": {"score": 1000, "errors": 0, "warnings": 0, "unconnected": 2, "tracks": 0, "vias": 0},
            "better_than": True,
            "next": f"Confirma con apply=true candidate_id={job.id}.",
        }

    def ipc_validate_correct(self, apply: bool = False, class_id: str = "2") -> dict:
        from kicad_ia.kicad.ipc import audit_placement, profile, safe_fixes

        fps = [
            {
                "reference": item.reference,
                "value": item.value,
                "x_mm": item.x_mm,
                "y_mm": item.y_mm,
                "width_mm": 4.0,
                "height_mm": 3.0,
            }
            for item in self.footprints.values()
        ]
        findings = audit_placement(fps, None, class_id=class_id)
        fixes = safe_fixes(findings, fps, None)
        result = {
            "ok": True,
            "applied": False,
            "profile": profile(class_id),
            "disclaimer": profile(class_id)["disclaimer"],
            "drc": {"ok": True, "verdict": "DRC simulado.", "error_count": 0, "warning_count": 0, "problems": []},
            "ipc_findings": [f.as_dict() for f in findings],
            "safe_fixes": fixes,
            "recommendations": [f.as_dict() for f in findings if not f.auto_fixable],
        }
        if apply and fixes:
            self.move_footprints(fixes)
            result.update(applied=True, moved=fixes)
        return result

    def _next_reference(self, prefix: str) -> str:
        if prefix == "#PWR":
            prefix = "PWR"
        number = 1
        taken = set(self.symbols)
        while f"{prefix}{number}" in taken:
            number += 1
        return f"{prefix}{number}"
