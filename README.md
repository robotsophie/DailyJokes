# Laugh Loop

Laugh Loop is a small local web app that displays a rotating English joke, lets visitors vote whether it is funny, and keeps the experience cheerful with a laughing cat in the corner.

It is designed to run on Linux with one command. The launcher creates the Python virtual environment, installs backend packages, installs frontend packages when needed, builds the React application, and starts the site.

## Run locally

### Requirements

- Python 3
- Node.js and npm

### Start

```bash
./startapp.sh
```

Open [http://localhost:8000](http://localhost:8000).

The first run creates `backend/.venv` and installs frontend dependencies. Later runs rebuild the frontend and reuse the existing local environment.

## How it works

### Frontend

The frontend lives in `frontend/` and uses React with Vite.

- It fetches the active 100-joke set from `GET /api/jokes`.
- It shows one joke for 30 seconds, or immediately advances after a thumbs-up or thumbs-down vote.
- It refreshes its joke set every 10 minutes.
- The compiled React build is served by the Python backend, so the app uses one local address: `http://localhost:8000`.

### Backend

The FastAPI backend lives in `backend/app/main.py`.

- It reads the supplied JSON sources from `backend/inputs/` at startup and every 10 minutes.
- On each refresh it randomly selects 100 new jokes, avoiding the active 100 from the previous batch.
- The active batch lives in server memory and is written to `backend/outputs/jokes.json` as a local snapshot.
- The previous batch remains available only as a short grace set for validating votes from browser tabs that have not refreshed yet.
- The laughing-cat image is served from `backend/happy-cat-on-yellow-background-photo.jpg`.

OpenRouter is not used because all joke content comes from local files. No API key is required.

## Voting and persistence

Each vote calls `POST /api/votes` with the joke ID, joke text, and either `up` or `down`.

The backend stores cumulative records in `backend/data/votes.json` using this shape:

```json
{
  "joke_id": "reddit:example",
  "joke_text": "Why did the joke cross the road?",
  "thumbs_up": 4,
  "thumbs_down": 1
}
```

Votes are protected by a server-side lock and written atomically: the app writes a complete temporary JSON file, then replaces the previous file. This means an interrupted write cannot leave a partially written vote file.

To confirm what is saved, use either:

```bash
cat backend/data/votes.json
```

or the read-only local API:

```bash
curl http://localhost:8000/api/votes
```

The API response is read from the same `votes.json` file that persists the counters. A successful vote request returns HTTP 200 and the updated totals for that joke.

## Project layout

```text
backend/
  app/main.py                         FastAPI API, cache, and vote persistence
  inputs/                             Read-only supplied joke sources
  data/votes.json                     Runtime vote counters
  outputs/jokes.json                  Current 100-joke cache snapshot
  happy-cat-on-yellow-background-photo.jpg
frontend/
  src/                                React user interface
  package.json                        Frontend scripts and dependencies
startapp.sh                           One-command Linux launcher
```

## Share on GitHub

The included `.gitignore` excludes generated dependencies, logs, local vote data, and generated cache snapshots. It keeps the code, supplied input data, image, and setup files ready to share.

```bash
git init
git add .
git commit -m "Initial Laugh Loop app"
git branch -M main
git remote add origin <your-github-repository-url>
git push -u origin main
```

Before publishing, review the supplied joke datasets to ensure their content and licensing are appropriate for your intended audience.
# DailyJokes
