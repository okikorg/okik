"""
Textual Dashboard for Okik CLI
Enhanced TUI experience with real-time monitoring
"""

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Header, Footer, DataTable, Log, Static, Button, 
    Input, Select, Tabs, TabbedContent, TabPane,
    ProgressBar, Tree, Collapsible
)
from textual.binding import Binding
from textual.screen import Screen
from textual.reactive import reactive
from textual import on
from rich.text import Text
from rich.table import Table
from rich.panel import Panel
import asyncio
import json
import os
from datetime import datetime
from typing import Dict, List, Any

class ServiceStatus:
    """Service status data model"""
    def __init__(self, name: str, status: str, replicas: int, available: int):
        self.name = name
        self.status = status
        self.replicas = replicas
        self.available = available
        self.last_updated = datetime.now()

class DeploymentStatus:
    """Deployment status data model"""
    def __init__(self, name: str, progress: int, stage: str):
        self.name = name
        self.progress = progress
        self.stage = stage
        self.last_updated = datetime.now()

class ServicesScreen(Screen):
    """Screen for service management"""
    
    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(classes="left-panel"):
                yield Static("Services", classes="panel-title")
                yield DataTable(id="services-table")
                with Horizontal():
                    yield Button("Deploy", id="deploy-btn", variant="success")
                    yield Button("Scale", id="scale-btn", variant="primary")
                    yield Button("Delete", id="delete-btn", variant="error")
            
            with Vertical(classes="right-panel"):
                yield Static("Service Details", classes="panel-title")
                yield Log(id="service-logs", auto_scroll=True)
        yield Footer()
    
    def on_mount(self) -> None:
        """Initialize the services table"""
        table = self.query_one("#services-table", DataTable)
        table.add_columns("Name", "Status", "Replicas", "Available", "Updated")
        self.refresh_services()
    
    def refresh_services(self) -> None:
        """Refresh the services table with current data"""
        table = self.query_one("#services-table", DataTable)
        table.clear()
        
        # Mock service data - in real implementation, fetch from Kubernetes
        services = [
            ServiceStatus("embedder", "Running", 3, 3),
            ServiceStatus("mockllm", "Running", 2, 1),
            ServiceStatus("api-gateway", "Pending", 1, 0),
        ]
        
        for service in services:
            status_style = "green" if service.status == "Running" else "yellow"
            table.add_row(
                service.name,
                Text(service.status, style=status_style),
                str(service.replicas),
                str(service.available),
                service.last_updated.strftime("%H:%M:%S")
            )
    
    @on(Button.Pressed, "#deploy-btn")
    def deploy_service(self) -> None:
        """Handle deploy button press"""
        log = self.query_one("#service-logs", Log)
        log.write_line("Starting deployment...")
        self.app.push_screen(DeploymentScreen())
    
    @on(Button.Pressed, "#scale-btn")
    def scale_service(self) -> None:
        """Handle scale button press"""
        self.app.push_screen(ScaleServiceScreen())
    
    @on(Button.Pressed, "#delete-btn")
    def delete_service(self) -> None:
        """Handle delete button press"""
        log = self.query_one("#service-logs", Log)
        log.write_line("Service deletion initiated...")

