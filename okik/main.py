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
import re

import pyfiglet
import questionary
import typer
import uvicorn
import yaml
from art import text2art
from fastapi.routing import APIRoute
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.status import Status
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.tree import Tree
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from okik.consts import ProjectDir
from okik.logger import log_error, log_info, log_start, log_success
from okik.scripts.dockerfiles.dockerfile_gen import create_dockerfile

# Initialize Typer app
typer_app = typer.Typer()
# Initialize Rich console
console = Console()

KUBE_CONFIG_PATH = os.path.expanduser("~/.kube/config")

# Heavy Kubernetes libraries are imported lazily to speed up CLI startup.

client = config = utils = ApiException = None  # type: ignore (populated lazily)

# -----------------------------------------------------------------------------
# Lazy import helper for Kubernetes modules to reduce startup time
# -----------------------------------------------------------------------------

def _import_kubernetes():
    """Dynamically import kubernetes modules when first required."""
    global client, config, utils, ApiException
    if client is not None:  # Already imported.
        return

    try:
        from kubernetes import client as _client, config as _config, utils as _utils
        from kubernetes.client import ApiException as _ApiException

        client = _client  # type: ignore
        config = _config  # type: ignore
        utils = _utils  # type: ignore
        ApiException = _ApiException  # type: ignore
    except ImportError:
        raise typer.Exit("The 'kubernetes' package is required for this command. Install it with `pip install kubernetes`. ")

