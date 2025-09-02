# Kortix Project Overview

This document provides a comprehensive overview of the Kortix project, its architecture, and instructions for building, running, and developing the application.

## Project Overview

Kortix is an open-source platform for building, managing, and training AI agents. It provides a complete ecosystem for creating autonomous AI agents that can perform a wide range of tasks, from general-purpose assistance to specialized automation.

The platform consists of four main components:

*   **Backend API:** A Python/FastAPI service that powers the agent platform with REST endpoints, thread management, agent orchestration, and LLM integration.
*   **Frontend Dashboard:** A Next.js/React application that provides a comprehensive interface for managing agents, including chat interfaces, configuration dashboards, and workflow builders.
*   **Agent Runtime:** Isolated Docker execution environments for each agent instance, providing browser automation, code interpretation, file system access, and tool integration.
*   **Database & Storage:** A Supabase-powered data layer for authentication, user management, agent configurations, and conversation history.

## Building and Running

The Kortix platform can be run using either Docker or a manual setup.

### Docker Setup (Recommended)

The recommended way to run the platform is by using the provided `docker-compose.yaml` file.

**1. Start the Platform:**

```bash
python start.py
```

This command will start all the services in the background, including the backend, frontend, worker, and Redis.

**2. Stop the Platform:**

```bash
python start.py
```

Running the `start.py` script again will stop all the running services.

### Manual Setup

For advanced users who prefer to run the services manually, the following steps are required:

**1. Start Infrastructure:**

```bash
docker compose up redis -d
```

**2. Start Frontend:**

In a new terminal, navigate to the `frontend` directory and run:

```bash
npm run dev
```

**3. Start Backend:**

In a new terminal, navigate to the `backend` directory and run:

```bash
uv run api.py
```

**4. Start Background Worker:**

In a new terminal, navigate to the `backend` directory and run:

```bash
uv run dramatiq run_agent_background
```

Once all the services are running, the Kortix platform will be accessible at `http://localhost:3000`.

## Development Conventions

### Backend

The backend is a Python/FastAPI application. Key development conventions include:

*   **Dependency Management:** Dependencies are managed using `pyproject.toml`.
*   **Code Style:** The project uses `black` for code formatting and `ruff` for linting.
*   **Testing:** Tests are written using `pytest` and can be run with the `pytest` command.

### Frontend

The frontend is a Next.js/React application written in TypeScript. Key development conventions include:

*   **Dependency Management:** Dependencies are managed using `package.json`.
*   **Code Style:** The project uses `prettier` for code formatting and `eslint` for linting.
*   **Styling:** The project uses `tailwindcss` for styling.
*   **Component Library:** The project uses `shadcn/ui` for its component library.
*   **State Management:** The project uses `zustand` for state management.
*   **Data Fetching:** The project uses `@tanstack/react-query` for data fetching.
