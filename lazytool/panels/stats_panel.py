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



def _mood_display(score: float) -> tuple[str, str]:
    """Return (label, color) for a mood score."""
    rounded = round(score)
    rounded = max(0, min(5, rounded))
    return MOOD_LABELS.get(rounded, "?"), MOOD_COLORS.get(rounded, "#f8f8f2")


class StatsPanel(VerticalScroll):
    """Displays aggregate productivity stats."""

    can_focus = False
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

            # Sort by hours descending and show only top 3
            sorted_activities = sorted(hours.items(), key=lambda x: x[1], reverse=True)
            
            for idx, (name, h) in enumerate(sorted_activities[:3]):
                from lazytool.panels.timeline_panel import _color_for
                color = _color_for(idx)
                label = name
                if len(label) > 15:
                    label = label[:12] + "..."
                yield Static(
                    f"  [{color}]■[/] {label:<15} [bold]{h:.1f}h[/]",
                    markup=True,
                )
            
            if len(sorted_activities) > 3:
                yield Static(f"  [dim]+ {len(sorted_activities) - 3} more...[/]", markup=True)

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
            f"[bold]Time[/]",
            f"  Total:    [yellow]{stats['total_tracked_hours']:.1f}h[/]",
            f"  [dim]Press [bold #f1fa8c]t[/dim] to toggle bar length formula[/]",
        ])

        if hours:
            sorted_acts = sorted(hours.items(), key=lambda x: x[1], reverse=True)
            # Modes: 0=Logged, 1=Total, 2=Z-Score, 3=Min/Max
            mode = self.data_manager.settings.get("stats_bar_mode", 3)
            
            # Setup denominator/stats info
            if mode == 1:
                denom = days * 24
                denom_label = f"Total Time ({days}d = {denom}h)"
            elif mode == 0:
                denom = stats["total_tracked_hours"]
                denom_label = f"Logged Time ({denom:.1f}h)"
            elif mode == 3:
                # Min-Max Normalization
                vals = list(hours.values())
                min_val = min(vals) if vals else 0
                max_val = max(vals) if vals else 1
                diff = max_val - min_val if max_val > min_val else 1.0
                denom_label = f"Min-Max Normalization (min={min_val:.1f}h, max={max_val:.1f}h)"
            else:
                # Z-Score Mode
                import math
                vals = list(hours.values())
                mu = sum(vals) if not vals else sum(vals) / len(vals)
                variance = 0 if not vals else sum((v - mu) ** 2 for v in vals) / len(vals)
                sigma = math.sqrt(variance) if variance > 0 else 1.0
                denom_label = f"Z-Score Percentile (µ={mu:.1f}h, σ={sigma:.1f}h)"
                
            parts.append(f"  [dim]Bars relative to: {denom_label}[/]")
            
            for idx, (name, h) in enumerate(sorted_acts):
                from lazytool.panels.timeline_panel import _color_for
                color = _color_for(idx)
                
                if mode == 2:
                    # Z-score normalization mapped to width (0-100%)
                    import math
                    if len(hours) <= 1 or sigma == 0:
                        pct = 50
                    else:
                        z = (h - mu) / sigma
                        pct = int(0.5 * (1.0 + math.erf(z / math.sqrt(2))) * 100)
                elif mode == 3:
                    # Min-Max normalization
                    if max_val == min_val:
                        pct = 100
                    else:
                        pct = int(((h - min_val) / diff) * 100)
                else:
                    target_denom = 1 if 'denom' not in locals() or denom == 0 else denom
                    pct = int(h / target_denom * 100)
                    
                pct = min(100, max(0, pct))
                bar = self._activity_bar(pct, color, width=40)
                label = name
                if len(label) > 20:
                    label = label[:17] + "..."
                parts.append(f"  [{color}]■[/] {label:<20} {bar} [bold]{h:.1f}h[/]")

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
            f"Generated: {self.data_manager.fmt_date(date.today().isoformat())}",
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
            f"*Generated: {self.data_manager.fmt_date(date.today().isoformat())}*",
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
        exports_dir = self.data_manager.exports_dir
        exports_dir.mkdir(parents=True, exist_ok=True)
        today = date.today().isoformat()
        today_fmt = self.data_manager.fmt_date(today)

        if fmt == "md":
            content = self.export_stats_markdown()
            filename = f"stats_{today_fmt}.md"
        else:
            content = self.export_stats_text()
            filename = f"stats_{today_fmt}.txt"

        filepath = exports_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return str(filepath)
