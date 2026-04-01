# ADC Frontend

This package contains the Next.js frontend for the Accident Documentation & Compliance (ADC) MVP. It is an App Router application that talks to the backend API for auth, incidents, exports, vehicle admin tools, and driver protocol administration.

## Implemented routes

### Core app routes

- `/login` – email/password sign-in page.
- `/` – public marketing homepage (canonical landing route).
  - always renders the marketing content for unauthenticated visitors,
  - runs a lightweight client-side session check for header CTA behavior,
  - shows `Sign in` when signed out and `Go to dashboard` when authenticated.
- `/dashboard` – primary landing page with summary cards and links into workflow areas.
- `/incidents` – incidents listing page.
- `/incidents/[id]` – incident detail page (evidence inventory, timeline, exports status/actions).
- `/exports` – export package listing and download actions.
- `/vehicles` – fleet vehicle management page for admins (non-admin users are blocked from actions).
- `/timeline` – currently a placeholder “live timeline” screen (not real-time yet).

### Admin routes

- `/admin/driver-protocol` – driver protocol settings editor.
- `/admin/driver-protocol/instructions` – instruction step editor (add/edit/reorder/enable/disable/reset).
- `/admin/vehicles` – admin vehicle list with QR generate/rotate workflow.

## Environment variables

The frontend API client resolves backend base URLs differently on client vs server:

- `NEXT_PUBLIC_API_BASE_URL` (**required**)
  - Public API base URL used by browser requests.
  - Example: `http://localhost:8000`
- `API_INTERNAL_BASE_URL` (**optional, server-side only**)
  - Used by server-side code when available (falls back to `NEXT_PUBLIC_API_BASE_URL`).
  - Useful when the frontend container/network should call a private backend hostname.

If neither variable is set, code falls back to `http://localhost:8000`.

## Local development

From `frontend/`:

```bash
npm install
npm run dev
```

Then open `http://localhost:3000`.

## Quality and build commands

From `frontend/`:

```bash
npm run lint
npm run build
```

Available package scripts:

- `npm run dev` – start development server.
- `npm run lint` – run ESLint.
- `npm run build` – create production build.
- `npm run start` – run production server from built output.

## Authentication model

Authentication is token-based with client-side session checks:

- Login/register API calls store `access_token` in `localStorage` under `token`.
- API requests attach `Authorization: Bearer <token>` when running in the browser.
- On `401 Unauthorized`, the token is removed and users are redirected to `/login`.
- Route protection is implemented in client code (`useAuth` + layout guards), which calls `/auth/me` to validate sessions.

Protected experiences include dashboard/incidents/exports/vehicles/admin UIs. Admin pages also enforce `user.role === "admin"` checks in the admin layout.

## Known limitations / placeholders

These behaviors are intentional in the current MVP and differ from what developers might assume from a stock Next.js template:

- **No Next.js middleware auth gate**: protection is primarily client-side; redirects happen after hydration/session checks.
- **Token storage is in `localStorage`**: not HTTP-only cookie auth.
- **Timeline page is a placeholder**: it does not yet use SSE/WebSockets for true live event streaming.
- **Some dashboard cards are placeholders**: counts for non-incident metrics currently render as `—`.
- **Root route is marketing-first**: `/` is always the public marketing page. Session-aware CTA links help returning users jump to `/dashboard`.
