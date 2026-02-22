"""Tests for lazytool.data.DataManager — covers all core operations.

Run with:  python -m pytest tests/test_data.py -v
"""
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

# We need to patch DATA_DIR and DATA_FILE before importing DataManager
# so it doesn't touch the real ~/.lazytool/data.json


@pytest.fixture
def dm(tmp_path):
    """Create a DataManager that uses a temporary directory."""
    data_dir = tmp_path / ".lazytool"
    data_file = data_dir / "data.json"

    with patch("lazytool.data.DATA_DIR", data_dir), \
         patch("lazytool.data.DATA_FILE", data_file):
        from lazytool.data import DataManager
        manager = DataManager()
        yield manager


# ═══════════════════════════════════════════════════════════
# TODOS
# ═══════════════════════════════════════════════════════════

class TestTodos:
    def test_add_todo(self, dm):
        dm.add_todo("Buy milk")
        assert len(dm.todos) == 1
        assert dm.todos[0]["text"] == "Buy milk"
        assert dm.todos[0]["done"] is False
        assert dm.todos[0]["priority"] == "medium"
        assert "id" in dm.todos[0]
        assert "created_at" in dm.todos[0]

    def test_multiple_todos(self, dm):
        dm.add_todo("Task 1")
        dm.add_todo("Task 2")
        dm.add_todo("Task 3")
        assert len(dm.todos) == 3

    def test_toggle_todo(self, dm):
        dm.add_todo("Test task")
        todo_id = dm.todos[0]["id"]
        dm.toggle_todo(todo_id)
        assert dm.todos[0]["done"] is True
        assert dm.todos[0]["done_at"] is not None

    def test_toggle_todo_back(self, dm):
        dm.add_todo("Test task")
        todo_id = dm.todos[0]["id"]
        dm.toggle_todo(todo_id)  # mark done
        dm.toggle_todo(todo_id)  # mark undone
        assert dm.todos[0]["done"] is False
        assert dm.todos[0]["done_at"] is None

    def test_edit_todo(self, dm):
        dm.add_todo("Old text")
        todo_id = dm.todos[0]["id"]
        dm.edit_todo(todo_id, "New text")
        assert dm.todos[0]["text"] == "New text"

    def test_delete_todo(self, dm):
        dm.add_todo("Task 1")
        dm.add_todo("Task 2")
        todo_id = dm.todos[0]["id"]
        dm.delete_todo(todo_id)
        assert len(dm.todos) == 1
        assert dm.todos[0]["text"] == "Task 2"

    def test_cycle_priority(self, dm):
        dm.add_todo("Test")
        todo_id = dm.todos[0]["id"]
        assert dm.todos[0]["priority"] == "medium"
        dm.cycle_priority(todo_id)
        assert dm.todos[0]["priority"] == "high"
        dm.cycle_priority(todo_id)
        assert dm.todos[0]["priority"] == "low"
        dm.cycle_priority(todo_id)
        assert dm.todos[0]["priority"] == "medium"


class TestTodoSorting:
    def test_pending_before_done(self, dm):
        dm.add_todo("Done task")
        dm.add_todo("Pending task")
        dm.toggle_todo(dm.todos[0]["id"])  # mark first as done
        sorted_todos = dm.get_sorted_todos()
        assert sorted_todos[0]["text"] == "Pending task"
        assert sorted_todos[1]["text"] == "Done task"

    def test_sort_by_priority(self, dm):
        dm.add_todo("Low")
        dm.add_todo("High")
        dm.add_todo("Medium")
        # Set priorities: medium->high for "High", medium->high->low for "Low"
        for t in dm.todos:
            if t["text"] == "High":
                dm.cycle_priority(t["id"])  # medium -> high
            elif t["text"] == "Low":
                dm.cycle_priority(t["id"])  # medium -> high
                dm.cycle_priority(t["id"])  # high -> low

        sorted_todos = dm.get_sorted_todos()
        assert sorted_todos[0]["text"] == "High"
        assert sorted_todos[1]["text"] == "Medium"
        assert sorted_todos[2]["text"] == "Low"


