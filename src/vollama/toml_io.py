import re


def _format_key(key: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_-]+", key):
        return key
    escaped = key.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _format_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, list):
        return "[" + ", ".join(_format_value(item) for item in value) + "]"
    if isinstance(value, dict):
        pairs = [f"{_format_key(str(key))} = {_format_value(val)}" for key, val in value.items()]
        return "{ " + ", ".join(pairs) + " }"
    # Fallback: serialize unknown objects (e.g., pydantic HttpUrl) as quoted strings.
    return _format_value(str(value))


def to_toml_str(data: dict) -> str:
    """Serialize a dictionary into TOML for current project config shapes."""

    lines: list[str] = []

    def _format_table_path(parts: list[str]) -> str:
        return ".".join(_format_key(part) for part in parts)

    def write_table(table_path_parts: list[str], table_data: dict):
        scalar_items = {k: v for k, v in table_data.items() if not isinstance(v, dict)}
        nested_tables = {k: v for k, v in table_data.items() if isinstance(v, dict)}

        if table_path_parts:
            lines.append(f"[{_format_table_path(table_path_parts)}]")

        for key, value in scalar_items.items():
            lines.append(f"{_format_key(str(key))} = {_format_value(value)}")

        if scalar_items and nested_tables:
            lines.append("")

        for idx, (key, value) in enumerate(nested_tables.items()):
            next_path = [*table_path_parts, str(key)]
            write_table(next_path, value)
            if idx != len(nested_tables) - 1:
                lines.append("")

    for idx, (top_key, top_value) in enumerate(data.items()):
        if isinstance(top_value, dict):
            write_table([str(top_key)], top_value)
        else:
            lines.append(f"{_format_key(str(top_key))} = {_format_value(top_value)}")
        if idx != len(data) - 1:
            lines.append("")

    return "\n".join(lines) + "\n"
