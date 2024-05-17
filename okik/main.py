import os
import pyfiglet
import shutil
import typer
from art import text2art
import subprocess
import sys
import asyncio
import uuid
from .endpoints import generate_service_yaml_file

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

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
        "main.py", "--entry-point", "-e", help="Entry point file"
    ),
    docker_file: str = typer.Option(
        ...,
        "--docker-file",
        "-d",
        help="Dockerfile name",
    ),
    app_name: str = typer.Option(
        None, "--app-name", "-a", help="Name of the Docker image"
    ),
    registry_id: str = typer.Option(None, "--registry-id", "-r", help="Registry ID"),
    tag: str = typer.Option("latest", "--tag", "-t", help="Tag for the Docker image"),
):
    """
    Take the python function, classes, or .py file, wrap it inside a container,
    and run it on the cloud based on user's configuration.
    """
    # Check if the entry point file exists
    if not os.path.isfile(entry_point):
        log_error(f"Entry point file '{entry_point}' not found.")
        return

    # Create a temporary directory
    temp_dir = ".okik_temp"
    os.makedirs(temp_dir, exist_ok=True)

    # Copy the entry point file to the temporary directory
    log_running(f"Copying entry point file to temporary directory")
    shutil.copy(entry_point, os.path.join(temp_dir, os.path.basename(entry_point)))

    # Check if the Dockerfile exists
    if not os.path.isfile(docker_file):
        log_error(f"Dockerfile '{docker_file}' not found.")
        return

    # Copy the Dockerfile to the temporary directory
    log_running(f"Copying Dockerfile to temporary directory")
    shutil.copy(docker_file, os.path.join(temp_dir, os.path.basename(docker_file)))

    # Copy the requirements.txt file to the temporary directory
    log_running(f"Copying requirements.txt file to temporary directory")
    shutil.copy("requirements.txt", os.path.join(temp_dir, "requirements.txt"))

    # If app_name is not provided, generate a unique one
    if not app_name:
        app_name = f"app-{uuid.uuid4()}"

    # Format the Docker image name
    docker_image_name = f"cr.ai.nebius.cloud/{registry_id}/{app_name}:{tag}"

    # Build the Docker image
    log_start(f"Building the Docker image '{docker_image_name}'")
    os.system(
        f"docker build -t {docker_image_name} -f {os.path.join(temp_dir, docker_file)} {temp_dir}"
    )

    # Clean up the temporary directory
    log_running(f"Cleaning up temporary directory")
    shutil.rmtree(temp_dir)

    log_success(f"Docker image '{docker_image_name}' built successfully.")

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
