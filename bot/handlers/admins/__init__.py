from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiogram import Router

from . import admin_panel, broadcast_panel

routers: list[Router] = [broadcast_panel.router, admin_panel.router, admin_panel.dialog]

_all__ = ["routers"]
