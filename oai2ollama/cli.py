import ast
import asyncio
import sys
import tomllib

import typer
from pydantic import HttpUrl, TypeAdapter
from rich.console import Console
from rich.table import Table

from .config import CONFIG_DIR, CONFIG_FILE, MODEL_REGISTRY_FILE, ConfigGroup, _parse_context_length
from .discovery import discover_models
from .model_registry import BUILTIN_MODELS
from .runtime import get_model_registry, get_settings
from .toml_io import to_toml_str

cli = typer.Typer(help="Wrap any OpenAI-compatible API into an Ollama-compatible API.")
console = Console()


def _save_config_groups(settings):
    data: dict = {"groups": {}}
    if CONFIG_FILE.exists():
        with CONFIG_FILE.open("rb") as f:
            loaded = tomllib.load(f)
        if isinstance(loaded, dict):
            data.update(loaded)
    data["groups"] = {name: group.model_dump(exclude_none=True) for name, group in settings.config_groups.items()}
    with CONFIG_FILE.open("w", encoding="utf-8") as f:
        f.write(to_toml_str(data))


def _save_model_registry(raw: dict):
    with MODEL_REGISTRY_FILE.open("w", encoding="utf-8") as f:
        f.write(to_toml_str(raw))


def _parse_literal(raw: str, expected: type):
    parsed = ast.literal_eval(raw)
    if not isinstance(parsed, expected):
        raise typer.BadParameter(f"Expected {expected.__name__}, got {type(parsed).__name__}")
    return parsed


def _parse_http_url(raw: str) -> HttpUrl:
    return TypeAdapter(HttpUrl).validate_python(raw)


@cli.command("run", help="Start the API server")
def run_server(
    config: str | None = typer.Option(None, "--config", "-C", help="Configuration group to use"),
    api_key: str | None = typer.Option(None, "--api-key", help="Legacy: API key for default group"),
    base_url: str | None = typer.Option(None, "--base-url", help="Legacy: base URL for default group"),
    capabilities: str | None = typer.Option(None, "--capabilities", "-c", help="Legacy: capabilities list literal, e.g. ['tools','vision']"),
    models: str | None = typer.Option(None, "--models", "-m", help="Legacy: models list literal, e.g. ['model-a']"),
    context_lengths: str | None = typer.Option(
        None,
        "--context-lengths",
        "-l",
        help="Legacy: context lengths dict literal, e.g. {'model-a':'128k'}",
    ),
    host: str | None = typer.Option(None, help="IP / hostname for the API server"),
    port: int | None = typer.Option(None, help="Port for the API server"),
):
    import uvicorn

    settings = get_settings()

    if config:
        settings.config = config

    if api_key and base_url:
        default_group = settings.config_groups.get("default")
        parsed_url = _parse_http_url(base_url)
        if default_group is None:
            default_group = ConfigGroup(base_url=parsed_url, api_key=api_key)
            settings.config_groups["default"] = default_group
        else:
            default_group.base_url = parsed_url
            default_group.api_key = api_key

        if models:
            parsed_models = _parse_literal(models, list)
            default_group.model_names = list(dict.fromkeys([*default_group.model_names, *parsed_models]))

        if capabilities:
            parsed_caps = _parse_literal(capabilities, list)
            for model_name in default_group.model_names:
                model_override = default_group.model_overrides.setdefault(model_name, {})
                model_override["capabilities"] = parsed_caps

        if context_lengths:
            parsed_lengths = _parse_literal(context_lengths, dict)
            for model_name, value in parsed_lengths.items():
                model_override = default_group.model_overrides.setdefault(model_name, {})
                model_override["context_length"] = _parse_context_length(value)

    active_config = settings.get_active_config()
    if active_config.auto_discover:
        console.print(f"\n[bold blue]Discovering models from {active_config.base_url}...[/bold blue]")
        active_config.model_names = asyncio.run(discover_models(active_config))
        _save_config_groups(settings)

    console.print(f"[bold green]Starting with config group: {settings.config or settings.default_config}[/bold green]")
    uvicorn.run("oai2ollama._app:app", host=host or settings.host, port=port or settings.port)


@cli.command("status", help="Show current status and configuration")
def status():
    settings = get_settings()
    registry = get_model_registry()
    console.print("\n[bold blue]oai2ollama Status[/bold blue]")
    console.print(f"  Configuration directory: {CONFIG_DIR}")
    console.print(f"  Configuration file: {CONFIG_FILE}")
    console.print(f"  Model registry file: {MODEL_REGISTRY_FILE}")
    console.print(f"  Default config group: {settings.default_config}")
    console.print(f"  Config groups: {len(settings.config_groups)}")
    console.print(f"  Models: {len(registry.user_defined)} user-defined, {len(BUILTIN_MODELS)} built-in\n")


