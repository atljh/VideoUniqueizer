from dataclasses import dataclass
from environs import Env


@dataclass
class TgBot:
    """
    Represents a Telegram bot configuration.
    """
    token: str
    channel_url: str
    channel_id: int

    @staticmethod
    def from_env(env: Env, prefix: str = ""):
        """
        Loads bot configuration from environment variables with an optional prefix.
        """
        token = env.str(f"{prefix}BOT_TOKEN")
        channel_url = env.str(f"{prefix}CHANNEL_URL")
        channel_id = env.int(f"{prefix}CHANNEL_ID")

        return TgBot(token=token, channel_url=channel_url, channel_id=channel_id)


@dataclass
class Config:
    """
    The main configuration class that stores multiple bot configurations.
    """
    bots: list[TgBot]
    admins_id: list[int]


def load_config(path: str = None) -> Config:
    """
    Loads multiple bot configurations from an .env file.
    """
    env = Env()
    env.read_env(path)

    bot_count = env.int("BOT_COUNT", 1)  # Количество ботов
    bots = [TgBot.from_env(env, prefix=f"BOT{i}_") for i in range(1, bot_count + 1)]
    admins_id = list(map(int, env.list("ADMINS_ID", default=[])))

    return Config(bots=bots, admins_id=admins_id)
