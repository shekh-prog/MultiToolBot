from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy import String, Integer, DateTime, select
from datetime import datetime, timezone

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)

class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(String())
    fire_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

engine = create_async_engine("sqlite+aiosqlite:///database/multitool.db")
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_reminder(reminder_id):
    async with async_session() as session:
        try:
            reminder = await session.get(Reminder, reminder_id)
            if reminder is None:
                return False
            return reminder
        except Exception:
            raise

async def add_reminder(user_id: int, text: str, fire_at):
    async with async_session() as session:
        try:
            reminder = Reminder(user_id=user_id, text=text, fire_at=fire_at)
            session.add(reminder)
            await session.commit()
            return reminder
        except:
            await session.rollback()
            raise

async def remove_reminder(reminder_id: int):
    async with async_session() as session:
        try:
            reminder = await session.get(Reminder, reminder_id)
            if reminder is None:
                return "RNF" # Reminder not found

            await session.delete(reminder)
            await session.commit()
            return reminder
        except:
            await session.rollback()
            raise

async def list_reminder(user_id: int):
    async with async_session() as session:
        try:
            reminders = await session.scalars(
                select(Reminder)
                .where(Reminder.user_id == user_id)
                .order_by(Reminder.fire_at)
            )
            return reminders
        except:
            raise

async def get_future_reminders(limit: int):
    async with async_session() as session:
        try:
            now = datetime.now(timezone.utc)

            reminders = await session.scalars(
                select(Reminder)
                .where(Reminder.fire_at > now)
                .order_by(Reminder.fire_at)
                .limit(limit)
            )

            reminders = reminders.all()

            return reminders

        except Exception:
            raise

async def clear_expired_reminders(): # Чистка от просроченных напоминаний
    async with async_session() as session:
        try:
            now = datetime.now(timezone.utc)

            reminders = await session.scalars( # выбирает все просроченые напоминания
                select(Reminder)
                .where(Reminder.fire_at <= now)
            )

            for reminder in reminders.all():
                await session.delete(reminder)
            await session.commit()

        except Exception:
            await session.rollback()
            raise
