"""Piezas de referencia para el modo de desarrollo.

Las posiciones de pin están en milímetros respecto al origen del símbolo y
caen en la retícula de 1,27 mm. En KiCad real, describe_part lee la biblioteca.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogPin:
    number: str
    name: str
    x_mm: float
    y_mm: float

    def as_dict(self) -> dict[str, str | float]:
        return {
            "number": self.number,
            "name": self.name,
            "x_mm": self.x_mm,
            "y_mm": self.y_mm,
        }


@dataclass(frozen=True)
class CatalogPart:
    lib_id: str
    description: str
    reference_prefix: str
    default_footprint: str
    default_model: str
    pins: tuple[CatalogPin, ...]

    def as_dict(self) -> dict:
        return {
            "lib_id": self.lib_id,
            "description": self.description,
            "reference_prefix": self.reference_prefix,
            "footprint": self.default_footprint,
            "model": self.default_model,
            "pins": [pin.as_dict() for pin in self.pins],
        }


def _pins(*pairs: tuple[str, float, float]) -> tuple[CatalogPin, ...]:
    return tuple(CatalogPin(number, "~", x, y) for number, x, y in pairs)


CATALOG: dict[str, CatalogPart] = {
    "Device:R": CatalogPart(
        "Device:R",
        "Resistencia",
        "R",
        "Resistor_SMD:R_0603_1608Metric",
        "${KICAD9_3DMODEL_DIR}/Resistor_SMD.3dshapes/R_0603_1608Metric.step",
        _pins(("1", -5.08, 0.0), ("2", 5.08, 0.0)),
    ),
    "Device:C": CatalogPart(
        "Device:C",
        "Condensador",
        "C",
        "Capacitor_SMD:C_0603_1608Metric",
        "${KICAD9_3DMODEL_DIR}/Capacitor_SMD.3dshapes/C_0603_1608Metric.step",
        _pins(("1", -2.54, 0.0), ("2", 2.54, 0.0)),
    ),
    "Device:L": CatalogPart(
        "Device:L",
        "Inductor",
        "L",
        "Inductor_SMD:L_0603_1608Metric",
        "${KICAD9_3DMODEL_DIR}/Inductor_SMD.3dshapes/L_0603_1608Metric.step",
        _pins(("1", -5.08, 0.0), ("2", 5.08, 0.0)),
    ),
    "Device:LED": CatalogPart(
        "Device:LED",
        "LED",
        "D",
        "LED_SMD:LED_0603_1608Metric",
        "${KICAD9_3DMODEL_DIR}/LED_SMD.3dshapes/LED_0603_1608Metric.step",
        _pins(("1", -3.81, 0.0), ("2", 3.81, 0.0)),
    ),
    "Device:Crystal": CatalogPart(
        "Device:Crystal",
        "Cristal",
        "Y",
        "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm",
        "${KICAD9_3DMODEL_DIR}/Crystal.3dshapes/Crystal_SMD_3225-4Pin_3.2x2.5mm.step",
        _pins(("1", -3.81, 0.0), ("2", 3.81, 0.0)),
    ),
    "power:VCC": CatalogPart(
        "power:VCC",
        "Alimentación VCC",
        "#PWR",
        "",
        "",
        _pins(("1", 0.0, 0.0)),
    ),
    "power:+3V3": CatalogPart(
        "power:+3V3",
        "Alimentación +3.3V",
        "#PWR",
        "",
        "",
        _pins(("1", 0.0, 0.0)),
    ),
    "power:VBAT": CatalogPart(
        "power:VBAT",
        "Voltaje de Batería (+3.7V Li-Ion)",
        "#PWR",
        "",
        "",
        _pins(("1", 0.0, 0.0)),
    ),
    "power:GND": CatalogPart(
        "power:GND",
        "Masa",
        "#PWR",
        "",
        "",
        _pins(("1", 0.0, 0.0)),
    ),
    "Connector_Generic:Conn_01x02": CatalogPart(
        "Connector_Generic:Conn_01x02",
        "Conector de dos pines",
        "J",
        "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
        "${KICAD9_3DMODEL_DIR}/Connector_PinHeader_2.54mm.3dshapes/PinHeader_1x02_P2.54mm_Vertical.step",
        _pins(("1", 0.0, 2.54), ("2", 0.0, -2.54)),
    ),
    "Battery:Battery_Cell_18650": CatalogPart(
        "Battery:Battery_Cell_18650",
        "Batería Li-Ion 18650 3.7V 3000mAh",
        "BT",
        "Battery:BatteryHolder_Keystone_1042_1x18650",
        "${KICAD9_3DMODEL_DIR}/Battery.3dshapes/BatteryHolder_Keystone_1042_1x18650.step",
        _pins(("1", 0.0, 5.08), ("2", 0.0, -5.08)),
    ),
    "Regulator_Linear:AP2112K-3.3": CatalogPart(
        "Regulator_Linear:AP2112K-3.3",
        "Regulador LDO 3.3V 600mA Low-Dropout (SOT-23-5)",
        "U",
        "Package_TO_SOT_SMD:SOT-23-5",
        "${KICAD9_3DMODEL_DIR}/Package_TO_SOT_SMD.3dshapes/SOT-23-5.step",
        (
            CatalogPin("1", "VIN", -5.08, 2.54),
            CatalogPin("2", "GND", 0.0, -5.08),
            CatalogPin("3", "EN", -5.08, -2.54),
            CatalogPin("4", "NC", 5.08, -2.54),
            CatalogPin("5", "VOUT", 5.08, 2.54),
        ),
    ),
    "RF_Module:ESP32-S3-WROOM-1": CatalogPart(
        "RF_Module:ESP32-S3-WROOM-1",
        "Módulo Microcontrolador ESP32-S3 (R8N16 16MB Flash 8MB PSRAM WiFi BLE)",
        "U",
        "RF_Module:ESP32-S3-WROOM-1",
        "${KICAD9_3DMODEL_DIR}/RF_Module.3dshapes/ESP32-S3-WROOM-1.step",
        (
            CatalogPin("1", "GND", -10.16, -12.7),
            CatalogPin("2", "3V3", -10.16, 12.7),
            CatalogPin("3", "EN", -10.16, 10.16),
            CatalogPin("4", "IO4", -10.16, 7.62),
            CatalogPin("5", "IO5", -10.16, 5.08),
            CatalogPin("6", "IO6", -10.16, 2.54),
            CatalogPin("7", "IO7", -10.16, 0.0),
            CatalogPin("10", "IO10_MOSI", 10.16, 5.08),
            CatalogPin("11", "IO11_SCK", 10.16, 2.54),
            CatalogPin("12", "IO12_MISO", 10.16, 0.0),
            CatalogPin("13", "IO13_CS", 10.16, -2.54),
            CatalogPin("14", "IO14_DC", 10.16, -5.08),
            CatalogPin("15", "IO15_RST", 10.16, -7.62),
            CatalogPin("41", "GND", 10.16, -12.7),
        ),
    ),
    "Display:ILI9341_SPI": CatalogPart(
        "Display:ILI9341_SPI",
        "Pantalla TFT Color SPI 2.4/2.8/3.2 (ILI9341 / ILI9140)",
        "DISP",
        "Display:TFT_2.4_240x320_SPI",
        "${KICAD9_3DMODEL_DIR}/Display.3dshapes/TFT_2.4_240x320_SPI.step",
        (
            CatalogPin("1", "VCC", -7.62, 10.16),
            CatalogPin("2", "GND", -7.62, 7.62),
            CatalogPin("3", "CS", -7.62, 5.08),
            CatalogPin("4", "RESET", -7.62, 2.54),
            CatalogPin("5", "DC_RS", -7.62, 0.0),
            CatalogPin("6", "MOSI_SDI", -7.62, -2.54),
            CatalogPin("7", "SCK_CLK", -7.62, -5.08),
            CatalogPin("8", "LED_BL", -7.62, -7.62),
            CatalogPin("9", "MISO_SDO", -7.62, -10.16),
        ),
    ),
}


def footprints() -> list[dict[str, str]]:
    seen: dict[str, str] = {}
    for part in CATALOG.values():
        if part.default_footprint:
            seen[part.default_footprint] = part.default_model
    return [
        {"lib_id": lib_id, "model": model}
        for lib_id, model in sorted(seen.items())
    ]