class DeploymentScreen(Screen):
    """Screen for managing deployments"""
    
    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Static("Deployment Manager", classes="screen-title")
            
            with Horizontal():
                with Vertical(classes="deployment-form"):
                    yield Static("Deployment Configuration")
                    yield Input(placeholder="Service Name", id="service-name")
                    yield Select(
                        [("embedder", "Embedder Service"), ("mockllm", "Mock LLM")],
                        id="service-type"
                    )
                    yield Input(placeholder="Replicas (default: 1)", id="replicas")
                    yield Button("Deploy", id="start-deploy", variant="success")
                
                with Vertical(classes="deployment-status"):
                    yield Static("Deployment Progress")
                    yield DataTable(id="deployment-table")
            
            yield Log(id="deployment-logs", auto_scroll=True)
        yield Footer()
    
    def on_mount(self) -> None:
        """Initialize deployment table"""
        table = self.query_one("#deployment-table", DataTable)
        table.add_columns("Service", "Progress", "Stage", "Status")
    
    @on(Button.Pressed, "#start-deploy")
    async def start_deployment(self) -> None:
        """Start deployment process"""
        service_name = self.query_one("#service-name", Input).value
        replicas = self.query_one("#replicas", Input).value or "1"
        
        if not service_name:
            log = self.query_one("#deployment-logs", Log)
            log.write_line("❌ Service name is required")
            return
        
        table = self.query_one("#deployment-table", DataTable)
        log = self.query_one("#deployment-logs", Log)
        
        # Simulate deployment stages
        stages = [
            ("Preparing", 20),
            ("Building Image", 40),
            ("Pushing to Registry", 60),
            ("Creating Deployment", 80),
            ("Waiting for Pods", 100)
        ]
        
        row_key = table.add_row(service_name, "0%", "Starting", "🟡 In Progress")
        
        for stage, progress in stages:
            await asyncio.sleep(1)  # Simulate work
            table.update_cell(row_key, "Progress", f"{progress}%")
            table.update_cell(row_key, "Stage", stage)
            log.write_line(f"📦 {service_name}: {stage} ({progress}%)")
        
        table.update_cell(row_key, "Status", "✅ Completed")
        log.write_line(f"🎉 {service_name} deployed successfully!")

class ScaleServiceScreen(Screen):
    """Screen for scaling services"""
    
    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Static("Scale Service", classes="screen-title")
            
            with Horizontal():
                yield Static("Service:")
                yield Select(
                    [("embedder", "Embedder"), ("mockllm", "Mock LLM")],
                    id="service-select"
                )
            
            with Horizontal():
                yield Static("Current Replicas:")
                yield Static("3", id="current-replicas")
            
            with Horizontal():
                yield Static("New Replicas:")
                yield Input(placeholder="Enter number of replicas", id="new-replicas")
            
            yield Button("Scale", id="scale-button", variant="primary")
            yield Log(id="scale-logs")
        yield Footer()
    
    @on(Button.Pressed, "#scale-button")
    async def scale_service(self) -> None:
        """Scale the selected service"""
        service = self.query_one("#service-select", Select).value
        new_replicas = self.query_one("#new-replicas", Input).value
        log = self.query_one("#scale-logs", Log)
        
        if not new_replicas or not new_replicas.isdigit():
            log.write_line("❌ Please enter a valid number of replicas")
            return
        
        log.write_line(f"🔄 Scaling {service} to {new_replicas} replicas...")
        await asyncio.sleep(2)  # Simulate scaling operation
        log.write_line(f"✅ {service} scaled to {new_replicas} replicas successfully!")

class MonitoringScreen(Screen):
    """Screen for monitoring system metrics"""
    
    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Static("System Monitoring", classes="screen-title")
            
            with Horizontal():
                with Vertical(classes="metrics-panel"):
                    yield Static("Resource Usage")
                    yield DataTable(id="metrics-table")
                
                with Vertical(classes="logs-panel"):
                    yield Static("System Logs")
                    yield Log(id="system-logs", auto_scroll=True)
            
            with Horizontal():
                yield Button("Refresh", id="refresh-metrics", variant="primary")
                yield Button("Export Logs", id="export-logs", variant="secondary")
        yield Footer()
    
    def on_mount(self) -> None:
        """Initialize monitoring data"""
        table = self.query_one("#metrics-table", DataTable)
        table.add_columns("Metric", "Value", "Status")
        self.refresh_metrics()
        
        # Start log streaming
        self.set_interval(2.0, self.stream_logs)
    
    def refresh_metrics(self) -> None:
        """Refresh system metrics"""
        table = self.query_one("#metrics-table", DataTable)
        table.clear()
        
        # Mock metrics data
        metrics = [
            ("CPU Usage", "45%", "🟢 Normal"),
            ("Memory Usage", "67%", "🟡 Warning"),
            ("Disk Usage", "23%", "🟢 Normal"),
            ("Network I/O", "1.2 MB/s", "🟢 Normal"),
            ("Active Pods", "7", "🟢 Normal"),
        ]
        
        for metric, value, status in metrics:
            table.add_row(metric, value, status)
    
    def stream_logs(self) -> None:
        """Stream system logs"""
        log = self.query_one("#system-logs", Log)
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Mock log entries
        import random
        log_entries = [
            f"[{timestamp}] Pod embedder-xyz started successfully",
            f"[{timestamp}] Service mockllm received 15 requests",
            f"[{timestamp}] Scaling operation completed for embedder",
            f"[{timestamp}] Health check passed for all services",
        ]
        
        log.write_line(random.choice(log_entries))
    
    @on(Button.Pressed, "#refresh-metrics")
    def refresh_button_pressed(self) -> None:
        """Handle refresh button press"""
        self.refresh_metrics()