@typer_app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """
    Okik CLI: Simplify. Deploy. Scale.
    """
    if ctx.invoked_subcommand is None:
        ascii_art = pyfiglet.figlet_format("Okik", font="ansi_regular")
        console.print(
            ascii_art, style="bold green"
        )  # Print ASCII art in bold green color
        console.print(
            "Simplify. Deploy. Scale.", style="bold green"
        )  # Tagline in bold green
        console.print(
            "Type 'okik --help' for more commands.", style="dim"
        )  # Helper prompt



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
    with console.status("[bold green]Initializing the project..."):
        # Create directories
        folders_list = [dir.value for dir in ProjectDir]

        # Use Rich Progress to give the user instant visual feedback
        progress = Progress(
            SpinnerColumn(style="green"),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=None),
            TimeElapsedColumn(),
            console=console,
        )

        with progress:
            progress_task = progress.add_task("Creating project structure...", total=len(folders_list))

            for folder in folders_list:
                os.makedirs(folder, exist_ok=True)
                tasks[folders_list.index(folder)]["status"] = "completed"
                progress.update(progress_task, advance=1)

        # Use dockerfile_gen to generate the Dockerfile
        try:
            create_dockerfile(docker_dir)
            tasks[3]["status"] = "completed"
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

        # Create configs.json in cache directory if not exists
        configs_path = os.path.join(config_dir, "configs.json")
        if not os.path.exists(configs_path):
            with open(configs_path, "w") as configs_file:
                json.dump({'image_name': '', 'app_name': ''}, configs_file)
            tasks[5]["status"] = "completed"
        else:
            tasks[5]["status"] = "skipped"

    # Display task statuses
    status_styles = {"completed": "bold green", "failed": "bold red", "skipped": "bold yellow", "pending": "bold"}

    for task in tasks:
        console.print(f"[{status_styles[task['status']]}] - {task['description']} [/{status_styles[task['status']]}]")

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

    # ---------------------
    # Visual progress setup
    # ---------------------
    progress = Progress(
        SpinnerColumn(style="green"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=None),
        TimeElapsedColumn(),
        console=console,
        transient=True,  # Remove after completion
    )

    # We will execute the context-preparation steps inside a single progress task.
    prepare_steps_total = 5  # Checking entrypoint, copy entrypoint, check Dockerfile, copy Dockerfile, copy requirements

    with progress:
        prepare_task = progress.add_task("Preparing build context...", total=prepare_steps_total)

        # 1️⃣ Check entry point file exists
        if not os.path.isfile(entry_point):
            log_error(f"Entry point file '{entry_point}' not found.")
            return
        steps.append("Checked entry point file.")
        progress.update(prepare_task, advance=1)

        # 2️⃣ Ensure temporary directory and copy entry point
        os.makedirs(temp_dir, exist_ok=True)
        shutil.copy(entry_point, os.path.join(temp_dir, os.path.basename(entry_point)))
        steps.append("Copied entry point file to temporary directory.")
        progress.update(prepare_task, advance=1)

        # 3️⃣ Check Dockerfile presence
        if not os.path.isfile(docker_file):
            log_error(f"Dockerfile '{docker_file}' not found.")
            return
        steps.append("Checked Dockerfile.")
        progress.update(prepare_task, advance=1)

        # 4️⃣ Copy Dockerfile
        shutil.copy(docker_file, os.path.join(temp_dir, os.path.basename(docker_file)))
        steps.append("Copied Dockerfile to temporary directory.")
        progress.update(prepare_task, advance=1)

        # 5️⃣ Copy requirements.txt
        shutil.copy("requirements.txt", os.path.join(temp_dir, "requirements.txt"))
        steps.append("Copied requirements.txt file to temporary directory.")
        progress.update(prepare_task, advance=1)
    # Progress context exits here (bar cleared)

    os.makedirs(config_dir, exist_ok=True)
    image_json_path = os.path.join(config_dir, "configs.json")

    if force_build:
        if os.path.exists(image_json_path):
            os.remove(image_json_path)
            console.print("Existing image configuration cleared due to force build.", style="bold yellow")
        steps.append("Force build option applied.")

    existing_app_name = None
    if os.path.exists(image_json_path):
        with open(image_json_path, "r") as json_file:
            try:
                json_content = json.load(json_file)
                existing_app_name = json_content.get("image_name")
                if existing_app_name:
                    console.print(f"Using existing Docker image name: '{existing_app_name}'", style="bold blue")
            except json.JSONDecodeError as e:
                log_error(f"Error reading JSON file: {e}")

    if existing_app_name and not force_build:
        docker_image_name = existing_app_name
        steps.append(f"Using existing app name from JSON: {docker_image_name}")
    else:
        if not app_name:
            app_name = f"app-{uuid.uuid4()}"
            steps.append(f"Generated unique app name: {app_name}")
        if cloud_prefix:
            steps.append(f"Prefixed app name: {app_name}")
            docker_image_name = f"{cloud_prefix}/{registry_id}/{app_name}:{tag}"
        else:
            docker_image_name = f"{registry_id}/{app_name}:{tag}"
        steps.append(f"Formatted Docker image name: {docker_image_name}")

        # Preserve image name in JSON file
        with open(image_json_path, "w") as json_file:
            json.dump({"image_name": docker_image_name, "app_name": app_name}, json_file)
        steps.append("Preserved image name in JSON file.")

    # Enable Docker BuildKit for faster & more efficient builds
    build_base_cmd = "docker build --no-cache" if force_build else "docker build"
    build_command = f"DOCKER_BUILDKIT=1 {build_base_cmd} -t {docker_image_name} -f {os.path.join(docker_file)} {temp_dir}"
    build_success = False

    # ------------------------------
    # Docker build with layer bar 🔨
    # ------------------------------
    progress_build = Progress(
        SpinnerColumn(style="cyan"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=None),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    )

    with progress_build:
        task_id = None
        last_completed = 0

        process = subprocess.Popen(build_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True)

        for raw_line in iter(process.stdout.readline, ''):
            line = raw_line.strip()

            # Detect "Step X/Y : ..." lines to track progress
            if line.startswith("Step "):
                match = re.match(r"Step\s+(\d+)/(\d+)\s*:\s*(.*)", line)
                if match:
                    current_step = int(match.group(1))
                    total_steps = int(match.group(2))
                    description = match.group(3) or "Building"

                    # Initialise progress task once we know total steps
                    if task_id is None:
                        task_id = progress_build.add_task("Building Docker image", total=total_steps)

                    # Advance only if new steps discovered (avoid rewinding on multi-stage noise)
                    if current_step > last_completed:
                        progress_build.update(task_id, completed=current_step, description=f"{description} ({current_step}/{total_steps})")
                        last_completed = current_step

                    steps.append(line)
                else:
                    # Fallback when regex doesn't match but still starts with Step
                    progress_build.console.log(line)

            elif verbose:
                progress_build.console.log(line)

        process.stdout.close()
        return_code = process.wait()
        build_success = return_code == 0

        if task_id is not None:
            progress_build.update(task_id, description="Build complete" if build_success else "Build failed")

        if build_success:
            steps.append(f"Built Docker image '{docker_image_name}'.")
        else:
            steps.append(f"Failed to build Docker image '{docker_image_name}'.")

    with console.status("[bold green]Cleaning up temporary directory..."):
        shutil.rmtree(temp_dir)
        steps.append("Cleaned up temporary directory.")

    end_time = time.time()
    elapsed_time = end_time - start_time

    if build_success:
        steps.append(f"Docker image '{docker_image_name}' built successfully in {elapsed_time:.2f} seconds.")
        log_success(f"Docker image '{docker_image_name}' built successfully in {elapsed_time:.2f} seconds.")
    else:
        steps.append(f"Docker image build failed after {elapsed_time:.2f} seconds.")
        log_error(f"Docker image '{docker_image_name}' build failed after {elapsed_time:.2f} seconds.")

    # Prompt the user to build the image with more details with --verbose flag
    steps.append("Build the image with more details using the --verbose flag if you want to see more details.")

    # Display all steps
    for step in steps:
        console.print(step, style="bold green" if build_success else "bold red")

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
    if dev:
        console.print(Panel(f"Serving the application with entry point: [bold]{entry_point}[/bold]", title="Okik CLI - Development mode"), style="bold yellow")
    else:
        console.print(Panel(f"Serving the application with entry point: [bold]{entry_point}[/bold]", title="Okik CLI - Production mode"), style="bold green")

    # Check if the entry point file exists
    if not os.path.isfile(entry_point):
        log_error(f"Entry point file '{entry_point}' not found.")
        return

    # Add the current directory to sys.path
    sys.path.insert(0, os.getcwd())

    # Try to import the module to catch any import errors
    try:
        module_name = os.path.splitext(os.path.basename(entry_point))[0]
        spec = importlib.util.spec_from_file_location(module_name, entry_point)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    except Exception:
        log_error(f"Error importing {entry_point}:")
        log_error(traceback.format_exc())
        return

    # Check if 'app' is defined in the module
    if not hasattr(module, 'app'):
        log_error(f"No 'app' object found in {entry_point}. Make sure you have defined an ASGI application named 'app'.")
        return

    # Determine the number of workers
    if dev:
        workers = 1
    else:
        workers = min(multiprocessing.cpu_count(), 8)

    # Prepare the uvicorn configuration
    config = uvicorn.Config(
        f"{module_name}:app",
        host=host,
        port=port,
        reload=reload and dev,
        workers=workers,
        log_level=log_level,
    )

    # Create the server
    server = uvicorn.Server(config)

    # Print server details
    console.print(Panel(
        f"Host: [bold]{host}[/bold]\n"
        f"Port: [bold]{port}[/bold]\n"
        f"Auto-reload: [bold]{'Enabled' if reload and dev else 'Disabled'}[/bold]\n"
        f"Environment: [bold]{'Development' if dev else 'Production'}[/bold]\n"
        f"Workers: [bold]{workers}[/bold]\n"
        f"Log level: [bold]{log_level}[/bold]\n"
        f"Listening to: [bold]http://{host}:{port}[/bold]",
        title="Server Details",
        subtitle=f"Open http://{host}:{port}/docs to view API documentation",
        style="bold yellow" if dev else "bold green"
    ))

    log_start("Server running. Press CTRL+C to stop.")
    log_info(f"Server listening to http://{host}:{port}")

    # Run the server
    try:
        server.run()
    except Exception as e:
        log_error(f"Failed to start the server: {str(e)}")
    finally:
        log_info("Server stopped.")


