"""Command-line interface for agent-lab."""

import asyncio
from pathlib import Path

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from agent_lab import __logo__, __version__
from agent_lab.agent import Agent
from agent_lab.config import Config, load_config, save_config, get_default_config_path
from agent_lab.providers import create_provider
from agent_lab.session import Session
from agent_lab.tools import ReadFileTool, WriteFileTool, ListDirTool, ToolRegistry
from agent_lab.workspace import Workspace
from agent_lab.api.server import create_app

app = typer.Typer(help=f"{__logo__} agent-lab - Minimal agent system")
console = Console()


@app.callback()
def version_option(
    version: bool = typer.Option(None, "--version", "-v", is_eager=True, help="Show version"),
) -> None:
    """Show version if requested."""
    if version:
        console.print(f"{__logo__} agent-lab v{__version__}")
        raise typer.Exit()


@app.command()
def init(
    workspace: str = typer.Option(
        "~/.agent-lab/workspace",
        "--workspace",
        "-w",
        help="Workspace directory",
    ),
) -> None:
    """Initialize agent-lab workspace and configuration."""
    config_path = get_default_config_path()
    workspace_path = Path(workspace).expanduser()

    # Create workspace
    ws = Workspace(workspace_path)
    ws.initialize()
    console.print(f"✓ Created workspace at {ws.path}")

    # Create config
    config = Config()
    config.agents.defaults.workspace = workspace
    save_config(config, config_path)
    console.print(f"✓ Created config at {config_path}")

    console.print("\n[green]Initialization complete![/green]")
    console.print(f"Config location: {config_path}")
    console.print(f"Workspace location: {workspace_path}")
    console.print("\nNext steps:")
    console.print("1. Edit config: agent-lab config show")
    console.print("2. Set API key in ~/.agent-lab/config.json")
    console.print("3. Try: agent-lab chat 'Hello!'")


@app.command()
def config(
    action: str = typer.Argument("show", help="Action: show"),
) -> None:
    """Manage configuration."""
    config_path = get_default_config_path()

    if action == "show":
        if not config_path.exists():
            console.print("[yellow]Configuration not found. Run 'agent-lab init' first.[/yellow]")
            raise typer.Exit(1)

        cfg = load_config(config_path)
        console.print("\n[cyan]Current Configuration[/cyan]")
        table = Table(show_header=True, header_style="bold")
        table.add_column("Setting")
        table.add_column("Value")
        table.add_row("model", cfg.agents.defaults.model)
        table.add_row("provider", cfg.agents.defaults.provider)
        table.add_row("workspace", cfg.agents.defaults.workspace)
        table.add_row("max_iterations", str(cfg.agents.defaults.max_iterations))
        table.add_row("temperature", str(cfg.agents.defaults.temperature))
        console.print(table)
        console.print(f"\nConfig file: {config_path}")
    else:
        console.print(f"Unknown action: {action}")


