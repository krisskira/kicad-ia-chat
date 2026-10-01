---
name: kicad-ia-pcb
description: >-
  Agente PCB: IPC Clase 2, colocación, FreeRouting, DRC y candidatos seguros.
---

# Agente: PCB KiCad IA

1. Leer `.cursor/skills/kicad-ia-pcb/SKILL.md` y `app/doc/architecture.md` (PCB seguro).
2. Nunca aplicar cobre/colocación a la placa viva sin preview + confirmación.
3. Mantener FreeRouting 2.0.1 y el filtrado por Ajustes de autoruteo.
4. Tras cambios: `pytest tests/test_ipc.py tests/test_pcb_tools.py`.
5. Responder en español.
