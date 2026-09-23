from __future__ import annotations

from dataclasses import dataclass
from math import isqrt

CHECKSUM_MODULUS: int = 1_000_000_007


@dataclass(frozen=True, slots=True)
class PrimeStats:
    count: int
    max_prime: int | None
    checksum: int


def is_prime(number: int) -> bool:
    """Вернуть True только для простого числа."""
    if number < 2:
        return False
    if number < 4:
        return True
    if number % 2 == 0:
        return False
    limit: int = isqrt(number)
    divisor: int = 3
    while divisor <= limit:
        if number % divisor == 0:
            return False
        divisor += 2
    return True


def analyze_range(bounds: tuple[int, int]) -> PrimeStats:
    """Проанализировать обе границы включительно."""
    start, stop = bounds
    if start > stop:
        raise ValueError(f"Некорректный диапазон: start={start} > stop={stop}")
    if start < 2:
        raise ValueError(f"Некорректная нижняя граница: {start} < 2")

    count: int = 0
    max_prime: int | None = None
    checksum: int = 0

    for number in range(start, stop + 1):
        if is_prime(number):
            count += 1
            if max_prime is None or number > max_prime:
                max_prime = number
            checksum += number

    checksum %= CHECKSUM_MODULUS
    return PrimeStats(count=count, max_prime=max_prime, checksum=checksum)


def merge_stats(items: list[PrimeStats]) -> PrimeStats:
    """Объединить непересекающиеся частичные результаты."""
    if not items:
        raise ValueError("Список частичных результатов пуст")

    total_count: int = 0
    total_checksum: int = 0
    max_prime: int | None = None

    for item in items:
        total_count += item.count
        total_checksum += item.checksum
        if item.max_prime is not None:
            if max_prime is None or item.max_prime > max_prime:
                max_prime = item.max_prime

    total_checksum %= CHECKSUM_MODULUS
    return PrimeStats(count=total_count, max_prime=max_prime, checksum=total_checksum)