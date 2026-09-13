from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import tempfile
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


BACKEND_DIR = Path(__file__).resolve().parents[1]
INPUT_DIR = BACKEND_DIR / "inputs"
VOTES_FILE = BACKEND_DIR / "data" / "votes.json"
JOKES_OUTPUT_FILE = BACKEND_DIR / "outputs" / "jokes.json"
CAT_IMAGE = BACKEND_DIR / "happy-cat-on-yellow-background-photo.jpg"
FRONTEND_DIST = BACKEND_DIR.parent / "frontend" / "dist"
REFRESH_INTERVAL_SECONDS = 10 * 60
CACHE_SIZE = 100
VOTE_LOCK = asyncio.Lock()
JOKE_CACHE: list[Joke] = []
VOTEABLE_JOKES: dict[str, Joke] = {}
LOGGER = logging.getLogger(__name__)


class Joke(BaseModel):
    id: str
    text: str


class VoteRequest(BaseModel):
    joke_id: str
    joke_text: str
    vote: Literal["up", "down"]


class VoteRecord(BaseModel):
    joke_id: str
    joke_text: str
    thumbs_up: int
    thumbs_down: int


def _read_json(path: Path) -> list[dict]:
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Could not load jokes from {path.name}: {error}") from error
    if not isinstance(content, list):
        raise RuntimeError(f"{path.name} must contain a JSON array")
    return content


def load_jokes() -> list[Joke]:
    """Normalize the two supplied source formats into a single public shape."""
    jokes: list[Joke] = []
    for item in _read_json(INPUT_DIR / "stupidstuff.json"):
        body = str(item.get("body", "")).strip()
        if body:
            jokes.append(Joke(id=f"stupidstuff:{item['id']}", text=body))

    for item in _read_json(INPUT_DIR / "reddit_jokes.json"):
        title = str(item.get("title", "")).strip()
        body = str(item.get("body", "")).strip()
        text = "\n\n".join(part for part in (title, body) if part)
        if text:
            jokes.append(Joke(id=f"reddit:{item['id']}", text=text))
    return jokes


def select_jokes_for_cache(all_jokes: list[Joke], current_jokes: list[Joke]) -> list[Joke]:
    """Choose the next memory window without repeating the active window."""
    current_ids = {joke.id for joke in current_jokes}
    candidates = [joke for joke in all_jokes if joke.id not in current_ids]
    selection_pool = candidates if len(candidates) >= CACHE_SIZE else all_jokes
    return random.sample(selection_pool, k=min(CACHE_SIZE, len(selection_pool)))


def load_joke_snapshot() -> list[Joke]:
    """Restore the last displayed batch to validate votes across a server restart."""
    if not JOKES_OUTPUT_FILE.exists():
        return []
    try:
        snapshot = json.loads(JOKES_OUTPUT_FILE.read_text(encoding="utf-8"))
        return [Joke.model_validate(item) for item in snapshot]
    except (OSError, json.JSONDecodeError, ValueError):
        LOGGER.warning("Could not restore the previous joke snapshot")
        return []


def _write_json_atomically(path: Path, content: list[dict]) -> None:
    """Persist a JSON snapshot without leaving a partially written file behind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_path = tempfile.mkstemp(
        prefix=f"{path.stem}-", suffix=".json", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as temporary_file:
            json.dump(content, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.write("\n")
        Path(temporary_path).replace(path)
    finally:
        if Path(temporary_path).exists():
            Path(temporary_path).unlink()


async def refresh_joke_cache() -> None:
    """Refresh the 100-joke memory window and save its snapshot."""
    global JOKE_CACHE, VOTEABLE_JOKES
    previous_jokes = JOKE_CACHE or load_joke_snapshot()
    refreshed_jokes = select_jokes_for_cache(load_jokes(), previous_jokes)
    _write_json_atomically(
        JOKES_OUTPUT_FILE,
        [joke.model_dump() for joke in refreshed_jokes],
    )
    JOKE_CACHE = refreshed_jokes
    VOTEABLE_JOKES = {joke.id: joke for joke in [*previous_jokes, *refreshed_jokes]}


async def refresh_joke_cache_forever() -> None:
    while True:
        await asyncio.sleep(REFRESH_INTERVAL_SECONDS)
        try:
            await refresh_joke_cache()
            LOGGER.info("Refreshed joke cache and output snapshot")
        except Exception:
            # Keep serving the last good in-memory cache if an input file is bad temporarily.
            LOGGER.exception("Could not refresh the joke cache")


def _ensure_votes_file() -> None:
    VOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not VOTES_FILE.exists():
        VOTES_FILE.write_text("[]\n", encoding="utf-8")


def _read_votes() -> list[dict]:
    _ensure_votes_file()
    try:
        votes = json.loads(VOTES_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RuntimeError("votes.json is not valid JSON") from error
    if not isinstance(votes, list):
        raise RuntimeError("votes.json must contain a JSON array")
    return votes


def _write_votes(votes: list[dict]) -> None:
    """Replace the data file atomically so an interrupted write cannot corrupt votes."""
    _write_json_atomically(VOTES_FILE, votes)


@asynccontextmanager
async def lifespan(_: FastAPI):
    _ensure_votes_file()
    await refresh_joke_cache()
    refresh_task = asyncio.create_task(refresh_joke_cache_forever())
    try:
        yield
    finally:
        refresh_task.cancel()
        with suppress(asyncio.CancelledError):
            await refresh_task


app = FastAPI(title="Laugh Loop API", lifespan=lifespan)


@app.get("/api/jokes", response_model=list[Joke])
async def jokes() -> list[Joke]:
    return JOKE_CACHE


@app.get("/api/cat-image")
async def cat_image() -> FileResponse:
    if not CAT_IMAGE.exists():
        raise HTTPException(status_code=404, detail="Cat image not found")
    return FileResponse(CAT_IMAGE, media_type="image/jpeg")


@app.get("/api/votes", response_model=list[VoteRecord])
async def vote_results() -> list[dict]:
    """Return the exact vote records persisted on this machine."""
    return _read_votes()


@app.post("/api/votes")
async def vote(request: VoteRequest) -> dict:
    joke = VOTEABLE_JOKES.get(request.joke_id)
    if joke is None or joke.text != request.joke_text:
        raise HTTPException(status_code=400, detail="Unknown or altered joke")

    async with VOTE_LOCK:
        votes = _read_votes()
        record = next((item for item in votes if item.get("joke_id") == joke.id), None)
        if record is None:
            record = {
                "joke_id": joke.id,
                "joke_text": joke.text,
                "thumbs_up": 0,
                "thumbs_down": 0,
            }
            votes.append(record)

        key = "thumbs_up" if request.vote == "up" else "thumbs_down"
        record[key] = int(record.get(key, 0)) + 1
        _write_votes(votes)

    return {"joke_id": joke.id, "thumbs_up": record["thumbs_up"], "thumbs_down": record["thumbs_down"]}


# The React project is built by startapp.sh, then served locally by FastAPI.
app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
