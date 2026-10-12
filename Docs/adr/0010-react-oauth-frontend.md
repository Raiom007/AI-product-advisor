# ADR 0010: React Frontend, FastAPI, and OAuth Integration

## Status
Proposed

## Context
The current MVP architecture strictly specifies **Streamlit** as the UI layer (see `AGENTS.md` and `ARCHITECTURE.md` §3). The user has requested to replace the frontend with **JavaScript and React** and add **OAuth** authentication.

To support a decoupled React frontend and OAuth flow, the backend must be exposed via a REST API (e.g., using FastAPI) instead of the direct in-process `service.advise()` calls currently used by Streamlit. This represents a major architectural shift and requires adding new dependencies.

## Decision
1. **Frontend**: Scaffold a new React application (via Vite or Next.js) in a `frontend/` or `ui/` directory.
2. **Backend**: Introduce `FastAPI` (and an ASGI server like `uvicorn`) as a new dependency to expose `advisor.service.advise()` over an HTTP endpoint.
3. **Authentication**: Implement OAuth in the React frontend, and validate tokens in the FastAPI backend.
4. **Deprecation**: Deprecate and remove the existing Streamlit codebase in `src/advisor/ui/` once the React UI reaches feature parity.

## Consequences
- **Pros**: More complex, dynamic, and premium UI; standard web auth patterns; cleanly decouples UI from the Python backend.
- **Cons**: Introduces multiple new dependencies (Node.js ecosystem, FastAPI, OAuth libraries); violates the original "Streamlit-only" constraint for the two-week MVP; increases system complexity.
