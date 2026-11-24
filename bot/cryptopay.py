import base64
import asyncio
import logging
import re
import requests

from aiocryptopay import AioCryptoPay, Networks
from bot.settings import settings

logger = logging.getLogger(__name__)

crypto: AioCryptoPay | None = None

if settings.cryptopay.token:
    crypto = AioCryptoPay(token=settings.cryptopay.token, network=Networks.MAIN_NET)


class CryptoPay:
    @staticmethod
    async def get_status(invoice_id: int) -> str:
        invoices = await crypto.get_invoices(invoice_ids=invoice_id)
        return invoices.status


class FragmentAPI:

    def __init__(self, cookies: str, hash_value: str):
        self.cookies = cookies
        self.hash_value = hash_value

    def _post(self, data: dict, referer: str = 'https://fragment.com/stars/buy') -> dict:
        params = {'hash': self.hash_value}
        headers = {
            'accept': 'application/json, text/javascript, */*; q=0.01',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'origin': 'https://fragment.com',
            'referer': referer,
            'cookie': self.cookies,
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'x-requested-with': 'XMLHttpRequest',
        }
        resp = requests.post('https://fragment.com/api', params=params, headers=headers, data=data, timeout=20)
        result = resp.json()
        if result.get('error') == 'Bad request':
            # Fragment rotates the API hash independently of the login cookies.
            page = requests.get(
                referer, headers={'Cookie': self.cookies}, timeout=20,
            )
            page.raise_for_status()
            match = re.search(r'/api\?hash=([a-f0-9]+)', page.text)
            if match and match[1] != self.hash_value:
                self.hash_value = match[1]
                params['hash'] = self.hash_value
                resp = requests.post('https://fragment.com/api', params=params, headers=headers, data=data, timeout=20)
                result = resp.json()
        if result.get('error') == 'This account is already subscribed to Telegram Premium.':
            result['error'] = 'У этого аккаунта уже есть Telegram Premium. Покупка сейчас недоступна.'
        elif result.get('error') == 'Bad request':
            result['error'] = 'Не удалось выполнить запрос Fragment. Обратитесь в поддержку — @maneramur.'
        return result

    def search_recipient(self, username: str) -> dict:
        return self._post({
            'query': username,
            'quantity': '',
            'method': 'searchStarsRecipient',
        })

    def init_buy_stars(self, recipient: str, quantity: int) -> dict:
        return self._post({
            'recipient': recipient,
            'quantity': quantity,
            'method': 'initBuyStarsRequest',
        })

    def get_buy_link(self, req_id: str, show_sender: bool = False) -> dict:
        return self._post({
            'transaction': '1',
            'id': req_id,
            'show_sender': '1' if show_sender else '0',
            'method': 'getBuyStarsLink',
        })

    def create_star_buy_invoice(self, amount: int, username: str) -> dict:
        user_info = self.search_recipient(username)
        if not user_info.get('ok'):
            return {'ok': False, 'error': user_info.get('error') or 'User not found'}

        recipient = user_info['found']['recipient']
        init_resp = self.init_buy_stars(recipient, amount)
        if not init_resp.get('req_id'):
            return {'ok': False, 'error': init_resp.get('error') or 'Failed to initiate buy'}

        link_resp = self.get_buy_link(init_resp['req_id'])
        if not link_resp.get('ok') and 'transaction' not in link_resp:
            return {'ok': False, 'error': link_resp.get('error') or 'Failed to get link'}

        return link_resp

    def search_premium_gift_recipient(self, username: str, months: int) -> dict:
        return self._post(
            {
                'query': username,
                'months': str(months),
                'method': 'searchPremiumGiftRecipient',
            },
            referer=f'https://fragment.com/premium/gift?months={months}',
        )

    def init_gift_premium(self, recipient: str, months: int) -> dict:
        return self._post(
            {
                'recipient': recipient,
                'months': str(months),
                'method': 'initGiftPremiumRequest',
                'payment_method': 'ton',
            },
            referer=f'https://fragment.com/premium/gift?months={months}',
        )

    def get_gift_premium_link(self, req_id: str, months: int, show_sender: bool = False) -> dict:
        return self._post(
            {
                'id': req_id,
                'show_sender': '1' if show_sender else '0',
                'method': 'getGiftPremiumLink',
                'transaction': '1',
            },
            referer=f'https://fragment.com/premium/gift?months={months}',
        )

    def get_premium_gift_quote(self, months: int, username: str) -> dict:
        user_info = self.search_premium_gift_recipient(username, months)
        if not user_info.get('ok'):
            return {'ok': False, 'error': user_info.get('error') or 'Пользователь не найден на Fragment.'}

        recipient = user_info['found']['recipient']
        init_resp = self.init_gift_premium(recipient, months)
        if not init_resp.get('req_id'):
            return {'ok': False, 'error': init_resp.get('error') or 'Не удалось создать заявку на подарок Telegram Premium.'}

        init_resp['ok'] = True
        init_resp['recipient'] = recipient
        init_resp['found'] = user_info.get('found', {})
        return init_resp

    def create_premium_gift_invoice(self, months: int, username: str) -> dict:
        quote = self.get_premium_gift_quote(months, username)
        if not quote.get('ok'):
            return quote

        link_resp = self.get_gift_premium_link(quote['req_id'], months)
        if not link_resp.get('ok') and 'transaction' not in link_resp:
            return {'ok': False, 'error': link_resp.get('error') or 'Не удалось получить ссылку на подарок Telegram Premium.'}

        return link_resp

    @staticmethod
    def parse_invoice(result: dict) -> dict | None:
        trans = result.get('transaction')
        if not trans:
            return None
        msgs = trans.get('messages', [])
        if not msgs:
            return None

        ton_amount = int(msgs[0].get('amount', 0)) / 1_000_000_000
        ton_address = msgs[0].get('address', '')
        payload = msgs[0].get('payload', '')
        if ton_amount <= 0 or not ton_address or not payload:
            return None

        # Preserve the full Fragment payload, including referenced cells.
        comment = None
        if payload:
            try:
                from pytoniq_core import Cell
                padded = payload + '=' * (4 - len(payload) % 4) if len(payload) % 4 else payload
                raw = base64.b64decode(padded)
                comment = Cell.one_from_boc(raw)
            except Exception:
                return None

        return {
            'ton_address': ton_address,
            'ton_amount': ton_amount,
            'comment': comment,
        }