class TestTodoPurge:
    def test_purge_old_done_todos(self, dm):
        dm.add_todo("Old done")
        dm.add_todo("Recent done")
        dm.add_todo("Still pending")

        # Mark first two as done
        dm.toggle_todo(dm.todos[0]["id"])
        dm.toggle_todo(dm.todos[1]["id"])

        # Backdated the first one's done_at to 10 days ago
        old_date = (datetime.now() - timedelta(days=10)).isoformat(timespec="seconds")
        for t in dm.todos:
            if t["text"] == "Old done":
                t["done_at"] = old_date

        dm.update_setting("todo_purge_days", 7)
        purged = dm.purge_old_done_todos()

        assert purged == 1
        texts = [t["text"] for t in dm.todos]
        assert "Old done" not in texts
        assert "Recent done" in texts
        assert "Still pending" in texts

    def test_purge_zero_days_disabled(self, dm):
        dm.add_todo("Done task")
        dm.toggle_todo(dm.todos[0]["id"])
        dm.update_setting("todo_purge_days", 0)
        purged = dm.purge_old_done_todos()
        assert purged == 0
        assert len(dm.todos) == 1


# ═══════════════════════════════════════════════════════════
# JOURNAL
# ═══════════════════════════════════════════════════════════

class TestJournal:
    def test_add_journal_entry(self, dm):
        dm.add_journal_entry("Today was great")
        assert len(dm.journal) == 1
        assert dm.journal[0]["content"] == "Today was great"
        assert "date" in dm.journal[0]

    def test_edit_journal_entry(self, dm):
        dm.add_journal_entry("Original")
        entry_id = dm.journal[0]["id"]
        dm.edit_journal_entry(entry_id, "Edited")
        assert dm.journal[0]["content"] == "Edited"

    def test_delete_journal_entry(self, dm):
        dm.add_journal_entry("Entry 1")
        dm.add_journal_entry("Entry 2")
        entry_id = dm.journal[0]["id"]
        dm.delete_journal_entry(entry_id)
        assert len(dm.journal) == 1


# ═══════════════════════════════════════════════════════════
# MOODS
# ═══════════════════════════════════════════════════════════

class TestMoods:
    def test_add_mood(self, dm):
        dm.add_mood("happy")
        assert len(dm.moods) == 1
        assert dm.moods[0]["mood"] == "happy"
        assert "date" in dm.moods[0]

    def test_add_mood_with_note(self, dm):
        dm.add_mood("happy", note="Feeling amazing")
        assert dm.moods[0]["note"] == "Feeling amazing"

    def test_delete_mood(self, dm):
        dm.add_mood("happy")
        dm.add_mood("sad")
        mood_id = dm.moods[0]["id"]
        dm.delete_mood(mood_id)
        assert len(dm.moods) == 1


# ═══════════════════════════════════════════════════════════
# GOALS
# ═══════════════════════════════════════════════════════════

class TestGoals:
    def test_add_goal(self, dm):
        dm.add_goal("Exercise daily")
        assert len(dm.goals) == 1
        assert dm.goals[0]["title"] == "Exercise daily"
        assert dm.goals[0]["description"] == ""
        assert dm.goals[0]["check_ins"] == []

    def test_add_goal_with_description(self, dm):
        dm.add_goal("Read", description="Read 30 minutes every day")
        assert dm.goals[0]["description"] == "Read 30 minutes every day"

    def test_edit_goal(self, dm):
        dm.add_goal("Old title")
        goal_id = dm.goals[0]["id"]
        dm.edit_goal(goal_id, title="New title", description="Updated desc")
        assert dm.goals[0]["title"] == "New title"
        assert dm.goals[0]["description"] == "Updated desc"

    def test_delete_goal(self, dm):
        dm.add_goal("Goal 1")
        dm.add_goal("Goal 2")
        goal_id = dm.goals[0]["id"]
        dm.delete_goal(goal_id)
        assert len(dm.goals) == 1
        assert dm.goals[0]["title"] == "Goal 2"