class ConfigurationScreen(Screen):
    """Screen for managing configurations"""
    
    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Static("Configuration Manager", classes="screen-title")
            
            with TabbedContent():
                with TabPane("Service Config", id="service-config"):
                    yield Input(placeholder="Image Registry", id="registry")
                    yield Input(placeholder="Namespace", id="namespace")
                    yield Button("Save Service Config", id="save-service")
                
                with TabPane("Cluster Config", id="cluster-config"):
                    yield Select([("minikube", "Minikube"), ("eks", "AWS EKS")], id="cluster-type")
                    yield Input(placeholder="Cluster Endpoint", id="endpoint")
                    yield Button("Save Cluster Config", id="save-cluster")
                
                with TabPane("Build Config", id="build-config"):
                    yield Input(placeholder="Docker Registry", id="docker-registry")
                    yield Input(placeholder="Build Cache Path", id="cache-path")
                    yield Button("Save Build Config", id="save-build")
            
            yield Log(id="config-logs")
        yield Footer()

class OkikDashboard(App):
    """Main Okik Dashboard Application"""
    
    TITLE = "Okik Dashboard"
    SUB_TITLE = "Cloud Service Management"
    
    BINDINGS = [
        Binding("s", "show_services", "Services", priority=True),
        Binding("d", "show_deployments", "Deploy", priority=True),
        Binding("m", "show_monitoring", "Monitor", priority=True),
        Binding("c", "show_config", "Config", priority=True),
        Binding("q", "quit", "Quit", priority=True),
    ]
    
    CSS = """
    .screen-title {
        dock: top;
        height: 3;
        content-align: center middle;
        text-style: bold;
    }
    
    .panel-title {
        dock: top;
        height: 1;
        text-style: bold;
        background: $secondary;
    }
    
    .left-panel {
        width: 1fr;
        margin: 1;
    }
    
    .right-panel {
        width: 1fr;
        margin: 1;
    }
    
    .deployment-form {
        width: 1fr;
        margin: 1;
    }
    
    .deployment-status {
        width: 2fr;
        margin: 1;
    }
    
    .metrics-panel {
        width: 1fr;
        margin: 1;
    }
    
    .logs-panel {
        width: 1fr;
        margin: 1;
    }
    
    DataTable {
        height: 100%;
    }
    
    Log {
        height: 100%;
        border: solid $primary;
    }
    
    Button {
        margin: 1;
    }
    """
    
    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
    
    def on_mount(self) -> None:
        """Start with services screen"""
        self.push_screen(ServicesScreen())
    
    def action_show_services(self) -> None:
        """Show services screen"""
        self.push_screen(ServicesScreen())
    
    def action_show_deployments(self) -> None:
        """Show deployments screen"""
        self.push_screen(DeploymentScreen())
    
    def action_show_monitoring(self) -> None:
        """Show monitoring screen"""
        self.push_screen(MonitoringScreen())
    
    def action_show_config(self) -> None:
        """Show configuration screen"""
        self.push_screen(ConfigurationScreen())

def run_dashboard():
    """Run the Okik dashboard"""
    app = OkikDashboard()
    app.run()

if __name__ == "__main__":
    run_dashboard()