# Watt

Watt is a to-do assistant that lives inside WhatsApp as its own contact. You text it tasks in plain English, it sorts them into categories, and it can research a task on request, pull a task out of a screenshot, or ping you with a reminder later. There's no app to install; you're just texting a number.

Under the hood it's one FastAPI server talking to three things: the Meta WhatsApp Cloud API for messages, Gemini for understanding what you meant and deciding which tool to call, and a SQLite file for tasks, reminders, and per-user history. A reminder scheduler runs in-process and checks the database for anything due.

```
 You (WhatsApp) <--> Meta Cloud API <--> /webhook (FastAPI)
                                              |
                                    agent loop (Gemini + tools)
                                              |
                                        SQLite (tasks,
                                     reminders, history, users)
                                              |
                                   APScheduler (fires due reminders
                                      back out through the client)
```

Each phone number gets its own isolated task list. Kian is the admin and can allowlist other numbers by texting the bot; everyone else gets one refusal message and then silence.

## Local dev

Set up a venv and install the requirements:

```
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in the values (see the Meta setup section below for where the WhatsApp ones come from):

```
cp .env.example .env
```

Run the tests:

```
.venv/bin/pytest -q
```

For a fast feedback loop with no WhatsApp involved at all, use the CLI chat tool, which talks to the same agent code the webhook uses:

```
.venv/bin/python -m assistant.cli
```

Type normally to chat with it, or `img:path/to/screenshot.png some caption` to test screenshot ingestion. `quit` exits.

## Meta setup walkthrough

Everything here is free on Meta's test tier.

1. Go to developers.facebook.com and create an app. Pick **Business** as the app type.
2. Add the **WhatsApp** product to the app.
3. Under API Setup you'll get a free test number automatically. Note its **Phone number ID**, which is `WHATSAPP_PHONE_NUMBER_ID` in `.env`.
4. Under API Setup → To, add up to five recipient phone numbers (yours and anyone you want testing with you). The test number can only message numbers on this list.
5. Generate a temporary access token from the same page and put it in `.env` as `WHATSAPP_TOKEN`. It expires in 24 hours, which is fine for initial testing. When you're ready to leave it running, create a System User under Business Settings and issue a permanent token instead, then swap it in.
6. Pick a `GEMINI_API_KEY` from Google AI Studio and drop that in too.

## Webhook wiring

Meta needs a public HTTPS URL to POST messages to, so during local dev we tunnel localhost.

1. Start the server: `python -m assistant.serve` (it listens on port 8000).
2. In another terminal, open a tunnel: `cloudflared tunnel --url http://localhost:8000`. It prints a random `https://*.trycloudflare.com` URL.
3. In the Meta app, go to WhatsApp → Configuration → Webhook and paste in `<tunnel-url>/webhook` as the callback URL, plus whatever you set as `WEBHOOK_VERIFY_TOKEN` in `.env` as the verify token.
4. Subscribe to the `messages` field. Meta will hit the callback with a GET verification request first, and the server answers that automatically as long as the verify token matches.

The tunnel URL changes every time you restart cloudflared, so you'll need to re-paste it into the webhook config each session. That's the one annoying part of Phase 1.

## Reminder template

WhatsApp only allows free-form replies within 24 hours of the user's last message to you. A reminder that fires outside that window has to go out as a pre-approved message template instead, so set one up once:

1. In WhatsApp Manager, go to Message Templates and create a new one.
2. Category: **Utility**. Name: `task_reminder` (this has to match `WHATSAPP_REMINDER_TEMPLATE` in `.env`).
3. Body: `⏰ Reminder: {{1}}`. The `{{1}}` gets filled in with the reminder text at send time.
4. Language: en_US.
5. Submit it and wait for approval, usually minutes, sometimes longer. The scheduler falls back to this template automatically whenever a reminder fires outside the 24-hour window; inside the window it just sends a normal message.

## Phase 2: always-on deploy

Phase 1 runs on your own machine, which means the bot goes quiet whenever the machine sleeps. Phase 2 moves the same container to a host that stays up, for a few dollars a month.

Build the image locally to confirm it works:

```
docker build -t assistant .
```

Then push it to Railway or Fly.io (either works fine for a single small container):

1. Create the app on Railway/Fly and point it at this repo or the built image.
2. Set the same env vars from `.env` in the platform's dashboard: `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WEBHOOK_VERIFY_TOKEN`, `GEMINI_API_KEY`, `WHATSAPP_REMINDER_TEMPLATE`, `ADMIN_PHONE`, `DEFAULT_TIMEZONE`. Leave `DB_PATH` as the Dockerfile default.
3. Mount a persistent volume at `/data` so the SQLite file survives deploys and restarts.
4. Point the WhatsApp webhook at the platform's public URL instead of the cloudflared tunnel, same `/webhook` path as before.
5. Attach a real phone number (eSIM works) when you're ready to go past the five-recipient test limit. No code changes needed, just new values in `.env`.
