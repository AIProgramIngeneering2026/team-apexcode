"""Реестр каналов доставки."""

from collections.abc import Iterable

from notify.domain.channel import Channel
from notify.domain.errors import UnknownChannel


class Registry:
    """Хранит соответствие имени канала его реализации."""

    def __init__(self, channels: Iterable[Channel] = ()) -> None:
        self._channels: dict[str, Channel] = {}
        for channel in channels:
            self.register(channel)

    def register(self, channel: Channel) -> None:
        """Зарегистрировать канал по его имени."""
        if not channel.name:
            raise ValueError("Channel name must not be empty")
        self._channels[channel.name] = channel

    def get(self, name: str) -> Channel:
        """Вернуть канал или выбросить доменную ошибку."""
        try:
            return self._channels[name]
        except KeyError:
            raise UnknownChannel(name, tuple(sorted(self._channels))) from None

    def list_channels(self) -> tuple[Channel, ...]:
        """Вернуть зарегистрированные каналы в стабильном порядке."""
        return tuple(self._channels[name] for name in sorted(self._channels))

    def names(self) -> tuple[str, ...]:
        """Вернуть имена зарегистрированных каналов."""
        return tuple(sorted(self._channels))
