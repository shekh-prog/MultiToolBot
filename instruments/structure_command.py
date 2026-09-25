# Примерный код
import asyncio
import os
from datetime import datetime
from typing import Literal

from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field


load_dotenv()


MODEL = "gemini-2.5-flash-lite"

client = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"]
)



class Reminder(BaseModel):
    text: str = Field(
        description="The reminder/task text in Russian."
    )
    fire_at: str | None = Field(
        description=(
            "Local datetime in format DD.MM.YYYY HH:MM:SS. "
            "Null when the time cannot be determined."
        )
    )


class Billing(BaseModel):
    amount: float = Field(
        description="Amount of money spent."
    )
    currency: Literal[
        "RUB",
        "USD",
        "EUR",
        "GBP",
        "CNY",
    ] | None = Field(
        description="Currency. Null when it cannot be determined."
    )
    text: str = Field(
        description="What the money was spent on."
    )
    category: Literal[
        "cafe",
        "market",
        "subscription",
        "travel",
        "other",
    ]


class ParsedMessage(BaseModel):
    reminders: list[Reminder] = Field(
        default_factory=list
    )
    billing: list[Billing] = Field(
        default_factory=list
    )
    notes: list[str] = Field(
        default_factory=list,
        description=(
            "Information explicitly requested to be remembered. "
            "Always written in English."
        ),
    )



SYSTEM_PROMPT = """
You are a Russian voice-message parser for a reminder and expense bot.

Extract ALL independent pieces of information from the user's message.

The user may speak naturally:
- without punctuation;
- with grammatical cases;
- with slang;
- with Russian and English mixed together;
- with several reminders and expenses in one sentence.

DO NOT depend on exact words or punctuation.
Understand the meaning of the sentence.

============================================================
REMINDERS
============================================================

Extract every separate task/action.

Examples:
"купить молоко и зайти в аптеку"
=> two reminders.

"надо позвонить маме а потом сделать дз"
=> two reminders.

Relative time:
- через N минут
- через N часов
- через N дней
- через неделю
- полчаса
- полтора часа

Convert these relative times using CURRENT DATETIME.

Named times:
- утром -> 08:00
- к утру -> 08:00
- в обед / к обеду -> 13:00
- после обеда -> 14:30
- вечером / к вечеру -> 17:00

Conversational times:
- полдевятого -> 08:30
- четверть девятого -> 08:15
- без пятнадцати девять -> 08:45

If there is no reliable time:
fire_at = null

fire_at MUST use:
DD.MM.YYYY HH:MM:SS

============================================================
BILLING
============================================================

Extract EVERY separate expense.

Examples:
"потратил 340 рублей на шаурму и 50 на мороженое"
=> two billing items.

Currency:
рубли / рублей / руб. / ₽ -> RUB
доллар / долларов / баксы / $ -> USD
евро / € -> EUR
фунт / фунтов / £ -> GBP
юань / юаней / ¥ -> CNY

If currency cannot be determined reliably:
currency = null

Categories MUST be exactly:

cafe
Restaurants, cafes, fast food, coffee shops, food delivery,
shawarma, pizza, ice cream and food for immediate consumption.

market
Supermarkets, grocery stores, groceries and household goods.

subscription
Subscriptions and memberships such as VPN, Netflix, Spotify.

travel
Bus, metro, train, plane, taxi and ride-hailing.

other
Everything else.

============================================================
NOTES
============================================================

Only create a note when the user explicitly asks to remember
information.

Notes MUST be written in English.

Do not invent information.

============================================================
CURRENT CONTEXT
============================================================

Current local datetime:
{current_datetime}

User timezone:
{timezone}
"""



async def parse_message(
    text: str,
    current_datetime: datetime,
    timezone: str,
) -> dict:
    """
    Parse one user message.

    Can be called from any async module:

        result = await parse_message(
            text,
            datetime.now(),
            "Europe/Riga",
        )
    """

    if not text.strip():
        return {
            "reminders": [],
            "billing": [],
            "notes": [],
        }

    prompt = SYSTEM_PROMPT.format(
        current_datetime=current_datetime.strftime(
            "%d.%m.%Y %H:%M:%S"
        ),
        timezone=timezone,
    )

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=MODEL,
            contents=[
                prompt,
                f"\nUSER MESSAGE:\n{text}",
            ],
            config={
                "response_mime_type": "application/json",
                "response_schema": ParsedMessage,
            },
        )

        result = response.parsed

        if result is None:
            raise RuntimeError(
                "Gemini returned no structured result"
            )

        return result.model_dump()

    except Exception as exc:
        raise RuntimeError(
            "Failed to parse message with Gemini"
        ) from exc