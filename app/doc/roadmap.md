# Hoja de ruta

## Piezas que no están en las bibliotecas de KiCad

Hoy, si `search_parts` no encuentra la pieza, el modelo busca en LCSC (`search_lcsc`) y, cuando el usuario confirma un código C, `import_lcsc` descarga símbolo, huella y 3D con `easyeda2kicad` a la biblioteca `kicad-ia` del proyecto. No pide cuenta.

Lo que sigue:

1. SnapEDA, Ultra Librarian, SamacSys / Component Search Engine. Piden cuenta; descarga en ZIP con `.kicad_sym`, `.kicad_mod` y STEP.
2. Biblioteca de KiCad de Digi-Key (`digikey-kicad-library`), clonable.
3. Gestor de contenidos de KiCad (PCM), bibliotecas de terceros.
4. Generar desde el datasheet, solo con confirmación del usuario:
   - Huella con `kicad-footprint-generator` cuando el encapsulado es estándar (SOIC, QFN, SOT, cabeceras).
   - Modelo 3D con `kicad-packages3D-generator` (CadQuery) para encapsulados estándar.
   - Símbolo a partir de la tabla de pines del datasheet.

Lo descargado o generado va a una biblioteca del proyecto (`<proyecto>/kicad-ia.kicad_sym`, `kicad-ia.pretty`, `kicad-ia.3dshapes`) y se registra en el `sym-lib-table` y `fp-lib-table` del proyecto. Nunca en las bibliotecas del sistema.

## Agentes

Hoy hay dos modelos. `LLM_MODEL` diseña con las herramientas. `LLM_REVIEW_MODEL` revisa la propuesta de `place_circuit` contra los pines reales y puede rechazarla dos veces por mensaje; a la tercera no se escribe. Si el revisor no responde, se escribe y el resultado lo indica.

Además, `python -m kicad_ia.mcp` publica las mismas herramientas por MCP stdio (Cursor y otros clientes). Ver [mcp.md](mcp.md) y [mcp.cursor.example.json](mcp.cursor.example.json).

Arquitectura del plugin: [architecture.md](architecture.md).

Falta separar la investigación del resto:

| Agente | Hace | Herramientas |
|---|---|---|
| Diseño | Arma el circuito con piezas que existen | Las de hoy |
| Investigación | Busca la pieza en los repositorios que faltan y el datasheet | HTTP, búsqueda web |
| Biblioteca | Genera símbolo, huella y 3D cuando no hay descarga | `kicad-cli sym/fp`, generadores, `libraries.py` |
| Revisión | Ya revisa pines y alimentación. Falta contrastar con el datasheet | `describe_part`, datasheet |

El agente de diseño delega cuando falta una pieza y espera la confirmación del usuario antes de crearla.

## Por decidir

- Qué cuentas usar para SnapEDA, Ultra Librarian y SamacSys. LCSC ya funciona sin cuenta.

## Otros pendientes

- KiCad 11: API de esquemático y de bibliotecas en vivo. Cuando salga estable, escribir por API y no por archivo.
- Marcar con no-connect los pines que el usuario decida no usar.
- Botón en el chat para restaurar la última copia de `.kicad-ia-backup/`.
- `organize_layout` en el esquemático rehace la hoja con etiquetas. Falta conservar los cables dibujados a mano y la rotación de cada símbolo.
- En la placa, `organize_layout` no tiene en cuenta los conectores en el borde ni las zonas prohibidas. Falta borrar las pistas que quedan huérfanas.
- Sin grupos dados por el modelo, un condensador de un riel va con el regulador que lo alimenta, aunque sea de desacoplo de otro integrado.
- El pre-chequeo IPC Clase 2 no cubre IPC-A-610 ni IPC-6012; no afirma certificación.
- FreeRouting no respeta planos de masa/alimentación a menos que marques clases a ignorar (`ignore_net_classes`).
- Fijamos FreeRouting **2.0.1** (Java 17+): 2.1.x ignora max_passes en headless; 2.2+ exige Java 25.
- Aplicar SES a la placa viva recrea pistas/vías por API; arcos y reglas avanzadas pueden quedar incompletos.
