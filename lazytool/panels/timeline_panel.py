"""Timeline panel widget — track daily activities with start/end times."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from textual.widgets import Static
from textual.containers import VerticalScroll
from textual.reactive import reactive

from lazytool.data import DataManager

# Colors for different activities (cycles through these)
ACTIVITY_COLORS = [
    "#50fa7b", "#8be9fd", "#f1fa8c", "#ff79c6", "#ffb86c",
    "#bd93f9", "#ff5555", "#6272a4", "#f8f8f2",
]


def _color_for(index: int) -> str:
    """Color by position index — guarantees adjacent events differ."""
    return ACTIVITY_COLORS[index % len(ACTIVITY_COLORS)]


def _fmt_time(iso: str) -> str:
    """Format ISO time to HH:MM."""
    try:
        return datetime.fromisoformat(iso).strftime("%H:%M")
    except (ValueError, TypeError):
        return "??:??"


def _fmt_duration(minutes: float) -> str:
    """Format minutes to Xh Ym."""
    h = int(minutes // 60)
    m = int(minutes % 60)
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m"


class TimelinePanel(VerticalScroll):
    """Displays timeline of daily activities.

    Sidebar shows only the current/last activity as a summary.
    Centre detail shows the full coloured timeline bar and event list.
    """

    selected_index: reactive[int] = reactive(0)
    view_day_offset: reactive[int] = reactive(0)  # 0 = today, 1 = yesterday, etc.

    def __init__(self, data_manager: DataManager, **kwargs):
        super().__init__(**kwargs)
        self.data_manager = data_manager
        self.border_title = "[5]─Timeline"

    def _viewed_date(self) -> str:
        return (date.today() - timedelta(days=self.view_day_offset)).isoformat()

    # ── Sidebar: compact summary ─────────────────────────

    def compose(self):
        yield from self._build_items()

    def _build_items(self):
        """Build sidebar — shows only current or last activity."""
        viewed = self._viewed_date()
        day_label = "Today" if self.view_day_offset == 0 else (
            "Yesterday" if self.view_day_offset == 1 else viewed
        )

        yield Static(
            f"[bold cyan]{day_label}[/]  [dim]({viewed})[/]  "
            f"[dim]<< h  l >>[/]",
            markup=True,
        )

        active = self.data_manager.get_active_event()

        if active and self.view_day_offset == 0:
            dur = _fmt_duration(self.data_manager.get_event_duration_minutes(active))
            yield Static(
                f"  [bold #50fa7b]▶ {active['name']}[/] [yellow]{dur}[/] [dim](now)[/]",
                markup=True,
            )
        else:
            # Show last completed activity for the viewed day
            events = self.data_manager.get_events_for_date(viewed)
            if events:
                last = events[-1]
                dur = _fmt_duration(self.data_manager.get_event_duration_minutes(last))
                color = _color_for(len(events) - 1)
                name = last["name"]
                if len(name) > 20:
                    name = name[:17] + "..."
                yield Static(
                    f"  [{color}]■[/] {name} [dim]{dur}[/]",
                    markup=True,
                )
            else:
                yield Static("  [dim]No activities[/]", markup=True)

        yield Static(
            f"  [dim]Select to view full timeline[/]",
            markup=True,
        )

    # ── Full detail for centre pane ──────────────────────

    def _build_timeline_bar(self, events: list[dict]) -> str:
        """Build a colored ASCII timeline bar representing the day."""
        if not events:
            return ""
        bar_width = 30
        bar = ["[dim]░[/]"] * bar_width

        for idx, ev in enumerate(events):
            try:
                start = datetime.fromisoformat(ev["start_time"])
                if ev.get("end_time"):
                    end = datetime.fromisoformat(ev["end_time"])
                else:
                    end = datetime.now()

                start_pos = int((start.hour * 60 + start.minute) / 1440 * bar_width)
                end_pos = int((end.hour * 60 + end.minute) / 1440 * bar_width)
                color = _color_for(idx)

                for p in range(max(0, start_pos), min(bar_width, end_pos + 1)):
                    bar[p] = f"[{color}]█[/]"
            except (ValueError, TypeError):
                continue

        return "  " + "".join(bar) + "\n  [dim]0    4    8    12   16   20  24[/]"

    # ── Refresh / nav ────────────────────────────────────

    def refresh_list(self):
        self.remove_children()
        self.mount(*list(self._build_items()))
        events = self.data_manager.get_events_for_date(self._viewed_date())
        if events:
            self.selected_index = min(self.selected_index, len(events) - 1)

    def get_selected(self) -> dict | None:
        events = self.data_manager.get_events_for_date(self._viewed_date())
        if events and 0 <= self.selected_index < len(events):
            return events[self.selected_index]
        return None

    def move_up(self):
        if self.selected_index > 0:
            self.selected_index -= 1
            self.refresh_list()

    def move_down(self):
        events = self.data_manager.get_events_for_date(self._viewed_date())
        if self.selected_index < len(events) - 1:
            self.selected_index += 1
            self.refresh_list()

    def prev_day(self):
        if self.view_day_offset < 7:
            self.view_day_offset += 1
            self.selected_index = 0
            self.refresh_list()

    def next_day(self):
        if self.view_day_offset > 0:
            self.view_day_offset -= 1
            self.selected_index = 0
            self.refresh_list()

    # ── Detail text (centre pane) ────────────────────────

    def get_detail_text(self) -> str:
        viewed = self._viewed_date()
        day_label = "Today" if self.view_day_offset == 0 else (
            "Yesterday" if self.view_day_offset == 1 else viewed
        )
        active = self.data_manager.get_active_event()
        events = self.data_manager.get_events_for_date(viewed)

        parts = [
            f"[bold cyan]Timeline — {day_label}[/]  [dim]({viewed})[/]",
            "[dim]─────────────────────────────────[/]\n",
        ]

        # Active event banner
        if active and self.view_day_offset == 0:
            dur = _fmt_duration(self.data_manager.get_event_duration_minutes(active))
            parts.append(
                f"[bold #50fa7b]▶ In Progress: {active['name']}[/]\n"
                f"  Started: {_fmt_time(active['start_time'])}  |  Duration: [yellow]{dur}[/]\n"
                f"  Press [bold cyan]a[/] to end & start new  |  [bold cyan]space[/] to end\n"
            )

        if not events:
            parts.append("[dim]No activities logged for this day.[/]\n")
            parts.append("Press [bold cyan]a[/] to start tracking an activity.\n")
            parts.append("Use [bold cyan]h[/]/[bold cyan]l[/] to browse days.")
            return "\n".join(parts)

        # Coloured timeline bar
        bar = self._build_timeline_bar(events)
        if bar:
            parts.append(bar)
            parts.append("")

        # Full event list with selection highlight
        for i, ev in enumerate(events):
            start = _fmt_time(ev["start_time"])
            end = _fmt_time(ev["end_time"]) if ev.get("end_time") else "now"
            dur = _fmt_duration(self.data_manager.get_event_duration_minutes(ev))
            color = _color_for(i)
            is_active = ev.get("end_time") is None
            status = " [yellow]▶[/]" if is_active else ""

            marker = "→" if i == self.selected_index else " "
            parts.append(
                f"  {marker} [{color}]■[/] {start} - {end}  {ev['name']}  [bold]{dur}[/]{status}"
            )

        # Summary
        total_mins = sum(self.data_manager.get_event_duration_minutes(ev) for ev in events)
        parts.append(f"\n[dim]Total: {_fmt_duration(total_mins)} across {len(events)} activities[/]")

        return "\n".join(parts)

    def get_counter_text(self) -> str:
        events = self.data_manager.get_events_for_date(self._viewed_date())
        total = len(events)
        active = self.data_manager.get_active_event()
        active_text = " ▶" if active else ""
        if total == 0:
            return f"0 of 0{active_text}"
        return f"{self.selected_index + 1} of {total}{active_text}"
