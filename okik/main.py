import importlib
import importlib.util
import json
import multiprocessing
import os
import shutil
import subprocess
import sys
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from pathlib import Path
from typing import List, Dict, Any, Optional

import pyfiglet
import questionary
import typer
import uvicorn
import yaml
from art import text2art
from fastapi.routing import APIRoute
from kubernetes import client, config, utils
from kubernetes.client import ApiException
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.prompt import Prompt, Confirm
from rich.spinner import Spinner
from rich.status import Status
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.tree import Tree
from rich.layout import Layout
from rich.align import Align
from rich.box import ROUNDED, DOUBLE
from rich import print as rprint

from okik.consts import ProjectDir
from okik.logger import log_error, log_info, log_start, log_success
from okik.scripts.dockerfiles.dockerfile_gen import create_dockerfile

# Initialize Typer app
typer_app = typer.Typer()
# Initialize Rich console
console = Console()

KUBE_CONFIG_PATH = os.path.expanduser("~/.kube/config")

# Cache for frequently accessed data
@lru_cache(maxsize=128)
def get_cached_config(config_path: str) -> Dict[str, Any]:
    """Cache configuration files to improve performance"""
    with open(config_path, 'r') as f:
        return json.load(f)

def create_fancy_header(text: str, subtitle: str = "") -> Panel:
    """Create a fancy header with ASCII art"""
    ascii_art = pyfiglet.figlet_format(text, font="slant")
    content = Text(ascii_art, style="bold cyan")
    if subtitle:
        content.append(f"\n{subtitle}", style="italic yellow")
    return Panel(content, box=DOUBLE, border_style="bright_blue")

def create_progress_bar() -> Progress:
    """Create a customized progress bar"""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console
    )

@typer_app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """
    Okik CLI: Simplify. Deploy. Scale.
    """
    if ctx.invoked_subcommand is None:
        # Enhanced welcome screen
        layout = Layout()
        layout.split_column(
            Layout(create_fancy_header("Okik", "Simplify. Deploy. Scale."), size=12),
            Layout(Panel(
                "[bold green]Welcome to Okik CLI![/bold green]\n\n"
                "Available commands:\n"
                "  • [cyan]init[/cyan]     - Initialize a new project\n"
                "  • [cyan]build[/cyan]    - Build Docker image\n"
                "  • [cyan]server[/cyan]   - Run development server\n"
                "  • [cyan]deploy[/cyan]   - Deploy to Kubernetes\n"
                "  • [cyan]routes[/cyan]   - Show API routes\n"
                "  • [cyan]serve[/cyan]    - Serve HuggingFace models\n\n"
                "[dim]Type 'okik --help' for more commands.[/dim]",
                box=ROUNDED,
                border_style="green"
            ))
        )
        console.print(layout)

