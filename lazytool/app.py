"""LazyTool — Main application with Lazygit-style TUI layout."""
from __future__ import annotations

import sys
import difflib
from datetime import datetime, timedelta
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static, Input, Header, Footer, Label, TextArea
from textual.containers import Vertical, Horizontal, VerticalScroll, Container
from textual.reactive import reactive

from lazytool.data import DataManager, get_profile_names, get_active_profile, set_active_profile, create_profile, rename_profile
from lazytool.panels.todo_panel import TodoPanel
from lazytool.panels.journal_panel import JournalPanel
from lazytool.panels.mood_panel import MoodPanel
from lazytool.panels.goals_panel import GoalsPanel
from lazytool.panels.timeline_panel import TimelinePanel
from lazytool.panels.stats_panel import StatsPanel


# ── Input modal ──────────────────────────────────────────

_CANCELLED = "\x00_CANCELLED_\x00"  # sentinel for InputModal cancel

class InputModal(ModalScreen[str]):
    """A modal for single-line text input."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    CSS = """
    InputModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.85);
    }
    #modal-box {
        width: 60;
        height: auto;
        max-height: 16;
        background: #282a36;
        border: solid #50fa7b;
        padding: 1 2;
    }
    #modal-title {
        color: #ff79c6;
        text-style: bold;
        margin-bottom: 1;
    }
    #modal-input {
        background: #44475a;
        color: #f8f8f2;
        border: solid #6272a4;
        height: 3;
    }
    #modal-input:focus {
        border: solid #50fa7b;
    }
    """

    def __init__(self, title: str, placeholder: str = "", default: str = "", allow_empty: bool = False, **kwargs):
        super().__init__(**kwargs)
        self._title = title
        self._placeholder = placeholder
        self._default = default
        self._allow_empty = allow_empty

    def compose(self) -> ComposeResult:
        with Container(id="modal-box"):
            yield Static(self._title, id="modal-title")
            yield Input(
                value=self._default,
                placeholder=self._placeholder,
                id="modal-input",
            )

    def on_mount(self) -> None:
        self.query_one("#modal-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if value or self._allow_empty:
            self.dismiss(value)

    def action_cancel(self) -> None:
        self.dismiss(_CANCELLED)


class AutocompleteModal(ModalScreen[str]):
    """A modal for single-line text input with fuzzy autocomplete suggestions."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("down", "focus_next", "Next Suggestion", show=False),
        Binding("up", "focus_previous", "Prev Suggestion", show=False),
    ]

    CSS = """
    AutocompleteModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.85);
    }
    #auto-box {
        width: 60;
        height: auto;
        max-height: 20;
        background: #282a36;
        border: solid #50fa7b;
        padding: 1 2;
    }
    #auto-title {
        color: #ff79c6;
        text-style: bold;
        margin-bottom: 1;
    }
    #auto-input {
        background: #44475a;
        color: #f8f8f2;
        border: solid #6272a4;
        height: 3;
    }
    #auto-input:focus {
        border: solid #50fa7b;
    }
    #auto-suggestions {
        margin-top: 1;
        height: auto;
    }
    .suggestion {
        padding: 0 1;
        color: #6272a4;
        height: 1;
    }
    .suggestion.highlight {
        background: #44475a;
        color: #f1fa8c;
        text-style: bold;
    }
    """

    def __init__(self, title: str, suggestions: list[str], placeholder: str = "", default: str = "", **kwargs):
        super().__init__(**kwargs)
        self._title = title
        self._all_suggestions = suggestions
        self._placeholder = placeholder
        self._default = default
        self._matches = []
        self._highlighted_index = -1

    def compose(self) -> ComposeResult:
        with Container(id="auto-box"):
            yield Static(self._title, id="auto-title")
            yield Input(
                value=self._default,
                placeholder=self._placeholder,
                id="auto-input",
            )
            yield Vertical(id="auto-suggestions")

    def on_mount(self) -> None:
        self.query_one("#auto-input", Input).focus()
        self._update_suggestions(self._default)

    def on_input_changed(self, event: Input.Changed) -> None:
        self._update_suggestions(event.value)

    def _update_suggestions(self, value: str) -> None:
        val = value.strip().lower()
        if not val:
            self._matches = []
        else:
            lower_to_orig = {}
            for s in self._all_suggestions:
                if s.lower() not in lower_to_orig:
                    lower_to_orig[s.lower()] = s
            matches = difflib.get_close_matches(val, list(lower_to_orig.keys()), n=3, cutoff=0.3)
            self._matches = [lower_to_orig[m] for m in matches]
        
        self._highlighted_index = -1
        self._render_suggestions()

    def _render_suggestions(self) -> None:
        container = self.query_one("#auto-suggestions", Vertical)
        container.remove_children()
        
        if not self._matches:
            return
            
        for i, match in enumerate(self._matches):
            classes = "suggestion highlight" if i == self._highlighted_index else "suggestion"
            prefix = "▶ " if i == self._highlighted_index else "  "
            container.mount(Static(f"{prefix}{match}", classes=classes))

    def action_focus_next(self) -> None:
        if not self._matches:
            return
        self._highlighted_index = min(self._highlighted_index + 1, len(self._matches) - 1)
        self._render_suggestions()

    def action_focus_previous(self) -> None:
        if not self._matches:
            return
        self._highlighted_index = max(-1, self._highlighted_index - 1)
        self._render_suggestions()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self._highlighted_index >= 0 and self._highlighted_index < len(self._matches):
            self.dismiss(self._matches[self._highlighted_index])
        else:
            value = event.value.strip()
            if value:
                self.dismiss(value)

    def action_cancel(self) -> None:
        self.dismiss(_CANCELLED)


# ── Journal entry modal ──────────────────────────────────

