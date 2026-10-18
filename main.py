
import json
import logging
import time
import uuid
from collections import deque
from datetime import datetime, timezone

from fastapi import FastAPI, Query, Request
from fastapi.responses import Response
from prometheus_client import Counter, REGISTRY, generate_latest
from prometheus_client import CONTENT_TYPE_LATEST

app = FastAPI()

# Replace this with your actual registered assignment email.
EMAIL = "YOUR_REGISTERED_EMAIL@example.com"

# Count every incoming HTTP request.
# Prometheus exposes this counter as http_requests_total.
REQUEST_COUNTER = Counter(
    "http_requests",
    "Total number of HTTP requests received",
)

# Remember when the service started.
START_TIME = time.monotonic()

# Keep the most recent 1000 log entries in memory.
recent_logs = deque(maxlen=1000)

# Print structured JSON logs to the Render logs.
logger = logging.getLogger("observability")
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


@app.middleware("http")
async def observe_requests(request: Request, call_next):
    # Count requests to ALL endpoints, including /metrics.
    REQUEST_COUNTER.inc()

    request_id = str(uuid.uuid4())

    try:
        response = await call_next(request)
    except Exception:
        entry = {
            "level": "ERROR",
            "ts": datetime.now(timezone.utc).isoformat(),
            "path": request.url.path,
            "request_id": request_id,
        }
        recent_logs.append(entry)
        logger.error(json.dumps(entry))
        raise

    entry = {
        "level": "INFO",
        "ts": datetime.now(timezone.utc).isoformat(),
        "path": request.url.path,
        "request_id": request_id,
        "method": request.method,
        "status_code": response.status_code,
    }

    recent_logs.append(entry)
    logger.info(json.dumps(entry))

    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/work")
def do_work(n: int = Query(default=1, ge=0, le=100000)):
    # Perform n simple units of work.
    done = 0
    for _ in range(n):
        done += 1

    return {
        "email": EMAIL,
        "done": done,
    }


@app.get("/metrics")
def metrics():
    # Generate live Prometheus metrics, not a static text file.
    return Response(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.get("/healthz")
def healthz():
    uptime = time.monotonic() - START_TIME
    return {
        "status": "ok",
        "uptime_s": float(max(0.0, uptime)),
    }


@app.get("/logs/tail")
def logs_tail(limit: int = Query(default=10, ge=1, le=1000)):
    # Return the newest log entries first.
    return list(reversed(list(recent_logs)[-limit:]))
