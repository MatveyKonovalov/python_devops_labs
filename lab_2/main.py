from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import platform
import sys
from enum import Enum
from pathlib import Path
from statistics import median
from time import perf_counter
from typing import Callable

from worker import PrimeStats, analyze_range, merge_stats

DEFAULT_LIMIT: int = 300_000
DEFAULT_REPEATS: int = 5
DEFAULT_WORKERS: tuple[int, ...] = (1, 2, 4)
EXPECTED = PrimeStats(25997, 299993, 709507093)


class RunMode(str, Enum):
    CHECK = "check"
    SEQUENTIAL = "sequential"
    PROCESSES = "processes"
    EXPERIMENT = "experiment"


class StartMethod(str, Enum):
    SPAWN = "spawn"
    FORK = "fork"


def _run_mode_choice(value: str) -> RunMode: # Проверка выбора ран мода
    try:
        return RunMode(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"неизвестный режим: {value!r} (допустимо: {', '.join(m.value for m in RunMode)})"
        )


def _start_method_choice(value: str) -> StartMethod:
    try:
        return StartMethod(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"неизвестный метод: {value!r} (допустимо: {', '.join(m.value for m in StartMethod)})"
        )


def _workers_choice(value: str) -> int:
    try:
        workers = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"не целое число: {value!r}")
    if workers < 1 or workers > 8:
        raise argparse.ArgumentTypeError(f"число процессов должно быть от 1 до 8, получено {workers}")
    return workers


def build_parser() -> argparse.ArgumentParser:
    """Создать CLI по установленному контракту."""
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Лабораторная работа 2: перечисления, командная строка и процессы.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        type=_run_mode_choice,
        default=RunMode.CHECK,
        help="Режим работы программы",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help="Верхняя граница диапазона (>= 1000)",
    )
    parser.add_argument(
        "--workers",
        type=_workers_choice,
        nargs="+",
        default=list(DEFAULT_WORKERS),
        help="Количество процессов (1..8)",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=DEFAULT_REPEATS,
        help="Количество измерений (>= 3)",
    )
    parser.add_argument(
        "--start-method",
        type=_start_method_choice,
        default=StartMethod.SPAWN,
        help="Метод multiprocessing для основной серии",
    )
    parser.add_argument(
        "--include-fork",
        action="store_true",
        help="Дополнительная серия с fork (если поддерживается)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/metrics.json"),
        help="Путь к файлу metrics.json внутри проекта",
    )
    return parser


