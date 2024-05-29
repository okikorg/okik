import logging
from rich.console import Console
from rich.logging import RichHandler
from logging.handlers import RotatingFileHandler

LOGFORMAT = "%(message)s"

# Set up Rich console for rich logging
console = Console()
error_console = Console(stderr=True, force_terminal=True)

# Set up a specific logger with our desired level and handler
logger = logging.getLogger("okik")
logger.setLevel(logging.INFO)
logger.propagate = (
    False  # This prevents the log messages from being propagated to the root logger
)

# Define our handlers
rich_handler = RichHandler(console=console, markup=True, rich_tracebacks=True)
file_handler = RotatingFileHandler(
    ".okik.log", maxBytes=1024 * 1024 * 10, backupCount=10  # 10 MB
)

# Setting the format for handlers
rich_handler.setFormatter(logging.Formatter(LOGFORMAT))
file_handler.setFormatter(logging.Formatter(LOGFORMAT))

# Adding handlers to our logger
logger.addHandler(rich_handler)
logger.addHandler(file_handler)


# Logging functions
def log_start(message: str):
    logger.info(f"[bold green]Starting: {message}[/bold green]")


def log_running(message: str):
    logger.info(f"[bold blue]Running: {message}[/bold blue]")


def log_success(message: str):
    logger.info(f"[bold green]Success: {message}[/bold green]")


def log_error(message: str):
    logger.error(f"[bold red]Error: {message}[/bold red]")


def log_warning(message: str):
    logger.warning(f"[bold yellow]Warning: {message}[/bold yellow]")


def log_info(message: str):
    logger.info(f"[bold cyan]Info: {message}[/bold cyan]")


def log_debug(message: str):
    logger.debug(f"[bold magenta]Debug: {message}[/bold magenta]")
