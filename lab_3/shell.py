from __future__ import annotations

import cmd
import shlex

from file_ops import FileManagerCore


class FileManagerShell(cmd.Cmd):
    intro = "Учебный файловый менеджер. Введите help."

    def __init__(self, core: FileManagerCore) -> None:
        super().__init__()
        self.core = core
        self.update_prompt()

    def update_prompt(self) -> None:
        self.prompt = f"fm:{self.core.display_path(self.core.current_dir)}> "

    # ---------- разбор аргументов ----------
    def split_args(self, raw: str, expected: int | tuple[int, ...]) -> list[str]:
        if "\\" in raw:
            raise ValueError("обратная косая черта не поддерживается")
        try:
            parts = shlex.split(raw, posix=True)
        except ValueError as exc:
            raise ValueError(f"ошибка разбора кавычек: {exc}") from exc

        if isinstance(expected, int):
            allowed = (expected,)
        else:
            allowed = expected
        if len(parts) not in allowed:
            raise ValueError(
                f"неверное число аргументов: ожидается {allowed}, получено {len(parts)}"
            )
        return parts

    def emptyline(self) -> None:
        """Не повторять предыдущую команду при пустом вводе."""
        return None

    # ---------- команды ----------
    def do_pwd(self, arg: str) -> None:
        """pwd: показать текущий каталог менеджера."""
        try:
            self.split_args(arg, 0)
            print(self.core.display_path(self.core.current_dir))
        except (ValueError, OSError) as exc:
            print(f"ERROR pwd: {exc}")

    def do_ls(self, arg: str) -> None:
        """ls [ПУТЬ]: показать содержимое каталога."""
        try:
            parts = self.split_args(arg, (0, 1))
            raw = parts[0] if parts else None
            entries = self.core.list_entries(raw)
            for kind, name in entries:
                print(f"{kind} {name}")
        except (ValueError, OSError) as exc:
            print(f"ERROR ls: {exc}")

    def do_cd(self, arg: str) -> None:
        """cd ПУТЬ: изменить текущий каталог менеджера."""
        try:
            parts = self.split_args(arg, 1)
            self.core.change_directory(parts[0])
            self.update_prompt()
            print("OK")
        except (ValueError, OSError) as exc:
            print(f"ERROR cd: {exc}")

    def do_cp(self, arg: str) -> None:
        """cp ИСТОЧНИК НАЗНАЧЕНИЕ: скопировать объект."""
        try:
            parts = self.split_args(arg, 2)
            src, dst = parts
            src_path = self.core.resolve_user_path(src, must_exist=True)
            dst_path = self.core.copy_entry(src, dst)
            print(
                f"OK cp {self.core.display_path(src_path)} -> "
                f"{self.core.display_path(dst_path)}"
            )
        except (ValueError, OSError) as exc:
            print(f"ERROR cp: {exc}")

    def do_mv(self, arg: str) -> None:
        """mv ИСТОЧНИК НАЗНАЧЕНИЕ: переместить объект."""
        try:
            parts = self.split_args(arg, 2)
            src, dst = parts
            src_path = self.core.resolve_user_path(src, must_exist=True)
            dst_path = self.core.move_entry(src, dst)
            print(
                f"OK mv {self.core.display_path(src_path)} -> "
                f"{self.core.display_path(dst_path)}"
            )
        except (ValueError, OSError) as exc:
            print(f"ERROR mv: {exc}")

    def do_rm(self, arg: str) -> None:
        """rm ПУТЬ: удалить обычный файл."""
        try:
            parts = self.split_args(arg, 1)
            target = self.core.remove_entry(parts[0])
            print(f"OK rm {self.core.display_path(target)}")
        except (ValueError, OSError) as exc:
            print(f"ERROR rm: {exc}")

    def do_exit(self, arg: str) -> bool:
        """exit: завершить программу."""
        try:
            self.split_args(arg, 0)
        except ValueError as exc:
            print(f"ERROR exit: {exc}")
            return False
        return True

    def do_EOF(self, arg: str) -> bool:
        """EOF: завершить программу по концу ввода."""
        print()
        return True