import asyncio


async def _run() -> None:
    # Payment SDKs bind to the event loop during import.
    from bot.runtime import _main

    await _main()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
