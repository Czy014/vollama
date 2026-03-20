def _format_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, list):
        return "[" + ", ".join(_format_value(item) for item in value) + "]"
    if isinstance(value, dict):
        pairs = [f"{key} = {_format_value(val)}" for key, val in value.items()]
        return "{ " + ", ".join(pairs) + " }"
    return str(value)


def to_toml_str(data: dict) -> str:
    """Serialize a dictionary into TOML for current project config shapes."""

    lines: list[str] = []

    def write_table(table_path: str, table_data: dict):
        scalar_items = {k: v for k, v in table_data.items() if not isinstance(v, dict)}
        nested_tables = {k: v for k, v in table_data.items() if isinstance(v, dict)}

        if table_path:
            lines.append(f"[{table_path}]")

        for key, value in scalar_items.items():
            lines.append(f"{key} = {_format_value(value)}")

        if scalar_items and nested_tables:
            lines.append("")

        for idx, (key, value) in enumerate(nested_tables.items()):
            next_path = f"{table_path}.{key}" if table_path else key
            write_table(next_path, value)
            if idx != len(nested_tables) - 1:
                lines.append("")

    for idx, (top_key, top_value) in enumerate(data.items()):
        if isinstance(top_value, dict):
            write_table(top_key, top_value)
        else:
            lines.append(f"{top_key} = {_format_value(top_value)}")
        if idx != len(data) - 1:
            lines.append("")

    return "\n".join(lines) + "\n"