class JournalEntryModal(ModalScreen[tuple[str, str]]):
    """A modal for entering journal name and content."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "save", "Save"),
    ]

    CSS = """
    JournalEntryModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.85);
    }
    #journal-modal-box {
        width: 80;
        height: auto;
        min-height: 13;
        background: #282a36;
        border: solid #50fa7b;
        padding: 1 2;
    }
    #journal-modal-title {
        color: #ff79c6;
        text-style: bold;
        margin-bottom: 1;
    }
    #journal-modal-title-input {
        background: #44475a;
        color: #f8f8f2;
        border: solid #6272a4;
        height: 3;
        margin-bottom: 1;
    }
    #journal-modal-title-input:focus {
        border: solid #50fa7b;
    }
    #journal-modal-content-input {
        background: #44475a;
        color: #f8f8f2;
        border: solid #6272a4;
        height: 5;
    }
    #journal-modal-content-input:focus {
        border: solid #50fa7b;
    }
    """

    def __init__(self, title: str, default_name: str = "", default_content: str = "", **kwargs):
        super().__init__(**kwargs)
        self._title = title
        self._default_name = default_name
        self._default_content = default_content

    def compose(self) -> ComposeResult:
        with Container(id="journal-modal-box"):
            yield Static(self._title, id="journal-modal-title")
            yield Input(
                value=self._default_name,
                placeholder="Journal Entry Name...",
                id="journal-modal-title-input",
            )
            yield TextArea(
                text=self._default_content,
                soft_wrap=True,
                show_line_numbers=False,
                id="journal-modal-content-input",
            )
            yield Static("\n  [dim]Press [bold #f1fa8c]ctrl+s[/] to save, [bold #f1fa8c]escape[/] to cancel[/]", markup=True)

    def on_mount(self) -> None:
        self.query_one("#journal-modal-title-input", Input).focus()

    def action_save(self) -> None:
        name = self.query_one("#journal-modal-title-input", Input).value.strip()
        content = self.query_one("#journal-modal-content-input", TextArea).text.strip()
        if name or content:
            if not name:
                name = "Untitled"
            self.dismiss((name, content))

    def action_cancel(self) -> None:
        self.dismiss((_CANCELLED, _CANCELLED))


# ── Mood picker modal ────────────────────────────────────

class MoodPickerModal(ModalScreen[str]):
    """A modal for picking a mood with number keys."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("1", "pick_1", "Amazing", show=False),
        Binding("2", "pick_2", "Great", show=False),
        Binding("3", "pick_3", "Good", show=False),
        Binding("4", "pick_4", "Okay", show=False),
        Binding("5", "pick_5", "Bad", show=False),
        Binding("6", "pick_6", "Terrible", show=False),
    ]

    CSS = """
    MoodPickerModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.85);
    }
    #mood-box {
        width: 40;
        height: auto;
        background: #282a36;
        border: solid #50fa7b;
        padding: 1 2;
    }
    #mood-title {
        color: #ff79c6;
        text-style: bold;
        margin-bottom: 1;
        text-align: center;
    }
    .mood-option {
        height: 1;
        padding: 0 1;
        color: #f8f8f2;
    }
    .mood-option:hover {
        background: #44475a;
    }
    """

    MOODS = ["amazing", "great", "good", "okay", "bad", "terrible"]
    MOOD_LABELS = {
        "amazing": "🤩 Amazing",
        "great": "😊 Great",
        "good": "🙂 Good",
        "okay": "😐 Okay",
        "bad": "😔 Bad",
        "terrible": "😢 Terrible",
    }

    def compose(self) -> ComposeResult:
        with Container(id="mood-box"):
            yield Static("How are you feeling?", id="mood-title")
            for i, mood in enumerate(self.MOODS):
                label = self.MOOD_LABELS[mood]
                yield Static(
                    f"  [bold yellow]{i + 1}[/]  {label}",
                    classes="mood-option",
                    markup=True,
                )

    def action_pick_1(self) -> None: self.dismiss("amazing")
    def action_pick_2(self) -> None: self.dismiss("great")
    def action_pick_3(self) -> None: self.dismiss("good")
    def action_pick_4(self) -> None: self.dismiss("okay")
    def action_pick_5(self) -> None: self.dismiss("bad")
    def action_pick_6(self) -> None: self.dismiss("terrible")
    def action_cancel(self) -> None: self.dismiss("")


# ── Export format picker modal ───────────────────────────

