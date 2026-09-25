from aiogram import Bot, Dispatcher, types
import asyncio
from aiogram.filters import Command
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import os

from database import db
from instruments import worker

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()


@dp.message(Command(commands=["start", "help"]))
async def start_cmd(message: types.Message):
    await message.answer(
        "Команды:\n"
        "/add_reminder <date> <time> <text...> - добавить\n"
        "/remove_reminder <reminder_id> - удалить\n"
        "/list_reminder - список"
    )


@dp.message(Command("add_reminder"))
async def add_reminder(message: types.Message):
    parts = message.text.split()[1:]

    if len(parts) < 3:
        await message.answer("Неверный формат!")
        return

    date, time, text = parts[0], parts[1], " ".join(parts[2:])
    fire_at = strToDateTime(f"{date} {time}")

    reminder = await db.add_reminder(
        user_id=message.from_user.id,
        text=text,
        fire_at=fire_at
    )

    if reminder:
        await worker.add_to_worker(
            fire_at=reminder.fire_at,
            reminder_id=reminder.id
        )

        await message.answer(
            "Добавлено новое напоминание!\n"
            f"Текст: {text}\n"
            f"Сработает {utcToMsk(fire_at)}"
        )
    else:
        await message.answer("Что-то пошло не так!")


@dp.message(Command("list_reminder"))
async def list_reminder(message: types.Message):
    reminders = await db.list_reminder(
        user_id=message.from_user.id
    )

    text = ""

    for reminder in reminders:
        text += (
            f"\nНапоминание: {reminder.text} (ID {reminder.id})\n"
            f"Сработает {utcToMsk(reminder.fire_at)}\n"
            "\n======================================\n"
        )

    if not text:
        await message.answer("У вас пока нет напоминаний!")
        return

    await message.answer(text)


@dp.message(Command("remove_reminder"))
async def remove_reminder(message: types.Message):
    reminder_id = int(message.text.split()[-1])

    reminder = await db.remove_reminder(
        reminder_id=reminder_id
    )

    if reminder:
        await message.answer(
            "Напоминание удалено!\n"
            f"Текст: {reminder.text}\n"
            f"Должно было сработать {utcToMsk(reminder.fire_at)}"
        )

        worker.wake_event.set()
    else:
        await message.answer("Что-то пошло не так!")


def strToDateTime(d: str) -> datetime:
    local_time = datetime.strptime(
        d,
        "%d.%m.%Y %H:%M"
    )

    return (
        local_time
        .replace(tzinfo=ZoneInfo("Europe/Moscow"))
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )


def utcToMsk(utc_time: datetime) -> datetime:
    return utc_time.replace(
        tzinfo=timezone.utc
    ).astimezone(
        ZoneInfo("Europe/Moscow")
    )


async def send_message(text: str, user_id: int):
    await bot.send_message(
        chat_id=user_id,
        text=text
    )


async def main():
    await db.init_db()
    await db.clear_expired_reminders()
    await worker.init()

    print("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())