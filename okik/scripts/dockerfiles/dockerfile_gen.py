dockerfile_content = """
# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install git
RUN apt-get update && apt-get install -y git

# Copy the current directory contents into the container at /app
COPY . /app

# Install okik and its dependencies
RUN pip install --upgrade pip
# create a virtual environment
RUN python3 -m venv venv
# activate the virtual environment
RUN . venv/bin/activate
# install okik
RUN echo "Installing okik"
RUN pip install -U okik
# install okik cli
RUN echo "Installing okik cli"
RUN export PATH="$HOME/.local/bin:$PATH"
RUN apt-get clean && rm -rf /var/lib/apt/lists/*
# verify installation
RUN echo "Verifying installation"
RUN which okik
# initialise okik
RUN okik init

# Upgrade pip and install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 3000

# Run okik app
CMD ["okik", "server", "-r", "-d"]
"""


dockerfile_content_uv_install = """
# Use an official Python runtime as a parent image
FROM python:3.12-slim-bullseye

# The installer requires curl (and certificates) to download the release archive
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates git

# Download the latest installer
ADD https://astral.sh/uv/install.sh /uv-installer.sh

# Run the installer then remove it
RUN sh /uv-installer.sh && rm /uv-installer.sh

# Ensure the installed binary is on the `PATH`
ENV PATH="/root/.cargo/bin/:$PATH"

# Set the working directory in the container
WORKDIR /app
# Copy the current directory contents into the container at /app
COPY . /app

# Sync the project into a new environment
ENV UV_SYSTEM_PYTHON=1

RUN uv venv /opt/venv
# Use the virtual environment automatically
ENV VIRTUAL_ENV=/opt/venv
# Place entry points in the environment at the front of the path
ENV PATH="/opt/venv/bin:$PATH"

COPY . .
RUN uv pip install -r requirements.txt

# install okik
RUN echo "Installing okik"
RUN uv add okik
# install okik cli
RUN echo "Installing okik cli"
RUN export PATH="$HOME/.local/bin:$PATH"
RUN apt-get clean && rm -rf /var/lib/apt/lists/*
# initialise okik
RUN okik init

# Upgrade pip and install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 3000

# Run okik app
CMD ["okik", "server", "-r", "-d"]
"""

def create_dockerfile(path, name:str = "Dockerfile"):
    with open(f"{path}/{name}", 'w') as file:
        file.write(dockerfile_content)
