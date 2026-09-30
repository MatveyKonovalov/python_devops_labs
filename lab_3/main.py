from __future__ import annotations

from pathlib import Path

from file_ops import FileManagerCore
from shell import FileManagerShell

ROOT_DIR: Path = Path(__file__).resolve().parent
WORKSPACE_DIR: Path = ROOT_DIR / "workspace"


def prepare_workspace() -> None:
    """Создать учебное дерево без перезаписи данных."""
    # Проверка существующих элементов
    for path in (WORKSPACE_DIR, WORKSPACE_DIR / "inbox", WORKSPACE_DIR / "archive"):
        if path.exists():
            if path.is_symlink():
                raise SystemExit(f"Ошибка: {path} является ссылкой")
            if not path.is_dir():
                raise SystemExit(f"Ошибка: {path} не является каталогом")

    WORKSPACE_DIR.mkdir(exist_ok=True)
    (WORKSPACE_DIR / "inbox").mkdir(exist_ok=True)
    (WORKSPACE_DIR / "archive").mkdir(exist_ok=True)

    alpha = WORKSPACE_DIR / "inbox" / "alpha.txt"
    beta = WORKSPACE_DIR / "inbox" / "beta.txt"
    if not alpha.exists():
        alpha.write_text("alpha", encoding="utf-8")
    if not beta.exists():
        beta.write_text("beta", encoding="utf-8")


def main() -> int:
    prepare_workspace()
    core = FileManagerCore(WORKSPACE_DIR)
    shell = FileManagerShell(core)
    shell.cmdloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())