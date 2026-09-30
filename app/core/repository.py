from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")


class Repository(ABC, Generic[T]):
    """Repository boundary for future persistence or in-memory adapters."""

    @abstractmethod
    def add(self, entity: T) -> T:
        """Store and return an entity."""
        raise NotImplementedError


class InMemoryRepository(Repository[T]):
    """Small in-memory adapter for unit tests and local development."""

    def __init__(self) -> None:
        self._entities: list[T] = []

    def add(self, entity: T) -> T:
        self._entities.append(entity)
        return entity
