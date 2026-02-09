"""
ShadowDesk Trading API - Main Application
"""

import time

from fastapi import FastAPI
from fastapi import Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from .routes import account, embeddings, health, predict, trading

HTTP_REQUESTS = Counter(
    "api_http_requests_total",
    "Total HTTP requests handled by the ShadowDesk API.",
    ["method", "path", "status"],
)
HTTP_REQUEST_LATENCY = Histogram(
    "api_http_request_duration_seconds",
    "HTTP request latency for the ShadowDesk API.",
    ["method", "path"],
)

app = FastAPI(
    title="ShadowDesk Trading API",
    version="1.0.0",
    description="ML-powered stock trading recommendation service",
)
app.state.broker = None
app.state.executor = None


@app.middleware("http")
async def collect_http_metrics(request: Request, call_next):
    """Record Prometheus metrics for API requests."""
    start = time.perf_counter()
    path = request.url.path
    status_code = 500

    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        if path != "/metrics":
            duration = time.perf_counter() - start
            HTTP_REQUESTS.labels(method=request.method, path=path, status=str(status_code)).inc()
            HTTP_REQUEST_LATENCY.labels(method=request.method, path=path).observe(duration)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["Health"])
app.include_router(predict.router, prefix="/predict", tags=["Predictions"])
app.include_router(embeddings.router, prefix="/embeddings", tags=["Embeddings"])
app.include_router(trading.router, prefix="/trading", tags=["Trading"])
app.include_router(account.router, prefix="/account", tags=["Account"])


@app.get("/")
def root():
    return {"message": "ShadowDesk Trading API", "version": "1.0.0", "docs": "/docs"}


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    """Expose Prometheus metrics for local observability."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
