# Gemini Code Assistant Context

This document provides context for the Gemini Code Assistant to understand the BahnVision project.

## Project Overview

BahnVision is a web application that provides real-time public transit information for Munich, Germany. It consists of a backend API and a frontend web application.

### Backend

The backend is a Python application built with the FastAPI framework. It provides a RESTful API for accessing transit data.

**Key Technologies:**

*   **Framework:** FastAPI
*   **Database:** PostgreSQL with SQLAlchemy and Alembic for migrations
*   **Caching:** Valkey (Redis-compatible)
*   **API Documentation:** OpenAPI (Swagger)
*   **Testing:** pytest

### Frontend

The frontend is a single-page application (SPA) built with React and TypeScript.

**Key Technologies:**

*   **Framework:** React 19
*   **Language:** TypeScript
*   **Build Tool:** Vite
*   **Styling:** Tailwind CSS
*   **Data Fetching:** TanStack Query
*   **Routing:** React Router
*   **Testing:** Vitest, React Testing Library, Playwright

## Building and Running

### Docker Compose (Recommended)

1.  Install Docker & Docker Compose.
2.  Run `docker compose up --build`.
3.  The backend API will be available at `http://127.0.0.1:8000/docs`.
4.  The frontend application will be available at `http://127.0.0.1:5173`.

### Local Development

#### Backend

1.  `python -m venv .venv && source .venv/bin/activate`
2.  `pip install -r backend/requirements.txt`
3.  Ensure Valkey and PostgreSQL are reachable.
4.  `uvicorn app.main:app --reload --app-dir backend`

#### Frontend

1.  `npm install`
2.  `npm run dev`

## Development Conventions

### Backend

*   Code is organized in a layered architecture under `backend/app`.
*   Services in `backend/app/services` encapsulate business logic.
*   The persistence layer in `backend/app/persistence` handles database interactions.
*   API endpoints are defined in `backend/app/api`.
*   Pydantic models in `backend/app/models` are used for data validation.

### Frontend

*   The project follows standard React best practices.
*   Components are located in `frontend/src/components`.
*   Pages are in `frontend/src/pages`.
*   Custom hooks are in `frontend/src/hooks`.
*   API interactions are handled in `frontend/src/services`.
*   The application uses a hybrid testing approach with Vitest, React Testing Library, and Playwright.
*   MSW is used for API mocking during development and testing.

## Commit Style Guide

This project follows the [Conventional Commits](https://www.conventionalcommits.org/) specification. The commit message should be structured as follows:

```
<type>(<scope>): <subject>

<body>
```

*   **type**: Must be one of the following:
    *   `feat`: A new feature
    *   `fix`: A bug fix
    *   `docs`: Documentation only changes
    *   `style`: Changes that do not affect the meaning of the code (white-space, formatting, missing semi-colons, etc)
    *   `refactor`: A code change that neither fixes a bug nor adds a feature
    *   `perf`: A code change that improves performance
    *   `test`: Adding missing tests or correcting existing tests
    *   `build`: Changes that affect the build system or external dependencies (example scopes: gulp, broccoli, npm)
    *   `ci`: Changes to our CI configuration files and scripts (example scopes: Travis, Circle, BrowserStack, SauceLabs)
    *   `chore`: Other changes that don't modify src or test files
    *   `revert`: Reverts a previous commit
*   **scope**: The scope should be the name of the npm package affected (as perceived by the person reading the changelog generated from the commit messages).
*   **subject**: The subject contains a succinct description of the change:
    *   use the imperative, present tense: "change" not "changed" nor "changes"
    *   don't capitalize the first letter
    *   no dot (.) at the end
*   **body**: A longer description of the changes.
