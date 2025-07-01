"""
Integration Examples for Okik CLI Improvements
Shows how to integrate performance and TUI enhancements
"""

import asyncio
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich.table import Table
from pathlib import Path
import time

console = Console()

# Example 1: Enhanced async build command
@typer.command()
def async_build(
    entry_point: str = typer.Option("main.py", "--entry-point", "-e"),
    services: str = typer.Option("all", "--services", "-s", help="Comma-separated services or 'all'"),
    parallel: bool = typer.Option(True, "--parallel", "-p", help="Build in parallel"),
    cache: bool = typer.Option(True, "--cache", "-c", help="Use build cache")
):
    """
    Enhanced build command with async operations and caching
    """
    asyncio.run(_async_build_implementation(entry_point, services, parallel, cache))

async def _async_build_implementation(entry_point: str, services: str, parallel: bool, cache: bool):
    """Implementation of async build"""
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        
        # Discover services
        discovery_task = progress.add_task("Discovering services...", total=100)
        await asyncio.sleep(0.5)  # Simulate discovery
        
        service_list = ["embedder", "mockllm", "api-gateway"] if services == "all" else services.split(",")
        progress.update(discovery_task, completed=100, description="✅ Services discovered")
        
        if parallel:
            # Build all services in parallel
            build_tasks = []
            task_ids = []
            
            for service in service_list:
                task_id = progress.add_task(f"Building {service}...", total=100)
                task_ids.append(task_id)
                build_tasks.append(_build_service_async(service, progress, task_id, cache))
            
            results = await asyncio.gather(*build_tasks, return_exceptions=True)
            
            # Display results
            success_count = sum(1 for r in results if not isinstance(r, Exception))
            console.print(f"\n🎉 Built {success_count}/{len(service_list)} services successfully!", style="bold green")
        else:
            # Build services sequentially
            for service in service_list:
                task_id = progress.add_task(f"Building {service}...", total=100)
                await _build_service_async(service, progress, task_id, cache)

async def _build_service_async(service: str, progress: Progress, task_id, use_cache: bool):
    """Build a single service asynchronously"""
    
    # Check cache first
    if use_cache:
        progress.update(task_id, advance=20, description=f"Checking cache for {service}...")
        await asyncio.sleep(0.2)
        
        # Simulate cache check
        cache_hit = service == "embedder"  # Simulate cache hit for embedder
        if cache_hit:
            progress.update(task_id, completed=100, description=f"✅ {service} (cached)")
            return f"{service} built from cache"
    
    # Simulate build stages
    stages = [
        ("Preparing context", 20),
        ("Building Docker image", 60),
        ("Pushing to registry", 80),
        ("Updating configurations", 100)
    ]
    
    for stage, total_progress in stages:
        progress.update(task_id, completed=total_progress, description=f"{stage} for {service}...")
        await asyncio.sleep(0.5)  # Simulate work
    
    progress.update(task_id, completed=100, description=f"✅ {service} built successfully")
    return f"{service} built successfully"

