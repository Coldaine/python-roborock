import re

with open("roborock/cli.py", "r") as f:
    content = f.read()

# Replace add_edit
content = re.sub(
    r"(\s+success, error = virtual_state\.add_edit\(edit\)\n\s+if success:\n\s+)(click\.echo\(\".*?\"\))",
    r"\1context.save_virtual_state(device_id)\n        \2",
    content
)

# Replace undo
content = re.sub(
    r"(\s+edit = virtual_state\.undo\(\)\n\s+)(click\.echo\(\"Undone: \{edit\.edit_type\.name\}\"\))",
    r"\1context.save_virtual_state(device_id)\n    \2",
    content
)

# Replace redo
content = re.sub(
    r"(\s+edit = virtual_state\.redo\(\)\n\s+)(click\.echo\(\"Redone: \{edit\.edit_type\.name\}\"\))",
    r"\1context.save_virtual_state(device_id)\n    \2",
    content
)

# Replace clear in sync
content = re.sub(
    r"(\s+virtual_state\.clear\(\)\n\s+else:\n\s+click\.echo\(\"Sync failed or partially completed\.\"\))",
    r"\n        virtual_state.clear()\n        context.save_virtual_state(device_id)\n    else:\n        click.echo(\"Sync failed or partially completed.\")",
    content
)

# Replace clear in map_edit_clear
content = re.sub(
    r"(\s+virtual_state\.clear\(\)\n\s+)(click\.echo\(\"Cleared all pending edits\"\))",
    r"\1context.save_virtual_state(device_id)\n    \2",
    content
)

with open("roborock/cli.py", "w") as f:
    f.write(content)