class ExportFormatModal(ModalScreen[str]):
    """Pick an export format for stats."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("1", "pick_txt", "Text", show=False),
        Binding("2", "pick_md", "Markdown", show=False),
    ]

    CSS = """
    ExportFormatModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.85);
    }
    #export-box {
        width: 40;
        height: auto;
        background: #282a36;
        border: solid #50fa7b;
        padding: 1 2;
    }
    #export-title {
        color: #ff79c6;
        text-style: bold;
        margin-bottom: 1;
        text-align: center;
    }
    .export-option {
        height: 1;
        padding: 0 1;
        color: #f8f8f2;
    }
    .export-option:hover {
        background: #44475a;
    }
    """

    def compose(self) -> ComposeResult:
        with Container(id="export-box"):
            yield Static("Export Stats As...", id="export-title")
            yield Static("  [bold yellow]1[/]  Plain Text (.txt)", classes="export-option", markup=True)
            yield Static("  [bold yellow]2[/]  Markdown (.md)", classes="export-option", markup=True)

    def action_pick_txt(self) -> None: self.dismiss("txt")
    def action_pick_md(self) -> None: self.dismiss("md")
    def action_cancel(self) -> None: self.dismiss("")


# ── Confirm modal ────────────────────────────────────────

class ConfirmModal(ModalScreen[bool]):
    """A Y/N confirmation modal."""

    BINDINGS = [
        Binding("y", "yes", "Yes"),
        Binding("n", "no", "No"),
        Binding("escape", "no", "No"),
    ]

    CSS = """
    ConfirmModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.85);
    }
    #confirm-box {
        width: 50;
        height: auto;
        background: #282a36;
        border: solid #50fa7b;
        padding: 1 2;
    }
    #confirm-title {
        color: #ff79c6;
        text-style: bold;
        margin-bottom: 1;
    }
    #confirm-hint {
        color: #6272a4;
    }
    """

    def __init__(self, message: str, **kwargs):
        super().__init__(**kwargs)
        self._message = message

    def compose(self) -> ComposeResult:
        with Container(id="confirm-box"):
            yield Static(self._message, id="confirm-title")
            yield Static(
                "  [bold #f1fa8c]y[/] Yes  |  [bold #f1fa8c]n[/] No",
                id="confirm-hint",
                markup=True,
            )

    def action_yes(self) -> None: self.dismiss(True)
    def action_no(self) -> None: self.dismiss(False)


# ── Help overlay ─────────────────────────────────────────

class HelpScreen(ModalScreen):
    """Shows all keyboard shortcuts."""

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("question_mark", "close", "Close", show=False),
    ]

    CSS = """
    HelpScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.85);
    }
    #help-container {
        width: 64;
        max-height: 85%;
        background: #282a36;
        border: solid #50fa7b;
        padding: 1 2;
        overflow-y: auto;
    }
    """

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="help-container"):
            yield Static(
                "[bold #ff79c6]LazyTool - Be Less Lazy[/]\n"
                "[dim]─────────────────────────────────────────[/]\n"
                "[dim]© Musaib Bin Bashir 2026[/]\n\n"
                "[bold cyan]Keyboard Shortcuts[/]\n"
                "[dim]─────────────────────────────────────────[/]\n\n"
                "[bold cyan]Navigation[/]\n"
                "  [bold #f1fa8c]1 - 6[/]      Switch panels\n"
                "  [bold #f1fa8c]↑ / k[/]      Move up in list\n"
                "  [bold #f1fa8c]↓ / j[/]      Move down in list\n\n"
                "[bold cyan]Actions[/]\n"
                "  [bold #f1fa8c]a[/]          Add new item / start activity\n"
                "  [bold #f1fa8c]e[/]          Edit selected item\n"
                "  [bold #f1fa8c]d[/]          Delete selected item\n"
                "  [bold #f1fa8c]space[/]      Toggle done / end activity\n"
                "  [bold #f1fa8c]p[/]          Cycle priority (Todos only)\n"
                "  [bold #f1fa8c]enter[/]      View / confirm\n\n"
                "[bold cyan]Todos[/]\n"
                "  [bold #f1fa8c]v[/]          View all todos (full list)\n"
                "  [bold #f1fa8c]s[/]          Set auto-purge days\n\n"
                "[bold cyan]Goals[/]\n"
                "  [bold #f1fa8c]space[/]      Check in for today\n"
                "  [bold #f1fa8c]s[/]          Set history window\n\n"
                "[bold cyan]Timeline[/]\n"
                "  [bold #f1fa8c]h[/]          Previous day\n"
                "  [bold #f1fa8c]l[/]          Next day\n"
                "  [bold #f1fa8c]e[/]          Edit event times\n\n"
                "[bold cyan]Stats[/]\n"
                "  [bold #f1fa8c]s[/]          Set tracking days\n"
                "  [bold #f1fa8c]x[/]          Export stats (.txt/.md)\n\n"
                "[bold cyan]General[/]\n"
                "  [bold #f1fa8c]Shift+P[/]  Switch profile\n"
                "  [bold #f1fa8c]?[/]          Show this help\n"
                "  [bold #f1fa8c]q[/]          Quit\n\n"
                "[dim]Press Escape or ? to close[/]\n\n"
                "[bold cyan]Contact Me[/]\n"
                "  Email: [bold #8be9fd]musaibbashir02@gmail.com[/]",
                markup=True,
            )

    def action_close(self) -> None:
        self.dismiss()


# ── Profile picker modal ───────────────────────────────────

class ProfilePickerModal(ModalScreen[str]):
    """A modal for switching or creating profiles."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("n", "new_profile", "New", show=False),
        Binding("e", "edit_profile", "Edit", show=False),
        Binding("1", "pick_1", "1", show=False),
        Binding("2", "pick_2", "2", show=False),
        Binding("3", "pick_3", "3", show=False),
        Binding("4", "pick_4", "4", show=False),
        Binding("5", "pick_5", "5", show=False),
        Binding("6", "pick_6", "6", show=False),
        Binding("7", "pick_7", "7", show=False),
        Binding("8", "pick_8", "8", show=False),
        Binding("9", "pick_9", "9", show=False),
    ]

    CSS = """
    ProfilePickerModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.85);
    }
    #profile-box {
        width: 50;
        height: auto;
        max-height: 80%;
        background: #282a36;
        border: solid #bd93f9;
        padding: 1 2;
    }
    #profile-title {
        color: #bd93f9;
        text-style: bold;
        margin-bottom: 1;
    }
    .profile-item {
        height: 1;
        padding: 0 1;
        color: #f8f8f2;
    }
    .profile-active {
        height: 1;
        padding: 0 1;
        color: #50fa7b;
        text-style: bold;
    }
    #profile-hint {
        color: #6272a4;
        margin-top: 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._profiles = get_profile_names()
        self._active = get_active_profile()

    def compose(self) -> ComposeResult:
        with Container(id="profile-box"):
            yield Static("Switch Profile", id="profile-title")
            for i, name in enumerate(self._profiles[:9]):
                marker = " *" if name == self._active else ""
                cls = "profile-active" if name == self._active else "profile-item"
                yield Static(
                    f"  [bold #f1fa8c]{i + 1}[/]  {name}{marker}",
                    classes=cls,
                    markup=True,
                )
            yield Static(
                "  [bold #f1fa8c]n[/]  Create new  |  "
                "[bold #f1fa8c]e[/]  Rename active  |  "
                "[bold #f1fa8c]Esc[/]  Cancel",
                id="profile-hint",
                markup=True,
            )

    def _pick(self, idx: int) -> None:
        if 0 <= idx < len(self._profiles):
            self.dismiss(self._profiles[idx])

    def action_pick_1(self) -> None: self._pick(0)
    def action_pick_2(self) -> None: self._pick(1)
    def action_pick_3(self) -> None: self._pick(2)
    def action_pick_4(self) -> None: self._pick(3)
    def action_pick_5(self) -> None: self._pick(4)
    def action_pick_6(self) -> None: self._pick(5)
    def action_pick_7(self) -> None: self._pick(6)
    def action_pick_8(self) -> None: self._pick(7)
    def action_pick_9(self) -> None: self._pick(8)

    def action_new_profile(self) -> None:
        self.dismiss("__NEW__")

    def action_edit_profile(self) -> None:
        self.dismiss("__EDIT__")

    def action_cancel(self) -> None:
        self.dismiss("")


# ── Main application ─────────────────────────────────────

class LazyToolApp(App):
    """A Lazygit-style terminal productivity tool."""

    TITLE = "LazyTool"

    @classmethod
    def _get_css_path(cls) -> Path:
        """Resolve CSS path for both normal and PyInstaller-frozen runs."""
        if getattr(sys, 'frozen', False):
            base = Path(sys._MEIPASS) / "lazytool"  # noqa: SLF001
        else:
            base = Path(__file__).parent
        return base / "app.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("question_mark", "show_help", "Help"),
        Binding("1", "panel_1", "Todos", show=False),
        Binding("2", "panel_2", "Journal", show=False),
        Binding("3", "panel_3", "Moods", show=False),
        Binding("4", "panel_4", "Notes", show=False),
        Binding("5", "panel_5", "Timeline", show=False),
        Binding("6", "panel_6", "Stats", show=False),
        Binding("k", "move_up", "Up", show=False),
        Binding("j", "move_down", "Down", show=False),
        Binding("up", "move_up", "Up", show=False),
        Binding("down", "move_down", "Down", show=False),
        Binding("a", "add_item", "Add", show=False),
        Binding("e", "edit_item", "Edit", show=False),
        Binding("n", "rename_item", "Rename", show=False),
        Binding("d", "delete_item", "Delete", show=False),
        Binding("space", "toggle_item", "Toggle", show=False),
        Binding("p", "cycle_priority", "Priority", show=False),
        Binding("h", "prev_day", "Prev day", show=False),
        Binding("l", "next_day", "Next day", show=False),
        Binding("s", "change_settings", "Settings", show=False),
        Binding("t", "toggle_stats_denom", "Toggle %", show=False),
        Binding("x", "export_stats", "Export", show=False),
        Binding("v", "view_all_todos", "View All", show=False),
        Binding("P", "switch_profile", "Profiles", show=False),
    ]

    active_panel: reactive[int] = reactive(-1)

    def __init__(self):
        super().__init__(css_path=self._get_css_path())
        self.dm = DataManager()
        self._panels: list = []

    def compose(self) -> ComposeResult:
        # Title bar
        yield Static(
            f"  [bold #8be9fd]LazyTool[/] [dim]— {self.dm.profile_name}[/]",
            id="right-title-bar",
            markup=True,
        )

        with Horizontal(id="main-container"):
            # Left: panels 1-3
            with Vertical(id="left-panels"):
                yield TodoPanel(self.dm, id="panel-todos", classes="panel")
                yield JournalPanel(self.dm, id="panel-journal", classes="panel")
                yield MoodPanel(self.dm, id="panel-moods", classes="panel")

            # Centre: detail view
            with VerticalScroll(id="centre-pane"):
                yield Static("", id="centre-detail", markup=True)

            # Right: panels 4-6
            with Vertical(id="right-panels"):
                yield GoalsPanel(self.dm, id="panel-goals", classes="panel")
                yield TimelinePanel(self.dm, id="panel-timeline", classes="panel")
                yield StatsPanel(self.dm, id="panel-stats", classes="panel")

        # Bottom status bar
        yield Static("", id="status-bar", markup=True)

    def on_mount(self) -> None:
        self._panels = [
            self.query_one("#panel-todos", TodoPanel),
            self.query_one("#panel-journal", JournalPanel),
            self.query_one("#panel-moods", MoodPanel),
            self.query_one("#panel-goals", GoalsPanel),
            self.query_one("#panel-timeline", TimelinePanel),
            self.query_one("#panel-stats", StatsPanel),
        ]
        self._update_active_panel()
        # Auto-purge old done todos
        purged = self.dm.purge_old_done_todos()
        if purged > 0:
            self._panels[0].refresh_list()

    def _get_welcome_text(self) -> str:
        """Return welcome + help content for the default centre pane."""
        return (
            "[bold #ff79c6]LazyTool - Be Less Lazy[/]\n"
            "[dim]─────────────────────────────────────────[/]\n"
            "[bold #8be9fd]Open a panel to display content[/]\n\n"
            "[dim]© Musaib Bin Bashir 2026[/]\n\n"
            "[bold cyan]Keyboard Shortcuts[/]\n"
            "[dim]─────────────────────────────────────────[/]\n\n"
            "[bold cyan]Navigation[/]\n"
            "  [bold #f1fa8c]1 - 6[/]      Switch panels\n"
            "  [bold #f1fa8c]↑ / k[/]      Move up in list\n"
            "  [bold #f1fa8c]↓ / j[/]      Move down in list\n\n"
            "[bold cyan]Actions[/]\n"
            "  [bold #f1fa8c]a[/]          Add new item / start activity\n"
            "  [bold #f1fa8c]e[/]          Edit selected item\n"
            "  [bold #f1fa8c]d[/]          Delete selected item\n"
            "  [bold #f1fa8c]space[/]      Toggle done / end activity\n"
            "  [bold #f1fa8c]p[/]          Cycle priority (Todos only)\n"
            "  [bold #f1fa8c]enter[/]      View / confirm\n\n"
            "[bold cyan]Todos[/]\n"
            "  [bold #f1fa8c]v[/]          View all todos (full list)\n"
            "  [bold #f1fa8c]s[/]          Set auto-purge days\n\n"
            "[bold cyan]Goals[/]\n"
            "  [bold #f1fa8c]space[/]      Check in for today\n"
            "  [bold #f1fa8c]s[/]          Set history window\n\n"
            "[bold cyan]Timeline[/]\n"
            "  [bold #f1fa8c]h[/]          Previous day\n"
            "  [bold #f1fa8c]l[/]          Next day\n"
            "  [bold #f1fa8c]e[/]          Edit event times\n\n"
            "[bold cyan]Stats[/]\n"
            "  [bold #f1fa8c]s[/]          Set tracking days\n"
            "  [bold #f1fa8c]x[/]          Export stats (.txt/.md)\n\n"
            "[bold cyan]General[/]\n"
            "  [bold #f1fa8c]Shift+P[/]  Switch profile\n"
            "  [bold #f1fa8c]?[/]          Show this help\n"
            "  [bold #f1fa8c]q[/]          Quit\n\n"
            "[bold cyan]Contact Me[/]\n"
            "  Email: [bold #8be9fd]musaibbashir02@gmail.com[/]"
        )

    def _update_active_panel(self) -> None:
        """Highlight the active panel and show its detail."""
        # Clear focused widget so the App can reliably catch navigation keys (up/down)
        # instead of them being trapped by the VerticalScroll native bindings of any panel.
        if self.screen is not None:
            self.screen.set_focus(None)

        for i, panel in enumerate(self._panels):
            if i == self.active_panel:
                panel.add_class("panel-active")
                panel.remove_class("panel")
                panel.styles.border = ("solid", "#50fa7b")
            else:
                panel.remove_class("panel-active")
                panel.add_class("panel")
                panel.styles.border = ("solid", "#44475a")

        # Update detail pane
        self._update_detail()
        self._update_status_bar()

    def _is_panel_active(self) -> bool:
        """Return True if a valid panel is selected."""
        return 0 <= self.active_panel < len(self._panels)

    def _update_detail(self) -> None:
        """Update the right-side detail pane with selected item info."""
        detail = self.query_one("#centre-detail", Static)

        if not self._is_panel_active():
            detail.update(self._get_welcome_text())
            return

        panel = self._panels[self.active_panel]

        panel_names = ["Todos", "Journal", "Moods", "Goals", "Timeline", "Stats"]
        panel_name = panel_names[self.active_panel]
        counter = panel.get_counter_text()

        header = f"[bold #8be9fd][{self.active_panel + 1}]─{panel_name}[/]  [dim]{counter}[/]\n[dim]{'─' * 40}[/]\n\n"
        detail.update(header + panel.get_detail_text())

    def _update_status_bar(self) -> None:
        """Update the bottom status bar with context-sensitive shortcuts."""
        panel_names = ["[1]Todos", "[2]Journal", "[3]Moods", "[4]Goals", "[5]Timeline", "[6]Stats"]

        # Highlight current panel
        parts = []
        for i, name in enumerate(panel_names):
            if i == self.active_panel:
                parts.append(f"[bold #50fa7b]{name}[/]")
            else:
                parts.append(f"[dim]{name}[/]")

        panel_bar = " │ ".join(parts)

        # Context-sensitive actions
        actions = {
            0: "[bold #f1fa8c]a[/]:add [bold #f1fa8c]e[/]:edit [bold #f1fa8c]d[/]:del [bold #f1fa8c]space[/]:toggle [bold #f1fa8c]p[/]:priority [bold #f1fa8c]s[/]:purge",
            1: "[bold #f1fa8c]a[/]:add [bold #f1fa8c]e[/]:edit [bold #f1fa8c]d[/]:del",
            2: "[bold #f1fa8c]a[/]:log mood [bold #f1fa8c]d[/]:del",
            3: "[bold #f1fa8c]a[/]:add [bold #f1fa8c]e[/]:edit [bold #f1fa8c]space[/]:check-in [bold #f1fa8c]d[/]:del [bold #f1fa8c]s[/]:history",
            4: "[bold #f1fa8c]a[/]:start [bold #f1fa8c]e[/]:edit [bold #f1fa8c]n[/]:rename [bold #f1fa8c]space[/]:end [bold #f1fa8c]h[/]:←day [bold #f1fa8c]l[/]:day→ [bold #f1fa8c]d[/]:del",
            5: "[bold #f1fa8c]s[/]:set days [bold #f1fa8c]t[/]:toggle % [bold #f1fa8c]x[/]:export",
        }

        action_text = actions.get(self.active_panel, "")
        bar = f" {panel_bar}  [dim]│[/]  {action_text}  [dim]│[/]  [bold #f1fa8c]?[/]:help [bold #f1fa8c]q[/]:quit"
        self.query_one("#status-bar", Static).update(bar)

    def _switch_panel(self, index: int) -> None:
        self.active_panel = index
        self._update_active_panel()

    def _refresh_stats(self) -> None:
        """Keep the Stats panel up-to-date after any data mutation."""
        self._panels[5].refresh_list()

    # ── Panel switching (number keys) ────────────────────

    def action_panel_1(self) -> None: self._switch_panel(0)
    def action_panel_2(self) -> None: self._switch_panel(1)
    def action_panel_3(self) -> None: self._switch_panel(2)
    def action_panel_4(self) -> None: self._switch_panel(3)
    def action_panel_5(self) -> None: self._switch_panel(4)
    def action_panel_6(self) -> None:
        self._panels[5].refresh_list()  # refresh stats on switch
        self._switch_panel(5)

    # ── Navigation ───────────────────────────────────────

    def action_move_up(self) -> None:
        if not self._is_panel_active():
            return
        panel = self._panels[self.active_panel]
        panel.move_up()
        self._update_detail()

    def action_move_down(self) -> None:
        if not self._is_panel_active():
            return
        panel = self._panels[self.active_panel]
        panel.move_down()
        self._update_detail()

    # ── Add item ─────────────────────────────────────────

    def action_add_item(self) -> None:
        idx = self.active_panel
        if idx == 0:  # Todos
            self.push_screen(
                InputModal("Add Todo", placeholder="What do you need to do?"),
                callback=self._on_add_todo,
            )
        elif idx == 1:  # Journal
            self.push_screen(
                JournalEntryModal("New Journal Entry"),
                callback=self._on_add_journal,
            )
        elif idx == 2:  # Moods
            self.push_screen(
                MoodPickerModal(),
                callback=self._on_add_mood,
            )
        elif idx == 3:  # Goals
            self.push_screen(
                InputModal("Add Goal", placeholder="Goal title (e.g. Read daily, Exercise, Meditate)"),
                callback=self._on_add_goal,
            )
        elif idx == 4:  # Timeline
            active = self.dm.get_active_event()
            if active:
                self.push_screen(
                    ConfirmModal(f"End '{active['name']}'?"),
                    callback=lambda yes: self._on_end_then_start(active, yes),
                )
            else:
                suggestions = self.dm.get_unique_activity_names()
                self.push_screen(
                    AutocompleteModal("Start Activity", suggestions=suggestions, placeholder="e.g. Studying, Working, Reading..."),
                    callback=self._on_start_event,
                )

    def _on_add_todo(self, value: str) -> None:
        if value and value != _CANCELLED:
            self.dm.add_todo(value)
            panel = self._panels[0]
            panel.refresh_list()
            self._refresh_stats()
            self._update_active_panel()

    def _on_add_journal(self, result) -> None:
        if isinstance(result, tuple):
            name, content = result
            if name != _CANCELLED and content != _CANCELLED:
                self.dm.add_journal_entry(name, content)
                panel = self._panels[1]
                panel.selected_index = 0
                panel.refresh_list()
                self._refresh_stats()
                self._update_active_panel()

    def _on_add_mood(self, value: str) -> None:
        if value and value != _CANCELLED:
            self.dm.add_mood(value)
            panel = self._panels[2]
            panel.selected_index = 0
            panel.refresh_list()
            self._refresh_stats()
            self._update_active_panel()

    def _on_add_goal(self, value: str) -> None:
        if value and value != _CANCELLED:
            # After title, ask for optional description
            self._pending_goal_title = value
            self.push_screen(
                InputModal("Goal Description", placeholder="Optional description (leave blank to skip)", allow_empty=True),
                callback=self._on_add_goal_desc,
            )

    def _on_add_goal_desc(self, value: str) -> None:
        if value == _CANCELLED:
            return
        title = getattr(self, "_pending_goal_title", "")
        if title:
            self.dm.add_goal(title, value)
            panel = self._panels[3]
            panel.refresh_list()
            self._refresh_stats()
            self._update_active_panel()

    def _on_start_event(self, value: str) -> None:
        if value and value != _CANCELLED:
            self.dm.start_event(value)
            events = self.dm.get_events_for_date(self._panels[4]._viewed_date())
            self._panels[4].selected_index = max(0, len(events) - 1)
            self._panels[4].refresh_list()
            self._refresh_stats()
            self._update_detail()

    def _on_end_then_start(self, active: dict, confirmed: bool) -> None:
        if confirmed:
            self.dm.end_event(active["id"])
            self._panels[4].refresh_list()
            self._refresh_stats()
            self._update_detail()
            # Ask for new activity
            suggestions = self.dm.get_unique_activity_names()
            self.push_screen(
                AutocompleteModal("Start New Activity", suggestions=suggestions, placeholder="What are you doing now?"),
                callback=self._on_start_event,
            )
        # If not confirmed, just stay

    # ── Edit item ────────────────────────────────────────

    def action_edit_item(self) -> None:
        idx = self.active_panel
        if idx == 0:  # Todos
            todo = self._panels[0].get_selected()
            if todo:
                self.push_screen(
                    InputModal("Edit Todo", default=todo["text"]),
                    callback=lambda v: self._on_edit_todo(todo["id"], v),
                )
        elif idx == 1:  # Journal
            entry = self._panels[1].get_selected()
            if entry:
                self.push_screen(
                    JournalEntryModal(
                        "Edit Journal Entry",
                        default_name=entry.get("name", "Untitled"),
                        default_content=entry.get("content", "")
                    ),
                    callback=lambda v: self._on_edit_journal(entry["id"], v),
                )
        elif idx == 3:  # Goals
            goal = self._panels[3].get_selected()
            if goal:
                self.push_screen(
                    InputModal("Edit Goal Title", default=goal["title"]),
                    callback=lambda v: self._on_edit_goal_title(goal["id"], v),
                )
        elif idx == 4:  # Timeline — edit event start/end time
            ev = self._panels[4].get_selected()
            if ev:
                from lazytool.panels.timeline_panel import _fmt_time
                current_start = _fmt_time(ev["start_time"])
                self._editing_event = ev
                self.push_screen(
                    InputModal("Edit Start Time", placeholder="HH:MM", default=current_start),
                    callback=self._on_edit_event_start,
                )

    def action_rename_item(self) -> None:
        idx = self.active_panel
        if idx == 4:  # Timeline
            ev = self._panels[4].get_selected()
            if ev:
                self.push_screen(
                    InputModal("Rename Activity", default=ev.get("name", "")),
                    callback=lambda v: self._on_rename_event(ev["id"], v),
                )

    def _on_rename_event(self, event_id: str, value: str) -> None:
        if value and value != _CANCELLED:
            self.dm.edit_event_name(event_id, value)
            self._panels[4].refresh_list()
            self._refresh_stats()
            self._update_detail()

    def _on_edit_todo(self, todo_id: str, value: str) -> None:
        if value and value != _CANCELLED:
            self.dm.edit_todo(todo_id, value)
            self._panels[0].refresh_list()
            self._refresh_stats()
            self._update_detail()

    def _on_edit_journal(self, entry_id: str, result) -> None:
        if isinstance(result, tuple):
            name, content = result
            if name != _CANCELLED and content != _CANCELLED:
                self.dm.edit_journal_entry(entry_id, name, content)
                self._panels[1].refresh_list()
                self._refresh_stats()
                self._update_detail()

    def _on_edit_goal_title(self, goal_id: str, value: str) -> None:
        if value and value != _CANCELLED:
            self.dm.edit_goal(goal_id, title=value)
            self._panels[3].refresh_list()
            self._refresh_stats()
            self._update_detail()

    def _on_edit_event_start(self, value: str) -> None:
        if value == _CANCELLED or not value:
            return
        ev = getattr(self, "_editing_event", None)
        if not ev:
            return
        # Validate HH:MM format
        try:
            parts = value.strip().split(":")
            h, m = int(parts[0]), int(parts[1])
            if not (0 <= h <= 23 and 0 <= m <= 59):
                return
        except (ValueError, IndexError):
            return
        # Build ISO datetime from the event's date + new time
        event_date = ev.get("date", ev["start_time"][:10])
        new_start = f"{event_date}T{h:02d}:{m:02d}:00"
        self.dm.edit_event_time(ev["id"], start_time=new_start)
        # Now ask for end time
        if ev.get("end_time"):
            from lazytool.panels.timeline_panel import _fmt_time
            current_end = _fmt_time(ev["end_time"])
            self.push_screen(
                InputModal("Edit End Time", placeholder="HH:MM", default=current_end),
                callback=self._on_edit_event_end,
            )
        else:
            # Active event, no end time to edit
            self._panels[4].refresh_list()
            self._refresh_stats()
            self._update_detail()

    def _on_edit_event_end(self, value: str) -> None:
        if value == _CANCELLED or not value:
            self._panels[4].refresh_list()
            self._update_detail()
            return
        ev = getattr(self, "_editing_event", None)
        if not ev:
            return
        try:
            parts = value.strip().split(":")
            h, m = int(parts[0]), int(parts[1])
            if not (0 <= h <= 23 and 0 <= m <= 59):
                self._panels[4].refresh_list()
                self._update_detail()
                return
        except (ValueError, IndexError):
            self._panels[4].refresh_list()
            self._update_detail()
            return
        event_date = ev.get("date", ev["start_time"][:10])
        new_end_dt = datetime.fromisoformat(f"{event_date}T{h:02d}:{m:02d}:00")
        
        # If we edited start_time in the previous step, ev["start_time"] is already updated in the DM,
        # but the `ev` dictionary we have here is stale. Let's fetch the fresh one.
        fresh_ev = next((e for e in self.dm._data.get("timeline", []) if e["id"] == ev["id"]), ev)
        start_dt = datetime.fromisoformat(fresh_ev["start_time"])
        
        # If the newly constructed end time is before the start time, 
        # it most likely crossed midnight into the next day.
        if new_end_dt < start_dt:
            new_end_dt += timedelta(days=1)
            
        self.dm.edit_event_time(ev["id"], end_time=new_end_dt.isoformat(timespec="seconds"))
        self._panels[4].refresh_list()
        self._refresh_stats()
        self._update_detail()

    # ── Delete item ──────────────────────────────────────

    def action_delete_item(self) -> None:
        idx = self.active_panel
        if idx == 0:
            todo = self._panels[0].get_selected()
            if todo:
                self.dm.delete_todo(todo["id"])
                self._panels[0].refresh_list()
                self._refresh_stats()
                self._update_detail()
                self._update_status_bar()
        elif idx == 1:
            entry = self._panels[1].get_selected()
            if entry:
                self.dm.delete_journal_entry(entry["id"])
                self._panels[1].refresh_list()
                self._refresh_stats()
                self._update_detail()
        elif idx == 2:
            mood = self._panels[2].get_selected()
            if mood:
                self.dm.delete_mood(mood["id"])
                self._panels[2].refresh_list()
                self._refresh_stats()
                self._update_detail()
        elif idx == 3:
            goal = self._panels[3].get_selected()
            if goal:
                self.dm.delete_goal(goal["id"])
                self._panels[3].refresh_list()
                self._refresh_stats()
                self._update_detail()
        elif idx == 4:
            ev = self._panels[4].get_selected()
            if ev:
                self.dm.delete_event(ev["id"])
                self._panels[4].refresh_list()
                self._refresh_stats()
                self._update_detail()

    # ── Toggle / Space ───────────────────────────────────

    def action_toggle_item(self) -> None:
        idx = self.active_panel
        if idx == 0:
            todo = self._panels[0].get_selected()
            if todo:
                self.dm.toggle_todo(todo["id"])
                self._panels[0].refresh_list()
                self._refresh_stats()
                self._update_detail()
                self._update_status_bar()
        elif idx == 3:  # Goals — check in for today
            goal = self._panels[3].get_selected()
            if goal:
                self.dm.check_in_goal(goal["id"])
                self._panels[3].refresh_list()
                self._refresh_stats()
                self._update_detail()
        elif idx == 4:  # Timeline — end current activity
            active = self.dm.get_active_event()
            if active:
                self.dm.end_event(active["id"])
                self._panels[4].refresh_list()
                self._refresh_stats()
                self._update_detail()
                self._update_status_bar()

    # ── Cycle priority ───────────────────────────────────

    def action_cycle_priority(self) -> None:
        if self.active_panel == 0:
            todo = self._panels[0].get_selected()
            if todo:
                self.dm.cycle_priority(todo["id"])
                self._panels[0].refresh_list()
                self._refresh_stats()
                self._update_detail()

    # ── Help ─────────────────────────────────────────────

    # ── Day navigation (Timeline) ─────────────────────────

    def action_prev_day(self) -> None:
        if self.active_panel == 4:
            self._panels[4].prev_day()
            self._update_detail()

    def action_next_day(self) -> None:
        if self.active_panel == 4:
            self._panels[4].next_day()
            self._update_detail()

    # ── Settings ─────────────────────────────────────────

    def action_change_settings(self) -> None:
        if self.active_panel == 5:
            current = self.dm.settings.get("stats_days", 7)
            self.push_screen(
                InputModal("Stats Tracking Days", placeholder=f"Current: {current} — enter new number of days"),
                callback=self._on_change_stats_days,
            )
        elif self.active_panel == 0:
            current = self.dm.settings.get("todo_purge_days", 7)
            self.push_screen(
                InputModal("Todo Auto-Purge Days", placeholder=f"Current: {current} — done todos older than this are deleted"),
                callback=self._on_change_purge_days,
            )
        elif self.active_panel == 3:
            current = self.dm.settings.get("goal_history_days", 30)
            self.push_screen(
                InputModal("Goal History Window", placeholder=f"Current: {current} — number of days to show"),
                callback=self._on_change_goal_history_days,
            )

    def _on_change_stats_days(self, value: str) -> None:
        if value:
            try:
                days = int(value.strip())
                if 1 <= days <= 365:
                    self.dm.update_setting("stats_days", days)
                    self._panels[5].refresh_list()
                    self._update_detail()
            except ValueError:
                pass

    def _on_change_purge_days(self, value: str) -> None:
        if value and value != _CANCELLED:
            try:
                days = int(value.strip())
                if 1 <= days <= 365:
                    self.dm.update_setting("todo_purge_days", days)
                    purged = self.dm.purge_old_done_todos()
                    self._panels[0].refresh_list()
                    self._update_detail()
            except ValueError:
                pass

    def _on_change_goal_history_days(self, value: str) -> None:
        if value and value != _CANCELLED:
            try:
                days = int(value.strip())
                if 1 <= days <= 365:
                    self.dm.update_setting("goal_history_days", days)
                    self._panels[3].refresh_list()
                    self._update_detail()
            except ValueError:
                pass

    def action_toggle_stats_denom(self) -> None:
        if self.active_panel == 5:
            # Modes: 0=Logged, 1=Total, 2=Z-Score, 3=Min/Max
            current = self.dm.settings.get("stats_bar_mode", 3)
            next_mode = (current + 1) % 4
            self.dm.update_setting("stats_bar_mode", next_mode)
            self._panels[5].refresh_list()
            self._update_detail()

    # ── Export stats ─────────────────────────────────────

    def action_export_stats(self) -> None:
        if self.active_panel == 5:
            self.push_screen(
                ExportFormatModal(),
                callback=self._on_export_stats,
            )

    def _on_export_stats(self, fmt: str) -> None:
        if fmt:
            filepath = self._panels[5].export_to_file(fmt)
            detail = self.query_one("#centre-detail", Static)
            detail.update(
                f"[bold #50fa7b]Stats exported![/]\n\n"
                f"  Saved to:\n  [cyan]{filepath}[/]\n\n"
                f"[dim]Press any panel key to continue.[/]"
            )

    # ── View all todos ──────────────────────────────────

    def action_view_all_todos(self) -> None:
        if self.active_panel == 0:
            detail = self.query_one("#centre-detail", Static)
            detail.update(self._panels[0].get_all_todos_text())

    # ── Profile switching ─────────────────────────────────

    def action_switch_profile(self) -> None:
        self.push_screen(
            ProfilePickerModal(),
            callback=self._on_profile_picked,
        )

    def _on_profile_picked(self, value: str) -> None:
        if not value:
            return  # cancelled
        if value == "__NEW__":
            self.push_screen(
                InputModal("New Profile Name", placeholder="e.g. Work, Personal, School..."),
                callback=self._on_new_profile_name,
            )
            return
        if value == "__EDIT__":
            self.push_screen(
                InputModal("Rename Profile", placeholder="Enter new name", default=self.dm.profile_name),
                callback=self._on_rename_profile,
            )
            return
        # Switch to existing profile
        if value != self.dm.profile_name:
            set_active_profile(value)
            self._reload_profile(value)

    def _on_new_profile_name(self, value: str) -> None:
        if not value or value == _CANCELLED:
            return
        name = value.strip()
        if not name:
            return
        create_profile(name)
        set_active_profile(name)
        self._reload_profile(name)

    def _on_rename_profile(self, value: str) -> None:
        if not value or value == _CANCELLED:
            return
        new_name = value.strip()
        if not new_name:
            return
        old_name = self.dm.profile_name
        if rename_profile(old_name, new_name):
            self._reload_profile(new_name)

    def _reload_profile(self, profile_name: str) -> None:
        """Reinitialize DataManager for a new profile and refresh everything."""
        self.dm = DataManager(profile_name)
        # Update all panels to use the new data manager
        for panel in self._panels:
            panel.data_manager = self.dm
            panel.selected_index = 0
            panel.refresh_list()
        # Reset timeline day view to today
        self._panels[4].view_day_offset = 0
        self._panels[4].refresh_list()
        # Update title bar
        title_bar = self.query_one("#right-title-bar", Static)
        title_bar.update(
            f"  [bold #8be9fd]LazyTool[/] [dim]— {profile_name}[/]"
        )
        # Reset to no active panel (welcome screen)
        self.active_panel = -1
        self._update_active_panel()

    # ── Help ─────────────────────────────────────────────

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())
