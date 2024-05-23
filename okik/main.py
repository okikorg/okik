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

# Initialize Typer app
typer_app = typer.Typer()
# Initialize Rich console
console = Console()


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

@typer_app.command(name="mock-deploy")
def deploy(
    entry_point: str = typer.Option(
        "main.py", "--entry-point", "-e", help="Entry point file"
    )
):
    """
    Deploy the application to a cloud or cluster.
    Warning: This is just a mockup
    """
    services_dir = f'{ProjectDir.SERVICES_DIR.value}/okik'
    yaml_files = [f for f in os.listdir(services_dir) if f.endswith('.yaml') or f.endswith('.yml')]

    if not yaml_files:
        console.print("No YAML configuration files found in the services directory.", style="bold red")
        return

    for yaml_file in yaml_files:
        yaml_path = os.path.join(services_dir, yaml_file)
        with open(yaml_path, 'r') as file:
            try:
                yaml_content = yaml.safe_load(file)
                yaml_content_neat = "\n".join([f"{key}: {value}" for key, value in yaml_content.items()])
                panel = Panel(Text(yaml_content_neat, justify="left"), title=f"YAML Configuration: {yaml_file}", border_style="blue")
                console.print(panel)
            except yaml.YAMLError as exc:
                console.print(f"Error parsing YAML file '{yaml_file}': {exc}", style="bold red")
                continue

    answer = typer.confirm("Do you want to continue with the deployment?")
    # Mock deployment process with async sleep
    if answer:
        with Progress() as progress:
            task = progress.add_task("Deploying...", total=100)
            for i in range(100):
                progress.update(task, advance=1)
                time.sleep(0.05)
        console.print("Deployment completed successfully!", style="bold green")

    if not answer:
        typer.echo("Deployment stopped by the user.")
        raise typer.Exit()

# mock show deployment
@typer_app.command("mock-show-deployment")
def show_deployment():
    """
    Show the deployment status of the application.
    """
    with Progress() as progress:
        task = progress.add_task("Fetching deployment status...", total=100)
        for i in range(100):
            progress.update(task, advance=1)
            time.sleep(0.05)
    console.print("Deployment status: [bold green]Running[/bold green]")

if __name__ == "__main__":
    if len(sys.argv) == 1:
        ascii_art = text2art("Okik", font="block")  # Generate ASCII art
        console.print(ascii_art, style="bold green")  # Print in bold green color
        typer_app()
    else:
        typer_app()