class TonWallet:

    def __init__(self, api_key: str, mnemonic: list[str]):
        from tonutils.client import TonapiClient
        from tonutils.wallet import WalletV4R2

        self.client = TonapiClient(
            api_key=api_key, is_testnet=False, rps=1, max_retries=3,
        )
        self._transfer_lock = asyncio.Lock()
        self.wallet, self.public_key, self.private_key, self.mnemonic = (
            WalletV4R2.from_mnemonic(self.client, mnemonic)
        )

    async def send_ton(self, destination: str, amount: float, comment: str = None):
        # tonutils.transfer accepts TON and performs its own nanoTON conversion.
        async with self._transfer_lock:
            tx_hash = await self.wallet.transfer(
                destination=destination,
                amount=amount,
                body=comment,
            )
        return tx_hash

    async def get_balance(self) -> float:
        balance = await self.client.get_account_balance(self.wallet.address)
        return balance / 1_000_000_000


class FrekassaClient:

    API_URL = 'https://api.fk.life/v1'

    # ID платёжных систем Frekassa
    PAYMENT_SYSTEMS = {
        'sbp': 36,
        'card': 44,
    }

    def __init__(self, shop_id: int, api_key: str):
        self.shop_id = shop_id
        self.api_key = api_key

    def _sign(self, data: dict) -> str:
        import hmac as hmac_mod
        import hashlib

        sorted_keys = sorted(data.keys())
        sign_string = '|'.join(str(data[k]) for k in sorted_keys)
        return hmac_mod.new(
            self.api_key.encode('utf-8'),
            sign_string.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()

    async def create_order(
        self,
        payment_id: str,
        amount: float,
        email: str = 'user@telegram.org',
        payment_system_id: int = 36,
        currency: str = 'RUB',
    ) -> str | None:
        """Создаёт заказ и возвращает URL оплаты или None."""
        import aiohttp
        import time as time_mod

        amount_val = int(amount) if float(amount).is_integer() else float(amount)

        request_data = {
            'shopId': self.shop_id,
            'nonce': int(time_mod.time() * 1000000),
            'i': payment_system_id,
            'email': email,
            'ip': '8.8.8.8',
            'amount': amount_val,
            'currency': currency,
            'paymentId': payment_id,
        }

        request_data['signature'] = self._sign(request_data)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f'{self.API_URL}/orders/create',
                    json=request_data,
                    headers={'Content-Type': 'application/json'},
                ) as resp:
                    result = await resp.json()
                    if result.get('type') == 'success' and result.get('location'):
                        return result['location']
                    logger.error('Frekassa API error: %s %s', resp.status, result)
                    return None
        except Exception as e:
            logger.error('Frekassa request failed: %s', e)
            return None

    async def get_order_status(self, payment_id: str) -> str | None:
        """Проверяет статус заказа. Возвращает статус или None."""
        import aiohttp
        import time as time_mod

        request_data = {
            'shopId': self.shop_id,
            'nonce': int(time_mod.time() * 1000000),
            'paymentId': payment_id,
        }
        request_data['signature'] = self._sign(request_data)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f'{self.API_URL}/orders',
                    json=request_data,
                    headers={'Content-Type': 'application/json'},
                ) as resp:
                    result = await resp.json()
                    if result.get('type') == 'success':
                        orders = result.get('orders', [])
                        for o in orders:
                            if str(o.get('merchant_order_id')) == payment_id:
                                return o.get('status')
                    return None
        except Exception as e:
            logger.error('Frekassa get_order failed: %s', e)
            return None


# Instances
fragment_api: FragmentAPI | None = None
ton_wallet: TonWallet | None = None
frekassa: FrekassaClient | None = None

if settings.fragment.cookies:
    fragment_api = FragmentAPI(settings.fragment.cookies, settings.fragment.hash_value)

if settings.ton_api.api_key and settings.ton_api.mnemonic_list:
    try:
        ton_wallet = TonWallet(settings.ton_api.api_key, settings.ton_api.mnemonic_list)
    except Exception as e:
        logger.warning('Failed to init TonWallet: %s', e)

if settings.frekassa.shop_id and settings.frekassa.api_key:
    frekassa = FrekassaClient(
        shop_id=settings.frekassa.shop_id,
        api_key=settings.frekassa.api_key,
    )
