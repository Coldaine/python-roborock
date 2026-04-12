import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI_PATH = REPO_ROOT / "roborock" / "cli.py"


def apply_substitution(content: str, name: str, pattern: str, replacement: str) -> str:
    updated, count = re.subn(pattern, replacement, content)
    if count == 0:
        raise RuntimeError(f"{name} pattern did not match")
    return updated


def main() -> None:
    with open(CLI_PATH) as f:
        content = f.read()

    content = apply_substitution(
        content,
        "add_edit",
        r"(\s+success, error = await virtual_state\.add_edit\(edit\)\n\s+if success:\n(?:\s+await context\.save_virtual_state\(device_id\)\n)?\s+)(click\.echo\(\".*?\"\))",
        r"\1\2",
    )
    content = apply_substitution(
        content,
        "undo",
        r"(\s+edit = await virtual_state\.undo\(\)\n\s+)(click\.echo\(\"Undone: \{edit\.edit_type\.name\}\"\))",
        r"\1await context.save_virtual_state(device_id)\n    \2",
    )
    content = apply_substitution(
        content,
        "redo",
        r"(\s+edit = await virtual_state\.redo\(\)\n\s+)(click\.echo\(\"Redone: \{edit\.edit_type\.name\}\"\))",
        r"\1await context.save_virtual_state(device_id)\n    \2",
    )
    content = apply_substitution(
        content,
        "sync_clear",
        r"(\s+await virtual_state\.clear\(\)\n\s+await context\.save_virtual_state\(device_id\)\n\s+else:\n\s+click\.echo\(\"Sync failed or partially completed\.\"\))",
        r"\1",
    )
    content = apply_substitution(
        content,
        "map_edit_clear",
        r"(\s+await virtual_state\.clear\(\)\n\s+await context\.save_virtual_state\(device_id\)\n\s+click\.echo\(\"Cleared all pending edits\"\))",
        r"\1",
    )

    with open(CLI_PATH, "w") as f:
        f.write(content)


if __name__ == "__main__":
    main()