@typer_app.command()
def routes(
    entry_point: str = typer.Option(
        "main.py", "--entry-point", "-e", help="Entry point file"
    ),
):
    """
    Creates routes, services, and other resources defined in the entry point.
    """
    if not os.path.isfile(entry_point):
        console.print(f"Entry point file '[bold red]{entry_point}[/bold red]' not found.", style="bold red")
        return

    module_name = os.path.splitext(entry_point)[0]

    try:
        spec = importlib.util.spec_from_file_location(module_name, entry_point)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        app = getattr(module, "app", None)
        if app is None:
            console.print(f"No 'app' instance found in '[bold red]{entry_point}[/bold red]'.", style="bold red")
            return

        # Organize routes by base path and build Rich Tree
        routes_tree = Tree(f"[bold cyan]{entry_point}[/bold cyan] Application Routes")
        routes_by_base_path = {}
        for route in app.routes:
            if isinstance(route, APIRoute):
                base_path = route.path.split("/")[1]  # Get the base path segment
                if base_path not in routes_by_base_path:
                    routes_by_base_path[base_path] = Tree(f"[bold cyan]<HOST>/{base_path}/[/bold cyan]")
                    routes_tree.add(routes_by_base_path[base_path])
                routes_by_base_path[base_path].add(f"[green]{route.path}[/green] | [green]{', '.join(route.methods)}[/green]")
        console.print(routes_tree)
    except Exception as e:
        console.print(f"Failed to load the entry point module '[bold red]{entry_point}[/bold red]': {e}", style="bold red")

