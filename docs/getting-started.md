# Getting Started

This guide will walk you through setting up your development environment for the FBA Bench project.

## Prerequisites

- **Docker and Docker Compose**: Ensure you have the latest versions installed. This is essential for running the containerized services.
- **Git**: For cloning and managing the source code.
- **An IDE of your choice**: We recommend VS Code with the Docker and Python extensions.

## Local Development Setup

The provided `run` scripts (`run.sh` for macOS/Linux and `run.bat` for Windows) are the fastest way to get started. They use the `docker-compose-simple.yml` file, which is configured for a minimal, local development environment.

**What the `run` script does:**
1.  **Checks for Docker**: Verifies that Docker is installed and running.
2.  **Builds and Starts Containers**: Uses `docker-compose` to build the necessary Docker images and start the services in the correct order.
3.  **Ready to Use**: Once the script is done, the application will be accessible at `http://localhost:5173`.

## Full Environment

If you need to run the full suite of services, including ClearML for experiment tracking, you can use the `docker-compose.full.yml` file.

To start the full environment, run:
```bash
docker-compose -f docker-compose.full.yml up --build -d
