from setuptools import setup, find_packages
from version import __version__

# Read requirements.txt and store contents in a list
with open("./requirements.txt") as f:
    required = f.read().splitlines()

setup(
    name="okik",
    version=__version__,
    packages=find_packages(),
    author="Okik",
    author_email="akash@okik.co.uk",
    description="A Python package to serve python functions, classes, or .py files on a local server or cloud-based environment.",
    # Add the Typer CLI as an entry point
    entry_points={
        "console_scripts": [
            "okik=okik.main:typer_app",
        ],
    },
    install_requires=['fastapi', required],
    classifiers=[
        "Programming Language :: Python :: 3.11",
    ],
)