# Example 2: Enhanced deployment with real-time monitoring
@typer.command()
def enhanced_deploy(
    yaml_file: str = typer.Option(None, "--file", "-f", help="YAML file to deploy"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Watch deployment progress"),
    timeout: int = typer.Option(300, "--timeout", "-t", help="Deployment timeout in seconds")
):
    """
    Enhanced deployment with real-time monitoring
    """
    asyncio.run(_enhanced_deploy_implementation(yaml_file, watch, timeout))

async def _enhanced_deploy_implementation(yaml_file: str, watch: bool, timeout: int):
    """Implementation of enhanced deployment"""
    
    # If no file specified, show file selector
    if not yaml_file:
        yaml_file = _interactive_file_selector()
    
    if not yaml_file:
        console.print("❌ No deployment file selected", style="bold red")
        return
    
    console.print(Panel(f"Deploying: [bold]{yaml_file}[/bold]", title="Deployment", style="blue"))
    
    with Progress(console=console) as progress:
        deploy_task = progress.add_task("Deploying resources...", total=100)
        
        # Simulate deployment stages
        stages = [
            ("Validating YAML", 20),
            ("Creating/updating resources", 60),
            ("Waiting for rollout", 90),
            ("Verifying deployment", 100)
        ]
        
        for stage, total_progress in stages:
            progress.update(deploy_task, completed=total_progress, description=stage)
            await asyncio.sleep(1)
        
        console.print("✅ Deployment completed successfully!", style="bold green")
        
        if watch:
            await _watch_deployment_status()

def _interactive_file_selector() -> str:
    """Interactive file selector for deployment files"""
    services_dir = Path(".okik/services/k8")
    
    if not services_dir.exists():
        console.print("❌ No services directory found", style="bold red")
        return ""
    
    yaml_files = list(services_dir.glob("*.yaml")) + list(services_dir.glob("*.yml"))
    
    if not yaml_files:
        console.print("❌ No YAML files found in services directory", style="bold red")
        return ""
    
    # Use Rich to display options
    table = Table(title="Available Deployment Files")
    table.add_column("Index", style="cyan", width=6)
    table.add_column("File", style="green")
    table.add_column("Size", style="blue")
    
    for i, file in enumerate(yaml_files, 1):
        size = f"{file.stat().st_size} bytes"
        table.add_row(str(i), file.name, size)
    
    console.print(table)
    
    try:
        choice = int(input("\nSelect file (number): ")) - 1
        if 0 <= choice < len(yaml_files):
            return str(yaml_files[choice])
    except (ValueError, IndexError):
        pass
    
    return ""

async def _watch_deployment_status():
    """Watch deployment status in real-time"""
    console.print("\n👀 Watching deployment status (Press Ctrl+C to stop)...", style="bold yellow")
    
    try:
        with Progress(console=console) as progress:
            status_task = progress.add_task("Monitoring...", total=None)
            
            for i in range(20):  # Monitor for 20 iterations
                # Simulate getting status
                pods_ready = min(i, 3)
                services_ready = 1 if i > 5 else 0
                
                status = f"Pods: {pods_ready}/3 | Services: {services_ready}/1"
                progress.update(status_task, description=f"Status: {status}")
                
                await asyncio.sleep(2)
                
                if pods_ready == 3 and services_ready == 1:
                    console.print("🎉 All resources are ready!", style="bold green")
                    break
    
    except KeyboardInterrupt:
        console.print("\n⏹️  Monitoring stopped", style="bold yellow")

# Example 3: Enhanced status with live updates
@typer.command()
def live_status(
    namespace: str = typer.Option("default", "--namespace", "-n"),
    refresh_interval: int = typer.Option(5, "--interval", "-i", help="Refresh interval in seconds"),
    watch: bool = typer.Option(True, "--watch", "-w", help="Enable live updates")
):
    """
    Display live status of deployments and services
    """
    if watch:
        asyncio.run(_live_status_implementation(namespace, refresh_interval))
    else:
        _static_status_display(namespace)

async def _live_status_implementation(namespace: str, refresh_interval: int):
    """Implementation of live status monitoring"""
    console.print(f"🔄 Live status monitoring for namespace: [bold]{namespace}[/bold]", style="blue")
    console.print("Press Ctrl+C to stop\n")
    
    try:
        while True:
            # Clear screen and show updated status
            console.clear()
            _display_status_tables(namespace)
            await asyncio.sleep(refresh_interval)
    
    except KeyboardInterrupt:
        console.print("\n⏹️  Status monitoring stopped", style="bold yellow")

def _static_status_display(namespace: str):
    """Display static status"""
    console.print(f"📊 Status for namespace: [bold]{namespace}[/bold]", style="blue")
    _display_status_tables(namespace)

def _display_status_tables(namespace: str):
    """Display status tables for deployments and services"""
    
    # Mock data - in real implementation, fetch from Kubernetes API
    deployments = [
        {"name": "embedder", "replicas": "3/3", "available": "3", "age": "2d"},
        {"name": "mockllm", "replicas": "2/2", "available": "2", "age": "1d"},
        {"name": "api-gateway", "replicas": "1/1", "available": "1", "age": "6h"},
    ]
    
    services = [
        {"name": "embedder", "type": "ClusterIP", "cluster_ip": "10.96.1.100", "ports": "80/TCP"},
        {"name": "mockllm", "type": "ClusterIP", "cluster_ip": "10.96.1.101", "ports": "80/TCP"},
        {"name": "api-gateway", "type": "LoadBalancer", "cluster_ip": "10.96.1.102", "ports": "80:32000/TCP"},
    ]
    
    # Deployments table
    dep_table = Table(title=f"Deployments in {namespace}")
    dep_table.add_column("Name", style="cyan")
    dep_table.add_column("Ready", style="green")
    dep_table.add_column("Available", style="blue")
    dep_table.add_column("Age", style="yellow")
    
    for dep in deployments:
        dep_table.add_row(dep["name"], dep["replicas"], dep["available"], dep["age"])
    
    # Services table
    svc_table = Table(title=f"Services in {namespace}")
    svc_table.add_column("Name", style="cyan")
    svc_table.add_column("Type", style="green")
    svc_table.add_column("Cluster IP", style="blue")
    svc_table.add_column("Ports", style="yellow")
    
    for svc in services:
        svc_table.add_row(svc["name"], svc["type"], svc["cluster_ip"], svc["ports"])
    
    console.print(dep_table)
    console.print()
    console.print(svc_table)
    
    # Resource usage summary
    usage_panel = Panel(
        "CPU: 45% | Memory: 67% | Storage: 23% | Network: 1.2MB/s",
        title="Resource Usage",
        style="green"
    )
    console.print()
    console.print(usage_panel)

# Example 4: Interactive service configuration
@typer.command()
def configure_service(
    service_name: str = typer.Argument(None, help="Service name to configure"),
    interactive: bool = typer.Option(True, "--interactive", "-i", help="Interactive configuration")
):
    """
    Configure service settings interactively
    """
    if interactive:
        _interactive_service_configuration(service_name)
    else:
        console.print("Non-interactive configuration not implemented yet", style="yellow")

def _interactive_service_configuration(service_name: str):
    """Interactive service configuration"""
    
    if not service_name:
        service_name = _prompt_for_service_name()
    
    if not service_name:
        return
    
    console.print(f"\n🛠️  Configuring service: [bold]{service_name}[/bold]", style="blue")
    
    # Configuration options
    config = {}
    
    # Replicas
    try:
        replicas = int(input(f"Number of replicas for {service_name} (default: 1): ") or "1")
        config["replicas"] = replicas
    except ValueError:
        config["replicas"] = 1
    
    # Resource configuration
    console.print("\n📊 Resource Configuration:")
    
    # Memory
    memory = input("Memory limit (e.g., 512Mi, 1Gi) [default: 512Mi]: ") or "512Mi"
    config["memory"] = memory
    
    # CPU
    cpu = input("CPU limit (e.g., 500m, 1) [default: 500m]: ") or "500m"
    config["cpu"] = cpu
    
    # GPU (if needed)
    gpu_needed = input("Requires GPU? (y/n) [default: n]: ").lower().startswith('y')
    if gpu_needed:
        gpu_type = input("GPU type (A100, V100, T4) [default: T4]: ") or "T4"
        gpu_count = int(input("GPU count [default: 1]: ") or "1")
        config["gpu"] = {"type": gpu_type, "count": gpu_count}
    
    # Display configuration summary
    console.print("\n📋 Configuration Summary:", style="bold blue")
    
    summary_table = Table()
    summary_table.add_column("Setting", style="cyan")
    summary_table.add_column("Value", style="green")
    
    summary_table.add_row("Service", service_name)
    summary_table.add_row("Replicas", str(config["replicas"]))
    summary_table.add_row("Memory", config["memory"])
    summary_table.add_row("CPU", config["cpu"])
    
    if "gpu" in config:
        summary_table.add_row("GPU", f"{config['gpu']['count']}x {config['gpu']['type']}")
    
    console.print(summary_table)
    
    # Confirm and save
    confirm = input("\nSave this configuration? (y/n) [default: y]: ").lower()
    if not confirm or confirm.startswith('y'):
        _save_service_configuration(service_name, config)
        console.print("✅ Configuration saved successfully!", style="bold green")
    else:
        console.print("❌ Configuration cancelled", style="bold red")

def _prompt_for_service_name() -> str:
    """Prompt user to select or enter service name"""
    
    # Show existing services
    console.print("📋 Available services:", style="blue")
    
    existing_services = ["embedder", "mockllm", "api-gateway"]  # Mock data
    
    table = Table()
    table.add_column("Index", style="cyan", width=6)
    table.add_column("Service", style="green")
    table.add_column("Status", style="blue")
    
    for i, service in enumerate(existing_services, 1):
        table.add_row(str(i), service, "Running")
    
    console.print(table)
    
    choice = input("\nSelect service by number or enter new name: ")
    
    try:
        index = int(choice) - 1
        if 0 <= index < len(existing_services):
            return existing_services[index]
    except ValueError:
        if choice.strip():
            return choice.strip()
    
    return ""

def _save_service_configuration(service_name: str, config: dict):
    """Save service configuration to file"""
    config_dir = Path(".okik/configs/services")
    config_dir.mkdir(parents=True, exist_ok=True)
    
    config_file = config_dir / f"{service_name}.json"
    
    import json
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)

# Example 5: Dashboard command
@typer.command()
def dashboard():
    """
    Launch the Okik TUI dashboard
    """
    try:
        # In a real implementation, this would import and run the Textual dashboard
        console.print("🚀 Launching Okik Dashboard...", style="bold green")
        console.print("Dashboard would launch here with full TUI interface", style="blue")
        console.print("Features:", style="bold")
        console.print("  • Real-time service monitoring")
        console.print("  • Interactive deployment management")
        console.print("  • Resource usage visualization")
        console.print("  • Log streaming")
        console.print("  • Configuration management")
        
        # Simulate dashboard running
        time.sleep(2)
        console.print("\n✨ Dashboard simulation complete", style="green")
        
    except KeyboardInterrupt:
        console.print("\n⏹️  Dashboard closed", style="bold yellow")

# Example usage in main CLI app
if __name__ == "__main__":
    app = typer.Typer(help="Enhanced Okik CLI with performance improvements")
    
    app.command()(async_build)
    app.command()(enhanced_deploy)
    app.command()(live_status)
    app.command()(configure_service)
    app.command()(dashboard)
    
    app()