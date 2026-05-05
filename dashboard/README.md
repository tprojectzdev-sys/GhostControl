# Axon Dashboard

Dark, card-based web UI for the same relay your phone hits. Built with
Vite + React 18 + TypeScript + Tailwind CSS. Authenticates with the same
bearer token (`USER_API_KEY`) you set on the relay.

## Features

- Live PC + bridge status (online/offline pills, uptime, hostname, OS).
- Power actions: Wake, Lock, Sleep, Restart, Shutdown — with confirm
  dialogs on destructive ones, disabled when the relevant agent is offline.
- App launcher with click-to-launch tiles based on your YAML aliases.
- Action group launcher.
- Free URL input (still subject to the PC's `url_policy`).
- Live system stats (CPU / RAM with sparklines, idle time, foreground app).
- Last 50 audit events, auto-refreshing every 5 s, with status icons.
- Session token stored in `localStorage`; sign-out clears it.

## Run locally

```bash
cd dashboard
npm install
npm run dev      # http://localhost:5173
```

The dev server's only build-time config is the optional list of default
app/group aliases shown until the user clicks one; see `.env.example`.

## Build for production

```bash
npm run build    # emits ./dist
```

You have three reasonable hosting options:

1. **Same Railway service as the relay** — copy `dist/` next to the relay
   and have FastAPI serve it as a static mount. Simplest deploy story.
2. **Cloudflare Pages / Vercel** — drop in `dist/` as a static site, point
   the user at the relay URL on the login page.
3. **Anywhere static** — it's a plain SPA. No SSR, no API routes.

## Auth model

- On first visit, the user types the relay URL and the bearer token
  (`USER_API_KEY` from the relay's env). The dashboard verifies by hitting
  `/healthz` then `/v1/status`.
- The token is stored in `localStorage` under `axon.session`.
- Every subsequent request adds `Authorization: Bearer <token>`.
- 401 from any endpoint → automatic sign-out.

This is the same trust model as the iOS app, intentionally.

## What it intentionally is NOT

- Not a whitelist editor. Aliases live in `whitelist.yaml` on the PC.
  Editing that here would mean shipping config back through the agent,
  which is Phase 3 work.
- Not a multi-tenant admin panel.
- Not a chat / AI / NLU surface. It only sends the strict commands defined
  in the wire schema.
