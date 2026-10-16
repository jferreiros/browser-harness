# Vivla Tools — sesión local autenticada para validación holdout

Field-tested 2026-06-16 contra un worktree de `vivla-tools` con el bypass dev-auth (PR vivla-tech/vivla-tools#223).

Cómo conectar browser-harness a **vivla-tools corriendo en localhost**, aterrizando en la UI **autenticada**, **sin** pasar por Auth0 Universal Login y **sin secuestrar la pestaña del usuario**. Para el agente `validate` (holdout) y para dev manual.

> ⚠️ Interno de Vivla. NO contribuir este archivo al upstream público `browser-use/browser-harness`. Vive solo en este checkout local. No contiene secretos (la API key vive en `.env.development.local`, gitignored).

## TL;DR

```bash
# 1. Levantar la app en el worktree (front :3000 + back :3001). El backend necesita APP_STAGE=development.
cd <worktree>            # p.ej. ~/Documents/vivla/worktrees/vivla-tools/<task>
pnpm dev:backend &       # NestJS :3001 (su script ya pone APP_STAGE=development)
pnpm dev:frontend &      # Vite :3000
# (o `pnpm dev` para todo en paralelo). Hacer polling de :3000 y :3001 hasta que respondan.

# 2. Chrome DEDICADO (no toca el Chrome del usuario)
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9333 --user-data-dir=/tmp/vivla-holdout-chrome \
  --headless=new --no-first-run --no-default-browser-check \
  --window-size=1440,1600 &
# --window-size es importante: sin él el headless arranca a ~756px de ancho →
# la app entra en layout MÓVIL con scroll interno y los screenshots/asserts de
# desktop no cuadran. Si ya arrancó pequeño, se corrige con Browser.setWindowBounds.
sleep 2

# 3. Harness apuntando a ESE Chrome (no start_remote_daemon, no el Chrome por defecto)
BU_CDP_URL=http://127.0.0.1:9333 BU_NAME=holdout browser-harness -c '
new_tab("http://localhost:3000/app")
wait_for_load()
print(page_info())     # title "🟢 Vivla Tools", url debe quedarse en /app (NO /sign-in)
capture_screenshot()   # debe verse el shell autenticado: saludo "Hola, <actor>", badge "DEV", avatar
'
```

## Por qué este patrón (y no los obvios)

- **`start_remote_daemon` NO sirve:** el navegador remoto de Browser Use no alcanza `localhost`. Es la causa raíz por la que los holdouts de UI autenticada fallaban antes.
- **El Chrome por defecto NO sirve:** el auto-descubrimiento del daemon se engancha al Chrome personal del usuario y secuestra su pestaña activa.
- **`BU_CDP_URL=http://127.0.0.1:<port>`** apunta el daemon a un Chrome dedicado (resuelve el ws vía `/json/version`). No necesita `BROWSER_USE_API_KEY`. `--user-data-dir` propio = perfil aislado; `--remote-debugging-port` propio = no colisiona. `BU_NAME` aísla el daemon (socket `/tmp/bu-<NAME>.sock`) para correr en paralelo a otros usos.

## Cómo funciona la sesión (el bypass)

vivla-tools tiene un **bypass dev-auth env-gated** (solo dev, doble candado, prod-safe):
- **Frontend:** con `VITE_DEV_AUTH_BYPASS=true` (en `apps/frontend/.env.development.local`), `useAuth0()` devuelve una sesión mock autenticada (usuario de test admin-all) → el guard de ruta de `/app` pasa, sin redirect a `/sign-in`. El api-client manda `x-api-key` (+ `x-vivla-actor-*`) en vez de `Bearer`.
- **Backend:** con `DEV_AUTH_BYPASS=true` (en `apps/backend/.env.development.local`) y `APP_STAGE=development`, el guard `Auth0AuthGuard` honra ese `x-api-key` (actor admin-all). Sin esto, ~39 endpoints Bearer-only (incluido el del home) devolverían 401 y la UI cargaría vacía.
- Ambos flags los propaga `bin/conductor-setup` a cada worktree (copia los `.env*.local`). En un worktree recién creado con conductor-setup ya están puestos.

## Verificar que la sesión es funcional (no solo visual)

El shell puede pintar pero los datos no cargar si el backend no honra la key. Confirmar con evidencia dura:

```bash
KEY=$(grep '^VITE_DEV_API_KEY=' apps/frontend/.env.development.local | cut -d= -f2-)
# endpoint del home (Bearer-only, el muro canónico):
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3001/api/permissions/modules/home                       # 401 (sin auth)
curl -s -o /dev/null -w "%{http_code}\n" -H "x-api-key: $KEY" http://localhost:3001/api/permissions/modules/home  # 200 (bypass OK)
```
En la UI: el home debe pintar tiles reales ("Web CMS / Guías / Chat / Teams / Notifications"), NO "No pudimos cargar tus herramientas". `/app/teams` pinta usuarios del tenant. NUNCA pegar el valor de la key en reportes/logs.

## Topología

| | |
|---|---|
| Front | Vite SPA, `http://localhost:3000`, rutas bajo `/app/*` (TanStack Router file-based). Proxy `/api` → `:3001`. |
| Back | NestJS, `http://localhost:3001`, prefijo `/api`. Supabase **remota** dev (requiere internet; creds en los `.env` copiados). |
| Sesión | localStorage (no cookies). |
| URL de aterrizaje | `http://localhost:3000/app`. |

## Gotchas

- **El guard de ruta de `/app` tiene timeout ~10s** (`routes/app.tsx`): dale tiempo a Vite + Nest antes de concluir. Haz polling de ambos puertos.
- **Si aterrizas en `/sign-in`** → el bypass NO está activo. Revisa que `apps/frontend/.env.development.local` tiene `VITE_DEV_AUTH_BYPASS=true`.
- **Si el shell carga pero los datos no** (estado de error) → el backend no honra la key. Revisa que el backend arrancó con `APP_STAGE=development` y que `apps/backend/.env.development.local` tiene `DEV_AUTH_BYPASS=true`. (`@nestjs/config` carga `.env.${APP_STAGE}.local`.)
- **Límite conocido:** el AI streaming (`hooks/ai/useAskStream.ts`) hace fetch fuera del api-client y usa `getAccessTokenSilently` → bajo bypass va sin auth. Pantallas estándar OK; chat/copilot por streaming NO valida bien con este método.
- **Verifica que NO se tocó el Chrome personal del usuario** (perfil aislado + puerto dedicado lo garantizan).

## Cleanup

```bash
pkill -f vivla-holdout-chrome     # mata el Chrome dedicado
# y mata los dev servers (pnpm dev / vite / nest) que levantaste
rm -rf /tmp/vivla-holdout-chrome  # opcional: limpia el perfil
```

## Gotchas añadidos (2026-07-03, validación tools-ux-quickwins)

- **Puerto 3001 compartido con apps personales:** si otra app tiene `[::1]:3001` (p.ej. barcos-renting), `localhost:3001` (→ IPv6) llega a la app equivocada mientras Nest (bind `[::]:3001`) responde en `127.0.0.1:3001`. NO mates la app personal: apunta el front con `VITE_API_URL` en `apps/frontend/.env.development.local` (gitignored) y bórralo al acabar.
- **`VITE_API_URL` necesita el prefijo `/api`:** es el baseURL de axios y el api-client añade rutas relativas tipo `/chat/...`; Nest tiene prefijo global `/api`. Valor correcto: `http://127.0.0.1:3001/api` (sin `/api` → 404 en todo).
- **Chat bajo bypass:** `GET /chat/users/me` lee `currentUser.id`, pero el actor del bypass (`buildApiKeyActor`) solo trae `supabaseUserId` → 404 y el chat Stream no carga (ni token). Workaround temporal: shim local NO commiteado añadiendo `id: actorUserId` al actor + `VITE_DEV_ACTOR_USER_ID=<uuid de un agente real con chat_user_id sincronizado>`. Con eso `/me` resuelve y el chat funciona entero. Fix real pendiente: que el bypass rellene `id` (o que `/me` caiga a `supabaseUserId`).
- **Impersonación útil:** con `VITE_DEV_ACTOR_USER_ID` el front manda `x-vivla-actor-user-id` y puedes actuar como un agente concreto (p.ej. probar flujos de agente activo). Verifica antes con curl: `curl -H "x-api-key: $KEY" -H "x-vivla-actor-user-id: <uuid>" http://127.0.0.1:3001/api/chat/users/me`.

## Gotchas añadidos (2026-07-14, validación home-icons-squared)

- **⚠️ Otro worktree puede estar ya sirviendo :3000/:3001** (sesiones paralelas). Vite entonces salta a otro puerto EN SILENCIO ("Port 3000 is in use, trying another one...") y tu screenshot de `localhost:3000` valida el **código equivocado**. Antes de dar por buena una validación: `lsof -ti :3000 | xargs ps -o command -p` y confirma que el proceso apunta a TU worktree. Para forzar puertos propios: front `pnpm exec vite dev --port 3010 --strictPort --mode development`, back `PORT=3011 pnpm dev`.
- **En puertos alternativos hay que abrir CORS y apuntar el api-client:** el backend solo permite el origen de `FRONTEND_URL` (default `http://localhost:3000`) → arranca el back con `FRONTEND_URL=http://localhost:3010`. El front llama al API directo (no via proxy) con baseURL de `VITE_API_URL` → `VITE_API_URL=http://127.0.0.1:3011/api` como env al lanzar vite.
- **Home vacía ("Aún no tienes herramientas") bajo bypass:** el actor QA por defecto no tiene módulos asignados; añade `VITE_DEV_ACTOR_USER_ID=<uuid agente real>` al lanzar vite para impersonar y que el grid cargue.
- **Backend en worktree nuevo:** compila primero `pnpm --filter @vivla-tools/common build` o Nest arranca con 55 errores TS2307 (`@vivla-tools/common`).
- **Si matas y relanzas el Chrome dedicado**, el daemon `BU_NAME` puede quedarse con socket muerto (`ConnectionRefusedError` en `/tmp/bu-<name>.sock`) → `rm -f /tmp/bu-<name>.sock` y reintenta (auto-arranca).

## Gotchas añadidos (2026-07-14, validación chat-fixes R3)

- **⚠️ `window.confirm()` nativo cuelga el harness en headless** (en el chat lo dispara "Eliminar mensaje"): el daemon habilita el dominio `Page` de CDP pero nunca responde `Page.javascriptDialogOpening`, así que el renderer se queda bloqueado y todo `js(...)` posterior parece colgado (no es bug del producto). Workaround: antes del click, conecta un websocket CDP crudo al target y auto-acepta el diálogo con `Page.handleJavaScriptDialog {accept: true}` al recibir `Page.javascriptDialogOpening`. Mecánica general en `interaction-skills/dialogs.md`.