class TestGoalCheckIn:
    def test_check_in_today(self, dm):
        dm.add_goal("Test goal")
        goal_id = dm.goals[0]["id"]
        result = dm.check_in_goal(goal_id)
        assert result is True
        assert date.today().isoformat() in dm.goals[0]["check_ins"]

    def test_uncheck(self, dm):
        dm.add_goal("Test goal")
        goal_id = dm.goals[0]["id"]
        dm.check_in_goal(goal_id)  # check in
        result = dm.check_in_goal(goal_id)  # uncheck
        assert result is False
        assert date.today().isoformat() not in dm.goals[0]["check_ins"]

    def test_check_in_specific_day(self, dm):
        dm.add_goal("Test goal")
        goal_id = dm.goals[0]["id"]
        dm.check_in_goal(goal_id, day="2026-01-15")
        assert "2026-01-15" in dm.goals[0]["check_ins"]

    def test_check_ins_sorted(self, dm):
        dm.add_goal("Test goal")
        goal_id = dm.goals[0]["id"]
        dm.check_in_goal(goal_id, day="2026-01-20")
        dm.check_in_goal(goal_id, day="2026-01-10")
        dm.check_in_goal(goal_id, day="2026-01-15")
        check_ins = dm.goals[0]["check_ins"]
        assert check_ins == sorted(check_ins)


class TestGoalStreak:
    def test_no_check_ins(self, dm):
        dm.add_goal("Test")
        assert dm.get_goal_streak(dm.goals[0]) == 0

    def test_streak_from_today(self, dm):
        dm.add_goal("Test")
        goal = dm.goals[0]
        today = date.today()
        # Check in today and the last 4 days
        for i in range(5):
            d = (today - timedelta(days=i)).isoformat()
            goal["check_ins"].append(d)
        assert dm.get_goal_streak(goal) == 5

    def test_streak_from_yesterday(self, dm):
        """Streak counts if yesterday was the last check-in."""
        dm.add_goal("Test")
        goal = dm.goals[0]
        today = date.today()
        # Check in yesterday and the 2 days before
        for i in range(1, 4):
            d = (today - timedelta(days=i)).isoformat()
            goal["check_ins"].append(d)
        assert dm.get_goal_streak(goal) == 3

    def test_broken_streak(self, dm):
        """Gap in check-ins breaks the streak."""
        dm.add_goal("Test")
        goal = dm.goals[0]
        today = date.today()
        # Check in today and 3 days ago (gap of 1 day)
        goal["check_ins"].append(today.isoformat())
        goal["check_ins"].append((today - timedelta(days=2)).isoformat())
        goal["check_ins"].append((today - timedelta(days=3)).isoformat())
        assert dm.get_goal_streak(goal) == 1  # only today


class TestGoalHistory:
    def test_history_new_goal_only_today(self, dm):
        """A goal created today should only show 1 day of history."""
        dm.add_goal("Test")
        history = dm.get_goal_history(dm.goals[0], days=30)
        assert len(history) == 1
        # First entry should be today
        assert history[0][0] == date.today().isoformat()

    def test_history_respects_created_at(self, dm):
        """History should only go back to created_at date."""
        dm.add_goal("Test")
        goal = dm.goals[0]
        # Backdate created_at to 10 days ago
        created = (date.today() - timedelta(days=10)).isoformat()
        goal["created_at"] = created + "T00:00:00"
        history = dm.get_goal_history(goal, days=30)
        assert len(history) == 11  # today + 10 days back
        assert history[0][0] == date.today().isoformat()
        assert history[-1][0] == created

    def test_history_with_check_ins(self, dm):
        dm.add_goal("Test")
        goal = dm.goals[0]
        today = date.today().isoformat()
        goal["check_ins"].append(today)
        history = dm.get_goal_history(goal, days=7)
        assert history[0] == (today, True)


# ═══════════════════════════════════════════════════════════
# TIMELINE
# ═══════════════════════════════════════════════════════════

