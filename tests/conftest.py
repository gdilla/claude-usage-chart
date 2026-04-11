"""Shared fixtures for analytics tests."""

import pytest
from datetime import datetime, timezone, timedelta


def make_record(
    date="2026-04-07",
    project="myapp",
    model="claude-sonnet-4-6",
    input_tokens=1000,
    output_tokens=500,
    cache_creation=200,
    cache_read=100,
    hour=10,
    weekday=0,
    session="session-001",
    timestamp=None,
):
    """Create a synthetic usage record matching the parser output format."""
    if timestamp is None:
        ts = datetime.strptime(date, "%Y-%m-%d").replace(
            hour=hour, tzinfo=timezone.utc
        )
    else:
        ts = timestamp
    return {
        "date": date,
        "project": project,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_creation_input_tokens": cache_creation,
        "cache_read_input_tokens": cache_read,
        "hour": hour,
        "weekday": weekday,
        "timestamp": ts,
        "session": session,
    }


@pytest.fixture
def sample_records():
    """Two weeks of synthetic records across projects, models, and time patterns."""
    records = []
    projects = ["webapp", "api-server", "cli-tool"]
    models = ["claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"]
    base = datetime(2026, 3, 30, tzinfo=timezone.utc)  # Monday

    for day_offset in range(14):
        dt = base + timedelta(days=day_offset)
        date_str = dt.strftime("%Y-%m-%d")
        wd = dt.weekday()
        is_weekend = wd >= 5

        # Fewer sessions on weekends
        sessions_today = 2 if is_weekend else 5
        for s in range(sessions_today):
            hour = 9 + s * 2  # 9am, 11am, 1pm, 3pm, 5pm
            proj = projects[s % len(projects)]
            model = models[s % len(models)]
            session_id = f"session-d{day_offset}-s{s}"

            # 3 messages per session
            for msg in range(3):
                records.append(make_record(
                    date=date_str,
                    project=proj,
                    model=model,
                    input_tokens=5000 + (day_offset * 100),
                    output_tokens=2000 + (day_offset * 50),
                    cache_creation=1000,
                    cache_read=500,
                    hour=hour,
                    weekday=wd,
                    session=session_id,
                    timestamp=dt.replace(hour=hour, minute=msg * 10),
                ))

    return records


@pytest.fixture
def empty_records():
    return []
