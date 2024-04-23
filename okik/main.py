import os
import pyfiglet
import shutil
import typer
from art import text2art
import subprocess
import sys
import asyncio
from .endpoints import generate_service_yaml_file

from rich.console import Console
from rich.table import Table

from okik.logger import log_error, log_running, log_start, log_success, log_info
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
    log_start("Initializing the project..")


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

    # Prepare the uvicorn command
    module_name = os.path.splitext(entry_point)[0]
    reload_command = "--reload" if reload else ""
    command = f"uvicorn {module_name}:app --host {host} --port {port} {reload_command}"

    # Execute the command while suppressing the direct output
    try:
        process = subprocess.Popen(
            command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        log_start("Server running. Press CTRL+C to stop.")
        log_info(f"Host: {host}, Port: {port}")
        log_info(f"Auto-reload: {'Enabled' if reload else 'Disabled'}")
        log_info(
            f'Open "http://{host}:{port}/docs" in your browser to view the API documentation and run test requests.'
        )
        # listening to
        log_info(f"Listening to http://{host}:{port}")
        stdout, stderr = process.communicate()
    except Exception as e:
        log_error(f"Failed to start the server: {str(e)}")
        return

    if process.returncode != 0:
        log_error("Server stopped with errors.")
        log_error(stderr.decode())

    log_info("Server stopped.")


@typer_app.command()
def serve(
    cluster_name: str = typer.Option(..., "--name", "-n", help="Name of the service"),
    config_file: str = typer.Option(
        ..., "--config", "-c", help="Configuration file (.yaml)"
    ),
):
    """
    Deploy the application to the cloud.
    """
    asyncio.run(run_launch(cluster_name, config_file))


async def run_launch(cluster_name, config_file):
    log_info("Preparing to deploy the application to the cloud...")

    # Ensure the config file path is correctly formatted
    corrected_config_file = f"./{config_file}"
    command = f"sky launch -c {cluster_name} {corrected_config_file}"
    log_start(f"Running command: {command}")

    try:
        process = await asyncio.create_subprocess_shell(
            command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        # Read output continuously to avoid buffer overflow
        while True:
            output = await process.stdout.readline()  # type: ignore
            if output == b"":
                break
            console.print(output.decode().strip())

        # Check for errors
        stderr_output = await process.stderr.read()  # type: ignore
        if stderr_output:
            log_error(stderr_output.decode())

        await process.wait()
        if process.returncode == 0:
            log_start("Application deployed successfully!")
        else:
            console.print(
                "Deployment failed with exit code: {}".format(process.returncode),
                style="bold red",
            )

    except Exception as e:
        log_error(f"An error occurred during deployment: {str(e)}")


@typer_app.command()
def create(
    file_path: str = typer.Option(
        "main.py", "--file", "-f", help="Path to the Python file"
    )
):
    """
    Create service YAML files to deploy the application to the cloud.
    """
    log_start("Creating the configuration files...")

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
        table = Table(title="Created Files")
        table.add_column("Class Name", style="cyan")
        table.add_column("YAML File", style="magenta")

        for class_name, yaml_file in created_files:
            table.add_row(class_name, yaml_file)

        console.print(table)
        log_success("Configs created successfully!")

    except FileNotFoundError:
        log_error(f"File '{file_path}' not found.")
    except Exception as e:
        log_error(f"An error occurred: {str(e)}")


@typer_app.command()
def show_config(
    services_dir: str = typer.Option(
        ".okik/services", "--dir", "-d", help="Directory containing the YAML files"
    )
):
    """
    Display all the YAML files stored in the specified directory.
    """

    if not os.path.exists(services_dir):
        log_error(f"Directory '{services_dir}' not found.")
        return

    yaml_files = [file for file in os.listdir(services_dir) if file.endswith(".yaml")]

    if not yaml_files:
        log_info("No YAML files found in the specified directory.")
        return

    table = Table(title="YAML Files")
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
