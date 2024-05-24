import os
import time
import pyfiglet
import shutil
from torch import backends
import typer
from art import text2art
import subprocess
import sys
import yaml
import asyncio
import uuid
import importlib
from fastapi.routing import APIRoute
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from okik.logger import log_error, log_running, log_start, log_success, log_info
from okik.consts import ProjectDir
import json
from rich.progress import Progress
from rich.tree import Tree
from okik.scripts.dockerfiles.dockerfile_gen import create_dockerfile
from kubernetes import client, config, utils
from kubernetes.client import ApiException
from rich.prompt import Prompt
from rich.prompt import Confirm
from rich.status import Status

# Initialize Typer app
typer_app = typer.Typer()
# Initialize Rich console
console = Console()

KUBE_CONFIG_PATH = os.path.expanduser("~/.kube/config")

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
    with console.status("[bold green]Initializing the project...") as status:
        # Create directories
        folders_list = [dir.value for dir in ProjectDir]
        for folder in folders_list:
            os.makedirs(folder, exist_ok=True)
            tasks[folders_list.index(folder)]["status"] = "completed"

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

    # Display arguments passed
    arguments = {
        "Entry Point": entry_point,
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

    with console.status("[bold green]Checking entry point file...") as status:
        if not os.path.isfile(entry_point):
            log_error(f"Entry point file '{entry_point}' not found.")
            return
        steps.append("Checked entry point file.")

    os.makedirs(temp_dir, exist_ok=True)

    with console.status("[bold green]Copying entry point file...") as status:
        shutil.copy(entry_point, os.path.join(temp_dir, os.path.basename(entry_point)))
        steps.append("Copied entry point file to temporary directory.")

    with console.status("[bold green]Checking Dockerfile...") as status:
        if not os.path.isfile(docker_file):
            log_error(f"Dockerfile '{docker_file}' not found.")
            return
        steps.append("Checked Dockerfile.")

    with console.status("[bold green]Copying Dockerfile...") as status:
        shutil.copy(docker_file, os.path.join(temp_dir, os.path.basename(docker_file)))
        steps.append("Copied Dockerfile to temporary directory.")

    with console.status("[bold green]Copying requirements.txt...") as status:
        shutil.copy("requirements.txt", os.path.join(temp_dir, "requirements.txt"))
        steps.append("Copied requirements.txt file to temporary directory.")

    os.makedirs(config_dir, exist_ok=True)
    image_json_path = os.path.join(config_dir, "configs.json")

    if force_build and os.path.exists(image_json_path):
        os.remove(image_json_path)
        console.print("Existing image name cleared due to force build.", style="bold red")

    existing_app_name = None
    if os.path.exists(image_json_path):
        with open(image_json_path, "r") as json_file:
            try:
                json_content = json.load(json_file)
                existing_app_name = json_content.get("image_name")
                if existing_app_name:
                    console.print(f"Warning: Existing Docker image '{existing_app_name}' will be overwritten.", style="bold red")
            except json.JSONDecodeError as e:
                log_error(f"Error reading JSON file: {e}")

    if existing_app_name:
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
            docker_image_name = f"cr.ai.nebius.cloud/{registry_id}/{app_name}:{tag}"
        steps.append(f"Formatted Docker image name: {docker_image_name}")

        # Preserve image name in JSON file
        with open(image_json_path, "w") as json_file:
            json.dump({"image_name": docker_image_name, "app_name": app_name}, json_file)
        steps.append("Preserved image name in JSON file.")

    build_command = f"docker build -t {docker_image_name} -f {os.path.join(docker_file)} {temp_dir}"
    with console.status("[bold green]Building Docker image...") as status:
        if verbose:
            process = subprocess.Popen(build_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            while True:
                output = process.stdout.readline()
                if not output and process.poll() is not None:
                    break
                if output:
                    console.print(output.strip())
            # Read any remaining output from stderr (error stream)
            stderr_output = process.stderr.readlines()
            for error in stderr_output:
                console.print(error.strip(), style="bold red")
        else:
            result = subprocess.run(build_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode != 0:
                console.print(result.stderr, style="bold red")
        steps.append(f"Built Docker image '{docker_image_name}'.")

    with console.status("[bold green]Cleaning up temporary directory...") as status:
        shutil.rmtree(temp_dir)
        steps.append("Cleaned up temporary directory.")

    end_time = time.time()
    elapsed_time = end_time - start_time
    steps.append(f"Docker image '{docker_image_name}' built successfully in {elapsed_time:.2f} seconds.")
    log_success(f"Docker image '{docker_image_name}' built successfully in {elapsed_time:.2f} seconds.")

    # Prompt the user to build the image with more details with --verbose flag
    steps.append("Build the image with more details using the --verbose flag if you want to see more details.")

    # Display all steps
    for step in steps:
        console.print(step, style="bold green")

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
):
    """
    Serve the app in development or production mode.
    """
    if dev:
        console.print(Panel(f"Serving the application with entry point: [bold]{entry_point}[/bold]", title="Okik CLI - Development mode"), style="bold yellow")
    else:
        console.print(Panel(f"Serving the application with entry point: [bold]{entry_point}[/bold]", title="Okik CLI - Production mode", style="bold green"))

    # Check if the entry point file exists
    if not os.path.isfile(entry_point):
        log_error(f"Entry point file '{entry_point}' not found.")
        return

    # Check if the user is importing the 'app' object in their code
    with open(entry_point, "r") as file:
        code = file.read()
        if "from okik import app" in code or "import okik.app" in code:
            log_error("Importing 'app' in the entry point file is not allowed.")
            return

    # Prepare the uvicorn command
    module_name = os.path.splitext(entry_point)[0]
    reload_command = "--reload" if reload and dev else ""
    command = f"uvicorn {module_name}:app --host {host} --port {port} {reload_command}"

    # Adjust command for production if not in dev mode
    if not dev:
        command += " --workers 4"

    # Execute the command and allow output to go directly to the console
    try:
        process = subprocess.Popen(
            command, shell=True
        )

        console.print(Panel(
                            f"Host: [bold]{host}[/bold]\nPort: [bold]{port}[/bold]\nAuto-reload: [bold]{'Enabled' if reload and dev else 'Disabled'}[/bold]\nEnvironment: [bold]{'Development' if dev else 'Production'}[/bold]\nListening to: [bold]http://{host}:{port}[/bold]", title="Server Details", subtitle=f"Open http://{host}:{port}/docs to view API documentation"
                            , style="bold yellow" if dev else "bold green")
                        )
        log_start("Server running. Press CTRL+C to stop.")
        log_info(f"Server listening to http://{host}:{port}")
        stdout, stderr = process.communicate()
    except Exception as e:
        log_error(f"Failed to start the server: {str(e)}")
        return

    if process.returncode != 0:
        log_error("Server stopped with errors.")
        log_error(stderr.decode() if stderr else "No error details available.")

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
    services_dir = os.path.join(ProjectDir.SERVICES_DIR.value,'k8')  # Adjusted for clarity
    yaml_files = [f for f in os.listdir(services_dir) if f.endswith('.yaml') or f.endswith('.yml')]

    if not yaml_files:
        console.print("No YAML configuration files found in the services directory.", style="bold red")
        return

    selected_file = Prompt.ask("Select a YAML file to deploy", choices=yaml_files)

    yaml_path = os.path.join(services_dir, selected_file)
    try:
        with open(yaml_path, 'r') as file:
            yaml_documents = list(yaml.safe_load_all(file))
            for index, yaml_content in enumerate(yaml_documents):
                yaml_content_neat = "\n".join([f"{key}: {value}" for key, value in yaml_content.items()])
                panel = Panel(Text(yaml_content_neat, justify="left"), title=f"YAML Configuration: {selected_file} (Document {index+1})", border_style="blue")
                console.print(panel)
    except yaml.YAMLError as exc:
        console.print(f"Error parsing YAML file '{selected_file}': {exc}", style="bold red")
        return

    if not Confirm.ask("Do you want to continue with the deployment?"):
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
        with Status("Deploying...", spinner="dots") as status:
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
                    console.print(f"To test the service, you can use the following command if you are using Minikube:")
                    console.print(f"  minikube service embedder")
                    console.print(f"Or you can port-forward the service with:")
                    console.print(f"  kubectl port-forward service/embedder 8080:80")
    except ApiException as e:
        console.print(f"Error retrieving services: {e}", style="bold red")

@typer_app.command(name="get")
def get_resources(resource: str):
    """
    Get deployments or services in the default namespace.
    """
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
    apps_v1 = client.AppsV1Api()
    try:
        deployments = apps_v1.list_namespaced_deployment(namespace="default")
        if not deployments.items:
            console.print("No deployments found in the default namespace.", style="bold yellow")
            return

        table = Table(title="Kubernetes Deployments in Default Namespace")
        table.add_column("Name", justify="left", style="cyan", no_wrap=True)
        table.add_column("Replicas", justify="right", style="magenta")
        table.add_column("Available Replicas", justify="right", style="green")

        for deployment in deployments.items:
            table.add_row(deployment.metadata.name, str(deployment.spec.replicas), str(deployment.status.available_replicas or 0))

        console.print(table)
    except client.exceptions.ApiException as e:
        console.print(f"Error listing deployments: {e}", style="bold red")

def get_services():
    core_v1 = client.CoreV1Api()
    try:
        services = core_v1.list_namespaced_service(namespace="default")
        if not services.items:
            console.print("No services found in the default namespace.", style="bold yellow")
            return

        table = Table(title="Kubernetes Services in Default Namespace")
        table.add_column("Name", justify="left", style="cyan", no_wrap=True)
        table.add_column("Type", justify="left", style="magenta")
        table.add_column("Cluster IP", justify="left", style="green")
        table.add_column("Ports", justify="left", style="blue")

        for service in services.items:
            ports = ", ".join([f"{p.port}/{p.protocol}" for p in service.spec.ports])
            table.add_row(service.metadata.name, service.spec.type, service.spec.cluster_ip, ports)

        console.print(table)
    except client.exceptions.ApiException as e:
        console.print(f"Error listing services: {e}", style="bold red")

@typer_app.command(name="delete")
def delete_resource(resource: str, name: str):
    """
    Delete a deployment or service in the default namespace.
    """
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
    apps_v1 = client.AppsV1Api()
    try:
        apps_v1.delete_namespaced_deployment(name=name, namespace="default")
        console.print(f"Deleted deployment '{name}'", style="bold yellow")
    except client.exceptions.ApiException as e:
        console.print(f"Failed to delete deployment '{name}': {e}", style="bold red")

def delete_service(name: str):
    core_v1 = client.CoreV1Api()
    try:
        core_v1.delete_namespaced_service(name=name, namespace="default")
        console.print(f"Deleted service '{name}'", style="bold yellow")
    except client.exceptions.ApiException as e:
        console.print(f"Failed to delete service '{name}': {e}", style="bold red")


def list_clusters():
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


if __name__ == "__main__":
    if len(sys.argv) == 1:
        ascii_art = text2art("Okik", font="block")  # Generate ASCII art
        console.print(ascii_art, style="bold green")  # Print in bold green color
        typer_app()
    else:
        typer_app()
