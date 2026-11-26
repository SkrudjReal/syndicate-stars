from . import start_help, support, partners, dev, buy_stars, inline_converter

routers = [
    dev.router,
    inline_converter.router,
    start_help.router,
    buy_stars.router,
    support.router,
    partners.router,
]

__all__ = ['routers']