class TestTimeline:
    def test_start_event(self, dm):
        ev = dm.start_event("Studying")
        assert ev["name"] == "Studying"
        assert ev["end_time"] is None
        assert len(dm.timeline) == 1

    def test_end_event(self, dm):
        ev = dm.start_event("Working")
        dm.end_event(ev["id"])
        assert dm.timeline[0]["end_time"] is not None

    def test_start_ends_previous(self, dm):
        """Starting a new event should end the currently active one."""
        ev1 = dm.start_event("Activity 1")
        ev2 = dm.start_event("Activity 2")
        assert dm.timeline[0]["end_time"] is not None  # ev1 ended
        assert dm.timeline[1]["end_time"] is None  # ev2 still active

    def test_get_active_event(self, dm):
        assert dm.get_active_event() is None
        ev = dm.start_event("Active")
        assert dm.get_active_event()["id"] == ev["id"]
        dm.end_event(ev["id"])
        assert dm.get_active_event() is None

    def test_delete_event(self, dm):
        ev = dm.start_event("Delete me")
        dm.delete_event(ev["id"])
        assert len(dm.timeline) == 0

    def test_event_duration(self, dm):
        ev = dm.start_event("Timed")
        # Manually set times for predictable duration
        ev["start_time"] = "2026-02-20T10:00:00"
        ev["end_time"] = "2026-02-20T10:30:00"
        duration = dm.get_event_duration_minutes(ev)
        assert duration == 30.0


class TestCrossMidnight:
    """Tests for events that span midnight boundaries."""

    def test_event_appears_on_both_days(self, dm):
        """An event from 22:00 day X to 03:00 day X+1 should appear on both days."""
        ev = dm.start_event("Night work")
        ev["date"] = "2026-02-20"
        ev["start_time"] = "2026-02-20T22:00:00"
        ev["end_time"] = "2026-02-21T03:00:00"

        day1 = dm.get_events_for_date("2026-02-20")
        day2 = dm.get_events_for_date("2026-02-21")

        assert len(day1) == 1, "Event should appear on start day"
        assert len(day2) == 1, "Event should spill over to next day"
        assert day1[0]["id"] == ev["id"]
        assert day2[0]["id"] == ev["id"]

    def test_clamped_times_day1(self, dm):
        """Day 1 should show 22:00–00:00:00 (midnight)."""
        ev = dm.start_event("Night work")
        ev["date"] = "2026-02-20"
        ev["start_time"] = "2026-02-20T22:00:00"
        ev["end_time"] = "2026-02-21T03:00:00"

        day1 = dm.get_events_for_date("2026-02-20")
        assert day1[0]["_day_start"] == "2026-02-20T22:00:00"
        # End should be clamped to midnight (end of day)
        clamped_end = datetime.fromisoformat(day1[0]["_day_end"])
        assert clamped_end.hour == 0 and clamped_end.day == 21

    def test_clamped_times_day2(self, dm):
        """Day 2 should show 00:00–03:00."""
        ev = dm.start_event("Night work")
        ev["date"] = "2026-02-20"
        ev["start_time"] = "2026-02-20T22:00:00"
        ev["end_time"] = "2026-02-21T03:00:00"

        day2 = dm.get_events_for_date("2026-02-21")
        assert day2[0]["_day_start"] == "2026-02-21T00:00:00"
        assert day2[0]["_day_end"] == "2026-02-21T03:00:00"

    def test_spillover_flag(self, dm):
        """The _is_spillover flag should be True on the next day, False on the start day."""
        ev = dm.start_event("Night work")
        ev["date"] = "2026-02-20"
        ev["start_time"] = "2026-02-20T22:00:00"
        ev["end_time"] = "2026-02-21T03:00:00"

        day1 = dm.get_events_for_date("2026-02-20")
        day2 = dm.get_events_for_date("2026-02-21")

        assert day1[0]["_is_spillover"] is False
        assert day2[0]["_is_spillover"] is True

    def test_per_day_duration(self, dm):
        """Per-day duration should be clamped, total duration should be full span."""
        ev = dm.start_event("Night work")
        ev["date"] = "2026-02-20"
        ev["start_time"] = "2026-02-20T22:00:00"
        ev["end_time"] = "2026-02-21T03:00:00"

        # Total duration = 5 hours = 300 minutes
        assert dm.get_event_duration_minutes(ev) == 300.0

        day1 = dm.get_events_for_date("2026-02-20")
        day2 = dm.get_events_for_date("2026-02-21")

        # Day 1: 22:00 to ~00:00 = ~2 hours
        d1_mins = dm.get_event_day_duration_minutes(day1[0])
        assert 119 <= d1_mins <= 121  # ~120 minutes (midnight boundary)

        # Day 2: 00:00 to 03:00 = 3 hours
        d2_mins = dm.get_event_day_duration_minutes(day2[0])
        assert d2_mins == 180.0

    def test_same_day_event_unaffected(self, dm):
        """A normal same-day event should work exactly as before."""
        ev = dm.start_event("Morning run")
        ev["date"] = "2026-02-20"
        ev["start_time"] = "2026-02-20T08:00:00"
        ev["end_time"] = "2026-02-20T09:00:00"

        events = dm.get_events_for_date("2026-02-20")
        assert len(events) == 1
        assert events[0]["_is_spillover"] is False
        assert events[0]["_day_start"] == "2026-02-20T08:00:00"
        assert events[0]["_day_end"] == "2026-02-20T09:00:00"

    def test_event_does_not_appear_on_unrelated_day(self, dm):
        """An event should not appear on a day it doesn't overlap."""
        ev = dm.start_event("Night work")
        ev["date"] = "2026-02-20"
        ev["start_time"] = "2026-02-20T22:00:00"
        ev["end_time"] = "2026-02-21T03:00:00"

        day3 = dm.get_events_for_date("2026-02-22")
        assert len(day3) == 0