def delete_existing_resources(yaml_documents):
    _import_kubernetes()
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
    _import_kubernetes()
    services_dir = os.path.join(ProjectDir.SERVICES_DIR.value, 'k8')  # Adjusted for clarity
    yaml_files = [f for f in os.listdir(services_dir) if f.endswith('.yaml') or f.endswith('.yml')]
    if not yaml_files:
        console.print("No YAML configuration files found in the services directory.", style="bold red")
        return

    # Use Select for file selection with highlighting
    selected_file = questionary.select(
            "Select a YAML file to deploy:",
            choices=yaml_files,
            use_indicator=True,
            use_arrow_keys=True,
            style=questionary.Style([
                ('selected', 'fg:cyan'),
                ('pointer', 'fg:cyan'),
            ])
        ).ask()

    if not selected_file:
        console.print("No file selected. Deployment cancelled.", style="bold red")
        return

    yaml_path = os.path.join(services_dir, selected_file)
    try:
        with open(yaml_path, 'r') as file:
            yaml_documents = list(yaml.safe_load_all(file))
            for index, yaml_content in enumerate(yaml_documents):
                # Convert YAML content to a formatted string
                yaml_str = yaml.dump(yaml_content, default_flow_style=False)
                # Create a Syntax object for syntax highlighting
                # yaml_syntax = Syntax(yaml_str, "yaml", theme="monokai", line_numbers=True)
                yaml_syntax = Syntax(yaml_str, "yaml", theme="monokai", background_color="default")
                panel = Panel(yaml_syntax, title=f"YAML Configuration: {selected_file} (Document {index+1})", border_style="blue")
                console.print(panel)
    except yaml.YAMLError as exc:
        console.print(f"Error parsing YAML file '{selected_file}': {exc}", style="bold red")
        return

    if not questionary.confirm(
            "Do you want to continue with the deployment?",
            style=questionary.Style([
                ('selected', 'fg:cyan'),
                ('pointer', 'fg:cyan'),
            ])
        ).ask():
            console.print("Deployment stopped by the user.", style="bold red")
            raise typer.Exit()

    # Load Kubernetes configuration
    try:
        config.load_kube_config()
        k8s_client = client.ApiClient()
        v1 = client.CoreV1Api()
        console.print("Kubernetes configuration loaded successfully.", style="bold green")
    except Exception as e:
        console.print(f"Failed to load Kubernetes configuration: {e}", style="bold red")
        return

    # Validate credentials
    credentials_path = os.path.expanduser('~/okik/credentials.json')
    if not os.path.exists(credentials_path):
        console.print("Credentials file not found.", style="bold red")
        return

    # Delete existing resources
    delete_existing_resources(yaml_documents)

    # Apply the YAML documents
    console.print("Applying YAML configurations...")
    try:
        with Status("Deploying...", spinner="dots"):
            for yaml_doc in yaml_documents:
                utils.create_from_dict(k8s_client, yaml_doc, namespace="default")
        console.print(f"Deployment applied successfully from '{selected_file}'", style="bold green")
    except ApiException as e:
        console.print(f"Failed to apply YAML file '{selected_file}': {e}", style="bold red")
        return

    # Wait for deployment to complete
    console.print("Waiting for deployment to complete...")
    console.print("Deployment completed successfully!", style="bold green")

    # Retrieve and display the endpoint
    try:
        services = v1.list_namespaced_service(namespace="default")
        if not services.items:
            console.print("No services found in the default namespace.", style="bold red")
        else:
            for service in services.items:
                console.print(f"Service {service.metadata.name} is available at {service.spec.cluster_ip}:{service.spec.ports[0].port}", style="bold blue")
                if service.metadata.name == 'embedder':
                    console.print("To test the service, you can use the following command if you are using Minikube:")
                    console.print("  minikube service embedder")
                    console.print("Or you can port-forward the service with:")
                    console.print("  kubectl port-forward service/embedder 8080:80")
    except ApiException as e:
        console.print(f"Error retrieving services: {e}", style="bold red")

