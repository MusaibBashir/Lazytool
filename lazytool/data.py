"""Data persistence layer for LazyTool — stores everything in ~/.lazytool/data.json"""
import json
import os
import uuid
from datetime import datetime, date, timedelta
from pathlib import Path


DATA_DIR = Path.home() / ".lazytool"
DATA_FILE = DATA_DIR / "data.json"

DEFAULT_DATA = {
    "todos": [],
    "journal": [],
    "moods": [],
    "habits": [],  # legacy, kept for data compat
    "goals": [],
    "notes": [],
    "timeline": [],
    "settings": {
        "stats_days": 7,
    },
}


class DataManager:
    def __init__(self):
        self._ensure_dir()
        self._data = self._load()

    def _ensure_dir(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict:
        if DATA_FILE.exists():
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Ensure all keys exist
                for key in DEFAULT_DATA:
                    if key not in data:
                        data[key] = []
                return data
            except (json.JSONDecodeError, IOError):
                return json.loads(json.dumps(DEFAULT_DATA))
        return json.loads(json.dumps(DEFAULT_DATA))

    def _save(self):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def _new_id(self) -> str:
        return uuid.uuid4().hex[:8]

    def _now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")

    def _today(self) -> str:
        return date.today().isoformat()

    # ── Todos ─────────────────────────────────────────────
    @property
    def todos(self) -> list[dict]:
        return self._data["todos"]

    def add_todo(self, text: str, priority: str = "medium") -> dict:
        todo = {
            "id": self._new_id(),
            "text": text,
            "done": False,
            "priority": priority,
            "created_at": self._now(),
        }
        self._data["todos"].append(todo)
        self._save()
        return todo

    def toggle_todo(self, todo_id: str):
        for t in self._data["todos"]:
            if t["id"] == todo_id:
                t["done"] = not t["done"]
                t["done_at"] = self._now() if t["done"] else None
                break
        self._save()

    def edit_todo(self, todo_id: str, text: str):
        for t in self._data["todos"]:
            if t["id"] == todo_id:
                t["text"] = text
                break
        self._save()

    def cycle_priority(self, todo_id: str):
        priorities = ["low", "medium", "high"]
        for t in self._data["todos"]:
            if t["id"] == todo_id:
                idx = priorities.index(t.get("priority", "medium"))
                t["priority"] = priorities[(idx + 1) % len(priorities)]
                break
        self._save()

    def delete_todo(self, todo_id: str):
        self._data["todos"] = [t for t in self._data["todos"] if t["id"] != todo_id]
        self._save()

    PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}

    def get_sorted_todos(self) -> list[dict]:
        """Return todos sorted: pending first (by priority then created),
        then done (by done_at descending)."""
        pending = [t for t in self.todos if not t["done"]]
        done = [t for t in self.todos if t["done"]]

        # Pending: sort by priority (high first), then by created_at (oldest first)
        pending.sort(key=lambda t: (
            self.PRIORITY_ORDER.get(t.get("priority", "medium"), 1),
            t.get("created_at", ""),
        ))

        # Done: sort by done_at descending (most recently completed first)
        done.sort(key=lambda t: t.get("done_at", t.get("created_at", "")), reverse=True)

        return pending + done

    def purge_old_done_todos(self) -> int:
        """Delete done todos older than the configured purge window. Returns count deleted."""
        purge_days = self.settings.get("todo_purge_days", 7)
        if purge_days <= 0:
            return 0
        cutoff = (datetime.now() - timedelta(days=purge_days)).isoformat(timespec="seconds")
        before = len(self._data["todos"])
        self._data["todos"] = [
            t for t in self._data["todos"]
            if not (t["done"] and t.get("done_at", t.get("created_at", "")) < cutoff)
        ]
        after = len(self._data["todos"])
        if before != after:
            self._save()
        return before - after

    # ── Journal ───────────────────────────────────────────
    @property
    def journal(self) -> list[dict]:
        return self._data["journal"]

    def add_journal_entry(self, content: str) -> dict:
        entry = {
            "id": self._new_id(),
            "content": content,
            "date": self._today(),
            "created_at": self._now(),
        }
        self._data["journal"].append(entry)
        self._save()
        return entry

    def edit_journal_entry(self, entry_id: str, content: str):
        for e in self._data["journal"]:
            if e["id"] == entry_id:
                e["content"] = content
                break
        self._save()

    def delete_journal_entry(self, entry_id: str):
        self._data["journal"] = [e for e in self._data["journal"] if e["id"] != entry_id]
        self._save()

    # ── Moods ─────────────────────────────────────────────
    MOOD_OPTIONS = [
        ("amazing", "🤩", "#50fa7b"),
        ("great", "😊", "#8be9fd"),
        ("good", "🙂", "#f1fa8c"),
        ("okay", "😐", "#ffb86c"),
        ("bad", "😔", "#ff79c6"),
        ("terrible", "😢", "#ff5555"),
    ]

    @property
    def moods(self) -> list[dict]:
        return self._data["moods"]

    def add_mood(self, mood: str, note: str = "") -> dict:
        entry = {
            "id": self._new_id(),
            "mood": mood,
            "note": note,
            "date": self._today(),
            "created_at": self._now(),
        }
        self._data["moods"].append(entry)
        self._save()
        return entry

    def delete_mood(self, mood_id: str):
        self._data["moods"] = [m for m in self._data["moods"] if m["id"] != mood_id]
        self._save()

    # ── Goals ─────────────────────────────────────────────
    @property
    def goals(self) -> list[dict]:
        if "goals" not in self._data:
            self._data["goals"] = []
        return self._data["goals"]

    def add_goal(self, title: str, description: str = "") -> dict:
        goal = {
            "id": self._new_id(),
            "title": title,
            "description": description,
            "check_ins": [],
            "created_at": self._now(),
        }
        self.goals.append(goal)
        self._save()
        return goal

    def edit_goal(self, goal_id: str, title: str = None, description: str = None):
        for g in self.goals:
            if g["id"] == goal_id:
                if title is not None:
                    g["title"] = title
                if description is not None:
                    g["description"] = description
                break
        self._save()

    def delete_goal(self, goal_id: str):
        self._data["goals"] = [g for g in self.goals if g["id"] != goal_id]
        self._save()

    def check_in_goal(self, goal_id: str, day: str = None) -> bool:
        """Toggle check-in for a goal on the given date (default today).
        Returns True if checked in, False if unchecked."""
        day = day or self._today()
        for g in self.goals:
            if g["id"] == goal_id:
                if "check_ins" not in g:
                    g["check_ins"] = []
                if day in g["check_ins"]:
                    g["check_ins"].remove(day)
                    self._save()
                    return False
                else:
                    g["check_ins"].append(day)
                    g["check_ins"].sort()
                    self._save()
                    return True
        return False

    def get_goal_streak(self, goal: dict) -> int:
        """Current consecutive-day streak ending today or yesterday."""
        check_ins = set(goal.get("check_ins", []))
        if not check_ins:
            return 0
        today = date.today()
        d = today
        if d.isoformat() not in check_ins:
            d = today - timedelta(days=1)
            if d.isoformat() not in check_ins:
                return 0
        streak = 0
        while d.isoformat() in check_ins:
            streak += 1
            d -= timedelta(days=1)
        return streak

    def get_goal_history(self, goal: dict, days: int = 30) -> list[tuple[str, bool]]:
        """Return [(date_str, was_checked_in)] for the last N days, newest first."""
        check_ins = set(goal.get("check_ins", []))
        today = date.today()
        result = []
        for i in range(days):
            d = (today - timedelta(days=i)).isoformat()
            result.append((d, d in check_ins))
        return result


    # ── Notes (legacy, kept for data compat) ────────────
    @property
    def notes(self) -> list[dict]:
        return self._data.get("notes", [])

    def add_note(self, title: str, content: str = "") -> dict:
        note = {
            "id": self._new_id(),
            "title": title,
            "content": content,
            "created_at": self._now(),
        }
        if "notes" not in self._data:
            self._data["notes"] = []
        self._data["notes"].append(note)
        self._save()
        return note

    def delete_note(self, note_id: str):
        self._data["notes"] = [n for n in self._data.get("notes", []) if n["id"] != note_id]
        self._save()

    # ── Timeline ──────────────────────────────────────────
    @property
    def timeline(self) -> list[dict]:
        return self._data.get("timeline", [])

    def get_active_event(self) -> dict | None:
        """Return the currently in-progress event, if any."""
        for ev in self.timeline:
            if ev.get("end_time") is None:
                return ev
        return None

    def start_event(self, name: str) -> dict:
        """Start a new timeline event. Ends any active event first."""
        active = self.get_active_event()
        if active:
            self.end_event(active["id"])
        event = {
            "id": self._new_id(),
            "name": name,
            "date": self._today(),
            "start_time": self._now(),
            "end_time": None,
        }
        if "timeline" not in self._data:
            self._data["timeline"] = []
        self._data["timeline"].append(event)
        self._save()
        return event

    def end_event(self, event_id: str) -> None:
        """End a timeline event by setting its end_time."""
        for ev in self._data.get("timeline", []):
            if ev["id"] == event_id:
                ev["end_time"] = self._now()
                break
        self._save()

    def get_events_for_date(self, target_date: str) -> list[dict]:
        """Get all events for a specific date string (YYYY-MM-DD)."""
        return [
            ev for ev in self.timeline
            if ev.get("date") == target_date
        ]

    def get_events_for_range(self, days: int = 7) -> dict[str, list[dict]]:
        """Get events grouped by date for the last N days."""
        result = {}
        for i in range(days):
            d = (date.today() - timedelta(days=i)).isoformat()
            result[d] = self.get_events_for_date(d)
        return result

    def get_event_duration_minutes(self, event: dict) -> float:
        """Calculate duration of an event in minutes."""
        start = datetime.fromisoformat(event["start_time"])
        if event.get("end_time"):
            end = datetime.fromisoformat(event["end_time"])
        else:
            end = datetime.now()
        return (end - start).total_seconds() / 60.0

    def delete_event(self, event_id: str):
        self._data["timeline"] = [
            ev for ev in self._data.get("timeline", []) if ev["id"] != event_id
        ]
        self._save()

    # ── Settings ───────────────────────────────────────────
    MOOD_SCORES = {
        "amazing": 5, "great": 4, "good": 3,
        "okay": 2, "bad": 1, "terrible": 0,
    }

    @property
    def settings(self) -> dict:
        default = {"stats_days": 7, "todo_purge_days": 7, "goal_history_days": 30}
        s = self._data.get("settings", None)
        if not isinstance(s, dict):
            self._data["settings"] = dict(default)
            return self._data["settings"]
        for k, v in default.items():
            if k not in s:
                s[k] = v
        return s

    def update_setting(self, key: str, value) -> None:
        if "settings" not in self._data:
            self._data["settings"] = {}
        self._data["settings"][key] = value
        self._save()

    # ── Stats helpers ─────────────────────────────────────
    def get_stats(self) -> dict:
        """Compute aggregate stats across all data."""
        today = self._today()
        todos = self.todos
        journal = self.journal
        moods = self.moods
        goals = self.goals
        timeline = self.timeline
        stats_days = self.settings.get("stats_days", 7)
        cutoff = (date.today() - timedelta(days=stats_days)).isoformat()

        # Todo stats
        total_todos = len(todos)
        done_todos = sum(1 for t in todos if t["done"])

        # Journal stats
        total_journal = len(journal)
        total_words = sum(len(e.get("content", "").split()) for e in journal)

        # Mood stats
        total_moods = len(moods)
        recent_moods = [m for m in moods if m.get("date", "") >= cutoff]
        if recent_moods:
            mood_sum = sum(self.MOOD_SCORES.get(m["mood"], 2) for m in recent_moods)
            avg_mood_score = mood_sum / len(recent_moods)
        else:
            avg_mood_score = None

        # Goal stats
        total_goals = len(goals)
        today = self._today()
        goals_checked_today = sum(
            1 for g in goals if today in g.get("check_ins", [])
        )

        # Timeline stats — hours by activity
        hours_by_activity: dict[str, float] = {}
        for ev in timeline:
            if ev.get("date", "") >= cutoff:
                mins = self.get_event_duration_minutes(ev)
                name = ev.get("name", "Unknown")
                hours_by_activity[name] = hours_by_activity.get(name, 0) + mins / 60.0

        total_tracked_hours = sum(hours_by_activity.values())

        return {
            "total_todos": total_todos,
            "done_todos": done_todos,
            "pending_todos": total_todos - done_todos,
            "total_journal": total_journal,
            "total_words": total_words,
            "total_moods": total_moods,
            "total_goals": total_goals,
            "goals_checked_today": goals_checked_today,
            "hours_by_activity": hours_by_activity,
            "total_tracked_hours": total_tracked_hours,
            "avg_mood_score": avg_mood_score,
            "stats_days": stats_days,
        }