@typer_app.command()
def init():
    """
    Initialize the project with the required files and directories.
    """
    tasks = [
        {"description": "Creating services directory", "status": "pending"},
        {"description": "Creating cache directory", "status": "pending"},
        {"description": "Creating docker directory", "status": "pending"},
        {"description": "Created Dockerfile", "status": "pending"},
        {"description": "Creating credentials file with token", "status": "pending"},
        {"description": "Create configs.json file in config directory", "status": "pending"}
    ]

    docker_dir = ProjectDir.DOCKER_DIR.value
    config_dir = ProjectDir.CONFIG_DIR.value
    
    # Use progress bar for initialization
    with create_progress_bar() as progress:
        task_id = progress.add_task("[cyan]Initializing project...", total=len(tasks))
        
        # Create directories in parallel
        folders_list = [dir.value for dir in ProjectDir]
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(os.makedirs, folder, exist_ok=True): i 
                      for i, folder in enumerate(folders_list[:3])}
            
            for future in as_completed(futures):
                idx = futures[future]
                tasks[idx]["status"] = "completed"
                progress.update(task_id, advance=1)

        # Use dockerfile_gen to generate the Dockerfile
        try:
            create_dockerfile(docker_dir)
            tasks[3]["status"] = "completed"
            progress.update(task_id, advance=1)
        except Exception as e:
            tasks[3]["status"] = "failed"
            console.print(f"Failed to generate Dockerfile: {str(e)}", style="bold red")
            raise typer.Exit(code=1)

        # Create okik folder in home directory and add credentials.json with token
        home_dir = os.path.expanduser("~")
        okik_home_dir = os.path.join(home_dir, "okik")
        os.makedirs(okik_home_dir, exist_ok=True)
        credentials_path = os.path.join(okik_home_dir, "credentials.json")

        if not os.path.exists(credentials_path):
            token = str(uuid.uuid4())
            credentials = {"token": token}
            with open(credentials_path, "w") as credentials_file:
                json.dump(credentials, credentials_file)
            tasks[4]["status"] = "completed"
        else:
            tasks[4]["status"] = "skipped"
        progress.update(task_id, advance=1)

        # Create configs.json in cache directory if not exists
        configs_path = os.path.join(config_dir, "configs.json")
        if not os.path.exists(configs_path):
            with open(configs_path, "w") as configs_file:
                json.dump({'image_name': '', 'app_name': ''}, configs_file)
            tasks[5]["status"] = "completed"
        else:
            tasks[5]["status"] = "skipped"
        progress.update(task_id, advance=1)

    # Display task statuses in a nice table
    table = Table(title="Initialization Results", box=ROUNDED)
    table.add_column("Task", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center")
    
    status_styles = {
        "completed": "[bold green]✓ Completed[/bold green]",
        "failed": "[bold red]✗ Failed[/bold red]",
        "skipped": "[bold yellow]⚠ Skipped[/bold yellow]",
        "pending": "[bold]○ Pending[/bold]"
    }
    
    for task in tasks:
        table.add_row(task['description'], status_styles[task['status']])
    
    console.print(table)

@typer_app.command()
def build(
    entry_point: str = typer.Option(
        "main.py", "--entry_point", "-e", help="Entry point file"
    ),
    docker_file: str = typer.Option(
        ".okik/docker/Dockerfile", "--docker-file", "-d", help="Dockerfile name",
    ),
    app_name: str = typer.Option(
        None, "--app-name", "-a", help="Name of the Docker image"
    ),
    cloud_prefix: str = typer.Option(
        None, "--cloud-prefix", "-c", help="Prefix for the cloud service"
    ),
    registry_id: str = typer.Option(None, "--registry-id", "-r", help="Registry ID"),
    tag: str = typer.Option("latest", "--tag", "-t", help="Tag for the Docker image"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Print outputs from Docker"),
    force_build: bool = typer.Option(False, "--force-build", "-f", help="Force rebuild of the Docker image"),
):
    """
    Build the Docker image for your app
    """
    start_time = time.time()
    steps = []
    temp_dir = ProjectDir.TEMP_DIR.value
    config_dir = ProjectDir.CONFIG_DIR.value

    # Display arguments in a nice table
    args_table = Table(title="Build Configuration", box=ROUNDED, title_style="bold cyan")
    args_table.add_column("Parameter", style="cyan")
    args_table.add_column("Value", style="yellow")
    
    arguments = {
        "Entry Point": entry_point,
        "Docker File": docker_file,
        "App Name": app_name or "[dim]auto-generated[/dim]",
        "Cloud Prefix": cloud_prefix or "[dim]none[/dim]",
        "Registry ID": registry_id or "[dim]none[/dim]",
        "Tag": tag,
        "Verbose": "Yes" if verbose else "No",
        "Force Build": "Yes" if force_build else "No"
    }
    
    for key, value in arguments.items():
        args_table.add_row(key, str(value))
    
    console.print(args_table)
    console.print()

    # Create progress tracker
    with create_progress_bar() as progress:
        # Pre-build checks
        check_task = progress.add_task("[cyan]Running pre-build checks...", total=5)
        
        # Check entry point
        if not os.path.isfile(entry_point):
            progress.stop()
            console.print(Panel(
                f"[bold red]Error:[/bold red] Entry point file '{entry_point}' not found.",
                box=ROUNDED,
                border_style="red"
            ))
            raise typer.Exit(code=1)
        progress.update(check_task, advance=1)
        steps.append("✓ Checked entry point file")

        # Create temp directory
        os.makedirs(temp_dir, exist_ok=True)
        progress.update(check_task, advance=1)
        steps.append("✓ Created temporary directory")

        # Copy files in parallel
        with ThreadPoolExecutor(max_workers=3) as executor:
            copy_futures = []
            
            # Copy entry point
            copy_futures.append(
                executor.submit(shutil.copy, entry_point, 
                              os.path.join(temp_dir, os.path.basename(entry_point)))
            )
            
            # Check and copy Dockerfile
            if not os.path.isfile(docker_file):
                progress.stop()
                console.print(Panel(
                    f"[bold red]Error:[/bold red] Dockerfile '{docker_file}' not found.",
                    box=ROUNDED,
                    border_style="red"
                ))
                raise typer.Exit(code=1)
            
            copy_futures.append(
                executor.submit(shutil.copy, docker_file, 
                              os.path.join(temp_dir, os.path.basename(docker_file)))
            )
            
            # Copy requirements.txt if exists
            if os.path.exists("requirements.txt"):
                copy_futures.append(
                    executor.submit(shutil.copy, "requirements.txt", 
                                  os.path.join(temp_dir, "requirements.txt"))
                )
            
            for future in as_completed(copy_futures):
                progress.update(check_task, advance=1)
        
        steps.append("✓ Copied necessary files")

        # Handle image configuration
        os.makedirs(config_dir, exist_ok=True)
        image_json_path = os.path.join(config_dir, "configs.json")

        if force_build and os.path.exists(image_json_path):
            os.remove(image_json_path)
            console.print("[yellow]⚠ Force build: Cleared existing configuration[/yellow]")
            steps.append("✓ Force build option applied")
        progress.update(check_task, advance=1)

        # Determine image name
        existing_app_name = None
        if os.path.exists(image_json_path):
            try:
                json_content = get_cached_config(image_json_path)
                existing_app_name = json_content.get("image_name")
                if existing_app_name:
                    console.print(f"[blue]ℹ Using existing image: {existing_app_name}[/blue]")
            except (json.JSONDecodeError, KeyError) as e:
                console.print(f"[yellow]⚠ Warning: {e}[/yellow]")

        if existing_app_name and not force_build:
            docker_image_name = existing_app_name
            steps.append(f"✓ Using existing app name: {docker_image_name}")
        else:
            if not app_name:
                app_name = f"app-{uuid.uuid4()}"
                steps.append(f"✓ Generated app name: {app_name}")
            
            if cloud_prefix:
                docker_image_name = f"{cloud_prefix}/{registry_id}/{app_name}:{tag}"
            else:
                docker_image_name = f"{registry_id}/{app_name}:{tag}" if registry_id else f"{app_name}:{tag}"
            
            steps.append(f"✓ Formatted image name: {docker_image_name}")

            # Save configuration
            with open(image_json_path, "w") as json_file:
                json.dump({"image_name": docker_image_name, "app_name": app_name}, json_file)
            steps.append("✓ Saved configuration")
        
        progress.update(check_task, advance=1)

    # Build Docker image with enhanced UI
    build_command = f"docker build {'--no-cache' if force_build else ''} -t {docker_image_name} -f {docker_file} {temp_dir}".strip()
    
    console.print(Panel(
        f"[bold]Building Docker image:[/bold] {docker_image_name}",
        box=ROUNDED,
        border_style="cyan"
    ))
    
    # Create layout for build output
    layout = Layout()
    layout.split_column(
        Layout(name="status", size=3),
        Layout(name="output", ratio=1)
    )
    
    build_success = False
    log_lines = []
    current_step = "Initializing..."
    
    # Use Rich Live display for real-time updates
    with Live(layout, refresh_per_second=4, console=console) as live:
        # Update status
        layout["status"].update(Panel(
            f"[bold cyan]Current step:[/bold cyan] {current_step}",
            box=ROUNDED
        ))
        
        # Start build process
        process = subprocess.Popen(
            build_command, 
            shell=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True, 
            bufsize=1, 
            universal_newlines=True
        )
        
        # Process output
        for line in iter(process.stdout.readline, ''):
            line = line.strip()
            if not line:
                continue
                
            # Update current step if it's a Docker step
            if line.startswith("Step "):
                current_step = line
                layout["status"].update(Panel(
                    f"[bold cyan]Current step:[/bold cyan] {current_step}",
                    box=ROUNDED
                ))
                steps.append(line)
            
            # Add to log
            if verbose or line.startswith("Step ") or "-->" in line or "error" in line.lower():
                log_lines.append(line)
                # Keep only last 20 lines for display
                display_lines = log_lines[-20:]
                
                # Create syntax highlighted output
                output_text = "\n".join(display_lines)
                layout["output"].update(Panel(
                    Syntax(output_text, "dockerfile", theme="monokai", line_numbers=False),
                    title="Build Output",
                    box=ROUNDED,
                    border_style="green" if "error" not in output_text.lower() else "red"
                ))
        
        process.stdout.close()
        return_code = process.wait()
        build_success = return_code == 0

    # Cleanup
    console.print("\n[cyan]Cleaning up temporary files...[/cyan]")
    shutil.rmtree(temp_dir)
    steps.append("✓ Cleaned up temporary directory")

    # Display results
    end_time = time.time()
    elapsed_time = end_time - start_time

    if build_success:
        # Success panel
        console.print(Panel(
            f"[bold green]✓ Build Successful![/bold green]\n\n"
            f"[cyan]Image:[/cyan] {docker_image_name}\n"
            f"[cyan]Time:[/cyan] {elapsed_time:.2f} seconds\n\n"
            f"[dim]Run with --verbose flag for detailed output[/dim]",
            title="Build Complete",
            box=DOUBLE,
            border_style="green"
        ))
        log_success(f"Docker image '{docker_image_name}' built successfully")
    else:
        # Failure panel
        console.print(Panel(
            f"[bold red]✗ Build Failed![/bold red]\n\n"
            f"[cyan]Image:[/cyan] {docker_image_name}\n"
            f"[cyan]Time:[/cyan] {elapsed_time:.2f} seconds\n\n"
            f"[yellow]Check the output above for errors[/yellow]\n"
            f"[dim]Run with --verbose flag for detailed output[/dim]",
            title="Build Failed",
            box=DOUBLE,
            border_style="red"
        ))
        log_error(f"Docker image build failed")
        raise typer.Exit(code=1)

@typer_app.command()
def server(
    entry_point: str = typer.Option(
        "main.py", "--entry-point", "-e", help="Entry point file"
    ),
    reload: bool = typer.Option(
        False, "--reload", "-r", help="Enable auto-reload for the server"
    ),
    host: str = typer.Option(
        "0.0.0.0", "--host", "-h", help="Host address for the server"
    ),
    port: int = typer.Option(3000, "--port", "-p", help="Port for the server"),
    dev: bool = typer.Option(False, "--dev", "-d", help="Run in development mode"),
    log_level: str = typer.Option("info", "--log-level", "-l", help="Log level"),
):
    """
    Serve the app in development or production mode.
    """
    # Create fancy header
    mode = "Development" if dev else "Production"
    mode_color = "yellow" if dev else "green"
    
    console.print(create_fancy_header("Okik Server", f"{mode} Mode"))
    
    # Check if the entry point file exists
    if not os.path.isfile(entry_point):
        console.print(Panel(
            f"[bold red]Error:[/bold red] Entry point file '{entry_point}' not found.",
            box=ROUNDED,
            border_style="red"
        ))
        raise typer.Exit(code=1)

    # Add the current directory to sys.path
    sys.path.insert(0, os.getcwd())

    # Try to import the module with progress indicator
    with console.status("[cyan]Loading application...[/cyan]"):
        try:
            module_name = os.path.splitext(os.path.basename(entry_point))[0]
            spec = importlib.util.spec_from_file_location(module_name, entry_point)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
        except Exception as e:
            console.print(Panel(
                f"[bold red]Import Error:[/bold red]\n{traceback.format_exc()}",
                title="Failed to import module",
                box=ROUNDED,
                border_style="red"
            ))
            raise typer.Exit(code=1)

    # Check if 'app' is defined in the module
    if not hasattr(module, 'app'):
        console.print(Panel(
            f"[bold red]Error:[/bold red] No 'app' object found in {entry_point}.\n"
            "Make sure you have defined an ASGI application named 'app'.",
            box=ROUNDED,
            border_style="red"
        ))
        raise typer.Exit(code=1)

    # Determine the number of workers
    workers = 1 if dev else min(multiprocessing.cpu_count(), 8)

    # Create server configuration table
    config_table = Table(title="Server Configuration", box=ROUNDED)
    config_table.add_column("Setting", style="cyan")
    config_table.add_column("Value", style="yellow")
    
    config_items = [
        ("Host", host),
        ("Port", str(port)),
        ("Entry Point", entry_point),
        ("Mode", mode),
        ("Workers", str(workers)),
        ("Auto-reload", "Enabled" if reload and dev else "Disabled"),
        ("Log Level", log_level.upper()),
    ]
    
    for key, value in config_items:
        config_table.add_row(key, value)
    
    console.print(config_table)
    console.print()

    # Create server status panel
    server_url = f"http://{host}:{port}"
    docs_url = f"{server_url}/docs"
    
    status_panel = Panel(
        f"[bold green]✓ Server Starting[/bold green]\n\n"
        f"[cyan]Main URL:[/cyan] {server_url}\n"
        f"[cyan]API Docs:[/cyan] {docs_url}\n"
        f"[cyan]Health Check:[/cyan] {server_url}/health\n\n"
        f"[yellow]Press CTRL+C to stop the server[/yellow]",
        title=f"Okik Server - {mode} Mode",
        box=DOUBLE,
        border_style=mode_color
    )
    console.print(status_panel)

    # Prepare the uvicorn configuration
    config = uvicorn.Config(
        f"{module_name}:app",
        host=host,
        port=port,
        reload=reload and dev,
        workers=workers,
        log_level=log_level,
        access_log=False,  # We'll handle our own logging
    )

    # Create the server
    server = uvicorn.Server(config)

    # Custom logging handler for better TUI
    class TUILogHandler:
        def __init__(self):
            self.request_count = 0
            self.error_count = 0
            self.start_time = time.time()
            
        def log_request(self, scope, info):
            self.request_count += 1
            method = scope.get("method", "?")
            path = scope.get("path", "?")
            status = info.get("status", "?")
            
            # Color code based on status
            if status < 300:
                status_color = "green"
            elif status < 400:
                status_color = "yellow"
            else:
                status_color = "red"
                self.error_count += 1
            
            # Log with nice formatting
            console.print(
                f"[dim]{time.strftime('%H:%M:%S')}[/dim] "
                f"[{status_color}]{status}[/{status_color}] "
                f"[cyan]{method}[/cyan] {path}"
            )

    # Start the server with enhanced logging
    log_handler = TUILogHandler()
    
    try:
        # Add startup message
        console.print(
            f"\n[bold green]🚀 Server is running![/bold green]\n"
            f"[dim]Listening on {server_url}[/dim]\n"
        )
        
        # Run the server
        server.run()
        
    except KeyboardInterrupt:
        # Show shutdown statistics
        uptime = time.time() - log_handler.start_time
        hours, remainder = divmod(uptime, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        stats_panel = Panel(
            f"[bold]Server Statistics[/bold]\n\n"
            f"[cyan]Uptime:[/cyan] {int(hours)}h {int(minutes)}m {int(seconds)}s\n"
            f"[cyan]Total Requests:[/cyan] {log_handler.request_count}\n"
            f"[cyan]Errors:[/cyan] {log_handler.error_count}\n",
            title="Session Summary",
            box=ROUNDED,
            border_style="blue"
        )
        console.print("\n")
        console.print(stats_panel)
        console.print("[yellow]Server stopped gracefully.[/yellow]")
        
    except Exception as e:
        console.print(Panel(
            f"[bold red]Server Error:[/bold red]\n{str(e)}",
            box=ROUNDED,
            border_style="red"
        ))
        raise typer.Exit(code=1)

@typer_app.command()
def routes(
    entry_point: str = typer.Option(
        "main.py", "--entry-point", "-e", help="Entry point file"
    ),
):
    """
    Creates routes, services, and other resources defined in the entry point.
    """
    # Create header
    console.print(create_fancy_header("Route Explorer", "Analyze your API endpoints"))
    
    if not os.path.isfile(entry_point):
        console.print(Panel(
            f"[bold red]Error:[/bold red] Entry point file '{entry_point}' not found.",
            box=ROUNDED,
            border_style="red"
        ))
        raise typer.Exit(code=1)

    module_name = os.path.splitext(entry_point)[0]

    with console.status("[cyan]Loading application routes...[/cyan]"):
        try:
            spec = importlib.util.spec_from_file_location(module_name, entry_point)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            app = getattr(module, "app", None)
            if app is None:
                console.print(Panel(
                    f"[bold red]Error:[/bold red] No 'app' instance found in '{entry_point}'.",
                    box=ROUNDED,
                    border_style="red"
                ))
                raise typer.Exit(code=1)

            # Analyze routes
            routes_by_base_path = {}
            total_routes = 0
            methods_count = {"GET": 0, "POST": 0, "PUT": 0, "DELETE": 0, "PATCH": 0}
            
            for route in app.routes:
                if isinstance(route, APIRoute):
                    total_routes += 1
                    base_path = route.path.split("/")[1] if "/" in route.path else "root"
                    
                    if base_path not in routes_by_base_path:
                        routes_by_base_path[base_path] = []
                    
                    routes_by_base_path[base_path].append({
                        "path": route.path,
                        "methods": list(route.methods),
                        "name": route.name,
                        "endpoint": route.endpoint.__name__ if hasattr(route.endpoint, '__name__') else str(route.endpoint)
                    })
                    
                    # Count methods
                    for method in route.methods:
                        if method in methods_count:
                            methods_count[method] += 1

    # Display route statistics
    stats_table = Table(title="Route Statistics", box=ROUNDED)
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Value", style="yellow")
    
    stats_table.add_row("Total Routes", str(total_routes))
    stats_table.add_row("Base Paths", str(len(routes_by_base_path)))
    for method, count in methods_count.items():
        if count > 0:
            stats_table.add_row(f"{method} Endpoints", str(count))
    
    console.print(stats_table)
    console.print()

    # Build enhanced route tree
    routes_tree = Tree(
        f"[bold cyan]{entry_point}[/bold cyan] - API Routes",
        guide_style="cyan"
    )
    
    # Sort base paths for better organization
    for base_path in sorted(routes_by_base_path.keys()):
        base_branch = routes_tree.add(f"[bold yellow]/{base_path}/[/bold yellow]")
        
        # Sort routes within each base path
        sorted_routes = sorted(routes_by_base_path[base_path], key=lambda x: x['path'])
        
        for route_info in sorted_routes:
            # Create method badges
            method_badges = " ".join([
                f"[bold white on {_get_method_color(m)}] {m} [/]" 
                for m in route_info['methods']
            ])
            
            # Add route with enhanced formatting
            route_display = f"{method_badges} [green]{route_info['path']}[/green]"
            
            # Add endpoint function name if available
            if route_info['endpoint'] != route_info['name']:
                route_display += f" [dim]→ {route_info['endpoint']}()[/dim]"
            
            base_branch.add(route_display)
    
    console.print(routes_tree)
    
    # Add helpful tips
    console.print(Panel(
        "[cyan]💡 Tips:[/cyan]\n"
        "• Use [yellow]okik server[/yellow] to start the development server\n"
        "• Visit [green]/docs[/green] for interactive API documentation\n"
        "• Use [yellow]okik build[/yellow] to containerize your application",
        title="Next Steps",
        box=ROUNDED,
        border_style="blue"
    ))

def _get_method_color(method: str) -> str:
    """Get color for HTTP method badges"""
    colors = {
        "GET": "green",
        "POST": "blue",
        "PUT": "yellow",
        "DELETE": "red",
        "PATCH": "magenta"
    }
    return colors.get(method, "white")

def delete_existing_resources(yaml_documents):
    apps_v1 = client.AppsV1Api()
    core_v1 = client.CoreV1Api()
    autoscaling_v1 = client.AutoscalingV1Api()

    for yaml_doc in yaml_documents:
        kind = yaml_doc.get('kind')
        metadata = yaml_doc.get('metadata', {})
        name = metadata.get('name')

        if not kind or not name:
            continue

        try:
            if kind == 'Deployment':
                apps_v1.delete_namespaced_deployment(name, namespace="default")
            elif kind == 'Service':
                core_v1.delete_namespaced_service(name, namespace="default")
            elif kind == 'HorizontalPodAutoscaler':
                autoscaling_v1.delete_namespaced_horizontal_pod_autoscaler(name, namespace="default")
            console.print(f"Deleted existing {kind} '{name}'", style="bold yellow")
        except ApiException as e:
            if e.status != 404:
                console.print(f"Failed to delete existing {kind} '{name}': {e}", style="bold red")

@typer_app.command(name="deploy")
def deploy(
    entry_point: str = typer.Option(
        "main.py", "--entry-point", "-e", help="Entry point file"
    )
):
    """
    Deploy the application to a Kubernetes cluster.
    """
    console.print(create_fancy_header("Deploy", "Deploy to Kubernetes"))
    
    services_dir = os.path.join(ProjectDir.SERVICES_DIR.value, 'k8')
    
    # Check if services directory exists
    if not os.path.exists(services_dir):
        console.print(Panel(
            "[bold red]Error:[/bold red] Services directory not found.\n"
            "Run [yellow]okik init[/yellow] first to initialize the project.",
            box=ROUNDED,
            border_style="red"
        ))
        raise typer.Exit(code=1)
    
    yaml_files = [f for f in os.listdir(services_dir) if f.endswith('.yaml') or f.endswith('.yml')]
    if not yaml_files:
        console.print(Panel(
            "[bold red]Error:[/bold red] No YAML configuration files found.\n"
            "Make sure you have run [yellow]okik build[/yellow] to generate deployment configs.",
            box=ROUNDED,
            border_style="red"
        ))
        raise typer.Exit(code=1)

    # Enhanced file selection with preview
    console.print("[cyan]Available deployment configurations:[/cyan]\n")
    
    # Create a table showing available files with metadata
    files_table = Table(box=ROUNDED)
    files_table.add_column("#", style="dim")
    files_table.add_column("File", style="cyan")
    files_table.add_column("Size", style="yellow")
    files_table.add_column("Modified", style="green")
    
    for idx, file in enumerate(yaml_files, 1):
        file_path = os.path.join(services_dir, file)
        file_stat = os.stat(file_path)
        size = f"{file_stat.st_size / 1024:.1f} KB"
        modified = time.strftime("%Y-%m-%d %H:%M", time.localtime(file_stat.st_mtime))
        files_table.add_row(str(idx), file, size, modified)
    
    console.print(files_table)
    console.print()

    # Use enhanced selection
    selected_file = questionary.select(
        "Select a YAML file to deploy:",
        choices=yaml_files,
        use_indicator=True,
        use_arrow_keys=True,
        instruction="(Use arrow keys to navigate, Enter to select)",
        style=questionary.Style([
            ('question', 'fg:cyan bold'),
            ('pointer', 'fg:cyan bold'),
            ('highlighted', 'fg:cyan bold'),
            ('selected', 'fg:green bold'),
        ])
    ).ask()

    if not selected_file:
        console.print("[yellow]Deployment cancelled.[/yellow]")
        raise typer.Exit()

    yaml_path = os.path.join(services_dir, selected_file)
    
    # Parse and display YAML with progress
    with console.status("[cyan]Parsing YAML configuration...[/cyan]"):
        try:
            with open(yaml_path, 'r') as file:
                yaml_documents = list(yaml.safe_load_all(file))
        except yaml.YAMLError as exc:
            console.print(Panel(
                f"[bold red]YAML Error:[/bold red] {exc}",
                box=ROUNDED,
                border_style="red"
            ))
            raise typer.Exit(code=1)
    
    # Display YAML documents with enhanced formatting
    console.print(f"\n[cyan]Configuration: {selected_file}[/cyan]")
    console.print(f"[dim]Documents: {len(yaml_documents)}[/dim]\n")
    
    for index, yaml_content in enumerate(yaml_documents):
        # Extract key information
        kind = yaml_content.get('kind', 'Unknown')
        name = yaml_content.get('metadata', {}).get('name', 'Unnamed')
        
        # Create a summary panel
        yaml_str = yaml.dump(yaml_content, default_flow_style=False)
        yaml_syntax = Syntax(
            yaml_str[:500] + "..." if len(yaml_str) > 500 else yaml_str,
            "yaml",
            theme="monokai",
            background_color="default"
        )
        
        panel = Panel(
            yaml_syntax,
            title=f"[{index + 1}/{len(yaml_documents)}] {kind}: {name}",
            border_style="blue",
            box=ROUNDED
        )
        console.print(panel)

    # Confirmation with enhanced prompt
    console.print()
    if not Confirm.ask(
        "[bold yellow]Do you want to deploy these resources?[/bold yellow]",
        default=False
    ):
        console.print("[yellow]Deployment cancelled by user.[/yellow]")
        raise typer.Exit()

    # Load Kubernetes configuration with progress
    with console.status("[cyan]Loading Kubernetes configuration...[/cyan]"):
        try:
            config.load_kube_config()
            k8s_client = client.ApiClient()
            v1 = client.CoreV1Api()
            console.print("[green]✓ Kubernetes configuration loaded[/green]")
        except Exception as e:
            console.print(Panel(
                f"[bold red]Kubernetes Error:[/bold red] {e}\n\n"
                "Make sure you have:\n"
                "• kubectl installed\n"
                "• Valid kubeconfig file\n"
                "• Access to the cluster",
                box=ROUNDED,
                border_style="red"
            ))
            raise typer.Exit(code=1)

    # Validate credentials
    credentials_path = os.path.expanduser('~/okik/credentials.json')
    if not os.path.exists(credentials_path):
        console.print(Panel(
            "[bold red]Error:[/bold red] Credentials file not found.\n"
            "Run [yellow]okik init[/yellow] to initialize credentials.",
            box=ROUNDED,
            border_style="red"
        ))
        raise typer.Exit(code=1)

    # Deploy with progress tracking
    with create_progress_bar() as progress:
        # Delete existing resources
        delete_task = progress.add_task(
            "[yellow]Cleaning up existing resources...[/yellow]",
            total=len(yaml_documents)
        )
        
        for yaml_doc in yaml_documents:
            delete_existing_resources([yaml_doc])
            progress.update(delete_task, advance=1)
        
        # Apply new resources
        apply_task = progress.add_task(
            "[green]Applying new resources...[/green]",
            total=len(yaml_documents)
        )
        
        try:
            for yaml_doc in yaml_documents:
                utils.create_from_dict(k8s_client, yaml_doc, namespace="default")
                progress.update(apply_task, advance=1)
        except ApiException as e:
            progress.stop()
            console.print(Panel(
                f"[bold red]Deployment Error:[/bold red] {e}",
                box=ROUNDED,
                border_style="red"
            ))
            raise typer.Exit(code=1)

    # Wait for deployment with animated spinner
    with console.status("[cyan]Waiting for pods to be ready...[/cyan]", spinner="dots"):
        time.sleep(5)  # Give pods time to start

    # Display deployment results
    console.print("\n[bold green]✓ Deployment completed successfully![/bold green]\n")

    # Retrieve and display services with enhanced formatting
    try:
        services = v1.list_namespaced_service(namespace="default")
        if services.items:
            service_table = Table(title="Deployed Services", box=ROUNDED)
            service_table.add_column("Service", style="cyan")
            service_table.add_column("Type", style="yellow")
            service_table.add_column("Cluster IP", style="green")
            service_table.add_column("Ports", style="blue")
            
            for service in services.items:
                ports = ", ".join([f"{p.port}:{p.target_port}" for p in service.spec.ports])
                service_table.add_row(
                    service.metadata.name,
                    service.spec.type,
                    service.spec.cluster_ip or "None",
                    ports
                )
            
            console.print(service_table)
            
            # Add access instructions
            console.print(Panel(
                "[cyan]To access your services:[/cyan]\n\n"
                "• [yellow]Minikube:[/yellow] minikube service <service-name>\n"
                "• [yellow]Port Forward:[/yellow] kubectl port-forward service/<service-name> <local-port>:<service-port>\n"
                "• [yellow]Get Pods:[/yellow] kubectl get pods\n"
                "• [yellow]View Logs:[/yellow] kubectl logs <pod-name>",
                title="Next Steps",
                box=ROUNDED,
                border_style="blue"
            ))
            
    except ApiException as e:
        console.print(f"[yellow]Warning: Could not retrieve services: {e}[/yellow]")

@typer_app.command(name="get")
def get_resources(resource: str):
    """
    Get deployments or services in the default namespace.
    """
    console.print(create_fancy_header("Resources", f"Kubernetes {resource.capitalize()}"))
    
    # Load Kubernetes configuration with progress
    with console.status("[cyan]Loading Kubernetes configuration...[/cyan]"):
        try:
            config.load_kube_config()
            console.print("[green]✓ Kubernetes configuration loaded[/green]\n")
        except Exception as e:
            console.print(Panel(
                f"[bold red]Kubernetes Error:[/bold red] {e}\n\n"
                "Make sure you have:\n"
                "• kubectl installed\n"
                "• Valid kubeconfig file\n"
                "• Access to the cluster",
                box=ROUNDED,
                border_style="red"
            ))
            raise typer.Exit(code=1)

    if resource.lower() in ["deployment", "deployments", "deploy"]:
        get_deployments()
    elif resource.lower() in ["service", "services", "svc"]:
        get_services()
    else:
        console.print(Panel(
            f"[bold red]Error:[/bold red] Unsupported resource type: '{resource}'\n\n"
            "Supported resources:\n"
            "• deployments (or deploy)\n"
            "• services (or svc)",
            box=ROUNDED,
            border_style="red"
        ))
        raise typer.Exit(code=1)

def get_deployments():
    apps_v1 = client.AppsV1Api()
    
    with console.status("[cyan]Fetching deployments...[/cyan]"):
        try:
            deployments = apps_v1.list_namespaced_deployment(namespace="default")
        except client.exceptions.ApiException as e:
            console.print(Panel(
                f"[bold red]API Error:[/bold red] {e}",
                box=ROUNDED,
                border_style="red"
            ))
            raise typer.Exit(code=1)
    
    if not deployments.items:
        console.print(Panel(
            "[yellow]No deployments found in the default namespace.[/yellow]\n\n"
            "Deploy your application using:\n"
            "[cyan]okik deploy[/cyan]",
            box=ROUNDED,
            border_style="yellow"
        ))
        return

    # Create enhanced table
    table = Table(
        title="Kubernetes Deployments",
        box=ROUNDED,
        title_style="bold cyan",
        show_lines=True
    )
    table.add_column("Name", justify="left", style="cyan", no_wrap=True)
    table.add_column("Ready", justify="center", style="green")
    table.add_column("Up-to-date", justify="center", style="blue")
    table.add_column("Available", justify="center", style="magenta")
    table.add_column("Age", justify="right", style="yellow")
    table.add_column("Status", justify="center")

    for deployment in deployments.items:
        # Calculate age
        creation_time = deployment.metadata.creation_timestamp
        age = time.time() - creation_time.timestamp()
        age_str = _format_age(age)
        
        # Determine status
        ready_replicas = deployment.status.ready_replicas or 0
        desired_replicas = deployment.spec.replicas or 0
        
        if ready_replicas == desired_replicas and ready_replicas > 0:
            status = "[green]✓ Running[/green]"
        elif ready_replicas < desired_replicas:
            status = "[yellow]⚠ Scaling[/yellow]"
        else:
            status = "[red]✗ Not Ready[/red]"
        
        table.add_row(
            deployment.metadata.name,
            f"{ready_replicas}/{desired_replicas}",
            str(deployment.status.updated_replicas or 0),
            str(deployment.status.available_replicas or 0),
            age_str,
            status
        )

    console.print(table)
    
    # Add summary
    total = len(deployments.items)
    running = sum(1 for d in deployments.items 
                  if (d.status.ready_replicas or 0) == (d.spec.replicas or 0) 
                  and (d.spec.replicas or 0) > 0)
    
    console.print(f"\n[dim]Total: {total} deployments, {running} running[/dim]")

def get_services():
    core_v1 = client.CoreV1Api()
    
    with console.status("[cyan]Fetching services...[/cyan]"):
        try:
            services = core_v1.list_namespaced_service(namespace="default")
        except client.exceptions.ApiException as e:
            console.print(Panel(
                f"[bold red]API Error:[/bold red] {e}",
                box=ROUNDED,
                border_style="red"
            ))
            raise typer.Exit(code=1)
    
    if not services.items:
        console.print(Panel(
            "[yellow]No services found in the default namespace.[/yellow]\n\n"
            "Deploy your application using:\n"
            "[cyan]okik deploy[/cyan]",
            box=ROUNDED,
            border_style="yellow"
        ))
        return

    # Create enhanced table
    table = Table(
        title="Kubernetes Services",
        box=ROUNDED,
        title_style="bold cyan",
        show_lines=True
    )
    table.add_column("Name", justify="left", style="cyan", no_wrap=True)
    table.add_column("Type", justify="left", style="yellow")
    table.add_column("Cluster IP", justify="left", style="green")
    table.add_column("External IP", justify="left", style="magenta")
    table.add_column("Ports", justify="left", style="blue")
    table.add_column("Age", justify="right", style="yellow")

    for service in services.items:
        # Calculate age
        creation_time = service.metadata.creation_timestamp
        age = time.time() - creation_time.timestamp()
        age_str = _format_age(age)
        
        # Format ports
        ports = []
        for p in service.spec.ports:
            port_str = f"{p.port}"
            if p.target_port and str(p.target_port) != str(p.port):
                port_str += f":{p.target_port}"
            if p.node_port:
                port_str += f":{p.node_port}"
            port_str += f"/{p.protocol}"
            ports.append(port_str)
        
        # Get external IPs
        external_ips = "None"
        if service.spec.external_i_ps:
            external_ips = ",".join(service.spec.external_i_ps)
        elif service.status.load_balancer and service.status.load_balancer.ingress:
            external_ips = ",".join([
                i.ip or i.hostname 
                for i in service.status.load_balancer.ingress
            ])
        
        table.add_row(
            service.metadata.name,
            service.spec.type,
            service.spec.cluster_ip or "None",
            external_ips,
            ", ".join(ports),
            age_str
        )

    console.print(table)
    
    # Add summary
    console.print(f"\n[dim]Total: {len(services.items)} services[/dim]")

def _format_age(seconds: float) -> str:
    """Format age in human-readable format"""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds / 60)}m"
    elif seconds < 86400:
        return f"{int(seconds / 3600)}h"
    else:
        return f"{int(seconds / 86400)}d"

@typer_app.command(name="delete")
def delete_resource(resource: str, name: str):
    """
    Delete a deployment or service in the default namespace.
    """
    console.print(create_fancy_header("Delete Resource", f"Remove {resource} '{name}'"))
    
    # Confirm deletion
    if not Confirm.ask(
        f"[bold red]⚠ Warning:[/bold red] Are you sure you want to delete {resource} '{name}'?",
        default=False
    ):
        console.print("[yellow]Deletion cancelled.[/yellow]")
        raise typer.Exit()
    
    # Load Kubernetes configuration
    with console.status("[cyan]Loading Kubernetes configuration...[/cyan]"):
        try:
            config.load_kube_config()
            console.print("[green]✓ Kubernetes configuration loaded[/green]\n")
        except Exception as e:
            console.print(Panel(
                f"[bold red]Kubernetes Error:[/bold red] {e}",
                box=ROUNDED,
                border_style="red"
            ))
            raise typer.Exit(code=1)

    if resource.lower() in ["deployment", "deploy"]:
        delete_deployment(name)
    elif resource.lower() in ["service", "svc"]:
        delete_service(name)
    else:
        console.print(Panel(
            f"[bold red]Error:[/bold red] Unsupported resource type: '{resource}'\n\n"
            "Supported resources:\n"
            "• deployment (or deploy)\n"
            "• service (or svc)",
            box=ROUNDED,
            border_style="red"
        ))
        raise typer.Exit(code=1)

def delete_deployment(name: str):
    apps_v1 = client.AppsV1Api()
    
    with console.status(f"[yellow]Deleting deployment '{name}'...[/yellow]"):
        try:
            apps_v1.delete_namespaced_deployment(name=name, namespace="default")
            time.sleep(2)  # Give it time to process
        except client.exceptions.ApiException as e:
            if e.status == 404:
                console.print(Panel(
                    f"[bold red]Error:[/bold red] Deployment '{name}' not found.",
                    box=ROUNDED,
                    border_style="red"
                ))
            else:
                console.print(Panel(
                    f"[bold red]API Error:[/bold red] {e}",
                    box=ROUNDED,
                    border_style="red"
                ))
            raise typer.Exit(code=1)
    
    console.print(Panel(
        f"[bold green]✓ Success![/bold green]\n\n"
        f"Deployment '{name}' has been deleted.",
        box=ROUNDED,
        border_style="green"
    ))

def delete_service(name: str):
    core_v1 = client.CoreV1Api()
    
    with console.status(f"[yellow]Deleting service '{name}'...[/yellow]"):
        try:
            core_v1.delete_namespaced_service(name=name, namespace="default")
            time.sleep(1)  # Give it time to process
        except client.exceptions.ApiException as e:
            if e.status == 404:
                console.print(Panel(
                    f"[bold red]Error:[/bold red] Service '{name}' not found.",
                    box=ROUNDED,
                    border_style="red"
                ))
            else:
                console.print(Panel(
                    f"[bold red]API Error:[/bold red] {e}",
                    box=ROUNDED,
                    border_style="red"
                ))
            raise typer.Exit(code=1)
    
    console.print(Panel(
        f"[bold green]✓ Success![/bold green]\n\n"
        f"Service '{name}' has been deleted.",
        box=ROUNDED,
        border_style="green"
    ))

def list_clusters():
    contexts, current_context = config.list_kube_config_contexts()

    table = Table(
        title="Kubernetes Clusters",
        box=ROUNDED,
        title_style="bold cyan",
        show_lines=True
    )
    table.add_column("Context", justify="left", style="cyan", no_wrap=True)
    table.add_column("Cluster", justify="left", style="yellow")
    table.add_column("User", justify="left", style="magenta")
    table.add_column("Namespace", justify="left", style="blue")
    table.add_column("Current", justify="center")

    for context in contexts:
        context_name = context['name']
        cluster_name = context['context']['cluster']
        user_name = context['context'].get('user', 'default')
        namespace = context['context'].get('namespace', 'default')
        is_current = "✓" if context_name == current_context['name'] else ""
        
        # Highlight current context
        if is_current:
            table.add_row(
                f"[bold]{context_name}[/bold]",
                f"[bold]{cluster_name}[/bold]",
                f"[bold]{user_name}[/bold]",
                f"[bold]{namespace}[/bold]",
                "[bold green]✓[/bold green]"
            )
        else:
            table.add_row(context_name, cluster_name, user_name, namespace, "")

    console.print(table)
    
    # Add helpful information
    console.print(Panel(
        f"[cyan]Current context:[/cyan] [bold]{current_context['name']}[/bold]\n\n"
        "[dim]To switch context, use:[/dim]\n"
        "[yellow]okik cluster <context-name>[/yellow]",
        box=ROUNDED,
        border_style="blue"
    ))

def switch_context(context_name: str):
    with console.status(f"[cyan]Switching to context '{context_name}'...[/cyan]"):
        try:
            with open(KUBE_CONFIG_PATH, 'r') as stream:
                kubeconfig = yaml.safe_load(stream)

            context_names = [context['name'] for context in kubeconfig['contexts']]
            if context_name not in context_names:
                console.print(Panel(
                    f"[bold red]Error:[/bold red] Context '{context_name}' not found.\n\n"
                    "Available contexts:\n" + 
                    "\n".join([f"• {ctx}" for ctx in context_names]),
                    box=ROUNDED,
                    border_style="red"
                ))
                raise typer.Exit(code=1)

            kubeconfig['current-context'] = context_name

            with open(KUBE_CONFIG_PATH, 'w') as stream:
                yaml.safe_dump(kubeconfig, stream)
                
        except FileNotFoundError:
            console.print(Panel(
                "[bold red]Error:[/bold red] Kubeconfig file not found.\n"
                "Make sure kubectl is configured properly.",
                box=ROUNDED,
                border_style="red"
            ))
            raise typer.Exit(code=1)

    console.print(Panel(
        f"[bold green]✓ Success![/bold green]\n\n"
        f"Switched to context: [cyan]{context_name}[/cyan]",
        box=ROUNDED,
        border_style="green"
    ))

@typer_app.command(name="cluster")
def cluster(context_name: str = typer.Argument(None, help="Name of the cluster context to switch to")):
    """
    List all Kubernetes clusters configured in the kubeconfig file or switch to a specified cluster.
    """
    console.print(create_fancy_header("Cluster Manager", "Manage Kubernetes contexts"))
    
    # Load kubeconfig
    with console.status("[cyan]Loading kubeconfig...[/cyan]"):
        try:
            config.load_kube_config()
            console.print("[green]✓ Kubeconfig loaded successfully[/green]\n")
        except Exception as e:
            console.print(Panel(
                f"[bold red]Error:[/bold red] Failed to load kubeconfig: {e}\n\n"
                "Make sure you have:\n"
                "• kubectl installed\n"
                "• Valid kubeconfig file (~/.kube/config)",
                box=ROUNDED,
                border_style="red"
            ))
            raise typer.Exit(code=1)

    if context_name:
        # Switch context
        switch_context(context_name)
    else:
        # List all clusters
        list_clusters()

@typer_app.command()
def serve(
    model_id: str = typer.Argument(..., help="HuggingFace model ID to serve"),
    docker_file: str = typer.Option(
        ".okik/docker/Dockerfile", "--docker-file", "-d", help="Dockerfile name",
    ),
    app_name: str = typer.Option(
        None, "--app-name", "-a", help="Name of the Docker image"
    ),
    cloud_prefix: str = typer.Option(
        None, "--cloud-prefix", "-c", help="Prefix for the cloud service"
    ),
    registry_id: str = typer.Option(None, "--registry-id", "-r", help="Registry ID"),
    tag: str = typer.Option("latest", "--tag", "-t", help="Tag for the Docker image"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Print outputs from Docker"),
    force_build: bool = typer.Option(False, "--force-build", "-f", help="Force rebuild of the Docker image"),
):
    """
    Package and serve a HuggingFace model as a Docker container
    """
    console.print(create_fancy_header("Model Server", f"Serve {model_id}"))
    
    start_time = time.time()
    steps = []
    temp_dir = ProjectDir.TEMP_DIR.value
    config_dir = ProjectDir.CONFIG_DIR.value

    # Display configuration
    config_table = Table(title="Model Serving Configuration", box=ROUNDED)
    config_table.add_column("Parameter", style="cyan")
    config_table.add_column("Value", style="yellow")
    
    config_items = [
        ("Model ID", model_id),
        ("Docker File", docker_file),
        ("App Name", app_name or "[dim]auto-generated[/dim]"),
        ("Cloud Prefix", cloud_prefix or "[dim]none[/dim]"),
        ("Registry ID", registry_id or "[dim]none[/dim]"),
        ("Tag", tag),
        ("Verbose", "Yes" if verbose else "No"),
        ("Force Build", "Yes" if force_build else "No")
    ]
    
    for key, value in config_items:
        config_table.add_row(key, str(value))
    
    console.print(config_table)
    console.print()

    with create_progress_bar() as progress:
        prep_task = progress.add_task("[cyan]Preparing model server...", total=6)
        
        # Create temp directory
        os.makedirs(temp_dir, exist_ok=True)
        progress.update(prep_task, advance=1)

        # Generate the model serving code with enhanced template
        model_code = f'''
from transformers import pipeline, AutoTokenizer, AutoModel
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import torch
import uvicorn
import logging
import sys

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="{model_id} Model Server",
    description="API server for {model_id} model",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global model variable
model = None

class TextRequest(BaseModel):
    text: str = Field(..., description="Input text for the model")
    max_length: Optional[int] = Field(50, description="Maximum length of generated text")
    temperature: Optional[float] = Field(1.0, description="Temperature for text generation")
    top_p: Optional[float] = Field(1.0, description="Top-p for text generation")
    num_return_sequences: Optional[int] = Field(1, description="Number of sequences to return")

class TextResponse(BaseModel):
    generated_text: List[str]
    model_id: str
    parameters: Dict[str, Any]

@app.on_event("startup")
async def load_model():
    global model
    try:
        logger.info(f"Loading model: {model_id}")
        model = pipeline("text-generation", model="{model_id}")
        logger.info("Model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load model: {{e}}")
        sys.exit(1)

@app.get("/")
async def root():
    return {{
        "message": "Model server is running",
        "model": "{model_id}",
        "endpoints": {{
            "/generate": "Generate text",
            "/health": "Health check",
            "/docs": "API documentation"
        }}
    }}

@app.get("/health")
async def health_check():
    return {{
        "status": "healthy",
        "model_loaded": model is not None,
        "model_id": "{model_id}"
    }}

@app.post("/generate", response_model=TextResponse)
async def generate_text(request: TextRequest):
    try:
        if model is None:
            raise HTTPException(status_code=503, detail="Model not loaded")
        
        # Generate text
        results = model(
            request.text,
            max_length=request.max_length,
            temperature=request.temperature,
            top_p=request.top_p,
            num_return_sequences=request.num_return_sequences,
            pad_token_id=model.tokenizer.eos_token_id
        )
        
        # Extract generated texts
        generated_texts = [r["generated_text"] for r in results]
        
        return TextResponse(
            generated_text=generated_texts,
            model_id="{model_id}",
            parameters={{
                "max_length": request.max_length,
                "temperature": request.temperature,
                "top_p": request.top_p,
                "num_return_sequences": request.num_return_sequences
            }}
        )
    except Exception as e:
        logger.error(f"Generation error: {{e}}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=80)
'''

        # Write model code to temp directory
        with open(os.path.join(temp_dir, "main.py"), "w") as f:
            f.write(model_code)
        steps.append("✓ Generated model serving code")
        progress.update(prep_task, advance=1)

        # Create comprehensive requirements.txt
        requirements = [
            "fastapi==0.104.1",
            "uvicorn[standard]==0.24.0",
            "torch>=2.0.0",
            "transformers>=4.35.0",
            "pydantic>=2.0.0",
            "python-multipart==0.0.6",
            "accelerate>=0.24.0"
        ]
        
        with open(os.path.join(temp_dir, "requirements.txt"), "w") as f:
            f.write("\n".join(requirements))
        steps.append("✓ Created requirements.txt")
        progress.update(prep_task, advance=1)

        # Check Dockerfile
        if not os.path.isfile(docker_file):
            progress.stop()
            console.print(Panel(
                f"[bold red]Error:[/bold red] Dockerfile '{docker_file}' not found.\n"
                "Run [yellow]okik init[/yellow] to create default Dockerfile.",
                box=ROUNDED,
                border_style="red"
            ))
            raise typer.Exit(code=1)
        progress.update(prep_task, advance=1)

        # Copy Dockerfile
        shutil.copy(docker_file, os.path.join(temp_dir, os.path.basename(docker_file)))
        steps.append("✓ Copied Dockerfile")
        progress.update(prep_task, advance=1)

        # Handle image configuration
        os.makedirs(config_dir, exist_ok=True)
        image_json_path = os.path.join(config_dir, "configs.json")

        if force_build:
            if os.path.exists(image_json_path):
                os.remove(image_json_path)
                steps.append("✓ Force build: cleared existing configuration")
        
        # Determine image name
        existing_app_name = None
        if os.path.exists(image_json_path):
            with open(image_json_path, "r") as json_file:
                try:
                    json_content = json.load(json_file)
                    existing_app_name = json_content.get("image_name")
                except json.JSONDecodeError as e:
                    log_error(f"Error reading JSON file: {e}")

        if existing_app_name and not force_build:
            docker_image_name = existing_app_name
        else:
            if not app_name:
                # Clean model ID for use in image name
                clean_model_id = model_id.replace('/', '-').replace(':', '-').lower()
                app_name = f"model-{clean_model_id}"
                
            if cloud_prefix:
                docker_image_name = f"{cloud_prefix.lower()}/{registry_id}/{app_name.lower()}:{tag}"
            else:
                docker_image_name = f"{registry_id}/{app_name.lower()}:{tag}"

            # Save configuration
            with open(image_json_path, "w") as json_file:
                json.dump({"image_name": docker_image_name, "app_name": app_name}, json_file)
        
        steps.append(f"✓ Image name: {docker_image_name}")
        progress.update(prep_task, advance=1)

    # Build Docker image
    build_command = f"docker build --no-cache -t {docker_image_name} -f {docker_file} {temp_dir}" if force_build else f"docker build -t {docker_image_name} -f {docker_file} {temp_dir}"
    
    console.print(Panel(
        f"[bold]Building model server image[/bold]\n"
        f"Model: [cyan]{model_id}[/cyan]\n"
        f"Image: [yellow]{docker_image_name}[/yellow]",
        box=ROUNDED,
        border_style="cyan"
    ))

    # Build with live output
    build_success = False
    log_lines = []
    
    layout = Layout()
    layout.split_column(
        Layout(name="status", size=3),
        Layout(name="output", ratio=1)
    )
    
    with Live(layout, refresh_per_second=4, console=console) as live:
        layout["status"].update(Panel(
            "[cyan]Building Docker image...[/cyan]",
            box=ROUNDED
        ))
        
        process = subprocess.Popen(
            build_command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        for line in iter(process.stdout.readline, ''):
            line = line.strip()
            if line.startswith("Step "):
                layout["status"].update(Panel(
                    f"[cyan]{line}[/cyan]",
                    box=ROUNDED
                ))
            
            if verbose or line.startswith("Step ") or "-->" in line or "error" in line.lower():
                log_lines.append(line)
                display_lines = log_lines[-15:]
                
                output_text = "\n".join(display_lines)
                layout["output"].update(Panel(
                    Syntax(output_text, "dockerfile", theme="monokai", line_numbers=False),
                    title="Build Output",
                    box=ROUNDED,
                    border_style="green" if "error" not in output_text.lower() else "red"
                ))
        
        process.stdout.close()
        return_code = process.wait()
        build_success = return_code == 0

    # Cleanup
    shutil.rmtree(temp_dir)
    
    # Display results
    end_time = time.time()
    elapsed_time = end_time - start_time

    if build_success:
        # Success panel with usage instructions
        console.print(Panel(
            f"[bold green]✓ Model Server Built Successfully![/bold green]\n\n"
            f"[cyan]Model:[/cyan] {model_id}\n"
            f"[cyan]Image:[/cyan] {docker_image_name}\n"
            f"[cyan]Build Time:[/cyan] {elapsed_time:.2f} seconds\n\n"
            f"[bold]To run the model server:[/bold]\n"
            f"[yellow]docker run -p 8000:80 {docker_image_name}[/yellow]\n\n"
            f"[bold]To test the API:[/bold]\n"
            f"[yellow]curl -X POST http://localhost:8000/generate \\[/yellow]\n"
            f"[yellow]  -H 'Content-Type: application/json' \\[/yellow]\n"
            f"[yellow]  -d '{{\"text\": \"Hello, how are\", \"max_length\": 50}}'[/yellow]\n\n"
            f"[bold]API Documentation:[/bold]\n"
            f"[yellow]http://localhost:8000/docs[/yellow]",
            title="Build Complete",
            box=DOUBLE,
            border_style="green"
        ))
    else:
        console.print(Panel(
            f"[bold red]✗ Build Failed![/bold red]\n\n"
            f"[cyan]Model:[/cyan] {model_id}\n"
            f"[cyan]Time:[/cyan] {elapsed_time:.2f} seconds\n\n"
            f"[yellow]Check the output above for errors[/yellow]\n"
            f"[dim]Run with --verbose flag for detailed output[/dim]",
            title="Build Failed",
            box=DOUBLE,
            border_style="red"
        ))
        raise typer.Exit(code=1)

if __name__ == "__main__":
    if len(sys.argv) == 1:
        ascii_art = text2art("Okik", font="block")  # Generate ASCII art
        console.print(ascii_art, style="bold green")  # Print in bold green color
        typer_app()
    else:
        typer_app()
