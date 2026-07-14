# WhatsApp Personal Assistant — Design Spec

**Date:** 2026-07-14
**Status:** Approved by Kian
**Goal:** A personal assistant that lives entirely inside WhatsApp as a dedicated contact. Users text it their to-do items; it organises, tracks, researches, reads screenshots, and sends scheduled reminders. No separate app.

## Requirements

1. **To-do management via natural text.** Add items conversationally; "X complete" (any phrasing) removes/completes items; "what's left?" returns the organised outstanding list.
2. **Categories.** The assistant groups tasks into categories (e.g. Applications, Errands, School) automatically, and re-organises on request.
3. **On-demand research.** Light web research on a list item **only when explicitly asked** — never proactively.
4. **Screenshot ingestion.** User sends a screenshot (e.g. a job opportunity); the assistant extracts it into a task with an appropriate category and confirms.
5. **Scheduled reminders.** Natural-language one-off and recurring reminders ("cancel Prime on the 28th", "laundry every Sunday 6pm"), interpreted in the user's timezone (default America/Los_Angeles).
6. **Multi-user with allowlist.** Each allowlisted phone number gets a fully isolated list. Kian is admin and can add users by texting the bot. Unknown numbers get one polite refusal, then are ignored.
7. **Privacy.** The bot only ever receives messages sent directly to its own number (a separate WhatsApp chat/contact). It has no access to any other conversation.
8. **Cost.** $0/month in Phase 1. Phase 2 adds only ~$0–5/mo hosting.

## Architecture

One Python **FastAPI** server with four components:

### 1. WhatsApp channel
- **Meta WhatsApp Business Cloud API** (official, free).
- Inbound: Meta POSTs each user message to our `/webhook` endpoint (with GET verification handshake). Webhook retries are deduplicated by WhatsApp message ID.
- Outbound: replies sent via the Graph API `/messages` endpoint.
- **Phase 1 number:** Meta's free test number (messages up to 5 verified recipients — doubles as the v1 allowlist). **Phase 2+:** attach a real number (eSIM); no code changes.
- **24-hour rule:** free-form messages are only allowed within 24h of the user's last inbound message. Scheduled reminders outside that window are sent via a pre-approved utility **message template** (one-time setup in Meta dashboard, e.g. `reminder` with one text variable).
- Media: image messages arrive as media IDs; server downloads bytes via Graph API for the vision model.

### 2. Agent brain
- **Gemini Flash, free tier** (~1,500 req/day), behind a thin `LLMProvider` adapter interface so switching to Claude/Groq/Ollama is a config change.
- Per message, the agent receives: system prompt (persona + rules), the sender's current task list, recent rolling conversation history, and tool definitions.
- **Tools:** `add_tasks` (batch), `complete_task`, `list_tasks`, `update_task` (text/category), `set_reminder`, `cancel_reminder`, `list_reminders`, `research` (web search; only when user explicitly asks), admin-only `add_user` / `remove_user` / `list_users`.
- Tool-call loop: model may chain multiple calls before producing the final reply text.
- Screenshots: image bytes go to the same Gemini call (native vision); the model extracts task(s) and calls `add_tasks`, then confirms in its reply.
- Research: DuckDuckGo search (free, no API key) fetched server-side; results passed back to the model, summarised into a short texting-friendly answer.

### 3. Storage
- **SQLite** single file. Tables:
  - `users` — phone (PK), name, is_admin, timezone, created_at
  - `tasks` — id, user_phone (FK), text, category, status (open/done), source (text/screenshot), created_at, completed_at
  - `reminders` — id, user_phone (FK), text, next_fire_at (UTC), recurrence (none/cron-like), active
  - `messages` — id, user_phone, role, content, created_at (rolling window per user for agent context)
- Every query scoped by `user_phone` — hard isolation between users.

### 4. Scheduler
- **APScheduler** in-process, polling due reminders (persistent via the DB, so restarts don't lose reminders).
- On fire: send free-form message if inside the 24h window, else the `reminder` template. Recurring reminders reschedule themselves.

## Message flow

```
User texts bot → Meta → POST /webhook → dedupe → allowlist check
  → load user context (tasks + history) → Gemini + tools → execute tool calls
  → store history → send reply via Graph API → user sees reply in WhatsApp
```

## Error handling
- Unknown sender: one polite "private assistant" reply per number, then silence.
- Gemini failure/rate limit: apologise briefly ("hit a snag, try again in a minute"); never lose the inbound message silently.
- Webhook must return 200 fast: message processing happens in a background task.
- Malformed/unsupported message types (audio, stickers): friendly "I can handle text and images" reply.

## Rollout
- **Phase 1 ($0):** run on Kian's Mac, exposed via Cloudflare tunnel, Meta test number, Kian + up to 4 friends. Limitation: bot pauses while the Mac sleeps.
- **Phase 2 (~$0–5/mo):** deploy the same Docker container to Railway/Fly.io; always on. Identical code, env-var config only.

## Testing
- Unit tests on the tool layer (task CRUD, reminder scheduling, allowlist).
- **Local CLI harness** that talks to the agent loop directly (text + image file inputs) — full end-to-end brain verification with zero WhatsApp dependency.
- Live verification through the Meta test number before calling Phase 1 done.

## Config (env vars)
`WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WEBHOOK_VERIFY_TOKEN`, `GEMINI_API_KEY`, `ADMIN_PHONE`, `DB_PATH`, `DEFAULT_TIMEZONE`.

## Out of scope (v1)
- Voice notes, group chats, non-English, calendar integration, payments, iMessage channel.