@typer_app.command(name="get")
def get_resources(resource: str):
    """
    Get deployments or services in the default namespace.
    """
    _import_kubernetes()
    try:
        # Load Kubernetes configuration
        config.load_kube_config()
        console.print("Kubernetes configuration loaded successfully.", style="bold green")
    except Exception as e:
        console.print(f"Failed to load Kubernetes configuration: {e}", style="bold red")
        return

    if resource == "deployments":
        get_deployments()
    elif resource == "services":
        get_services()
    else:
        console.print(f"Unsupported resource type: {resource}", style="bold red")

def get_deployments():
    """Display deployments in a navigable Tree and page the output if it is long."""
    _import_kubernetes()
    apps_v1 = client.AppsV1Api()
    try:
        deployments = apps_v1.list_namespaced_deployment(namespace="default")
        if not deployments.items:
            console.print("No deployments found in the default namespace.", style="bold yellow")
            return

        root = Tree("[bold cyan]Deployments (default namespace)[/bold cyan]")
        for d in deployments.items:
            replicas = d.status.available_replicas or 0
            desired = d.spec.replicas
            root.add(f"[cyan]{d.metadata.name}[/cyan] • [green]{replicas}/{desired} ready[/green]")

        # Use a pager so the user can scroll when there are many items
        with console.pager():
            console.print(root)
    except client.exceptions.ApiException as e:
        console.print(f"Error listing deployments: {e}", style="bold red")

def get_services():
    """Display services in a navigable Tree and page the output if it is long."""
    _import_kubernetes()
    core_v1 = client.CoreV1Api()
    try:
        services = core_v1.list_namespaced_service(namespace="default")
        if not services.items:
            console.print("No services found in the default namespace.", style="bold yellow")
            return

        root = Tree("[bold cyan]Services (default namespace)[/bold cyan]")
        for s in services.items:
            ports = ", ".join([f"{p.port}/{p.protocol}" for p in s.spec.ports])
            root.add(f"[cyan]{s.metadata.name}[/cyan] • [magenta]{s.spec.type}[/magenta] • [green]{s.spec.cluster_ip}[/green] • [blue]{ports}[/blue]")

        with console.pager():
            console.print(root)
    except client.exceptions.ApiException as e:
        console.print(f"Error listing services: {e}", style="bold red")

@typer_app.command(name="delete")
def delete_resource(resource: str, name: str):
    """
    Delete a deployment or service in the default namespace.
    """
    _import_kubernetes()
    try:
        # Load Kubernetes configuration
        config.load_kube_config()
        console.print("Kubernetes configuration loaded successfully.", style="bold green")
    except Exception as e:
        console.print(f"Failed to load Kubernetes configuration: {e}", style="bold red")
        return

    if resource == "deployment":
        delete_deployment(name)
    elif resource == "service":
        delete_service(name)
    else:
        console.print(f"Unsupported resource type: {resource}", style="bold red")

def delete_deployment(name: str):
    _import_kubernetes()
    apps_v1 = client.AppsV1Api()
    try:
        apps_v1.delete_namespaced_deployment(name=name, namespace="default")
        console.print(f"Deleted deployment '{name}'", style="bold yellow")
    except client.exceptions.ApiException as e:
        console.print(f"Failed to delete deployment '{name}': {e}", style="bold red")

def delete_service(name: str):
    _import_kubernetes()
    core_v1 = client.CoreV1Api()
    try:
        core_v1.delete_namespaced_service(name=name, namespace="default")
        console.print(f"Deleted service '{name}'", style="bold yellow")
    except client.exceptions.ApiException as e:
        console.print(f"Failed to delete service '{name}': {e}", style="bold red")


