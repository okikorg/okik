import os
import pyfiglet
import shutil
import typer
from art import text2art
import sys
import asyncio
from .endpoints import generate_service_yaml_file, create_route_handlers

from rich.console import Console
from rich.table import Table

from okik.logger import log_error, log_running, log_start, log_success
from okik.version import __version__


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
    console.print("Initializing the project..", style="bold green")


@typer_app.command()
def check():
    """
    Check if the project is ready to be deployed.
    """
    console.print("Checking the project and deployments..", style="bold green")


@typer_app.command()
def build(
    entry_point: str = typer.Option(
        "main.py", "--entry-point", "-e", help="Entry point file"
    ),
    docker_file: str = typer.Option(
        "Dockerfile", "--docker-file", "-d", help="Dockerfile name"
    ),
    app_name: str = typer.Option(
        "okik-app", "--app-name", "-a", help="Name of the Docker image"
    ),
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

    # Generate the Dockerfile content
    dockerfile_content = f"""
    FROM python:3.9

    WORKDIR /app

    COPY {os.path.basename(entry_point)} .
    COPY requirements.txt .

    RUN pip install --no-cache-dir -r requirements.txt

    CMD ["uvicorn", "okik:app", "--host", "0.0.0.0", "--port", "80"]
    """

    # Write the Dockerfile to the temporary directory
    log_running(f"Writing Dockerfile to temporary directory")
    with open(os.path.join(temp_dir, docker_file), "w") as f:
        f.write(dockerfile_content)

    # Copy the requirements.txt file to the temporary directory
    log_running(f"Copying requirements.txt file to temporary directory")
    shutil.copy("requirements.txt", os.path.join(temp_dir, "requirements.txt"))

    # Build the Docker image
    log_start(f"Building the Docker image '{app_name}'")
    os.system(
        f"docker build -t {app_name} -f {os.path.join(temp_dir, docker_file)} {temp_dir}"
    )

    # Clean up the temporary directory
    log_running(f"Cleaning up temporary directory")
    shutil.rmtree(temp_dir)

    log_success(f"Docker image '{app_name}' built successfully.")


@typer_app.command()
def serve(
    entry_point: str = typer.Option(
        "main.py", "--entry-point", "-e", help="Entry point file"
    ),
):
    """
    Serve the python function, classes, or .py file on a local server or cloud-based environment.
    """
    log_start(f"Serving the application with entry point: {entry_point}")

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

    # Run the server with the specified entry point file
    os.system(
        f"uvicorn {os.path.splitext(entry_point)[0]}:app --host 0.0.0.0 --port 3000 --reload"
    )


@typer_app.command()
def launch(
    cluster_name: str = typer.Option(
        ..., "--cluster", "-c", help="Name of the cluster"
    ),
    config_file: str = typer.Option(
        ..., "--config", "-f", help="Configuration file (.yaml)"
    ),
):
    """
    Deploy the application to the cloud.
    """
    asyncio.run(run_launch(cluster_name, config_file))


async def run_launch(cluster_name, config_file):
    console.print(
        "Preparing to deploy the application to the cloud...", style="bold blue"
    )

    # Build the command
    command = f"sky launch -c {cluster_name} {config_file}"
    console.print(f"Running command: {command}", style="bold blue")

    try:
        # Execute the sky launch command with the provided cluster name and configuration file
        process = await asyncio.create_subprocess_shell(
            command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=10
            )  # Timeout after 180 seconds
        except asyncio.TimeoutError:
            console.print("Deployment process timed out.", style="bold red")
            process.kill()
            stdout, stderr = await process.communicate()

        if process.returncode == 0:
            console.print("Application deployed successfully!", style="bold green")
            console.print(stdout.decode("utf-8"))
        else:
            console.print("Deployment failed.", style="bold red")
            console.print(stderr.decode("utf-8"))

    except Exception as e:
        console.print(
            f"An error occurred during deployment: {str(e)}", style="bold red"
        )


@typer_app.command()
def create(
    file_path: str = typer.Option(
        "main.py", "--file", "-f", help="Path to the Python file"
    )
):
    """
    Create service YAML files to deploy the application to the cloud.
    """
    console = Console()
    console.print("Creating the configuration files...", style="bold green")

    try:
        # Load the user-provided file
        with open(file_path, "r") as file:
            code = file.read()

        # Execute the user-provided code
        exec(code, globals())

        # Find all classes decorated with @service
        service_classes = [
            obj
            for obj in globals().values()
            if isinstance(obj, type) and hasattr(obj, "_service_params")
        ]

        # Create the .okik/services/ directory if it doesn't exist
        os.makedirs(".okik/services", exist_ok=True)

        processed_classes = set()
        created_files = []

        for cls in service_classes:
            if cls not in processed_classes:
                yaml_file = generate_service_yaml_file(cls)
                processed_classes.add(cls)

                # Get the YAML file path
                yaml_file_name = f"{cls.__name__.lower()}.yaml"
                yaml_file_path = os.path.join(".okik/services", yaml_file_name)

                created_files.append((cls.__name__, yaml_file_path))

        # Create a table to display the created files and class names
        table = Table(title="Created Files", show_header=True, header_style="bold")
        table.add_column("Class Name", style="cyan")
        table.add_column("YAML File", style="magenta")

        for class_name, yaml_file in created_files:
            table.add_row(class_name, yaml_file)

        console.print(table)
        console.print("Configs created successfully!", style="bold green")

    except FileNotFoundError:
        console.print(f"File '{file_path}' not found.", style="bold red")
    except Exception as e:
        console.print(f"An error occurred: {str(e)}", style="bold red")


@typer_app.command()
def show_config(
    services_dir: str = typer.Option(
        ".okik/services", "--dir", "-d", help="Directory containing the YAML files"
    )
):
    """
    Display all the YAML files stored in the specified directory.
    """
    console = Console()

    if not os.path.exists(services_dir):
        console.print(f"Directory '{services_dir}' not found.", style="bold red")
        return

    yaml_files = [file for file in os.listdir(services_dir) if file.endswith(".yaml")]

    if not yaml_files:
        console.print(
            "No YAML files found in the specified directory.", style="bold yellow"
        )
        return

    table = Table(title="YAML Files", show_header=True, header_style="bold")
    table.add_column("File Name", style="cyan")
    table.add_column("File Path", style="magenta")

    for yaml_file in yaml_files:
        file_path = os.path.join(services_dir, yaml_file)
        table.add_row(yaml_file, file_path)

    console.print(table)


@typer_app.command()
def version():
    """
    Display the version of the package.
    """
    console.print(f"[bold green] version: [bold red]{__version__}")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        ascii_art = text2art("Okik", font="block")  # Generate ASCII art
        console.print(ascii_art, style="bold green")  # Print in bold green color
        typer_app()
    else:
        typer_app()
