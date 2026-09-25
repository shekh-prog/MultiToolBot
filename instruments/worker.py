import asyncio
import heapq
from datetime import datetime, timezone

from database import db
from main import send_message, utcToMsk


heap = []
wake_event = asyncio.Event()


async def init():
    global heap

    reminders = await db.get_future_reminders(1000)

    for reminder in reminders:
        heapq.heappush(
            heap,
            (reminder.fire_at, reminder.id)
        )

    asyncio.create_task(worker())


async def worker():
    while True:
        if not heap:
            await wake_event.wait()
            wake_event.clear()
            continue

        fire_at, reminder_id = heap[0]

        now = datetime.now(timezone.utc).replace(
            tzinfo=None
        )

        sleep_seconds = (
            fire_at - now
        ).total_seconds()

        if sleep_seconds <= 0:
            await step()
            continue

        wake_event.clear()

        try:
            await asyncio.wait_for(
                wake_event.wait(),
                timeout=sleep_seconds
            )
        except asyncio.TimeoutError:
            await step()


async def step():
    if not heap:
        return

    fire_at, reminder_id = heap[0]

    reminder = await db.get_reminder(
        reminder_id=reminder_id
    )

    if not reminder:
        heapq.heappop(heap)
        return

    if reminder.fire_at != fire_at:
        heapq.heappop(heap)

        heapq.heappush(
            heap,
            (reminder.fire_at, reminder.id)
        )

        return

    text = (
        "НАПОМИНАНИЕ\n"
        f"{reminder.text}\n\n"
        f"Было запланировано на "
        f"{utcToMsk(reminder.fire_at)}"
    )

    await send_message(
        text=text,
        user_id=reminder.user_id
    )

    heapq.heappop(heap)

    await db.remove_reminder(reminder.id)


async def add_to_worker(
    fire_at: datetime,
    reminder_id: int
):
    heapq.heappush(
        heap,
        (fire_at, reminder_id)
    )

    wake_event.set()