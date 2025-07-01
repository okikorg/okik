from __future__ import annotations

"""Okik Textual Dashboard for full-screen monitoring.

Run via: `okik dashboard` (Typer command added separately).
"""

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, TabbedContent, TabPane, Static, Input, Button, ProgressBar
from textual.containers import Container
import asyncio
import os
import re
from datetime import datetime
from textual.reactive import reactive


# Regex to capture Docker "Step X/Y" progress lines
_STEP_REGEX = re.compile(r"Step\s+(\d+)/(\d+)\s*:\s*(.*)")


class BuildView(Static):
    """Interactive view that lets user trigger a Docker build and watch progress in real time."""

    # Reactive values to trigger UI updates
    progress_value: int = reactive(0)
    progress_total: int = reactive(1)

    def compose(self) -> ComposeResult:  # type: ignore[override]
        yield Static("[b]Docker Build[/b] • Fill paths and press [green]Start[/green]", markup=True)
        yield Input(value="main.py", placeholder="Entry point", id="entry")
        yield Input(value=".okik/docker/Dockerfile", placeholder="Dockerfile", id="dockerfile")
        yield Button("Start Build", id="start", variant="success")
        yield ProgressBar(total=self.progress_total, id="progress")
        yield Static("", id="log", expand=True)

    def watch_progress_value(self, value: int) -> None:  # reactive watcher
        bar = self.query_one("#progress", ProgressBar)
        bar.update(total=self.progress_total, progress=value)

    def watch_progress_total(self, value: int) -> None:  # ensure bar total updated
        bar = self.query_one("#progress", ProgressBar)
        bar.update(total=value, progress=self.progress_value)

    async def on_button_pressed(self, event: Button.Pressed) -> None:  # type: ignore
        if event.button.id == "start":
            entry = self.query_one("#entry", Input).value.strip()
            dockerfile = self.query_one("#dockerfile", Input).value.strip()
            await self._start_build(entry, dockerfile)

    async def _start_build(self, entry_point: str, docker_file: str) -> None:
        """Kick off the docker build in the background and stream progress."""

        # Reset UI state
        self.progress_value = 0
        self.progress_total = 1
        self.query_one("#log", Static).update("Starting build…\n")

        # Build command (temp image tag with timestamp)
        image_tag = f"okik-dashboard-temp:{datetime.utcnow().timestamp()}"
        cmd = (
            f"DOCKER_BUILDKIT=1 docker build -t {image_tag} -f {docker_file} ."
        )

        # Run in worker to avoid blocking the UI loop
        self.app.run_worker(self._run_build(cmd), description="docker build")

    async def _run_build(self, cmd: str):  # type: ignore[return-value]
        """Worker coroutine executed in a separate thread by Textual."""
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env={**os.environ, "DOCKER_BUILDKIT": "1"},
        )

        log_widget = self.query_one("#log", Static)

        async for raw_line in process.stdout:  # type: ignore[attr-defined]
            line = raw_line.decode().rstrip()

            # parse step lines
            if line.startswith("Step "):
                m = _STEP_REGEX.match(line)
                if m:
                    current = int(m.group(1))
                    total = int(m.group(2))
                    desc = m.group(3)

                    # schedule UI updates from thread-safe context
                    self.call_from_thread(self._update_progress, current, total, desc)
            # Always append log line (truncated to last 50 lines)
            self.call_from_thread(self._append_log, line)

        await process.wait()

        if process.returncode == 0:
            self.call_from_thread(self._append_log, "\n[green]Build completed successfully.[/green]")
        else:
            self.call_from_thread(self._append_log, f"\n[red]Build failed (code {process.returncode}).[/red]")

    # ---------- thread-safe helpers ----------

    def _update_progress(self, current: int, total: int, desc: str) -> None:
        self.progress_total = total
        self.progress_value = current
        bar = self.query_one("#progress", ProgressBar)
        bar.show_percentage = True  # type: ignore[attr-defined]
        # update label
        bar.label = f"{desc} ({current}/{total})"  # type: ignore[attr-defined]

    def _append_log(self, line: str, max_lines: int = 50) -> None:  # pragma: no cover
        log_widget = self.query_one("#log", Static)
        existing = log_widget.renderable.plain if hasattr(log_widget.renderable, "plain") else str(log_widget.renderable)
        lines = (existing + "\n" + line).splitlines()[-max_lines:]
        log_widget.update("\n".join(lines))


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