@app.command()
def chat(
    message: str | None = typer.Argument(None, help="Message to send (interactive if empty)"),
    model: str | None = typer.Option(None, "--model", "-m", help="Model override"),
    session: str = typer.Option("default", "--session", "-s", help="Session ID"),
    clear: bool = typer.Option(False, "--clear", help="Clear session history"),
) -> None:
    """Chat with the agent."""
    config_path = get_default_config_path()

    if not config_path.exists():
        console.print("[red]✗ Configuration not found.[/red]")
        console.print("Run 'agent-lab init' first.")
        raise typer.Exit(1)

    cfg = load_config(config_path)

    # Validate API key is configured
    provider_name = cfg.agents.defaults.provider
    if provider_name == "auto":
        model_lower = (model or cfg.agents.defaults.model).lower()
        provider_name = "anthropic" if "claude" in model_lower else "openai"

    prov_cfg = getattr(cfg.providers, provider_name, None)
    if not prov_cfg or not prov_cfg.api_key:
        console.print(f"[red]✗ API key not configured for '{provider_name}'.[/red]")
        console.print(f"Set it in {config_path}")
        raise typer.Exit(1)

    # Setup workspace and tools
    workspace_path = cfg.workspace_path
    workspace_path.mkdir(parents=True, exist_ok=True)

    # Create provider
    try:
        provider = create_provider(cfg, model)
    except ValueError as e:
        console.print(f"[red]✗ Error creating provider: {e}[/red]")
        raise typer.Exit(1)

    # Setup tools
    tools = ToolRegistry()
    if cfg.tools.enable_read_file:
        tools.register(ReadFileTool(workspace_path))
    if cfg.tools.enable_write_file:
        tools.register(WriteFileTool(workspace_path))
    if cfg.tools.enable_list_dir:
        tools.register(ListDirTool(workspace_path))

    # Load or create session
    sess = Session(session, workspace_path)
    if clear:
        sess.clear_history()

    # Create agent
    agent = Agent(
        provider=provider,
        tools=tools,
        workspace=workspace_path,
        model=model,
        max_iterations=cfg.agents.defaults.max_iterations,
        max_tokens=cfg.agents.defaults.max_tokens,
        temperature=cfg.agents.defaults.temperature,
    )

    async def run_chat():
        # Load history
        history = sess.load_history()
        if history and history[0].get("role") != "system":
            # Add system message if not present
            history.insert(0, {
                "role": "system",
                "content": agent._build_system_prompt(),
            })

        # Determine message source
        user_message = message
        if not user_message:
            # Interactive mode
            try:
                user_message = console.input("[cyan]You:[/cyan] ").strip()
            except EOFError:
                return

            if not user_message:
                console.print("[dim]Empty message, exiting.[/dim]")
                return

        # Run agent
        try:
            console.print()
            response, messages = await agent.run(user_message, history)
            sess.save_history(messages)

            console.print(f"[cyan]Agent:[/cyan] {response}\n")

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted.[/yellow]")
            raise typer.Exit(0)
        except Exception as e:
            console.print(f"[red]✗ Error: {str(e)}[/red]")
            raise typer.Exit(1)

    asyncio.run(run_chat())


@app.command()
def tools_list() -> None:
    """List available tools."""
    config_path = get_default_config_path()
    if not config_path.exists():
        console.print("[yellow]Configuration not found. Run 'agent-lab init' first.[/yellow]")
        return

    cfg = load_config(config_path)
    workspace_path = cfg.workspace_path

    registry = ToolRegistry()
    registry.register(ReadFileTool(workspace_path))
    registry.register(WriteFileTool(workspace_path))
    registry.register(ListDirTool(workspace_path))

    console.print("\n[cyan]Available Tools[/cyan]")
    if not registry.tool_names:
        console.print("[dim]No tools available.[/dim]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Name")
    table.add_column("Description")

    for tool_name in registry.tool_names:
        t = registry.get(tool_name)
        if t:
            table.add_row(t.name, t.description)

    console.print(table)


@app.command()
def skills_list() -> None:
    """List available skills."""
    config_path = get_default_config_path()
    if not config_path.exists():
        console.print("[yellow]Configuration not found. Run 'agent-lab init' first.[/yellow]")
        return

    cfg = load_config(config_path)
    workspace_path = cfg.workspace_path

    from agent_lab.skills import SkillsLoader

    loader = SkillsLoader(workspace_path)
    skill_list = loader.list_skills()

    if not skill_list:
        console.print("[dim]No skills found in workspace.[/dim]")
        return

    console.print("\n[cyan]Available Skills[/cyan]")
    for skill in skill_list:
        console.print(f"  • {skill}")


@app.command("api")
def run_api(
    host: str = typer.Option("127.0.0.1", "--host", help="API host"),
    port: int = typer.Option(8000, "--port", help="API port"),
    config_path: str | None = typer.Option(None, "--config", help="Path to config file"),
) -> None:
    """Run OpenAI-compatible HTTP API server."""
    app_instance = create_app(config_path=config_path)
    console.print(f"[green]Starting API server on http://{host}:{port}[/green]")
    uvicorn.run(app_instance, host=host, port=port)


def main() -> None:
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()

