from aiogram.filters.callback_data import CallbackData
from pydantic import Field


class MainMenu(CallbackData, prefix='mm'):
    action: str = 'return'


class AccountBalance(CallbackData, prefix='ab'):
    action: str


class Support(CallbackData, prefix='sup'):
    action: str = 'support'


class Partners(CallbackData, prefix='partners'):
    action: str = 'menu'


class BuyStars(CallbackData, prefix='bstars'):
    action: str = ''       # custom | ''
    stars_count: int = 50
    recipient: str = Field(default='', pattern=r'^(?:[A-Za-z][A-Za-z0-9_]{3,30}[A-Za-z0-9])?$', max_length=32)


class BuyPremium(CallbackData, prefix='bprem'):
    action: str = ''       # menu | ''
    months: int = 3
    recipient: str = Field(default='', pattern=r'^(?:[A-Za-z][A-Za-z0-9_]{3,30}[A-Za-z0-9])?$', max_length=32)


class PayMethod(CallbackData, prefix='pm'):
    method: str            # pay_cryptobot | pay_fragment
    stars_count: int
    recipient: str = Field(default='', pattern=r'^(?:[A-Za-z][A-Za-z0-9_]{3,30}[A-Za-z0-9])?$', max_length=32)


class RubPayMethod(CallbackData, prefix='rubpm'):
    method: str            # unitpay | frekassa | donationalerts
    stars_count: int
    recipient: str = Field(default='', pattern=r'^(?:[A-Za-z][A-Za-z0-9_]{3,30}[A-Za-z0-9])?$', max_length=32)


class PremiumPayMethod(CallbackData, prefix='ppm'):
    method: str            # pay_cryptobot | pay_rub
    months: int
    recipient: str = Field(default='', pattern=r'^(?:[A-Za-z][A-Za-z0-9_]{3,30}[A-Za-z0-9])?$', max_length=32)


class PremiumRubPayMethod(CallbackData, prefix='prubpm'):
    method: str            # frekassa_sbp | frekassa_card
    months: int
    recipient: str = Field(default='', pattern=r'^(?:[A-Za-z][A-Za-z0-9_]{3,30}[A-Za-z0-9])?$', max_length=32)


class Calculator(CallbackData, prefix='calc'):
    action: str = 'menu'
