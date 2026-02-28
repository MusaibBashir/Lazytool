"""Journal panel widget."""
from __future__ import annotations

from textual.widgets import Static
from textual.containers import VerticalScroll
from textual.reactive import reactive


class JournalPanel(VerticalScroll):
    """Displays and manages journal entries."""

    can_focus = False
    selected_index: reactive[int] = reactive(0)

    def __init__(self, data_manager, **kwargs):
        super().__init__(**kwargs)
        self.data_manager = data_manager
        self.border_title = "[2]─Journal"

    def compose(self):
        yield from self._build_items()

    def _build_items(self):
        entries = self.data_manager.journal
        if not entries:
            yield Static("  No journal entries yet.\n  Press [a] to write.", classes="empty-message")
            return
        # Show newest first
        sorted_entries = list(reversed(entries))
        for i, entry in enumerate(sorted_entries):
            name = entry.get("name", "Untitled")
            if len(name) > 25:
                name = name[:22] + "..."

            classes = "list-item"
            if i == self.selected_index:
                classes += " list-item-selected"

            line = f"[dim]{self.data_manager.fmt_date(entry['date'])}[/] {name}"
            yield Static(line, classes=classes, markup=True)

    def refresh_list(self):
        self.remove_children()
        self.mount(*list(self._build_items()))
        count = len(self.data_manager.journal)
        if count > 0:
            self.selected_index = min(self.selected_index, count - 1)

    def _get_sorted_entries(self):
        return list(reversed(self.data_manager.journal))

    def get_selected(self) -> dict | None:
        entries = self._get_sorted_entries()
        if entries and 0 <= self.selected_index < len(entries):
            return entries[self.selected_index]
        return None

    def move_up(self):
        if self.selected_index > 0:
            self.selected_index -= 1
            self.refresh_list()

    def move_down(self):
        if self.selected_index < len(self.data_manager.journal) - 1:
            self.selected_index += 1
            self.refresh_list()

    def get_detail_text(self) -> str:
        entry = self.get_selected()
        if not entry:
            return "No journal entries.\n\nPress [bold cyan]a[/] to write a new entry."
        name = entry.get("name", "Untitled")
        return (
            f"[bold cyan]Journal Entry — {self.data_manager.fmt_date(entry['date'])}[/]\n"
            f"[bold #f1fa8c]{name}[/]\n"
            f"[dim]─────────────────────────────────[/]\n\n"
            f"{entry['content']}\n\n"
            f"[dim]Created: {self.data_manager.fmt_time(entry['created_at'])}[/]"
        )

    def get_counter_text(self) -> str:
        total = len(self.data_manager.journal)
        if total == 0:
            return "0 of 0"
        return f"{self.selected_index + 1} of {total}"
