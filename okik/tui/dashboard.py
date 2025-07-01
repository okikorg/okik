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
    """Deploy a selected YAML file and display progress logs."""

    deploying: reactive[bool] = reactive(False)

    def compose(self) -> ComposeResult:  # type: ignore[override]
        yield Static("[b]Kubernetes Deploy[/b] • Choose YAML and press [green]Deploy[/green]", markup=True)
        yield Input(placeholder="/path/to/manifest.yaml", id="yamlpath")
        yield Button("Browse", id="browse")
        yield Button("Deploy", id="deploy", variant="success")
        yield ProgressBar(total=1, id="progress-deploy")
        yield Static("", id="deploy-log", expand=True)

    def watch_deploying(self, value: bool) -> None:
        bar = self.query_one("#progress-deploy", ProgressBar)
        bar.animate = value  # type: ignore[attr-defined]

    async def on_button_pressed(self, event: Button.Pressed) -> None:  # type: ignore
        btn_id = event.button.id
        if btn_id == "browse":
            # Auto-fill input with first YAML found in services dir
            from pathlib import Path
            from okik.consts import ProjectDir

            services_dir = Path(ProjectDir.SERVICES_DIR.value) / "k8"
            ymls = list(services_dir.glob("*.y*ml"))
            if ymls:
                self.query_one("#yamlpath", Input).value = str(ymls[0])
        elif btn_id == "deploy":
            yaml_path = self.query_one("#yamlpath", Input).value.strip()
            if not yaml_path:
                self.query_one("#deploy-log", Static).update("[red]Please specify a YAML file.[/red]")
                return
            await self._start_deploy(yaml_path)

    async def _start_deploy(self, yaml_path: str):
        from okik.main import _import_kubernetes
        import yaml as _yaml
        from pathlib import Path

        log = self.query_one("#deploy-log", Static)
        log.update(f"Starting deployment of {yaml_path}\n")

        path_obj = Path(yaml_path)
        if not path_obj.exists():
            log.update(f"[red]File not found: {yaml_path}[/red]")
            return

        # Read YAML documents for later display
        try:
            documents = list(_yaml.safe_load_all(path_obj.read_text()))
        except Exception as exc:
            log.update(f"[red]Failed to parse YAML: {exc}[/red]")
            return

        # Worker coroutine to interact with K8s
        async def _worker():
            _import_kubernetes()
            api_client = client.ApiClient()
            self.call_from_thread(self._update_deploy_progress, 0, 1)

            from kubernetes import utils as k8s_utils  # type: ignore

            for idx, doc in enumerate(documents, start=1):
                try:
                    k8s_utils.create_from_dict(api_client, doc, namespace="default")
                    self.call_from_thread(self._append_deploy_log, f"Applied {doc.get('kind')} {doc.get('metadata', {}).get('name')}")
                except Exception as exc:
                    self.call_from_thread(self._append_deploy_log, f"[red]Error: {exc}[/red]")
                self.call_from_thread(self._update_deploy_progress, idx, len(documents))

            self.call_from_thread(self._append_deploy_log, "[green]Deployment finished.[/green]")

        self.deploying = True
        self.app.run_worker(_worker(), description="deploy")

    # helper methods
    def _update_deploy_progress(self, current: int, total: int):
        bar = self.query_one("#progress-deploy", ProgressBar)
        bar.update(total=total, progress=current)

    def _append_deploy_log(self, line: str, max_lines: int = 100):
        log = self.query_one("#deploy-log", Static)
        existing = str(log.renderable)
        lines = (existing + "\n" + line).splitlines()[-max_lines:]
        log.update("\n".join(lines))


class ClusterView(Static):
    """Live resource monitoring for Deployments and Services."""

    refresh_task = None  # handle to cancel on unmount

    def compose(self) -> ComposeResult:  # type: ignore[override]
        yield Static("[b]Cluster Resources (auto-refresh every 5s)[/b]", markup=True)
        yield Static("Loading…", id="cluster-body", expand=True)

    async def on_mount(self) -> None:  # type: ignore
        # schedule periodic refresh every 5 seconds
        self.refresh_task = self.set_interval(5, self._refresh_data, pause=False)
        await self._refresh_data()

    async def on_unmount(self) -> None:  # type: ignore
        if self.refresh_task:
            self.refresh_task.stop()

    async def _refresh_data(self):
        from okik.main import _import_kubernetes
        _import_kubernetes()

        try:
            config.load_kube_config()
        except Exception:
            self.query_one("#cluster-body", Static).update("[red]Could not load kubeconfig.[/red]")
            return

        apps_v1 = client.AppsV1Api()
        core_v1 = client.CoreV1Api()

        try:
            deployments = apps_v1.list_namespaced_deployment(namespace="default")
            services = core_v1.list_namespaced_service(namespace="default")
        except Exception as exc:
            self.query_one("#cluster-body", Static).update(f"[red]{exc}[/red]")
            return

        from rich.tree import Tree

        root = Tree("[bold cyan]default namespace[/bold cyan]")

        dep_node = root.add("[magenta]Deployments[/magenta]")
        for d in deployments.items:
            replicas = d.status.available_replicas or 0
            desired = d.spec.replicas
            dep_node.add(f"{d.metadata.name} • {replicas}/{desired} ready")

        svc_node = root.add("[green]Services[/green]")
        for s in services.items:
            ports = ", ".join([f"{p.port}/{p.protocol}" for p in s.spec.ports])
            svc_node.add(f"{s.metadata.name} • {s.spec.type} • {ports}")

        self.query_one("#cluster-body", Static).update(root)


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