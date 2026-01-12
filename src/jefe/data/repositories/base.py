"""Base repository with generic CRUD operations."""

from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jefe.data.models.base import BaseModel

ModelType = TypeVar("ModelType", bound=BaseModel)


class BaseRepository(Generic[ModelType]):
    """
    Generic repository for CRUD operations on SQLAlchemy models.

    Args:
        model: The SQLAlchemy model class to operate on.
        session: The async database session.
    """

    def __init__(self, model: type[ModelType], session: AsyncSession) -> None:
        """Initialize repository with model and session."""
        self.model = model
        self.session = session

    async def create(self, **kwargs: Any) -> ModelType:
        """
        Create a new model instance.

        Args:
            **kwargs: Field values for the new instance.

        Returns:
            The created model instance.
        """
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.commit()
        await self.session.refresh(instance)
        return instance

    async def get_by_id(self, id_: int) -> ModelType | None:
        """
        Get a model instance by ID.

        Args:
            id_: The ID of the instance to retrieve.

        Returns:
            The model instance if found, None otherwise.
        """
        result = await self.session.execute(select(self.model).where(self.model.id == id_))
        return result.scalar_one_or_none()

    async def get_all(self, limit: int | None = None, offset: int = 0) -> list[ModelType]:
        """
        Get all model instances.

        Args:
            limit: Maximum number of instances to return.
            offset: Number of instances to skip.

        Returns:
            List of model instances.
        """
        query = select(self.model).offset(offset)
        if limit is not None:
            query = query.limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update(self, id_: int, **kwargs: Any) -> ModelType | None:
        """
        Update a model instance by ID.

        Args:
            id_: The ID of the instance to update.
            **kwargs: Field values to update.

        Returns:
            The updated model instance if found, None otherwise.
        """
        instance = await self.get_by_id(id_)
        if instance is None:
            return None

        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)

        await self.session.commit()
        await self.session.refresh(instance)
        return instance

    async def delete(self, id_: int) -> bool:
        """
        Delete a model instance by ID.

        Args:
            id_: The ID of the instance to delete.

        Returns:
            True if deleted, False if not found.
        """
        instance = await self.get_by_id(id_)
        if instance is None:
            return False

        await self.session.delete(instance)
        await self.session.commit()
        return True

    async def count(self) -> int:
        """
        Count the total number of model instances.

        Returns:
            The total count.
        """
        result = await self.session.execute(select(self.model))
        return len(list(result.scalars().all()))
