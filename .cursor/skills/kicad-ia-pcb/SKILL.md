---
name: kicad-ia-pcb
description: >-
  PCB del plugin KiCad IA: pre-chequeo IPC Clase 2, colocación, autoruteo
  FreeRouting (DSN/SES), DRC, candidatos apply=false/true, reglas de fabricación.
  Usar al tocar ipc.py, freerouting, pcbnew_bridge, copper_apply, pcb_review, autoroute.
---

# Skill: PCB / IPC / autoruteo

Leer [app/AGENTS.md](../../../app/AGENTS.md), [app/doc/architecture.md](../../../app/doc/architecture.md) (sección PCB seguro) y el mapa en [app/README.md](../../../app/README.md).

## Módulos

| Archivo | Rol |
|---------|-----|
| `kicad/ipc.py` | Perfil Clase 2, auditoría, `place_ipc`, `safe_fixes` |
| `kicad/pcb_metrics.py` | Scores y comparación before/after |
| `kicad/candidates.py` | Almacén de candidatos |
| `kicad/pcbnew_bridge.py` | DSN/SES + `apply_fab_rules` vía Python de KiCad |
| `kicad/freerouting.py` | JAR verificado 2.0.1, Java, pipeline |
| `kicad/copper_apply.py` | Aplicar cobre del candidato a la placa viva |
| `agent/pcb_review.py` | Revisor: no aprobar DRC duro / regresiones |

Herramientas: `ipc_place_components`, `autoroute_board`, `ipc_validate_correct`.

## Reglas

- Siempre preview (`apply=false`) → `candidate_id` → confirmación → `apply=true`.
- No mover huellas bloqueadas; si hay cobre y se recolocan pads, avisar de re-ruteo.
- Autoruteo solo si `autoroute_enabled` y fab (pista, clearance, vía, taladro) configurados.
- FreeRouting **2.0.1** (no 2.1.x headless infinito; 2.2+ pide Java 25).
- El informe debe decir que es **pre-chequeo**, no certificación IPC-A-610/6012.
- Trabajar sobre copias; no tocar el proyecto demo vivo en pruebas E2E.

## Comprobar

```bash
cd app && .venv/bin/pytest tests/test_ipc.py tests/test_pcb_tools.py
```
