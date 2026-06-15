# Setup — running Mirror end to end

This is the full runbook for standing up Mirror from a clean machine: Docker
stack → public webhook via Cloudflare Tunnel → n8n credentials → Telegram bot →
first journal entry.

> **Why a tunnel is required.** n8n's **Telegram Trigger** node is
> webhook-based — it registers a callback URL with Telegram's Bot API and waits
> for Telegram to `POST` updates to it. Telegram only delivers to a public
> HTTPS endpoint, so the locally-bound n8n (`127.0.0.1:5678`) needs a public
> front door. A Cloudflare Tunnel provides that without opening a port on your
> router.

## Prerequisites

- Docker + Docker Compose
- A Cloudflare account with a domain managed in Cloudflare DNS
- A Telegram account
- An Anthropic API key

## 1. Clone and configure

```bash
git clone https://github.com/solidx86/mirror.git
cd mirror
cp env.template .env
```

Fill in `.env` (it is gitignored):

```
TELEGRAM_BOT_TOKEN=...      # from BotFather, step 4
ANTHROPIC_API_KEY=...       # from console.anthropic.com
TELEGRAM_ALLOWED_CHAT_ID=... # your numeric chat id, step 4
```

> These values feed your own records. The running workflow reads its secrets
> from **n8n credentials** (step 7), not from `.env` — credentials are stored
> in n8n's encrypted store, which is why they must be re-entered by hand after
> importing the workflow.

## 2. Start the stack

```bash
docker compose up -d
docker logs -f mirror-n8n     # wait for "Editor is now accessible"
```

This brings up Postgres (schema auto-applied on first init) and n8n, both bound
to `127.0.0.1` only. The n8n editor is at <http://localhost:5678>.

## 3. Expose n8n with a Cloudflare Tunnel

Install `cloudflared` (`brew install cloudflared`, or see Cloudflare's docs),
then create a **named tunnel** and route a hostname to the local n8n port.

```bash
cloudflared tunnel login                      # opens a browser; pick your zone
cloudflared tunnel create mirror              # creates a tunnel + credentials file
cloudflared tunnel route dns mirror mirror.example.com   # your domain
```

Create `~/.cloudflared/config.yml`:

```yaml
tunnel: mirror
credentials-file: /Users/<you>/.cloudflared/<tunnel-id>.json

ingress:
  - hostname: mirror.example.com
    service: http://localhost:5678
  - service: http_status:404
```

Run it (foreground to test, then install as a service):

```bash
cloudflared tunnel run mirror
# once verified:
sudo cloudflared service install
```

`https://mirror.example.com` should now load the n8n editor.

## 4. Point n8n at the public URL

n8n must advertise the tunnel hostname when it registers the Telegram webhook —
otherwise it tells Telegram to deliver to `localhost`, which silently never
fires. Edit the `n8n` service environment in `docker-compose.yml`:

```yaml
    environment:
      - N8N_HOST=mirror.example.com
      - N8N_PROTOCOL=https
      - WEBHOOK_URL=https://mirror.example.com/
      # ... keep the existing vars
```

Then recreate the container so the new env takes effect:

```bash
docker compose up -d --force-recreate n8n
```

## 5. Create the Telegram bot

1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → follow prompts →
   copy the **bot token** into `.env` (`TELEGRAM_BOT_TOKEN`).
2. Find your **numeric chat id**: message your new bot once, then open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` and read
   `result[].message.chat.id`. Put it in `.env` (`TELEGRAM_ALLOWED_CHAT_ID`).

## 6. Import the workflow

In the n8n editor: **Workflows → Import from File →**
`workflows/mirror-workflow.json`.

> n8n CE **strips credentials on import** — every credential reference in the
> committed JSON is blank by design. You attach them next.

## 7. Create and attach the three credentials

Create each credential once (**Credentials → New**), then open each listed node
and select it under the node's *Credential* dropdown.

| Credential (n8n type) | Used by node(s) | Values |
|---|---|---|
| **Telegram API** (`telegramApi`) | `Telegram Trigger`, and every `Send …` Telegram node | **Access Token** = your BotFather token |
| **Postgres** (`postgres`) | every Postgres node (session read/write, persist) | Host `postgres` · Database `mirror` · User `mirror` · Password `mirrorlocal` · Port `5432` · SSL `disable` |
| **Anthropic API** (`anthropicApi`) | the LLM `HTTP Request` nodes (intake + reflection) | **API Key** = your Anthropic key |

> Postgres host is `postgres` (the compose service name), not `localhost` —
> n8n reaches it over the compose network. The password matches
> `POSTGRES_PASSWORD` in `docker-compose.yml`.

After attaching, confirm no node shows a red "credential required" badge.

## 8. Set the allowlist

Open the **`Authz + Parse`** code node and set your chat id:

```js
const ALLOWED_CHAT_ID = 0; // <-- replace 0 with your numeric chat id from step 5
```

Leaving it at `0` runs in bootstrap mode (accepts any chat so you can discover
your id) — fine for first contact, but set it before real use so only you can
reach the bot.

## 9. Activate and test

Toggle the workflow **Active** (top-right). On activation n8n registers the
webhook with Telegram using `WEBHOOK_URL`. Then in Telegram:

```
/journal      → the Intake Agent should reply with its first question
```

Work through the interview; when intake emits its readiness sentinel the
Reflection Agent runs and sends back the structured review. The entry is
persisted to Postgres and exported to `archive/`.

## Troubleshooting

- **Bot never replies.** Check the registered webhook:
  `https://api.telegram.org/bot<TOKEN>/getWebhookInfo` — `url` must be your
  tunnel hostname and `last_error_message` should be empty. If `url` shows
  `localhost`, `WEBHOOK_URL` wasn't set before activation — fix step 4, then
  deactivate/reactivate the workflow to re-register.
- **Tunnel 502 / editor won't load.** `cloudflared` isn't running or the
  `ingress` service port doesn't match `127.0.0.1:5678`.
- **n8n login cookie rejected over the tunnel.** `N8N_SECURE_COOKIE=false` is
  set for local http; once you front it with https you can remove that override.
- **Postgres auth failed from n8n.** Host must be `postgres` (not `localhost`),
  and the password must match `POSTGRES_PASSWORD`.
- **Silent drops.** If `ALLOWED_CHAT_ID` is set, messages from any other chat
  are dropped by design — verify your id with `getUpdates`.