def validate_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Завершить разбор с ошибкой для недопустимых сочетаний."""
    if args.limit < 1000:
        parser.error(f"--limit должен быть не меньше 1000, получено {args.limit}")
    if args.repeats < 3:
        parser.error(f"--repeats должен быть не меньше 3, получено {args.repeats}")
    if not args.workers:
        parser.error("--workers должен содержать хотя бы одно значение")
    if args.output.is_absolute():
        parser.error("--output должен быть относительным путём внутри проекта")
    if args.start_method is StartMethod.FORK:
        if "fork" not in mp.get_all_start_methods():
            parser.error("метод fork недоступен на этой платформе")
    if args.include_fork and "fork" not in mp.get_all_start_methods():
        # не ошибка: просто отметим unsupported в отчёте
        pass


def split_ranges(limit: int, part_count: int) -> list[tuple[int, int]]:
    """Разбить закрытый диапазон 2..limit без пропусков."""
    if part_count < 1:
        raise ValueError("part_count должен быть >= 1")
    if limit < 2:
        raise ValueError("limit должен быть >= 2")

    total: int = limit - 2 + 1  # количество чисел в диапазоне 2..limit
    if part_count > total:
        part_count = total

    base_size: int = total // part_count
    remainder: int = total % part_count

    ranges: list[tuple[int, int]] = []
    start: int = 2
    for index in range(part_count):
        size: int = base_size + (1 if index < remainder else 0)
        if size <= 0:
            continue
        stop: int = start + size - 1
        ranges.append((start, stop))
        start = stop + 1
    return ranges


def run_sequential(limit: int) -> PrimeStats:
    return analyze_range((2, limit))


def run_processes(limit: int, workers: int, method: StartMethod) -> PrimeStats:
    """Выполнить задачу через контекст multiprocessing."""
    ctx = mp.get_context(method.value)
    ranges = split_ranges(limit, workers)
    with ctx.Pool(processes=workers) as pool:
        partials: list[PrimeStats] = pool.map(analyze_range, ranges)
    return merge_stats(partials)


def measure(action: Callable[[], PrimeStats], repeats: int) -> tuple[list[float], PrimeStats]:
    """Измерить action несколько раз и вернуть последний результат."""
    durations: list[float] = []
    last_result: PrimeStats | None = None
    for _ in range(repeats):
        start = perf_counter()
        result = action()
        elapsed = perf_counter() - start
        durations.append(elapsed)
        if last_result is None:
            last_result = result
        elif last_result != result:
            raise RuntimeError("Результаты повторных запусков не совпадают")
    assert last_result is not None
    return durations, last_result


def _stats_to_dict(stats: PrimeStats) -> dict[str, object]:
    return {
        "count": stats.count,
        "max_prime": stats.max_prime,
        "checksum": stats.checksum,
    }


def build_metrics(args: argparse.Namespace) -> dict[str, object]:
    """Провести эксперимент и построить словарь установленной схемы."""
    limit: int = args.limit
    repeats: int = args.repeats
    worker_counts: list[int] = sorted(set(args.workers))

    # Проверка ожидаемого результата
    check_result = run_sequential(limit)
    matches_expected = check_result == EXPECTED if limit == DEFAULT_LIMIT else None

    # Последовательная серия
    seq_durations, seq_result = measure(lambda: run_sequential(limit), repeats)
    seq_median = median(seq_durations)

    # Основная серия процессов со spawn
    process_runs: list[dict[str, object]] = []
    process_results: list[PrimeStats] = []
    for workers in worker_counts:
        durations, result = measure(
            lambda w=workers: run_processes(limit, w, StartMethod.SPAWN),
            repeats,
        )
        med = median(durations)
        speedup = seq_median / med if med > 0 else 0.0
        efficiency = speedup / workers if workers > 0 else 0.0
        process_runs.append(
            {
                "start_method": StartMethod.SPAWN.value,
                "workers": workers,
                "durations_seconds": durations,
                "median_seconds": med,
                "speedup": speedup,
                "efficiency": efficiency,
                "result_matches_sequential": result == seq_result,
            }
        )
        process_results.append(result)

    # Дополнительная серия fork
    fork_run: dict[str, object] = {
        "status": "not_requested",
        "workers": 4,
        "durations_seconds": [],
        "median_seconds": None,
        "fork_to_spawn_ratio": None,
        "result_matches_sequential": None,
    }

    available_methods = mp.get_all_start_methods()

    if args.include_fork:
        if "fork" not in available_methods:
            fork_run = {
                "status": "unsupported",
                "workers": 4,
                "durations_seconds": [],
                "median_seconds": None,
                "fork_to_spawn_ratio": None,
                "result_matches_sequential": None,
            }
        else:
            fork_workers = 4
            fork_durations, fork_result = measure(
                lambda: run_processes(limit, fork_workers, StartMethod.FORK),
                repeats,
            )
            fork_median = median(fork_durations)

            # Найти spawn-медиану для 4 процессов
            spawn_median_4: float | None = None
            for run in process_runs:
                if run["workers"] == fork_workers and run["start_method"] == StartMethod.SPAWN.value:
                    spawn_median_4 = float(run["median_seconds"])
                    break

            ratio: float | None = None
            if spawn_median_4 is not None and spawn_median_4 > 0:
                ratio = fork_median / spawn_median_4

            fork_run = {
                "status": "completed",
                "workers": fork_workers,
                "durations_seconds": fork_durations,
                "median_seconds": fork_median,
                "fork_to_spawn_ratio": ratio,
                "result_matches_sequential": fork_result == seq_result,
            }

    metrics: dict[str, object] = {
        "environment": {
            "operating_system": platform.system(),
            "python_version": platform.python_version(),
            "python_executable": sys.executable,
            "available_start_methods": available_methods,
        },
        "experiment": {
            "limit": limit,
            "repeats": repeats,
            "worker_counts": worker_counts,
            "required_start_method": StartMethod.SPAWN.value,
        },
        "expected_result": _stats_to_dict(EXPECTED),
        "sequential": {
            "durations_seconds": seq_durations,
            "median_seconds": seq_median,
            "result_matches_expected": matches_expected if matches_expected is not None else (seq_result == EXPECTED),
        },
        "process_runs": process_runs,
        "fork_run": fork_run,
    }
    return metrics


def write_metrics(path: Path, metrics: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _print_experiment_report(metrics: dict[str, object]) -> None:
    env = metrics["environment"]  # type: ignore[assignment]
    exp = metrics["experiment"]  # type: ignore[assignment]
    seq = metrics["sequential"]  # type: ignore[assignment]
    process_runs = metrics["process_runs"]  # type: ignore[assignment]
    fork_run = metrics["fork_run"]  # type: ignore[assignment]

    print("Лабораторная работа 2")
    print(f"Операционная система: {env['operating_system']}")
    print(f"Python: {env['python_version']}")
    print(f"Методы запуска: {', '.join(env['available_start_methods'])}")
    print(f"Диапазон: 2..{exp['limit']}")
    print(f"Повторы: {exp['repeats']}")
    print()
    print(f"Последовательно, медиана: {seq['median_seconds']:.6f} с")
    print("spawn | Процессы | Медиана, с | Ускорение | Эффективность")
    for run in process_runs:  # type: ignore[union-attr]
        print(
            f"      | {run['workers']:>8} | {run['median_seconds']:>10.6f} | "
            f"{run['speedup']:>9.4f} | {run['efficiency']:>13.4f}"
        )
    print()
    all_match = all(run["result_matches_sequential"] for run in process_runs)  # type: ignore[union-attr]
    print(f"Результаты процессов совпадают: {all_match}")
    print(f"fork: {fork_run['status']}")
    print(f"Метрики записаны в: {Path('results/metrics.json')}")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    validate_args(args, parser)

    if args.mode is RunMode.CHECK:
        result = run_sequential(args.limit)
        matches = result == EXPECTED if args.limit == DEFAULT_LIMIT else None
        print(f"count={result.count}")
        print(f"max_prime={result.max_prime}")
        print(f"checksum={result.checksum}")
        print(f"matches_expected={matches}")
        return 0

    if args.mode is RunMode.SEQUENTIAL:
        result = run_sequential(args.limit)
        print(json.dumps(_stats_to_dict(result), ensure_ascii=False))
        return 0

    if args.mode is RunMode.PROCESSES:
        # Запускаем по одному разу для каждого workers
        for workers in sorted(set(args.workers)):
            result = run_processes(args.limit, workers, args.start_method)
            print(json.dumps(
                {"workers": workers, "start_method": args.start_method.value, **_stats_to_dict(result)},
                ensure_ascii=False,
            ))
        return 0

    # RunMode.EXPERIMENT
    metrics = build_metrics(args)
    write_metrics(args.output, metrics)
    _print_experiment_report(metrics)
    return 0


if __name__ == "__main__":
    mp.freeze_support()
    raise SystemExit(main())