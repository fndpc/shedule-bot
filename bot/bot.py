import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message
from bot.keyboards import MAIN_KEYBOARD

from config import BOT_TOKEN
from db.session import SessionLocal, close_db, init_db
from parser.parser import (
    TARGET_GROUP,
    fetch_latest_pdf_url,
    format_schedule_message,
    parse_schedule_from_pdf_url,
)
from repository.user_repository import UserRepository

CHECK_INTERVAL_SECONDS = 60


async def broadcast_schedule_update(bot: Bot, message_text: str) -> None:
    async with SessionLocal() as session:
        repo = UserRepository(session)
        chat_ids = await repo.list_subscribed_chat_ids()

    if not chat_ids:
        logging.info("No subscribed users to notify")
        return

    for chat_id in chat_ids:
        try:
            await bot.send_message(chat_id=chat_id, text=message_text)
        except Exception:
            logging.exception("Failed to send update to chat_id=%s", chat_id)


async def schedule_polling_loop(bot: Bot) -> None:
    last_seen_pdf_url: str | None = None

    while True:
        try:
            pdf_url = await asyncio.to_thread(fetch_latest_pdf_url)

            if last_seen_pdf_url is None:
                last_seen_pdf_url = pdf_url
                logging.info("Schedule watcher started with %s for group %s", pdf_url, TARGET_GROUP)
            elif pdf_url != last_seen_pdf_url:
                last_seen_pdf_url = pdf_url
                schedule = await asyncio.to_thread(parse_schedule_from_pdf_url, pdf_url, TARGET_GROUP)
                message_text = format_schedule_message(schedule, pdf_url)
                await broadcast_schedule_update(bot, message_text)
                logging.info("New schedule sent to subscribers: %s", pdf_url)
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.exception("Schedule polling failed")

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set. Configure it in .env")

    await init_db()
    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()

    @dp.message(Command("start"))
    async def cmd_start(message: Message):
        await message.answer(
            "Чтобы получать расписание, нажми «Подписаться ✅».",
            reply_markup=MAIN_KEYBOARD,
        )

    @dp.message(F.text == "Подписаться ✅")
    async def msg_subscribe(message: Message):
        chat_id = message.chat.id
        async with SessionLocal() as session:
            repo = UserRepository(session)
            is_changed = await repo.subscribe_user(chat_id)
        if is_changed:
            await message.answer("Подписка включена.")
        else:
            await message.answer("Ты уже подписан.")

    @dp.message(F.text == "Отписаться ❎")
    async def msg_unsubscribe(message: Message):
        chat_id = message.chat.id
        async with SessionLocal() as session:
            repo = UserRepository(session)
            is_changed = await repo.unsubscribe_user(chat_id)
        if is_changed:
            await message.answer("Подписка отключена.")
        else:
            await message.answer("Ты уже отписан.")

    watcher_task = asyncio.create_task(schedule_polling_loop(bot))

    try:
        await dp.start_polling(bot, skip_updates=True)
    finally:
        watcher_task.cancel()
        await asyncio.gather(watcher_task, return_exceptions=True)
        await bot.session.close()
        await close_db()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped")
