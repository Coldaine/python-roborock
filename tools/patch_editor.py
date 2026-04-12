import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
EDITOR_PATH = REPO_ROOT / "roborock" / "map" / "editor.py"


def replace_once(content: str, needle: str, replacement: str, name: str) -> str:
    if needle not in content:
        raise RuntimeError(f"{name} target not found")
    return content.replace(needle, replacement, 1)


def sub_once(content: str, pattern: str, replacement: str, name: str, flags: int = 0) -> str:
    updated, count = re.subn(pattern, replacement, content, count=1, flags=flags)
    if count == 0:
        raise RuntimeError(f"{name} pattern did not match")
    return updated


def ensure_locked_async_method(content: str, method_name: str) -> str:
    pattern = rf"(    async def {method_name}\(.*?:\n)(.*?)(?=\n    (?:async )?def |\Z)"

    def repl(match: re.Match[str]) -> str:
        prefix = match.group(1)
        body = match.group(2)
        if "async with self._lock:" in body:
            return match.group(0)
        indented = "\n".join(["        " + line if line else line for line in body.splitlines()])
        return prefix + "        async with self._lock:\n" + indented + "\n"

    return sub_once(content, pattern, repl, f"{method_name}_lock_wrap", flags=re.DOTALL)


def main() -> None:
    with open(EDITOR_PATH) as f:
        content = f.read()

    from_dict_code = """
    @classmethod
    def from_dict(cls, data: dict) -> 'EditObject':
        \"\"\"Create edit from dictionary.\"\"\"
        edit_type_name = data.get("edit_type")
        
        # Determine subclass based on type name
        if edit_type_name == "VIRTUAL_WALL":
            from .editor import VirtualWallEdit as edit_class
        elif edit_type_name == "NO_GO_ZONE":
            from .editor import NoGoZoneEdit as edit_class
        elif edit_type_name == "SPLIT_ROOM":
            from .editor import SplitRoomEdit as edit_class
        elif edit_type_name == "MERGE_ROOMS":
            from .editor import MergeRoomsEdit as edit_class
        elif edit_type_name == "RENAME_ROOM":
            from .editor import RenameRoomEdit as edit_class
        else:
            raise ValueError(f"Unknown or unsupported edit type: {edit_type_name}")
            
        kwargs = dict(data)
        kwargs.pop("edit_type", None)
        status_name = kwargs.pop("status", "PENDING")
        edit_id = kwargs.pop("edit_id", None)
        
        obj = edit_class(**kwargs)
        if edit_id:
            obj.edit_id = edit_id
        obj.status = EditStatus[status_name]
        return obj
"""

    to_dict_orig = """        return {
            "edit_id": self.edit_id,
            "edit_type": self.edit_type.name,
            "status": self.status.name,
        }"""
    to_dict_new = to_dict_orig + "\n" + from_dict_code
    content = replace_once(content, to_dict_orig, to_dict_new, "to_dict_from_dict_injection")

    content = replace_once(content, "import logging\n", "import logging\nimport json\nimport pathlib\n", "imports")

    if "self._lock" not in content:
        content = replace_once(
            content,
            "        self._redo_stack: list[EditObject] = []\n",
            "        self._redo_stack: list[EditObject] = []\n        self._lock = asyncio.Lock()\n",
            "async_lock",
        )

    for method in ["add_edit", "undo", "redo", "clear"]:
        content = ensure_locked_async_method(content, method)

    persistence_code = """
    async def save(self, filepath: str | pathlib.Path) -> None:
        \"\"\"Save pending edits to a JSON file.\"\"\"
        path = pathlib.Path(filepath)
        async with self._lock:
            data = {"edits": [edit.to_dict() for edit in self._edit_stack]}
            await asyncio.to_thread(path.write_text, json.dumps(data, indent=2), "utf-8")

    async def load(self, filepath: str | pathlib.Path) -> None:
        \"\"\"Load pending edits from a JSON file.\"\"\"
        path = pathlib.Path(filepath)
        if not path.exists():
            return

        async with self._lock:
            try:
                raw = await asyncio.to_thread(path.read_text, "utf-8")
                data = json.loads(raw)
                self._edit_stack.clear()
                self._redo_stack.clear()
                for edit_data in data.get("edits", []):
                    try:
                        edit = EditObject.from_dict(edit_data)
                        self._edit_stack.append(edit)
                    except Exception as e:
                        _LOGGER.error(f"Failed to load edit: {e}")
            except Exception as e:
                _LOGGER.error(f"Failed to parse virtual state file: {e}")
"""
    if "def save(self" not in content:
        content += persistence_code

    with open(EDITOR_PATH, "w") as f:
        f.write(content)


if __name__ == "__main__":
    main()
