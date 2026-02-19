"""Mood tracker panel widget — groups moods by day."""
from __future__ import annotations

from collections import OrderedDict
from textual.widgets import Static
from textual.containers import VerticalScroll
from textual.reactive import reactive

from lazytool.data import DataManager


MOOD_DISPLAY = {
    "amazing":  ("🤩", "#50fa7b", "Amazing"),
    "great":    ("😊", "#8be9fd", "Great"),
    "good":     ("🙂", "#f1fa8c", "Good"),
    "okay":     ("😐", "#ffb86c", "Okay"),
    "bad":      ("😔", "#ff79c6", "Bad"),
    "terrible": ("😢", "#ff5555", "Terrible"),
}


class MoodPanel(VerticalScroll):
    """Displays mood history grouped by day.

    Sidebar shows one row per day (most recent mood).
    Centre detail shows all moods for the selected day.
    """

    selected_index: reactive[int] = reactive(0)

    def __init__(self, data_manager: DataManager, **kwargs):
        super().__init__(**kwargs)
        self.data_manager = data_manager
        self.border_title = "[3]─Moods"

    # ── Grouping helper ──────────────────────────────────

    def _get_grouped_moods(self) -> list[tuple[str, list[dict]]]:
        """Return moods grouped by date, newest day first.

        Each entry is (date_str, [moods_for_that_day_newest_first]).
        """
        groups: OrderedDict[str, list[dict]] = OrderedDict()
        # Iterate newest-to-oldest
        for mood in reversed(self.data_manager.moods):
            day = mood.get("date", "unknown")
            groups.setdefault(day, []).append(mood)
        return list(groups.items())

    # ── Build sidebar items ──────────────────────────────

    def compose(self):
        yield from self._build_items()

    def _build_items(self):
        groups = self._get_grouped_moods()
        if not groups:
            yield Static("  No moods logged yet.\n  Press [a] to log.", classes="empty-message")
            return

        for i, (day, moods) in enumerate(groups):
            # Show most recent mood for this day
            latest = moods[0]
            emoji, color, label = MOOD_DISPLAY.get(
                latest["mood"], ("❓", "#f8f8f2", latest["mood"])
            )
            count = len(moods)
            count_text = f" (+{count - 1})" if count > 1 else ""

            classes = "list-item"
            if i == self.selected_index:
                classes += " list-item-selected"

            line = f"[dim]{day}[/] {emoji} [{color}]{label}[/]{count_text}"
            yield Static(line, classes=classes, markup=True)

    def refresh_list(self):
        self.remove_children()
        self.mount(*list(self._build_items()))
        count = len(self._get_grouped_moods())
        if count > 0:
            self.selected_index = min(self.selected_index, count - 1)

    # ── Selection ────────────────────────────────────────

    def get_selected(self) -> dict | None:
        """Return the most recent mood of the selected day group."""
        groups = self._get_grouped_moods()
        if groups and 0 <= self.selected_index < len(groups):
            _day, moods = groups[self.selected_index]
            return moods[0]  # most recent
        return None

    def move_up(self):
        if self.selected_index > 0:
            self.selected_index -= 1
            self.refresh_list()

    def move_down(self):
        if self.selected_index < len(self._get_grouped_moods()) - 1:
            self.selected_index += 1
            self.refresh_list()

    # ── Detail (centre pane) ─────────────────────────────

    def get_detail_text(self) -> str:
        groups = self._get_grouped_moods()
        if not groups:
            return "No moods logged.\n\nPress [bold cyan]a[/] to log today's mood."

        if self.selected_index >= len(groups):
            return ""

        day, moods = groups[self.selected_index]

        parts = [
            f"[bold cyan]Moods — {day}[/]",
            f"[dim]─────────────────────────────────[/]\n",
        ]

        for mood in moods:
            emoji, color, label = MOOD_DISPLAY.get(
                mood["mood"], ("❓", "#f8f8f2", mood["mood"])
            )
            time_str = mood.get("created_at", "")
            # Extract just the time portion (HH:MM:SS)
            if "T" in time_str:
                time_str = time_str.split("T")[1]
            note_text = f"  [dim]{mood['note']}[/]" if mood.get("note") else ""
            parts.append(
                f"  {emoji}  [{color}][bold]{label}[/bold][/]  [dim]{time_str}[/]{note_text}"
            )

        parts.append(f"\n[dim]{len(moods)} mood(s) logged on {day}[/]")
        return "\n".join(parts)

    def get_counter_text(self) -> str:
        groups = self._get_grouped_moods()
        total_days = len(groups)
        total_moods = len(self.data_manager.moods)
        if total_days == 0:
            return "0 of 0"
        return f"Day {self.selected_index + 1} of {total_days} ({total_moods} total)"
