from __future__ import annotations

from pathlib import Path
from typing import Literal

from dotenv import find_dotenv, load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

from redis.asyncio import Redis

from bot.enums.db import Databases, PostgreSQLDrivers, MySQLDrivers

load_dotenv(find_dotenv())

ProjectDir = Path(__file__).parent.parent
BotDir = ProjectDir / "bot"
LogDir = Path(ProjectDir) / "logs"


class BotSettings(BaseSettings):
    bot_token: str
    parse_mode: Literal["MARKDOWN_V2", "MARKDOWN", "HTML"] = "HTML"
    drop_pending_updates: bool = True
    rate_limit: int | float = 1


class DatabaseSettings(BaseSettings):
    used: Databases = Databases.PostgreSQl
    ip: str
    user: str
    password: str
    name: str

    test_name: str | None = None

    model_config = SettingsConfigDict(env_prefix="DB_")

    def build_postgres_url(self) -> str:
        return f"postgresql+{PostgreSQLDrivers.ASYNC_DRIVER}://{self.user}:{self.password}@{self.ip}/{self.name}"

    def build_mysql_url(self) -> str:
        return f"mysql+{MySQLDrivers.ASYNC_DRIVER}://{self.user}:{self.password}@{self.ip}/{self.name}"


class RedisSettings(BaseSettings):
    use: bool
    ip: str
    port: int
    password: str

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    def get_redis(self, db: int = 0) -> Redis:
        return Redis(host=self.ip, port=self.port, password=self.password, db=db)


class CryptoPaySettings(BaseSettings):
    token: str = ''

    model_config = SettingsConfigDict(env_prefix='CRYPTOPAY_')


class FragmentAPISettings(BaseSettings):
    cookies: str = ''
    hash_value: str = ''

    model_config = SettingsConfigDict(env_prefix='FRAGMENT_')


class TonAPISettings(BaseSettings):
    mnemonic: str = ''
    api_key: str = ''
    receive_address: str = ''

    model_config = SettingsConfigDict(env_prefix='TONAPI_')

    @property
    def mnemonic_list(self) -> list[str]:
        raw = self.mnemonic.strip('[]')
        if not raw:
            return []
        if ',' in raw:
            return [w.strip().strip('"').strip("'") for w in raw.split(',')]
        return raw.split()


class FrekassaSettings(BaseSettings):
    shop_id: int = 0
    api_key: str = ''
    secret_word_2: str = ''

    model_config = SettingsConfigDict(env_prefix='FREKASSA_')


class NotificationsSettings(BaseSettings):
    host: str = '127.0.0.1'
    port: int = 8789
    return_url: str = 'https://t.me/syndicatestars_bot'

    model_config = SettingsConfigDict(env_prefix='NOTIFICATIONS_')


class XRocketSettings(BaseSettings):
    token: str = ''
    webhook_token: str = ''
    callback_url: str = ''

    model_config = SettingsConfigDict(env_prefix='XROCKET_')


class Settings(BaseSettings):
    log_chat: int | None = None
    admins: list[int]
    debug_mode: bool

    bot: BotSettings = BotSettings()
    db: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    cryptopay: CryptoPaySettings = CryptoPaySettings()
    fragment: FragmentAPISettings = FragmentAPISettings()
    ton_api: TonAPISettings = TonAPISettings()
    frekassa: FrekassaSettings = FrekassaSettings()
    notifications: NotificationsSettings = NotificationsSettings()
    xrocket: XRocketSettings = XRocketSettings()


settings = Settings()
