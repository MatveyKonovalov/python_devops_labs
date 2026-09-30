from __future__ import annotations

import shutil
from pathlib import Path


class FileManagerCore:
    """Ядро файлового менеджера: модель путей и файловые операции."""

    def __init__(self, root: Path) -> None:
        if root.is_symlink():
            raise ValueError("root: каталог workspace не должен быть ссылкой")
        if not root.exists():
            raise ValueError("root: каталог workspace не существует")
        if not root.is_dir():
            raise ValueError("root: workspace должен быть каталогом")
        self.root: Path = root.resolve()
        self.current_dir: Path = self.root

    # ---------- отображение пути ----------
    def display_path(self, path: Path) -> str:
        """Вернуть путь вида / или /inbox/file.txt."""
        rel = path.resolve().relative_to(self.root)
        parts = rel.parts
        if not parts:
            return "/"
        return "/" + "/".join(parts)

    # ---------- проверка компонентов на ссылки ----------
    def _reject_symlink_components(self, candidate: Path) -> None:
        """Проверить все существующие компоненты пути на ссылки/точки соединения."""
        current = self.root
        rel_parts = candidate.relative_to(self.root).parts
        for part in rel_parts:
            current = current / part
            if current.is_symlink():
                raise ValueError(
                    f"путь содержит ссылку: {part}"
                )

    def _reject_symlinks_in_tree(self, root_dir: Path) -> None:
        """Рекурсивно проверить дерево на наличие ссылок."""
        for item in root_dir.rglob("*"):
            if item.is_symlink():
                raise ValueError(f"дерево содержит ссылку: {item.name}")

    # ---------- разрешение пути ----------
    def resolve_user_path(
            self,
            raw: str,
            *,
            must_exist: bool = False,
    ) -> Path:
        """Разрешить путь внутри root; ссылки не поддерживаются."""
        if raw is None or raw == "":
            raise ValueError("пустой путь")
        if "\\" in raw:
            raise ValueError("обратная косая черта не поддерживается, используйте /")
        # путь с буквой диска Windows
        if len(raw) >= 2 and raw[1] == ":":
            raise ValueError("путь с буквой диска не поддерживается")

        if raw.startswith("/"):
            # абсолютный путь интерфейса
            relative = raw.lstrip("/")
            if relative == "":
                candidate = self.root
            else:
                candidate = self.root
                for part in relative.split("/"):
                    if part in ("", "."):
                        continue
                    candidate = candidate / part
        else:
            candidate = self.current_dir
            for part in raw.split("/"):
                if part in ("", "."):
                    continue
                candidate = candidate / part

        # нормализация без раскрытия ссылок
        candidate = Path(candidate)

        # отклоняем ссылочные компоненты до resolve
        # (проверяем только те компоненты, что уже существуют)
        self._check_existing_components_symlink(candidate)

        candidate = candidate.resolve(strict=False)

        if not (candidate == self.root or candidate.is_relative_to(self.root)):
            raise ValueError("путь выходит за пределы workspace")

        if must_exist and not candidate.exists():
            raise FileNotFoundError(f"объект не существует: {raw}")

        return candidate

    def _check_existing_components_symlink(self, candidate: Path) -> None:
        """Пройти по компонентам от root и проверить существующие на ссылки."""
        # Если candidate вне root по строкам — пропускаем, отдельно проверим после resolve
        try:
            rel = candidate.relative_to(self.root)
        except ValueError:
            # путь с .. уходит за root — вернём как есть, отклоним позже
            return
        current = self.root
        for part in rel.parts:
            current = current / part
            if current.exists() and current.is_symlink():
                raise ValueError(f"путь содержит ссылку: {part}")

    # ---------- ls ----------
    def list_entries(self, raw: str | None = None) -> list[tuple[str, str]]:
        """Вернуть пары (DIR или FILE, имя), отсортированные по имени."""
        if raw is None or raw == "":
            target = self.current_dir
        else:
            target = self.resolve_user_path(raw, must_exist=True)

        if target.is_symlink():
            raise ValueError("ссылки не поддерживаются")
        if not target.is_dir():
            raise ValueError("не каталог")

        result: list[tuple[str, str]] = []
        for item in target.iterdir():
            if item.is_symlink():
                raise ValueError(f"обнаружена ссылка: {item.name}")
            if item.is_dir():
                result.append(("DIR", item.name))
            elif item.is_file():
                result.append(("FILE", item.name))
        result.sort(key=lambda pair: pair[1])
        return result

    # ---------- cd ----------
    def change_directory(self, raw: str) -> Path:
        """Проверить каталог и изменить current_dir."""
        target = self.resolve_user_path(raw, must_exist=True)
        if target.is_symlink():
            raise ValueError("ссылки не поддерживаются")
        if not target.is_dir():
            raise ValueError("cd: не каталог")
        self.current_dir = target
        return target

    # ---------- cp ----------
    def copy_entry(self, source: str, destination: str) -> Path:
        """Проверить типы, назначение и родительский каталог."""
        src = self.resolve_user_path(source, must_exist=True)
        dst = self.resolve_user_path(destination, must_exist=False)

        if src.is_symlink():
            raise ValueError("источник — ссылка")
        if dst.exists() or dst.is_symlink():
            raise ValueError("назначение уже существует")
        if dst == self.root:
            raise ValueError("нельзя перезаписать корень workspace")

        parent = dst.parent
        if not parent.exists() or not parent.is_dir():
            raise ValueError("родительский каталог назначения не существует")

        if src.is_file():
            if src == dst:
                raise ValueError("источник и назначение совпадают")
            shutil.copy2(src, dst)
            return dst

        if src.is_dir():
            # запрет копирования в себя / внутрь себя
            if dst == src or dst.is_relative_to(src):
                raise ValueError("нельзя копировать каталог внутрь самого себя")
            # проверить всё дерево источника на ссылки
            self._reject_symlinks_in_tree(src)
            shutil.copytree(src, dst)
            return dst

        raise ValueError("неподдерживаемый тип источника")

    # ---------- mv ----------
    def move_entry(self, source: str, destination: str) -> Path:
        """Проверить назначение и применить shutil.move."""
        src = self.resolve_user_path(source, must_exist=True)
        dst = self.resolve_user_path(destination, must_exist=False)

        if src == self.root:
            raise ValueError("нельзя перемещать корень workspace")
        if src == self.current_dir:
            raise ValueError("нельзя перемещать текущий каталог")
        # нельзя перемещать предка current_dir
        if self.current_dir.is_relative_to(src):
            raise ValueError("нельзя перемещать предка текущего каталога")

        if src.is_symlink():
            raise ValueError("источник — ссылка")
        if dst.exists() or dst.is_symlink():
            raise ValueError("назначение уже существует")

        parent = dst.parent
        if not parent.exists() or not parent.is_dir():
            raise ValueError("родительский каталог назначения не существует")

        if src.is_dir():
            if dst == src or dst.is_relative_to(src):
                raise ValueError("нельзя перемещать каталог внутрь самого себя")
            self._reject_symlinks_in_tree(src)

        if src.is_file() or src.is_dir():
            shutil.move(str(src), str(dst))
            return dst

        raise ValueError("неподдерживаемый тип источника")

    # ---------- rm ----------
    def remove_entry(self, raw: str) -> Path:
        """Удалить через unlink только обычный файл."""
        target = self.resolve_user_path(raw, must_exist=True)
        if target.is_symlink():
            raise ValueError("нельзя удалять ссылку")
        if not target.is_file():
            raise ValueError("rm удаляет только обычные файлы")
        target.unlink()
        return target