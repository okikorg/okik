import os
import pyfiglet
import shutil
import typer
from art import text2art
import subprocess
import sys
import yaml
import asyncio
import uuid
from .endpoints import generate_service_yaml_file

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from okik.logger import log_error, log_running, log_start, log_success, log_info


# Initialize Typer app
typer_app = typer.Typer()
console = Console()


@typer_app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """
    This function is called whenever the Typer app is invoked without a specific command.
    It will display the ASCII art and additional text if no sub-command is provided.
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
    Also login to the Okik cloud.
    """
    log_start("Initializing the project..")
    services_dir = ".okik/services"
    if not os.path.exists(services_dir):
        os.makedirs(services_dir)
    log_success("Services directory checked/created.")


@typer_app.command()
def check():
    """
    Check if the project is ready to be deployed.
    """
    log_start("Checking the project and deployments..")

@typer_app.command()
def build(
    entry_point: str = typer.Option(
        "main.py", "--entry_point", "-e", help="Entry point file"
    ),
    docker_file: str = typer.Option(
        ..., "--docker-file", "-d", help="Dockerfile name",
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
    Take the python function, classes, or .py file, wrap it inside a container,
    and run it on the cloud based on user's configuration.
    """
    steps = []

    with console.status("[bold green]Checking entry point file...") as status:
        if not os.path.isfile(entry_point):
            log_error(f"Entry point file '{entry_point}' not found.")
            return
        steps.append("Checked entry point file.")

    temp_dir = ".okik_temp"
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

    images_dir = ".okik/images"
    os.makedirs(images_dir, exist_ok=True)
    image_yaml_path = os.path.join(images_dir, "images.yaml")

    if force_build and os.path.exists(image_yaml_path):
        os.remove(image_yaml_path)
        console.print("Existing image name cleared due to force build.", style="bold red")

    existing_app_name = None
    if os.path.exists(image_yaml_path):
        with open(image_yaml_path, "r") as yaml_file:
            try:
                yaml_content = yaml.safe_load(yaml_file)
                existing_app_name = yaml_content.get("image_name")
                if existing_app_name:
                    console.print(f"Warning: Existing Docker image '{existing_app_name}' will be overwritten.", style="bold red")
            except yaml.YAMLError as e:
                log_error(f"Error reading YAML file: {e}")

    if existing_app_name:
        docker_image_name = existing_app_name
        steps.append(f"Using existing app name from YAML: {docker_image_name}")
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

        # Preserve image name in YAML file
        with open(image_yaml_path, "w") as yaml_file:
            yaml.dump({"image_name": docker_image_name}, yaml_file)
        steps.append("Preserved image name in YAML file.")

    build_command = f"docker build -t {docker_image_name} -f {os.path.join(temp_dir, docker_file)} {temp_dir}"
    with console.status("[bold green]Building Docker image...") as status:
        if verbose:
            process = subprocess.Popen(build_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    console.print(output.strip())
            stderr = process.stderr.read()
            if stderr:
                console.print(stderr, style="bold red")
        else:
            subprocess.run(build_command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        steps.append(f"Built Docker image '{docker_image_name}'.")

    with console.status("[bold green]Cleaning up temporary directory...") as status:
        shutil.rmtree(temp_dir)
        steps.append("Cleaned up temporary directory.")

    steps.append(f"Docker image '{docker_image_name}' built successfully.")
    log_success(f"Docker image '{docker_image_name}' built successfully.")

    # Prompt the user to build the image with more details with --verbose flag
    steps.append("Build the image with more details using the --verbose flag if you want to see more details.")

    # Display all steps inside a panel
    steps_text = "\n".join(steps)
    panel = Panel(Text(steps_text, justify="left"), title="Build Process Steps", border_style="green")
    console.print(panel)

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
    Serve the python function, classes, or .py file on a local server or cloud-based environment.
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

if __name__ == "__main__":
    if len(sys.argv) == 1:
        ascii_art = text2art("Okik", font="block")  # Generate ASCII art
        console.print(ascii_art, style="bold green")  # Print in bold green color
        typer_app()
    else:
        typer_app()
