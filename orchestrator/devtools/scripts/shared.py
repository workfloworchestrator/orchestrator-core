import re
from pathlib import Path
from subprocess import run
from typing import Callable


def remove_imports(text: str, module: str, symbol: str) -> tuple[str, bool]:
    """Find imports and remove them.

    Assumes code is formatted through Black to keep the regex somewhat readable.
    """
    text_orig = text

    # single import from module (may have a #comment) -> remove line
    rgx = r"(from %s import \b%s\b(\s*#[^\n]*)*\n)" % (re.escape(module), symbol)
    text = re.sub(rgx, "", text)

    # middle or last of multiple imports from module -> strip symbol
    rgx = r"(from %s import .+)(, \b%s\b)" % (re.escape(module), symbol)
    text = re.sub(rgx, r"\1", text)

    # first of multiple imports from same module -> strip symbol
    rgx = r"(from %s import )\b%s\b, " % (re.escape(module), symbol)
    text = re.sub(rgx, r"\1", text)

    # multiline import -> remove line with symbol
    rgx_verbose = r"""(?P<before>^from\s%s\simport\s*\([^\n]*\n(?:^[^\n]+,\n)*)
                      (^\s*\b%s\b,[^\n]*\n)
                      (?P<after>(?:^[^\n]+,\n)*\)[^\n]*$)"""
    text = re.sub(rgx_verbose % (re.escape(module), symbol), r"\g<before>\g<after>", text, flags=re.M | re.X)
    return text, text_orig != text


def insert_import(text: str, import_stmt: str) -> str:
    # Find the first import line and add our line above that
    # Rely on ruff & black for formatting
    return re.sub(r"(^(?:from .+|import .+)$)", f"{import_stmt}\n" + r"\1", text, count=1, flags=re.M)


def move_import(f: Path, symbol: str, old_module: str, new_module: str) -> bool:
    text = f.read_text()
    text, changed = remove_imports(text, old_module, symbol)
    if not changed:
        return False
    text = insert_import(text, f"from {new_module} import {symbol}")
    with f.open(mode="w"):
        f.write_text(text)
    return True


def find_and_remove_aliases(text: str, symbol: str) -> tuple[str, list[str]]:
    """In the given text find aliases of the given symbol and remove them.

    Return updated text and aliases removed.
    """
    rgx = r"(\b%s as (\w+))" % (symbol,)
    aliases = [aliasgroup for fullgroup, aliasgroup in re.findall(rgx, text)]
    newtext = re.sub(rgx, symbol, text)
    return newtext, aliases


def replace_words(text: str, words: list[str], replace: str) -> str:
    rgx = r"\b(%s)\b" % ("|".join(words),)
    return re.sub(rgx, replace, text)


def has_word(text: str, word: str) -> bool:
    return bool(re.search(r"\b%s\b" % (word,), text))


def run_tool(*args: str) -> bool:
    cmd = " ".join(args)
    try:
        r = run(args, capture_output=True)  # noqa: S603
        if r.returncode == 0:
            return True
        print(f"{cmd} failed:", r.stdout, r.stderr)
    except FileNotFoundError:
        print(f"{cmd} failed: could not find executable in the current venv")
    return False


def migrate(target_dir: Path, migrate_file: Callable[[Path], bool]) -> bool:
    abs_path = str(target_dir.resolve())

    def run_tools() -> bool:
        return run_tool("ruff", "check", "--fix", abs_path) and run_tool("black", "--quiet", abs_path)

    print(f"\n### Verifying files in {abs_path}... ", end="")
    if not run_tools():
        print("Failed to verify files, aborting migration. Please resolve errors.")
        return False
    print("Ok")

    files_migrated = files_checked = 0
    print(f"\n### Migrating files in {abs_path}")
    try:
        for f in target_dir.glob("**/*.py"):
            if migrate_file(f):
                files_migrated += 1
            files_checked += 1
    except KeyboardInterrupt:
        print("Interrupted...")

    print(f"\n### Migrated {files_migrated}/{files_checked} files in {abs_path}")

    print(f"\n### Formatting files in {abs_path}")
    return run_tools()