config_cli = typer.Typer(help="Manage configuration groups")
cli.add_typer(config_cli, name="config")


@config_cli.command("list", help="List all configuration groups")
def list_configs():
    settings = get_settings()
    table = Table(title="Configuration Groups")
    table.add_column("Name", style="cyan")
    table.add_column("Base URL", style="magenta")
    table.add_column("Models", style="green")
    table.add_column("Auto Discover", style="yellow")

    for name, group in settings.config_groups.items():
        table.add_row(name, str(group.base_url), str(len(group.model_names)), "yes" if group.auto_discover else "no")

    console.print(table)


@config_cli.command("show", help="Show details of a configuration group")
def show_config(name: str):
    settings = get_settings()
    if name not in settings.config_groups:
        raise typer.BadParameter(f"Unknown config group: {name}")
    group = settings.config_groups[name]
    console.print(f"\n[bold]Group:[/bold] {name}")
    console.print(f"  base_url: {group.base_url}")
    console.print(f"  auto_discover: {group.auto_discover}")
    console.print(f"  model_names: {group.model_names}\n")


@config_cli.command("add", help="Add a new configuration group")
def add_config(
    name: str,
    base_url: str,
    api_key: str,
    auto_discover: bool = True,
):
    settings = get_settings()
    if name in settings.config_groups:
        raise typer.BadParameter(f"Config group already exists: {name}")

    group = ConfigGroup(base_url=_parse_http_url(base_url), api_key=api_key, auto_discover=auto_discover)
    if auto_discover:
        group.model_names = asyncio.run(discover_models(group))
    settings.config_groups[name] = group
    _save_config_groups(settings)
    console.print(f"Added config group: {name}")


@config_cli.command("discover", help="Manually discover models for a config group")
def discover_config(name: str):
    settings = get_settings()
    if name not in settings.config_groups:
        raise typer.BadParameter(f"Unknown config group: {name}")
    group = settings.config_groups[name]
    group.model_names = asyncio.run(discover_models(group))
    _save_config_groups(settings)
    console.print(f"Discovered {len(group.model_names)} models for {name}")


model_cli = typer.Typer(help="Manage global model registry")
cli.add_typer(model_cli, name="model")


@model_cli.command("list", help="List all models in the global registry")
def list_models():
    registry = get_model_registry()
    table = Table(title="Global Model Registry")
    table.add_column("Model Name", style="cyan")
    table.add_column("Context", style="green")
    table.add_column("Capabilities", style="magenta")
    table.add_column("Source", style="yellow")

    for name, entry in registry.user_defined.items():
        table.add_row(name, str(entry.context_length), ", ".join(entry.capabilities), "user")

    for name, entry in BUILTIN_MODELS.items():
        if name not in registry.user_defined:
            table.add_row(name, str(entry["context_length"]), ", ".join(entry["capabilities"]), "builtin")

    console.print(table)


@model_cli.command("set", help="Add or update a model in the global registry")
def set_model(
    name: str,
    context_length: str,
    capability: list[str] | None = typer.Option(None, "--capability", "-c"),
    description: str | None = typer.Option(None, "--description", "-d"),
):
    parsed = _parse_context_length(context_length)
    raw: dict = {}
    if MODEL_REGISTRY_FILE.exists():
        with MODEL_REGISTRY_FILE.open("rb") as f:
            loaded = tomllib.load(f)
        if isinstance(loaded, dict):
            raw = loaded

    raw[name] = {
        "context_length": parsed,
        "capabilities": capability or [],
        **({"description": description} if description else {}),
    }
    _save_model_registry(raw)
    get_model_registry().reload()
    console.print(f"Updated model: {name}")


@model_cli.command("remove", help="Remove a model from the global registry")
def remove_model(name: str):
    if not MODEL_REGISTRY_FILE.exists():
        raise typer.BadParameter("Model registry file does not exist")

    with MODEL_REGISTRY_FILE.open("rb") as f:
        raw = tomllib.load(f)
    if name not in raw:
        raise typer.BadParameter(f"Model not found: {name}")

    del raw[name]
    _save_model_registry(raw)
    get_model_registry().reload()
    console.print(f"Removed model: {name}")


def main():
    # Backward compatibility: `oai2ollama --api-key ...` behaves like `oai2ollama run ...`
    if len(sys.argv) == 1:
        sys.argv.insert(1, "run")
    elif len(sys.argv) > 1:
        first = sys.argv[1]
        known = {"run", "status", "config", "model", "-h", "--help"}
        if first not in known and first.startswith("-"):
            sys.argv.insert(1, "run")
    cli()
