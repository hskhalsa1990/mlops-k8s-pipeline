"""Tiny dependency-free load test: python load_test.py --url http://localhost:8080"""
import argparse
import json
import statistics
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor


def one_call(url: str, api_key: str | None) -> float:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    body = json.dumps({"features": [0.0] * 20}).encode()
    req = urllib.request.Request(f"{url}/v1/predict", data=body, headers=headers)
    start = time.perf_counter()
    with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
        resp.read()
    return (time.perf_counter() - start) * 1000


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8080")
    ap.add_argument("--requests", type=int, default=200)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--api-key", default=None)
    args = ap.parse_args()

    with ThreadPoolExecutor(args.concurrency) as pool:
        lat = sorted(pool.map(lambda _: one_call(args.url, args.api_key), range(args.requests)))
    p = lambda q: lat[min(len(lat) - 1, int(len(lat) * q))]  # noqa: E731
    print(f"n={len(lat)} mean={statistics.mean(lat):.1f}ms "
          f"p50={p(0.5):.1f}ms p95={p(0.95):.1f}ms p99={p(0.99):.1f}ms")


if __name__ == "__main__":
    main()
