"""Shared Rich console helpers used across CLI commands.

Every helper here escapes the dynamic `message` before handing it to Rich —
Rich's console.print interprets bare `[...]` as markup tags (and silently drops
unrecognized ones) by default, which would otherwise corrupt or crash on task
titles, reminder text, or LLM output that happens to contain square brackets.
"""

from rich.console import Console
from rich.markup import escape

console = Console()


def print_section(title: str) -> None:
    console.print(f"\n[bold cyan]{escape(title)}[/bold cyan]")


def print_ok(message: str) -> None:
    console.print(f"  [green]✓[/green] {escape(message)}")


def print_warn(message: str) -> None:
    console.print(f"  [yellow]![/yellow] {escape(message)}")


def print_error(message: str) -> None:
    console.print(f"  [red]✗[/red] {escape(message)}")
