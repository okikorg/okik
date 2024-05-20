def python_dockerfile(image_name: str):
    return f"""
# Use an official Python runtime as a parent image
FROM python:latest

# Set the working directory in the container
WORKDIR /app

# Install git
RUN apt-get update && apt-get install -y git

# Copy the current directory contents into the container at /app
COPY . /app

# Install okik and its dependencies
RUN pip install --upgrade pip
RUN git clone https://github.com/okikorg/okik.git
RUN pip install ./okik
RUN pip install numpy
RUN export PATH="$HOME/.local/bin:$PATH"
RUN apt-get clean && rm -rf /var/lib/apt/lists/*
RUN okik --help
RUN okik init
RUN mkdir -p /app/.okik/services

# Upgrade pip and install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 3000

# Run okik app
CMD ["okik", "server"]
    """
