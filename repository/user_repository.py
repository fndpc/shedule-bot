from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Subscription


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_subscription(self, chat_id: int) -> Subscription | None:
        query = select(Subscription).where(Subscription.chat_id == chat_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def subscribe_user(self, chat_id: int) -> bool:
        subscription = await self.get_subscription(chat_id)
        if subscription is None:
            self.session.add(Subscription(chat_id=chat_id, is_subscribed=True))
            await self.session.commit()
            return True

        if subscription.is_subscribed:
            return False

        subscription.is_subscribed = True
        await self.session.commit()
        return True

    async def unsubscribe_user(self, chat_id: int) -> bool:
        subscription = await self.get_subscription(chat_id)
        if subscription is None:
            return False

        if not subscription.is_subscribed:
            return False

        subscription.is_subscribed = False
        await self.session.commit()
        return True

    async def list_subscribed_chat_ids(self) -> list[int]:
        query = select(Subscription.chat_id).where(Subscription.is_subscribed.is_(True))
        result = await self.session.execute(query)
        return list(result.scalars().all())
