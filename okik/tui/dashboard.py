from __future__ import annotations

"""Okik Textual Dashboard for full-screen monitoring.

Run via: `okik dashboard` (Typer command added separately).
"""

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, TabbedContent, TabPane, Static
from textual.containers import Container


class BuildView(Static):
    """Placeholder for the Build monitoring view."""

    def compose(self) -> ComposeResult:  # type: ignore[override]
        yield Static("[bold green]Build view coming soon…[/bold green]", markup=True)


class DeployView(Static):
    """Placeholder for the Deploy monitoring view."""

    def compose(self) -> ComposeResult:  # type: ignore[override]
        yield Static("[bold cyan]Deploy view coming soon…[/bold cyan]", markup=True)


class ClusterView(Static):
    """Placeholder for Cluster monitoring view."""

    def compose(self) -> ComposeResult:  # type: ignore[override]
        yield Static("[bold yellow]Cluster view coming soon…[/bold yellow]", markup=True)


class OkikDashboard(App):
    """Main Textual application with tabbed interface."""

    CSS_PATH = None  # Could reference an external .tcss later
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:  # type: ignore[override]
        yield Header(show_clock=True)
        with Container():
            yield TabbedContent(
                TabPane(BuildView(), title="Build"),
                TabPane(DeployView(), title="Deploy"),
                TabPane(ClusterView(), title="Cluster"),
            )
        yield Footer()


if __name__ == "__main__":
    OkikDashboard().run()