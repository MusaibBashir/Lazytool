"""Goals panel widget — track goals with streaks and check-in history."""
from __future__ import annotations

from datetime import date

from textual.widgets import Static
from textual.containers import VerticalScroll
from textual.reactive import reactive

from lazytool.data import DataManager


def _fire_str(streak: int) -> str:
    """Return fire emojis for a streak count."""
    if streak == 0:
        return "[dim]no streak[/]"
    fires = min(streak, 7)  # cap emoji count
    return "🔥" * fires + (f"  [bold yellow]{streak}d[/]" if streak > 1 else "")


class GoalsPanel(VerticalScroll):
    """Displays goals with streaks. Check in daily to build streaks."""

    selected_index: reactive[int] = reactive(0)

    def __init__(self, data_manager: DataManager, **kwargs):
        super().__init__(**kwargs)
        self.data_manager = data_manager
        self.border_title = "[4]─Goals"

    # ── Sidebar ──────────────────────────────────────────

    def compose(self):
        yield from self._build_items()

    def _build_items(self):
        goals = self.data_manager.goals
        if not goals:
            yield Static(
                "  No goals yet.\n  Press [bold cyan]a[/] to add a goal.",
                classes="empty-message", markup=True,
            )
            return

        today = date.today().isoformat()

        for i, goal in enumerate(goals):
            streak = self.data_manager.get_goal_streak(goal)
            checked_today = today in goal.get("check_ins", [])

            check = "[green]✓[/]" if checked_today else "[dim]○[/]"
            title = goal["title"]
            if len(title) > 20:
                title = title[:17] + "..."

            fire = _fire_str(streak) if streak > 0 else ""

            classes = "list-item"
            if i == self.selected_index:
                classes += " list-item-selected"

            line = f"  {check} {title}  {fire}"
            yield Static(line, classes=classes, markup=True)

    def refresh_list(self):
        self.remove_children()
        self.mount(*list(self._build_items()))
        count = len(self.data_manager.goals)
        if count > 0:
            self.selected_index = min(self.selected_index, count - 1)

    def get_selected(self) -> dict | None:
        goals = self.data_manager.goals
        if goals and 0 <= self.selected_index < len(goals):
            return goals[self.selected_index]
        return None

    def move_up(self):
        if self.selected_index > 0:
            self.selected_index -= 1
            self.refresh_list()

    def move_down(self):
        if self.selected_index < len(self.data_manager.goals) - 1:
            self.selected_index += 1
            self.refresh_list()

    # ── Detail (centre pane) ─────────────────────────────

    def get_detail_text(self) -> str:
        goal = self.get_selected()
        if not goal:
            return (
                "No goals yet.\n\n"
                "Press [bold cyan]a[/] to add a goal.\n"
                "Track daily progress and build streaks!"
            )

        streak = self.data_manager.get_goal_streak(goal)
        today = date.today().isoformat()
        checked_today = today in goal.get("check_ins", [])
        history_days = self.data_manager.settings.get("goal_history_days", 30)
        history = self.data_manager.get_goal_history(goal, history_days)
        total_check_ins = len(goal.get("check_ins", []))

        parts = [
            f"[bold cyan]{goal['title']}[/]",
            "[dim]─────────────────────────────────[/]\n",
        ]

        # Description
        desc = goal.get("description", "")
        if desc:
            parts.append(f"  [dim]{desc}[/]\n")

        # Streak
        parts.append(f"  [bold]Streak:[/]  {_fire_str(streak)}")

        # Today status
        if checked_today:
            parts.append(f"  [bold]Today:[/]   [green]✓ Checked in[/]")
        else:
            parts.append(f"  [bold]Today:[/]   [yellow]○ Not yet[/]  — press [bold cyan]space[/] to check in")

        parts.append(f"  [bold]Total:[/]   {total_check_ins} check-ins")
        parts.append(f"  [bold]Created:[/] [dim]{self.data_manager.fmt_date(goal.get('created_at', ''))}[/]\n")

        # History grid — bigger, symmetric
        parts.append(f"[bold cyan]Last {history_days} Days[/]")
        parts.append("[dim]─────────────────────────────────────────[/]")
        parts.append("")

        # Use 7 columns (like a week calendar), with day abbreviations
        from datetime import timedelta as _td
        cols = 7
        # Pad history to fill the last row
        padded = list(history)
        while len(padded) % cols != 0:
            padded.append(("", False))

        # Build rows
        for row_start in range(0, len(padded), cols):
            row_cells = padded[row_start:row_start + cols]
            line_blocks = "  "
            line_dates = "  "
            for day_str, checked in row_cells:
                if not day_str:
                    line_blocks += "     "
                    line_dates += "     "
                elif checked:
                    line_blocks += "[green]██[/]   "
                    # Show day of month
                    d_num = day_str[-2:]
                    line_dates += f"[dim]{d_num}[/]   "
                else:
                    line_blocks += "[dim]░░[/]   "
                    d_num = day_str[-2:]
                    line_dates += f"[dim]{d_num}[/]   "
            parts.append(line_blocks)
            parts.append(line_dates)
            parts.append("")

        # Legend & stats
        checked_count = sum(1 for _, c in history if c)
        rate = int(checked_count / len(history) * 100) if history else 0
        parts.append(f"  [green]██[/] done  [dim]░░[/] missed    "
                     f"[bold]{checked_count}[/]/{len(history)} days ([bold cyan]{rate}%[/])")
        parts.append(f"\n[dim]Press [bold #f1fa8c]s[/dim] to change history window (current: {history_days}d)[/]")

        return "\n".join(parts)

    def get_counter_text(self) -> str:
        goals = self.data_manager.goals
        total = len(goals)
        if total == 0:
            return "0 of 0"
        return f"{self.selected_index + 1} of {total}"
