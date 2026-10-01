from kicad_ia.kicad.fake import FakeGateway
from kicad_ia.kicad.gateway import Gateway
from kicad_ia.config import Settings


def open_gateway(settings: Settings) -> Gateway:
    if settings.kicad_mode == "fake":
        return FakeGateway()
    from kicad_ia.kicad.kipy_gateway import KipyGateway

    if settings.kicad_mode == "live":
        return KipyGateway(settings)
    try:
        return KipyGateway(settings)
    except Exception as exc:
        gateway = FakeGateway()
        gateway.fallback_reason = str(exc)
        return gateway
