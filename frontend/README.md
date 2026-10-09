# Mis Eventos frontend

The frontend uses React 19, Vite, React Router, and React Context with a reducer for shared authentication and event state. API requests are centralized in `src/api/client.js`; authentication relies on the backend's HttpOnly cookie and never stores credentials or tokens in browser storage.

## Development

The API base defaults to `/api/v1`, which keeps browser requests on the Vite origin and routes them through the development proxy. Copy `.env.example` to `.env` to customize local settings. `VITE_API_BASE_URL` is exposed to browser code and must not contain secrets. `API_PROXY_TARGET` is server-side Vite configuration; its local default is `http://localhost:5000`.

Run the frontend directly with:

```bash
npm install
npm run dev
```

When using the repository's Docker Compose setup, Vite proxies API traffic to `http://backend:5000` using the Compose service name. The application is available at `http://localhost:5173`.

## Routes

| Route | Purpose |
| --- | --- |
| `/events` | Browse events |
| `/events/:eventId` | View event details |
| `/events/new` | Create an event |
| `/login` | Sign in |
| `/register` | Create an account |
| `/profile` | View the authenticated profile |

Run `npm run lint` and `npm run build` to check the frontend.
