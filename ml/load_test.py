"""Load test: do the main pages answer within 2 seconds with many users at once?

Logs in the demo accounts, then has N concurrent clients repeatedly fetch the pages a teacher and a
student use most (courses, runs, ranked pairs, one pair with both files, clusters, a review, flags).
Reports the median, 95th percentile and maximum per endpoint, and any errors.

Run against a running API (local by default):
    python ml/load_test.py --base http://localhost:8000 --users 25 --seconds 30
Uses the demo data from `python -m codetwin.cli seed-demo`.
"""
from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from collections import defaultdict

import httpx

PASSWORD = "codetwin-demo-1"


async def login(client: httpx.AsyncClient, email: str) -> dict:
    r = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def discover(client: httpx.AsyncClient, teacher: dict, student: dict) -> tuple[list[str], list[str]]:
    course = (await client.get("/courses", headers=teacher)).json()[0]["course_id"]
    assignment = (await client.get(f"/courses/{course}/assignments", headers=teacher)).json()[0]["assignment_id"]
    run = next(r for r in (await client.get(f"/assignments/{assignment}/runs", headers=teacher)).json()
               if r["status"] == "completed")["run_id"]
    pair = (await client.get(f"/runs/{run}/pairs?limit=1", headers=teacher)).json()["items"][0]["pair_id"]
    review = (await client.get(f"/runs/{run}/clusters", headers=teacher)).json()[0]["review_id"]
    teacher_paths = ["/courses", f"/courses/{course}/assignments", f"/assignments/{assignment}/submissions",
                     f"/assignments/{assignment}/runs", f"/runs/{run}", f"/runs/{run}/pairs?min_probability=0",
                     f"/pairs/{pair}", f"/runs/{run}/clusters", f"/reviews/{review}",
                     f"/courses/{course}/repeat-pairs"]
    student_paths = ["/me/flags", "/courses"]
    return teacher_paths, student_paths


async def user(client, headers, paths, until, timings, errors):
    i = 0
    while time.perf_counter() < until:
        path = paths[i % len(paths)]
        started = time.perf_counter()
        try:
            r = await client.get(path, headers=headers)
            ok = r.status_code == 200
        except httpx.HTTPError:
            ok = False
        key = path.split("?")[0]
        for part in key.split("/"):
            if part.isdigit():
                key = key.replace(f"/{part}", "/{id}", 1)
        timings[key].append((time.perf_counter() - started) * 1000)
        if not ok:
            errors[key] += 1
        i += 1


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8000")
    parser.add_argument("--users", type=int, default=25)
    parser.add_argument("--seconds", type=int, default=30)
    args = parser.parse_args()

    limits = httpx.Limits(max_connections=args.users * 2)
    async with httpx.AsyncClient(base_url=args.base, timeout=30, limits=limits) as client:
        teacher = await login(client, "teacher@demo.edu")
        student = await login(client, "student1@demo.edu")
        teacher_paths, student_paths = await discover(client, teacher, student)
        timings, errors = defaultdict(list), defaultdict(int)
        until = time.perf_counter() + args.seconds
        jobs = [user(client, teacher, teacher_paths[i % len(teacher_paths):] + teacher_paths[:i % len(teacher_paths)],
                     until, timings, errors) for i in range(args.users - args.users // 5)]
        jobs += [user(client, student, student_paths, until, timings, errors) for _ in range(args.users // 5)]
        await asyncio.gather(*jobs)

    total = sum(len(v) for v in timings.values())
    print(f"{args.users} concurrent users for {args.seconds}s: {total} requests, "
          f"{total / args.seconds:.0f} per second, {sum(errors.values())} errors")
    print(f"{'endpoint':42s} {'n':>6s} {'median':>8s} {'p95':>8s} {'max':>8s}  (ms)")
    worst = 0.0
    for key in sorted(timings):
        v = sorted(timings[key])
        p95 = v[min(len(v) - 1, int(0.95 * len(v)))]
        worst = max(worst, p95)
        print(f"{key:42s} {len(v):6d} {statistics.median(v):8.0f} {p95:8.0f} {v[-1]:8.0f}"
              + (f"  {errors[key]} errors" if errors[key] else ""))
    print(f"\nslowest 95th percentile: {worst:.0f} ms -> target (2,000 ms) {'met' if worst < 2000 else 'NOT met'}")


if __name__ == "__main__":
    asyncio.run(main())
