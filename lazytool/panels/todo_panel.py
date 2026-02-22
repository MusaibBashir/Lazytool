"""Todo panel widget — smart sorting and full-list view."""
from __future__ import annotations

from textual.widgets import Static
from textual.containers import VerticalScroll
from textual.reactive import reactive

from lazytool.data import DataManager

PRIORITY_COLORS = {"high": "red", "medium": "yellow", "low": "white"}


class TodoPanel(VerticalScroll):
    """Displays and manages todo items with smart sorting."""

    selected_index: reactive[int] = reactive(0)

    def __init__(self, data_manager: DataManager, **kwargs):
        super().__init__(**kwargs)
        self.data_manager = data_manager
        self.border_title = "[1]─Todos"

    # ── Sorted access ────────────────────────────────────

    def _sorted(self) -> list[dict]:
        return self.data_manager.get_sorted_todos()

    # ── Sidebar ──────────────────────────────────────────

    def compose(self):
        yield from self._build_items()

    def _build_items(self):
        todos = self._sorted()
        if not todos:
            yield Static("  No todos yet. Press [a] to add.", classes="empty-message")
            return
        for i, todo in enumerate(todos):
            check = "✓" if todo["done"] else " "
            pri = todo.get("priority", "medium")[0].upper()
            pri_class = f"priority-{todo.get('priority', 'medium')}"

            text = todo["text"]
            if len(text) > 28:
                text = text[:25] + "..."

            classes = "list-item"
            if i == self.selected_index:
                classes += " list-item-selected"
            if todo["done"]:
                classes += " list-item-done"

            line = f"[{check}] [{pri_class}]{pri}[/] {text}"
            yield Static(line, classes=classes, markup=True)

    def refresh_list(self):
        self.remove_children()
        self.mount(*list(self._build_items()))
        count = len(self._sorted())
        if count > 0:
            self.selected_index = min(self.selected_index, count - 1)

    def get_selected(self) -> dict | None:
        todos = self._sorted()
        if todos and 0 <= self.selected_index < len(todos):
            return todos[self.selected_index]
        return None

    def move_up(self):
        if self.selected_index > 0:
            self.selected_index -= 1
            self.refresh_list()

    def move_down(self):
        if self.selected_index < len(self._sorted()) - 1:
            self.selected_index += 1
            self.refresh_list()

    # ── Detail (single selected item) ────────────────────

    def get_detail_text(self) -> str:
        return self.get_all_todos_text()

    # ── Full list (all todos with status, priority, created) ──

    def get_all_todos_text(self) -> str:
        """Generate a full list of all todos for the centre display."""
        todos = self._sorted()
        if not todos:
            return "No todos.\n\nPress [bold cyan]a[/] to add a new todo."

        pending = [t for t in todos if not t["done"]]
        done = [t for t in todos if t["done"]]

        parts = [
            f"[bold cyan]All Todos[/]  [dim]({len(pending)} pending, {len(done)} done)[/]",
            "[dim]─────────────────────────────────────────[/]\n",
        ]

        # pending section
        if pending:
            parts.append("[bold #50fa7b]Pending[/]")
            for i, t in enumerate(pending, 1):
                pri = t.get("priority", "medium")
                pri_color = PRIORITY_COLORS.get(pri, "white")
                created = t.get("created_at", "")[0:10]  # date only
                parts.append(
                    f"  {i:>2}. [{pri_color}]{pri[0].upper()}[/]  {t['text']}"
                    f"  [dim]{created}[/]"
                )
            parts.append("")

        # done section
        if done:
            parts.append(f"[bold #6272a4]Done ({len(done)})[/]")
            for t in done:
                pri = t.get("priority", "medium")
                pri_color = PRIORITY_COLORS.get(pri, "white")
                done_at = t.get("done_at", t.get("created_at", ""))[0:10]
                parts.append(
                    f"  [dim]✓[/]  [{pri_color}]{pri[0].upper()}[/]  "
                    f"[dim]{t['text']}[/]  [dim]{done_at}[/]"
                )

        purge_days = self.data_manager.settings.get("todo_purge_days", 7)
        parts.append(f"\n[dim]Done todos auto-purge after {purge_days}d  ·  press [bold #f1fa8c]s[/dim] to change[/]")

        return "\n".join(parts)

    def get_counter_text(self) -> str:
        todos = self._sorted()
        total = len(todos)
        done = sum(1 for t in todos if t["done"])
        if total == 0:
            return "0 of 0"
        return f"{self.selected_index + 1} of {total} ({done} done)"
