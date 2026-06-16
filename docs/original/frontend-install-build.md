# Frontend Install and Build

The frontend now lives inside this backend repository:

```text
NERD-Explains-Reviews-and-Drills/frontend
```

## Prerequisites

- Node.js 18 or newer.
- npm, bundled with Node.js.
- Backend API available at `http://localhost:8000` for local development.

## Install Dependencies

Run these commands from the repository root:

```bash
cd frontend
npm install
```

`node_modules/` is generated locally and is intentionally ignored by git and Docker.

## Start Development Server

Start the backend first:

```bash
docker compose up --build -d
docker compose exec api alembic upgrade head
```

Then start the frontend:

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Open:

```text
http://127.0.0.1:5173
```

During development, Vite proxies frontend requests from `/api/*` to the backend:

```text
/api/auth/login -> http://localhost:8000/auth/login
```

This keeps the browser-facing API base URL stable while avoiding CORS friction in local development.

## Production Build

From `frontend/`:

```bash
npm run build
```

The build output is generated in:

```text
frontend/dist
```

`dist/` is generated output and is intentionally ignored by git and Docker.

## Preview Built Frontend

After a successful build:

```bash
npm run preview -- --host 127.0.0.1 --port 4173
```

Open:

```text
http://127.0.0.1:4173
```

Use preview only to inspect the built static assets. For full local API integration, prefer the development server with the Vite proxy unless a deployment environment provides its own `/api` reverse proxy.

## Useful Scripts

```bash
npm run dev
npm run build
npm run preview
```

## Troubleshooting

If TypeScript incremental build files cause permission or stale-cache issues, delete the generated files below and rebuild:

```text
frontend/*.tsbuildinfo
```

If API calls fail in development, confirm:

- Backend is running at `http://localhost:8000`.
- Frontend is opened at `http://127.0.0.1:5173`.
- Requests use the frontend API base path `/api`.