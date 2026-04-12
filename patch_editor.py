import re
import os

with open("roborock/map/editor.py", "r") as f:
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

content = content.replace(to_dict_orig, to_dict_new)

# Add imports
content = content.replace("import logging\n", "import logging\nimport threading\nimport json\nimport pathlib\n")

# Add lock
content = content.replace("        self._redo_stack: list[EditObject] = []\n", "        self._redo_stack: list[EditObject] = []\n        self._lock = threading.Lock()\n")

# Thread safety wrappers
for method in ["add_edit", "undo", "redo", "clear"]:
    if f"def {method}(self" in content:
        pattern = r"(    def " + method + r"\(.*?:\n)(.*?)(?=\n    def |\Z)"
        def repl(match):
            prefix = match.group(1)
            body = match.group(2)
            if "with self._lock:" in body:
                return match.group(0)
            indented_body = "\n".join(["        " + line if line else line for line in body.split("\n")])
            return prefix + "        with self._lock:\n" + indented_body
        
        content = re.sub(pattern, repl, content, count=1, flags=re.DOTALL)

# Add save and load methods
persistence_code = """
    def save(self, filepath: str | pathlib.Path) -> None:
        \"\"\"Save pending edits to a JSON file.\"\"\"
        with self._lock:
            data = {
                "edits": [edit.to_dict() for edit in self._edit_stack]
            }
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)

    def load(self, filepath: str | pathlib.Path) -> None:
        \"\"\"Load pending edits from a JSON file.\"\"\"
        path = pathlib.Path(filepath)
        if not path.exists():
            return
            
        with self._lock:
            with open(path, "r") as f:
                try:
                    data = json.load(f)
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
    content = content + persistence_code

with open("roborock/map/editor.py", "w") as f:
    f.write(content)
