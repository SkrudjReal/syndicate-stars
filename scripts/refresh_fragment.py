"""
Semi-automatic Fragment cookie refresh.

Usage:
    uv run python scripts/refresh_fragment.py

What it does:
    1. Opens fragment.com in a browser
    2. You log in manually (wallet + Telegram)
    3. Script intercepts API requests to extract hash
    4. Extracts cookies
    5. Updates .env file automatically

Requirements:
    uv sync --frozen
    uv run playwright install chromium
"""

import re
import sys
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print('playwright not installed. Run:')
    print('  uv sync --frozen')
    print('  uv run playwright install chromium')
    sys.exit(1)


ENV_PATH = Path(__file__).parent.parent / '.env'


def update_env(key: str, value: str) -> None:
    if not ENV_PATH.exists():
        ENV_PATH.write_text(f'{key}={value}\n')
        return

    content = ENV_PATH.read_text()
    pattern = re.compile(rf'^{re.escape(key)}=.*$', re.MULTILINE)

    if pattern.search(content):
        content = pattern.sub(f'{key}={value}', content)
    else:
        content = content.rstrip('\n') + f'\n{key}={value}\n'

    ENV_PATH.write_text(content)


def main():
    print('Starting browser...')

    captured_hash = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # Intercept all requests to fragment.com/api?hash=...
        def on_request(request):
            if 'fragment.com/api' in request.url and 'hash=' in request.url:
                h = re.search(r'hash=([a-f0-9]+)', request.url)
                if h and h.group(1) not in captured_hash:
                    captured_hash.append(h.group(1))
                    print('  Captured Fragment API hash.')

        page.on('request', on_request)

        page.goto('https://fragment.com')
        print('Opened fragment.com')
        print()
        print('>>> Log in manually: connect wallet + Telegram account <<<')
        print('>>> Then navigate around (e.g. click Stars) to trigger API requests <<<')
        print('>>> Waiting for fragment.com/api?hash=... requests (up to 10 min) <<<')
        print()

        # Poll until we capture a hash (up to 600 seconds)
        elapsed = 0
        while not captured_hash and elapsed < 600:
            page.wait_for_timeout(2000)
            elapsed += 2

        if not captured_hash:
            print('Timeout — no API requests captured. Try again.')
            browser.close()
            sys.exit(1)

        print()
        print(f'Got hash! Extracting cookies...')

        # Extract cookies
        cookies = context.cookies()
        cookie_str = '; '.join(f'{c["name"]}={c["value"]}' for c in cookies)
        hash_value = captured_hash[0]

        browser.close()

    if not cookie_str:
        print('Failed to extract cookies!')
        sys.exit(1)

    # Update .env
    update_env('FRAGMENT_COOKIES', cookie_str)
    update_env('FRAGMENT_HASH_VALUE', hash_value)

    print()
    print('Done! Updated .env:')
    print('  FRAGMENT_COOKIES updated (not displayed).')
    print('  FRAGMENT_HASH_VALUE updated (not displayed).')
    print()
    print('Restart the bot to apply changes.')


if __name__ == '__main__':
    main()