# ═══════════════════════════════════════════════════════════
# SETTINGS
# ═══════════════════════════════════════════════════════════

class TestSettings:
    def test_default_settings(self, dm):
        assert dm.settings.get("stats_days") == 7
        assert dm.settings.get("todo_purge_days") == 7
        assert dm.settings.get("goal_history_days") == 30

    def test_update_setting(self, dm):
        dm.update_setting("stats_days", 14)
        assert dm.settings["stats_days"] == 14

    def test_update_preserves_others(self, dm):
        dm.update_setting("stats_days", 14)
        assert dm.settings.get("todo_purge_days") == 7  # unchanged


# ═══════════════════════════════════════════════════════════
# STATS
# ═══════════════════════════════════════════════════════════

class TestStats:
    def test_stats_structure(self, dm):
        stats = dm.get_stats()
        expected_keys = [
            "total_todos", "done_todos", "pending_todos",
            "total_journal", "total_words",
            "total_moods", "avg_mood_score",
            "total_goals", "goals_checked_today",
            "hours_by_activity", "total_tracked_hours",
            "stats_days",
        ]
        for key in expected_keys:
            assert key in stats, f"Missing key: {key}"

    def test_stats_counts(self, dm):
        dm.add_todo("Task 1")
        dm.add_todo("Task 2")
        dm.toggle_todo(dm.todos[0]["id"])
        dm.add_journal_entry("Hello world")
        dm.add_mood("happy")
        dm.add_goal("Exercise")

        stats = dm.get_stats()
        assert stats["total_todos"] == 2
        assert stats["done_todos"] == 1
        assert stats["pending_todos"] == 1
        assert stats["total_journal"] == 1
        assert stats["total_words"] == 2
        assert stats["total_moods"] == 1
        assert stats["total_goals"] == 1


# ═══════════════════════════════════════════════════════════
# DATA PERSISTENCE
# ═══════════════════════════════════════════════════════════

class TestPersistence:
    def test_data_survives_reload(self, tmp_path):
        """Data should persist across DataManager instances."""
        data_dir = tmp_path / ".lazytool"
        data_file = data_dir / "data.json"

        with patch("lazytool.data.DATA_DIR", data_dir), \
             patch("lazytool.data.DATA_FILE", data_file):
            from lazytool.data import DataManager

            dm1 = DataManager()
            dm1.add_todo("Persistent task")
            dm1.add_goal("Persistent goal")
            dm1.add_journal_entry("Persistent entry")

            # Create a new DataManager instance (simulates app restart)
            dm2 = DataManager()
            assert len(dm2.todos) == 1
            assert dm2.todos[0]["text"] == "Persistent task"
            assert len(dm2.goals) == 1
            assert dm2.goals[0]["title"] == "Persistent goal"
            assert len(dm2.journal) == 1
