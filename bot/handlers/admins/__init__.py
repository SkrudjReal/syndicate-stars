from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiogram import Router

from . import admin_panel

routers: list[Router] = [admin_panel.router, admin_panel.dialog]

_all__ = ["routers"]
