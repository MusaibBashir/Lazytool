"""Stats panel widget — aggregated productivity statistics with export."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from textual.widgets import Static
from textual.containers import VerticalScroll
from textual.reactive import reactive

from lazytool.data import DataManager


MOOD_LABELS = {5: "Amazing", 4: "Great", 3: "Good", 2: "Okay", 1: "Bad", 0: "Terrible"}
MOOD_COLORS = {5: "#50fa7b", 4: "#8be9fd", 3: "#f1fa8c", 2: "#ffb86c", 1: "#ff79c6", 0: "#ff5555"}

EXPORTS_DIR = Path.home() / ".lazytool" / "exports"


def _mood_display(score: float) -> tuple[str, str]:
    """Return (label, color) for a mood score."""
    rounded = round(score)
    rounded = max(0, min(5, rounded))
    return MOOD_LABELS.get(rounded, "?"), MOOD_COLORS.get(rounded, "#f8f8f2")


class StatsPanel(VerticalScroll):
    """Displays aggregate productivity stats."""

    selected_index: reactive[int] = reactive(0)

    def __init__(self, data_manager: DataManager, **kwargs):
        super().__init__(**kwargs)
        self.data_manager = data_manager
        self.border_title = "[6]─Stats"

    def compose(self):
        yield from self._build_items()

    def _build_items(self):
        stats = self.data_manager.get_stats()
        days = stats["stats_days"]

        yield Static(
            f"[bold cyan]Productivity Overview[/]  [dim]({days}-day window)[/]",
            markup=True,
        )
        yield Static("[dim]─────────────────────────────[/]", markup=True)

        # Todos
        done = stats["done_todos"]
        total = stats["total_todos"]
        pct = int(done / total * 100) if total > 0 else 0
        bar = self._progress_bar(pct, "#50fa7b")
        yield Static(
            f"  [bold]Todos[/]      {done}/{total} done ({pct}%)",
            markup=True,
        )
        yield Static(f"  {bar}", markup=True)

        # Journal
        yield Static(
            f"  [bold]Journal[/]    {stats['total_journal']} entries, "
            f"[cyan]{stats['total_words']}[/] words",
            markup=True,
        )

        # Moods with average
        avg = stats.get("avg_mood_score")
        if avg is not None:
            label, color = _mood_display(avg)
            yield Static(
                f"  [bold]Moods[/]      {stats['total_moods']} total  "
                f"Avg: [{color}]{avg:.1f}/5 ({label})[/]",
                markup=True,
            )
        else:
            yield Static(
                f"  [bold]Moods[/]      {stats['total_moods']} recorded",
                markup=True,
            )

        yield Static("")
        yield Static(f"[bold cyan]Time Tracked ({days} days)[/]", markup=True)
        yield Static("[dim]─────────────────────────────[/]", markup=True)

        hours = stats["hours_by_activity"]
        total_h = stats["total_tracked_hours"]

        if not hours:
            yield Static("  [dim]No activities tracked yet.[/]", markup=True)
        else:
            yield Static(
                f"  Total: [bold yellow]{total_h:.1f}h[/]",
                markup=True,
            )
            yield Static("")

            # Sort by hours descending
            sorted_activities = sorted(hours.items(), key=lambda x: x[1], reverse=True)
            max_hours = max(hours.values()) if hours else 1

            for name, h in sorted_activities:
                from lazytool.panels.timeline_panel import _color_for
                color = _color_for(name)
                pct = int(h / max_hours * 100) if max_hours > 0 else 0
                bar = self._activity_bar(pct, color)
                label = name
                if len(label) > 12:
                    label = label[:9] + "..."
                yield Static(
                    f"  [{color}]■[/] {label:<12} {bar} [bold]{h:.1f}h[/]",
                    markup=True,
                )

        yield Static("")
        yield Static("[dim]─────────────────────────────[/]", markup=True)
        yield Static(
            f"  [dim]Window: {days}d  |  [/][bold #f1fa8c]s[/][dim] change  |  [/][bold #f1fa8c]x[/][dim] export[/]",
            markup=True,
        )

    def _progress_bar(self, pct: int, color: str, width: int = 20) -> str:
        filled = int(pct / 100 * width)
        empty = width - filled
        return f"[{color}]{'█' * filled}[/][dim]{'░' * empty}[/]"

    def _activity_bar(self, pct: int, color: str, width: int = 12) -> str:
        filled = int(pct / 100 * width)
        empty = width - filled
        return f"[{color}]{'█' * filled}[/][dim]{'░' * empty}[/]"

    def refresh_list(self):
        self.remove_children()
        self.mount(*list(self._build_items()))

    def get_selected(self) -> dict | None:
        return None

    def move_up(self):
        pass

    def move_down(self):
        pass

    def get_detail_text(self) -> str:
        stats = self.data_manager.get_stats()
        hours = stats["hours_by_activity"]
        days = stats["stats_days"]

        parts = [
            f"[bold cyan]Detailed Statistics ({days}-day window)[/]",
            "[dim]─────────────────────────────────[/]\n",
            "[bold]Tasks[/]",
            f"  Total:    {stats['total_todos']}",
            f"  Done:     [green]{stats['done_todos']}[/]",
            f"  Pending:  [yellow]{stats['pending_todos']}[/]\n",
            "[bold]Journal[/]",
            f"  Entries:  {stats['total_journal']}",
            f"  Words:    [cyan]{stats['total_words']}[/]",
        ]

        if stats['total_journal'] > 0:
            avg = stats['total_words'] / stats['total_journal']
            parts.append(f"  Avg/entry: {avg:.0f} words\n")
        else:
            parts.append("")

        # Mood detail
        avg_mood = stats.get("avg_mood_score")
        parts.append("[bold]Mood Trend[/]")
        parts.append(f"  Recorded: {stats['total_moods']}")
        if avg_mood is not None:
            label, color = _mood_display(avg_mood)
            parts.append(f"  Average:  [{color}]{avg_mood:.2f}/5.0 ({label})[/]")
            # Mood bar
            pct = int(avg_mood / 5 * 100)
            bar = self._progress_bar(pct, color)
            parts.append(f"  {bar}")
        parts.append("")

        parts.extend([
            f"[bold]Time ({days} days)[/]",
            f"  Total:    [yellow]{stats['total_tracked_hours']:.1f}h[/]",
        ])

        if hours:
            sorted_acts = sorted(hours.items(), key=lambda x: x[1], reverse=True)
            for name, h in sorted_acts[:8]:
                parts.append(f"  • {name}: {h:.1f}h")

        parts.append(f"\n[dim]Press [bold #f1fa8c]s[/dim] to change tracking window (current: {days} days)[/]")
        parts.append(f"[dim]Press [bold #f1fa8c]x[/dim] to export stats[/]")

        return "\n".join(parts)

    def get_counter_text(self) -> str:
        days = self.data_manager.settings.get("stats_days", 7)
        return f"{days}-day view"

    # ── Export helpers ────────────────────────────────────

    def export_stats_text(self) -> str:
        """Generate a plain text export of stats."""
        stats = self.data_manager.get_stats()
        hours = stats["hours_by_activity"]
        days = stats["stats_days"]

        lines = [
            f"LazyTool — Productivity Stats ({days}-day window)",
            f"Generated: {date.today().isoformat()}",
            "=" * 50,
            "",
            "TASKS",
            f"  Total:   {stats['total_todos']}",
            f"  Done:    {stats['done_todos']}",
            f"  Pending: {stats['pending_todos']}",
            "",
            "JOURNAL",
            f"  Entries: {stats['total_journal']}",
            f"  Words:   {stats['total_words']}",
        ]

        if stats['total_journal'] > 0:
            avg = stats['total_words'] / stats['total_journal']
            lines.append(f"  Avg/entry: {avg:.0f} words")

        lines.append("")
        lines.append("MOOD TREND")
        lines.append(f"  Recorded: {stats['total_moods']}")
        avg_mood = stats.get("avg_mood_score")
        if avg_mood is not None:
            label = MOOD_LABELS.get(round(max(0, min(5, avg_mood))), "?")
            lines.append(f"  Average: {avg_mood:.2f}/5.0 ({label})")

        lines.append("")
        lines.append(f"TIME TRACKED ({days} days)")
        lines.append(f"  Total: {stats['total_tracked_hours']:.1f}h")

        if hours:
            lines.append("")
            sorted_acts = sorted(hours.items(), key=lambda x: x[1], reverse=True)
            for name, h in sorted_acts:
                lines.append(f"  - {name}: {h:.1f}h")

        lines.append("")
        lines.append("=" * 50)
        return "\n".join(lines)

    def export_stats_markdown(self) -> str:
        """Generate a markdown export of stats."""
        stats = self.data_manager.get_stats()
        hours = stats["hours_by_activity"]
        days = stats["stats_days"]

        lines = [
            f"# LazyTool — Productivity Stats ({days}-day window)",
            f"*Generated: {date.today().isoformat()}*",
            "",
            "## Tasks",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total | {stats['total_todos']} |",
            f"| Done | {stats['done_todos']} |",
            f"| Pending | {stats['pending_todos']} |",
            "",
            "## Journal",
            f"- **Entries:** {stats['total_journal']}",
            f"- **Words:** {stats['total_words']}",
        ]

        if stats['total_journal'] > 0:
            avg = stats['total_words'] / stats['total_journal']
            lines.append(f"- **Avg/entry:** {avg:.0f} words")

        lines.append("")
        lines.append("## Mood Trend")
        lines.append(f"- **Recorded:** {stats['total_moods']}")
        avg_mood = stats.get("avg_mood_score")
        if avg_mood is not None:
            label = MOOD_LABELS.get(round(max(0, min(5, avg_mood))), "?")
            lines.append(f"- **Average:** {avg_mood:.2f}/5.0 ({label})")

        lines.append("")
        lines.append(f"## Time Tracked ({days} days)")
        lines.append(f"- **Total:** {stats['total_tracked_hours']:.1f}h")

        if hours:
            lines.append("")
            lines.append("| Activity | Hours |")
            lines.append("|----------|-------|")
            sorted_acts = sorted(hours.items(), key=lambda x: x[1], reverse=True)
            for name, h in sorted_acts:
                lines.append(f"| {name} | {h:.1f}h |")

        return "\n".join(lines)

    def export_to_file(self, fmt: str) -> str:
        """Export stats to a file and return the file path."""
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        today = date.today().isoformat()

        if fmt == "md":
            content = self.export_stats_markdown()
            filename = f"stats_{today}.md"
        else:
            content = self.export_stats_text()
            filename = f"stats_{today}.txt"

        filepath = EXPORTS_DIR / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return str(filepath)
