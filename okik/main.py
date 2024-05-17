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

    # Execute the command and allow output to go directly to the console
    try:
        process = subprocess.Popen(
            command, shell=True
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
        log_error(stderr.decode() if stderr else "No error details available.")

    log_info("Server stopped.")


@typer_app.command()
def deploy_instance(
    name: str = typer.Option(..., help="Name of the instance"),
    platform: str = typer.Option(..., help="Platform type, e.g., 'standard-v2'"),
    zone: str = typer.Option(..., help="Zone in which the instance is to be created"),
    subnet_name: str = typer.Option(..., help="Subnet name for the network interface"),
    nat_ip_version: str = typer.Option(..., help="NAT IP version, e.g., 'ipv4'"),
    image_folder_id: str = typer.Option(..., help="ID of the image folder"),
    image_family: str = typer.Option(..., help="Image family, e.g., 'centos-7'"),
    ssh_key_path: str = typer.Option(..., help="Path to the SSH key file"),
):
    """
    Deploy a compute instance with the specified parameters.
    """
    ssh_key_path = os.path.expanduser(ssh_key_path)
    command = [
        "ncp",
        "compute",
        "instance",
        "create",
        "--name",
        name,
        "--platform",
        platform,
        "--zone",
        zone,
        "--network-interface",
        f"subnet-name={subnet_name},nat-ip-version={nat_ip_version}",
        "--create-boot-disk",
        f"image-folder-id={image_folder_id},image-family={image_family}",
        "--ssh-key",
        ssh_key_path,
    ]

    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode == 0:
        log_success("Instance created successfully.")
    else:
        log_error("Failed to create instance.")
        log_error(f"Error: {result.stderr}")


@typer_app.command()
def deploy():
    """
    Deploy the application to the cloud.
    """
    services_dir = ".okik/services"
    service_files = [f for f in os.listdir(services_dir) if f.endswith(".yaml")]
    if not service_files:
        console.print("No service files found in the directory.")
        return

    console.print("Please select a service to deploy:", style="bold")
    table = Table(title="Services")
    table.add_column("Index", style="cyan")
    table.add_column("Name", style="magenta")
    table.add_column("YAML File Location", style="green")
    for i, service_file in enumerate(service_files, start=1):
        table.add_row(str(i), service_file, os.path.join(services_dir, service_file))
    console.print(table)

    service_number = input("Enter the number of the service: ")
    if service_number.isdigit() and 1 <= int(service_number) <= len(service_files):
        service_file = service_files[int(service_number) - 1]
        config_file = os.path.join(services_dir, service_file)
        asyncio.run(run_launch(config_file))
    else:
        console.print("Invalid service number.")
        return


async def run_launch(config_file):
    log_info(f"Preparing to deploy the service to the cloud...")

    command = f"sky launch -c runpod_main {config_file}"
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
            log_start("Service deployed successfully!")
        else:
            console.print(
                f"Deployment of service failed with exit code: {process.returncode}",
                style="bold red",
            )

    except Exception as e:
        log_error(f"An error occurred during deployment: {str(e)}")



# @typer_app.command()
# def apply(
#     file_path: str = typer.Option(None, "--file", "-f", help="Path to the Python file")
# ):
#     """
#     Apply service YAML files to deploy the application to the cloud.
#     """
#     log_start("Applying the configuration files...")

#     if file_path is None:
#         file_path = os.path.join(os.getcwd(), "main.py")

#     try:
#         # Load the user-provided file
#         if not os.path.isfile(file_path):
#             raise FileNotFoundError(f"File '{file_path}' not found.")
#         with open(file_path, "r") as file:
#             code = file.read()

#         # Execute the user-provided code
#         exec(code, globals())

#         # Find all classes decorated with @service
#         service_classes = [
#             obj
#             for obj in globals().values()
#             if isinstance(obj, type) and hasattr(obj, "_service_params")
#         ]

#         # Create the .okik/services/ directory if it doesn't exist
#         os.makedirs(".okik/services", exist_ok=True)

#         processed_classes = set()
#         created_files = []

#         for cls in service_classes:
#             if cls not in processed_classes:
#                 yaml_file = generate_service_yaml_file(cls)
#                 processed_classes.add(cls)

#                 # Get the YAML file path
#                 yaml_file_name = f"{cls.__name__.lower()}.yaml"
#                 yaml_file_path = os.path.join(".okik/services", yaml_file_name)

#                 # Get the status of the file
#                 status = get_file_status(
#                     yaml_file_path
#                 )  # This function needs to be implemented
#                 status_color = get_status_color(
#                     status
#                 )  # This function needs to be implemented

#                 created_files.append(
#                     (cls.__name__, yaml_file_path, status, status_color)
#                 )

#         if not created_files:
#             log_info("No configurations found to apply YAML files.")
#             return

#         # Create a table to display the created files, class names and status
#         table = Table(title="Applied Files")
#         table.add_column("Class Name", style="cyan")
#         table.add_column("YAML File", style="magenta")
#         table.add_column("Status", style="yellow")

#         for class_name, yaml_file, status, status_color in created_files:
#             table.add_row(
#                 class_name, yaml_file, f"[{status_color}]{status}[/{status_color}]"
#             )

#         console.print(table)
#         log_success("Configs applied successfully!")

#     except FileNotFoundError:
#         log_error(f"File '{file_path}' not found.")
#     except Exception as e:
#         log_error(f"An error occurred: {str(e)}")


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
    table.add_column("Status", style="yellow")

    for yaml_file in yaml_files:
        file_path = os.path.join(services_dir, yaml_file)
        status = get_file_status(file_path)  # This function needs to be implemented
        status_color = get_status_color(status)  # This function needs to be implemented
        table.add_row(
            yaml_file, file_path, f"[{status_color}]{status}[/{status_color}]"
        )

    console.print(table)


def get_file_status(file_path: str) -> str:
    """
    Check if the file exists and return a status string.
    """
    if os.path.exists(file_path):
        return "Exists"
    else:
        return "Does not exist"


def get_status_color(status: str) -> str:
    """
    Return a color string based on the status.
    """
    if status == "Exists":
        return "green"
    else:
        return "red"


if __name__ == "__main__":
    if len(sys.argv) == 1:
        ascii_art = text2art("Okik", font="block")  # Generate ASCII art
        console.print(ascii_art, style="bold green")  # Print in bold green color
        typer_app()
    else:
        typer_app()
