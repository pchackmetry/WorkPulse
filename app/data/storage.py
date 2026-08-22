import json
from datetime import datetime
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[2] / "data"
HISTORY_FILE = DATA_DIR / "workpulse_history.json"


DEFAULT_HISTORY = {
    "settings": {
        "water_goal_ml": 2000,
        "eye_interval_minutes": 20,
    },
    "water_records": [],
    "work_sessions": [],
    "break_records": [],
    "active_session": None,
}


def ensure_storage():
    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not HISTORY_FILE.exists():
        HISTORY_FILE.write_text(
            json.dumps(
                DEFAULT_HISTORY,
                indent=4,
            ),
            encoding="utf-8",
        )


def load_history():
    ensure_storage()

    try:
        content = HISTORY_FILE.read_text(
            encoding="utf-8"
        )

        data = json.loads(content)

        if not isinstance(data, dict):
            raise ValueError(
                "Invalid history format"
            )

    except (
        json.JSONDecodeError,
        OSError,
        ValueError,
    ):
        data = {
            "settings": dict(
                DEFAULT_HISTORY["settings"]
            ),
            "water_records": [],
            "work_sessions": [],
            "break_records": [],
            "active_session": None,
        }

    if not isinstance(
        data.get("settings"),
        dict,
    ):
        data["settings"] = dict(
            DEFAULT_HISTORY["settings"]
        )

    data["settings"].setdefault(
        "water_goal_ml",
        2000,
    )

    data["settings"].setdefault(
        "eye_interval_minutes",
        20,
    )

    data.setdefault(
        "water_records",
        [],
    )

    data.setdefault(
        "work_sessions",
        [],
    )

    data.setdefault(
        "break_records",
        [],
    )

    return data


def save_history(data):
    ensure_storage()

    HISTORY_FILE.write_text(
        json.dumps(
            data,
            indent=4,
        ),
        encoding="utf-8",
    )


def get_settings():
    data = load_history()

    return dict(
        data.get(
            "settings",
            DEFAULT_HISTORY["settings"],
        )
    )


def save_settings(
    water_goal_ml=None,
    eye_interval_minutes=None,
):
    data = load_history()

    settings = data.setdefault(
        "settings",
        {},
    )

    if water_goal_ml is not None:
        settings["water_goal_ml"] = int(
            water_goal_ml
        )

    if eye_interval_minutes is not None:
        settings["eye_interval_minutes"] = int(
            eye_interval_minutes
        )

    save_history(data)

    return settings


def add_water_record(amount_ml):
    data = load_history()

    now = datetime.now()

    record = {
        "amount_ml": int(amount_ml),
        "date": now.strftime(
            "%Y-%m-%d"
        ),
        "time": now.strftime(
            "%H:%M:%S"
        ),
        "local_datetime": now.isoformat(
            timespec="seconds"
        ),
    }

    data["water_records"].append(
        record
    )

    save_history(data)

    return record


def add_break_record():
    data = load_history()

    now = datetime.now()

    record = {
        "date": now.strftime(
            "%Y-%m-%d"
        ),
        "time": now.strftime(
            "%H:%M:%S"
        ),
        "local_datetime": now.isoformat(
            timespec="seconds"
        ),
    }

    data["break_records"].append(
        record
    )

    save_history(data)

    return record


def add_work_session(
    start_time,
    end_time,
    duration_seconds,
):
    data = load_history()

    record = {
        "start_time": start_time,
        "end_time": end_time,
        "duration_seconds": int(
            duration_seconds
        ),
        "date": datetime.now().strftime(
            "%Y-%m-%d"
        ),
    }

    data["work_sessions"].append(
        record
    )

    save_history(data)

    return record