def list_clusters():
    _import_kubernetes()
    contexts, current_context = config.list_kube_config_contexts()

    table = Table(title="Kubernetes Clusters Configured")
    table.add_column("Context Name", justify="left", style="cyan", no_wrap=True)
    table.add_column("Cluster Name", justify="left", style="magenta")
    table.add_column("Current", justify="center", style="green")

    for context in contexts:
        context_name = context['name']
        cluster_name = context['context']['cluster']
        is_current = "Yes" if context_name == current_context['name'] else "No"
        table.add_row(context_name, cluster_name, is_current)

    console.print(table)

def switch_context(context_name: str):
    _import_kubernetes()
    with open(KUBE_CONFIG_PATH, 'r') as stream:
        kubeconfig = yaml.safe_load(stream)

    context_names = [context['name'] for context in kubeconfig['contexts']]
    if context_name not in context_names:
        console.print(f"Cluster context '{context_name}' not found.", style="bold red")
        return

    kubeconfig['current-context'] = context_name

    with open(KUBE_CONFIG_PATH, 'w') as stream:
        yaml.safe_dump(kubeconfig, stream)

    console.print(f"Switched to cluster context '{context_name}'", style="bold green")

@typer_app.command(name="cluster")
def cluster(context_name: str = typer.Argument(None, help="Name of the cluster context to switch to")):
    """
    List all Kubernetes clusters configured in the kubeconfig file or switch to a specified cluster.
    """
    _import_kubernetes()
    try:
        # Load kubeconfig
        config.load_kube_config()
        console.print("Kubernetes configuration loaded successfully.", style="bold green")
    except Exception as e:
        console.print(f"Failed to load Kubernetes configuration: {e}", style="bold red")
        return

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
    start_time = time.time()
    steps = []
    temp_dir = ProjectDir.TEMP_DIR.value
    config_dir = ProjectDir.CONFIG_DIR.value

    # Display arguments passed
    arguments = {
        "Model ID": model_id,
        "Docker File": docker_file,
        "App Name": app_name,
        "Cloud Prefix": cloud_prefix,
        "Registry ID": registry_id,
        "Tag": tag,
        "Verbose": verbose,
        "Force Build": force_build
    }

    arguments_text = "\n".join([f"{key}: {value}" for key, value in arguments.items()])
    console.print(arguments_text, style="bold blue")

    os.makedirs(temp_dir, exist_ok=True)

    # Generate the model serving code
    model_code = f"""
from transformers import pipeline
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import torch

app = FastAPI()
model = pipeline("text-generation", model="{model_id}")

class TextRequest(BaseModel):
    text: str
    max_length: int = 50

@app.post("/generate")
def generate_text(request: TextRequest):
    try:
        result = model(request.text, max_length=request.max_length)
        return {{"generated_text": result[0]["generated_text"]}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    """

    # Write model code to temp directory
    with open(os.path.join(temp_dir, "main.py"), "w") as f:
        f.write(model_code)
    steps.append("Generated model serving code")

    # Create requirements.txt
    requirements = [
        "fastapi",
        "uvicorn",
        "torch",
        "transformers",
        "pydantic"
    ]
    with open(os.path.join(temp_dir, "requirements.txt"), "w") as f:
        f.write("\n".join(requirements))
    steps.append("Created requirements.txt")

    with console.status("[bold green]Checking Dockerfile..."):
        if not os.path.isfile(docker_file):
            log_error(f"Dockerfile '{docker_file}' not found.")
            return
        steps.append("Checked Dockerfile.")

    with console.status("[bold green]Copying Dockerfile..."):
        shutil.copy(docker_file, os.path.join(temp_dir, os.path.basename(docker_file)))
        steps.append("Copied Dockerfile to temporary directory.")

    os.makedirs(config_dir, exist_ok=True)
    image_json_path = os.path.join(config_dir, "configs.json")

    if force_build and os.path.exists(image_json_path):
        os.remove(image_json_path)
        console.print("Existing image configuration cleared due to force build.", style="bold yellow")
        steps.append("Force build option applied.")

    existing_app_name = None
    if os.path.exists(image_json_path):
        with open(image_json_path, "r") as json_file:
            try:
                json_content = json.load(json_file)
                existing_app_name = json_content.get("image_name")
                if existing_app_name:
                    console.print(f"Using existing Docker image name: '{existing_app_name}'", style="bold blue")
            except json.JSONDecodeError as e:
                log_error(f"Error reading JSON file: {e}")

    if existing_app_name and not force_build:
        docker_image_name = existing_app_name
        steps.append(f"Using existing app name from JSON: {docker_image_name}")
    else:
        if not app_name:
            app_name = f"model-{model_id.replace('/', '-').lower()}"
            steps.append(f"Generated model-based app name: {app_name}")
        if cloud_prefix:
            steps.append(f"Prefixed app name: {app_name}")
            docker_image_name = f"{cloud_prefix.lower()}/{registry_id}/{app_name.lower()}:{tag}"
        else:
            docker_image_name = f"okik.cloud/{registry_id}/{app_name.lower()}:{tag}"
        steps.append(f"Formatted Docker image name: {docker_image_name}")

        with open(image_json_path, "w") as json_file:
            json.dump({"image_name": docker_image_name, "app_name": app_name}, json_file)
        steps.append("Preserved image name in JSON file.")

    # Enable Docker BuildKit for faster & more efficient builds
    build_base_cmd = "docker build --no-cache" if force_build else "docker build"
    build_command = f"DOCKER_BUILDKIT=1 {build_base_cmd} -t {docker_image_name} -f {os.path.join(docker_file)} {temp_dir}"
    build_success = False

    # ------------------------------
    # Docker build with layer bar 🔨
    # ------------------------------
    progress_build = Progress(
        SpinnerColumn(style="cyan"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=None),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    )

    with progress_build:
        task_id = None
        last_completed = 0

        process = subprocess.Popen(build_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True)

        for raw_line in iter(process.stdout.readline, ''):
            line = raw_line.strip()

            # Detect "Step X/Y : ..." lines to track progress
            if line.startswith("Step "):
                match = re.match(r"Step\s+(\d+)/(\d+)\s*:\s*(.*)", line)
                if match:
                    current_step = int(match.group(1))
                    total_steps = int(match.group(2))
                    description = match.group(3) or "Building"

                    # Initialise progress task once we know total steps
                    if task_id is None:
                        task_id = progress_build.add_task("Building Docker image", total=total_steps)

                    # Advance only if new steps discovered (avoid rewinding on multi-stage noise)
                    if current_step > last_completed:
                        progress_build.update(task_id, completed=current_step, description=f"{description} ({current_step}/{total_steps})")
                        last_completed = current_step

                    steps.append(line)
                else:
                    # Fallback when regex doesn't match but still starts with Step
                    progress_build.console.log(line)

            elif verbose:
                progress_build.console.log(line)

        process.stdout.close()
        return_code = process.wait()
        build_success = return_code == 0

        if task_id is not None:
            progress_build.update(task_id, description="Build complete" if build_success else "Build failed")

        if build_success:
            steps.append(f"Built Docker image '{docker_image_name}'.")
        else:
            steps.append(f"Failed to build Docker image '{docker_image_name}'.")

    with console.status("[bold green]Cleaning up temporary directory..."):
        shutil.rmtree(temp_dir)
        steps.append("Cleaned up temporary directory.")

    end_time = time.time()
    elapsed_time = end_time - start_time

    if build_success:
        steps.append(f"Docker image for model {model_id} built successfully in {elapsed_time:.2f} seconds.")
        log_success(f"Docker image '{docker_image_name}' built successfully in {elapsed_time:.2f} seconds.")
        console.print("\nTo run the model server:", style="bold green")
        console.print(f"docker run -p 8000:80 {docker_image_name}")
        console.print("\nTo test the API:", style="bold green")
        console.print("curl -X POST http://localhost:8000/generate -H 'Content-Type: application/json' -d '{\"text\":\"Hello, how are\"}'")
    else:
        steps.append(f"Docker image build failed after {elapsed_time:.2f} seconds.")
        log_error(f"Docker image '{docker_image_name}' build failed after {elapsed_time:.2f} seconds.")

    for step in steps:
        console.print(step, style="bold green" if build_success else "bold red")

if __name__ == "__main__":
    if len(sys.argv) == 1:
        ascii_art = text2art("Okik", font="block")  # Generate ASCII art
        console.print(ascii_art, style="bold green")  # Print in bold green color
        typer_app()
    else:
        typer_app()
