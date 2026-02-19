"""Notes panel widget — supports optional titles."""
from __future__ import annotations

from textual.widgets import Static
from textual.containers import VerticalScroll
from textual.reactive import reactive

from lazytool.data import DataManager


class NotesPanel(VerticalScroll):
    """Displays quick scratch notes. Titles are optional."""

    selected_index: reactive[int] = reactive(0)

    def __init__(self, data_manager: DataManager, **kwargs):
        super().__init__(**kwargs)
        self.data_manager = data_manager
        self.border_title = "[4]─Notes"

    def compose(self):
        yield from self._build_items()

    def _build_items(self):
        notes = self.data_manager.notes
        if not notes:
            yield Static("  No notes yet.\n  Press [a] to add.", classes="empty-message")
            return
        for i, note in enumerate(notes):
            title = note.get("title", "")
            if not title:
                # Show content preview for untitled notes
                content = note.get("content", "")
                if content:
                    preview = content.replace("\n", " ")
                    if len(preview) > 27:
                        preview = preview[:24] + "..."
                    display = f"[dim](untitled)[/] {preview}"
                else:
                    display = "[dim](untitled)[/]"
            else:
                if len(title) > 30:
                    title = title[:27] + "..."
                display = title

            classes = "list-item"
            if i == self.selected_index:
                classes += " list-item-selected"

            line = f"[cyan]•[/] {display}"
            yield Static(line, classes=classes, markup=True)

    def refresh_list(self):
        self.remove_children()
        self.mount(*list(self._build_items()))
        count = len(self.data_manager.notes)
        if count > 0:
            self.selected_index = min(self.selected_index, count - 1)

    def get_selected(self) -> dict | None:
        notes = self.data_manager.notes
        if notes and 0 <= self.selected_index < len(notes):
            return notes[self.selected_index]
        return None

    def move_up(self):
        if self.selected_index > 0:
            self.selected_index -= 1
            self.refresh_list()

    def move_down(self):
        if self.selected_index < len(self.data_manager.notes) - 1:
            self.selected_index += 1
            self.refresh_list()

    def get_detail_text(self) -> str:
        note = self.get_selected()
        if not note:
            return "No notes.\n\nPress [bold cyan]a[/] to add a quick note."
        title = note.get("title", "") or "(untitled)"
        content = note.get("content", "") or "[dim]No content[/]"
        return (
            f"[bold]{title}[/]\n"
            f"[dim]─────────────────────────────────[/]\n\n"
            f"{content}\n\n"
            f"[dim]Created: {note['created_at']}[/]"
        )

    def get_counter_text(self) -> str:
        total = len(self.data_manager.notes)
        if total == 0:
            return "0 of 0"
        return f"{self.selected_index + 1} of {total}"
