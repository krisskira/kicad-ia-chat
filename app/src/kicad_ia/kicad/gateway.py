"""Puerta de acceso a KiCad.

Las herramientas del registry no importan `kipy` directamente: pasan por un
Gateway (real o fake). Así el chat y MCP comparten contrato y las pruebas
pueden usar FakeGateway sin editor abierto.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class GatewayError(RuntimeError):
    pass


class Gateway(ABC):
    @abstractmethod
    def capabilities(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def inspect(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def search_parts(self, kind: str, query: str, limit: int) -> dict:
        raise NotImplementedError

    @abstractmethod
    def search_lcsc(self, query: str, limit: int) -> dict:
        raise NotImplementedError

    @abstractmethod
    def import_lcsc(self, lcsc_id: str) -> dict:
        raise NotImplementedError

    @abstractmethod
    def describe_part(self, lib_id: str) -> dict:
        raise NotImplementedError

    @abstractmethod
    def describe_footprint(self, lib_id: str) -> dict:
        raise NotImplementedError

    @abstractmethod
    def place_circuit(self, symbols: list[dict], nets: list[dict], connections: list[dict], replace: bool = False) -> dict:
        raise NotImplementedError

    @abstractmethod
    def assign_footprint(self, reference: str, footprint: str) -> dict:
        raise NotImplementedError

    @abstractmethod
    def sync_board(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def board_state(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def move_footprints(self, placements: list[dict]) -> dict:
        raise NotImplementedError

    @abstractmethod
    def list_models(self, reference: str | None) -> dict:
        raise NotImplementedError

    @abstractmethod
    def routing(self, mode: str, action: str | None) -> dict:
        raise NotImplementedError

    @abstractmethod
    def selection(self) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def render_view(self, view: str) -> dict:
        raise NotImplementedError

    @abstractmethod
    def organize_layout(self, target: str, groups: list[dict] | None, apply: bool = True) -> dict:
        raise NotImplementedError

    @abstractmethod
    def ipc_place_components(
        self, groups: list[dict] | None, apply: bool = False, candidate_id: str | None = None, class_id: str = "2"
    ) -> dict:
        raise NotImplementedError

    @abstractmethod
    def autoroute_board(
        self,
        apply: bool = False,
        candidate_id: str | None = None,
        ignore_net_classes: list[str] | None = None,
        max_passes: int = 100,
    ) -> dict:
        raise NotImplementedError

    @abstractmethod
    def ipc_validate_correct(self, apply: bool = False, class_id: str = "2") -> dict:
        raise NotImplementedError
