"""Manually (re)set or inspect the webhook. The app also does this on startup.
Usage: python -m scripts.set_webhook [info|set|delete]"""
import asyncio
import sys

from telegram import Bot, Update

from app.config import get_settings


async def main(cmd: str) -> None:
    s = get_settings()
    bot = Bot(s.BOT_TOKEN)
    async with bot:
        if cmd == "set":
            ok = await bot.set_webhook(
                url=s.webhook_url, secret_token=s.WEBHOOK_SECRET,
                allowed_updates=[Update.MESSAGE, Update.CALLBACK_QUERY],
            )
            print("set_webhook:", ok, s.webhook_url)
        elif cmd == "delete":
            print("delete_webhook:", await bot.delete_webhook(drop_pending_updates=True))
        info = await bot.get_webhook_info()
        print(info.to_dict())


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "info"))
