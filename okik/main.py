import os
import pyfiglet
import shutil
import typer
from art import text2art
import sys


from rich.console import Console


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
def serve_dev(
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
