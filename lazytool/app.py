"""LazyTool — Main application with Lazygit-style TUI layout."""
from __future__ import annotations

import sys
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static, Input, Header, Footer, Label
from textual.containers import Vertical, Horizontal, VerticalScroll, Container
from textual.reactive import reactive

from lazytool.data import DataManager
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
                "  [bold #f1fa8c]?[/]          Show this help\n"
                "  [bold #f1fa8c]q[/]          Quit\n\n"
                "[dim]Press Escape or ? to close[/]\n\n"
                "[bold cyan]Contact Me[/]\n"
                "  Email: [bold #8be9fd]musaibbashir02@gmail.com[/]",
                markup=True,
            )

    def action_close(self) -> None:
        self.dismiss()


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
        Binding("d", "delete_item", "Delete", show=False),
        Binding("space", "toggle_item", "Toggle", show=False),
        Binding("p", "cycle_priority", "Priority", show=False),
        Binding("h", "prev_day", "Prev day", show=False),
        Binding("l", "next_day", "Next day", show=False),
        Binding("s", "change_settings", "Settings", show=False),
        Binding("x", "export_stats", "Export", show=False),
        Binding("v", "view_all_todos", "View All", show=False),
    ]

    active_panel: reactive[int] = reactive(-1)

    def __init__(self):
        super().__init__(css_path=self._get_css_path())
        self.dm = DataManager()
        self._panels: list = []

    def compose(self) -> ComposeResult:
        # Title bar
        yield Static(
            "  [bold #8be9fd]LazyTool[/] [dim]— Personal Productivity[/]",
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
            "  [bold #f1fa8c]?[/]          Show this help\n"
            "  [bold #f1fa8c]q[/]          Quit\n\n"
            "[bold cyan]Contact Me[/]\n"
            "  Email: [bold #8be9fd]musaibbashir02@gmail.com[/]"
        )

    def _update_active_panel(self) -> None:
        """Highlight the active panel and show its detail."""
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
            4: "[bold #f1fa8c]a[/]:start [bold #f1fa8c]e[/]:edit [bold #f1fa8c]space[/]:end [bold #f1fa8c]h[/]:←day [bold #f1fa8c]l[/]:day→ [bold #f1fa8c]d[/]:del",
            5: "[bold #f1fa8c]s[/]:set days [bold #f1fa8c]x[/]:export",
        }

        action_text = actions.get(self.active_panel, "")
        bar = f" {panel_bar}  [dim]│[/]  {action_text}  [dim]│[/]  [bold #f1fa8c]?[/]:help [bold #f1fa8c]q[/]:quit"
        self.query_one("#status-bar", Static).update(bar)

    def _switch_panel(self, index: int) -> None:
        self.active_panel = index
        self._update_active_panel()

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
                InputModal("New Journal Entry", placeholder="Write your thoughts..."),
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
                self.push_screen(
                    InputModal("Start Activity", placeholder="e.g. Studying, Working, Reading..."),
                    callback=self._on_start_event,
                )

    def _on_add_todo(self, value: str) -> None:
        if value and value != _CANCELLED:
            self.dm.add_todo(value)
            panel = self._panels[0]
            panel.refresh_list()
            self._update_detail()
            self._update_status_bar()

    def _on_add_journal(self, value: str) -> None:
        if value and value != _CANCELLED:
            self.dm.add_journal_entry(value)
            panel = self._panels[1]
            panel.selected_index = 0
            panel.refresh_list()
            self._update_detail()

    def _on_add_mood(self, value: str) -> None:
        if value and value != _CANCELLED:
            self.dm.add_mood(value)
            panel = self._panels[2]
            panel.selected_index = 0
            panel.refresh_list()
            self._update_detail()

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
            self._update_detail()

    def _on_start_event(self, value: str) -> None:
        if value and value != _CANCELLED:
            self.dm.start_event(value)
            self._panels[4].refresh_list()
            self._update_detail()

    def _on_end_then_start(self, active: dict, confirmed: bool) -> None:
        if confirmed:
            self.dm.end_event(active["id"])
            self._panels[4].refresh_list()
            self._update_detail()
            # Ask for new activity
            self.push_screen(
                InputModal("Start New Activity", placeholder="What are you doing now?"),
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
                    InputModal("Edit Journal Entry", default=entry["content"]),
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

    def _on_edit_todo(self, todo_id: str, value: str) -> None:
        if value and value != _CANCELLED:
            self.dm.edit_todo(todo_id, value)
            self._panels[0].refresh_list()
            self._update_detail()

    def _on_edit_journal(self, entry_id: str, value: str) -> None:
        if value and value != _CANCELLED:
            self.dm.edit_journal_entry(entry_id, value)
            self._panels[1].refresh_list()
            self._update_detail()

    def _on_edit_goal_title(self, goal_id: str, value: str) -> None:
        if value and value != _CANCELLED:
            self.dm.edit_goal(goal_id, title=value)
            self._panels[3].refresh_list()
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
        new_end = f"{event_date}T{h:02d}:{m:02d}:00"
        self.dm.edit_event_time(ev["id"], end_time=new_end)
        self._panels[4].refresh_list()
        self._update_detail()

    # ── Delete item ──────────────────────────────────────

    def action_delete_item(self) -> None:
        idx = self.active_panel
        if idx == 0:
            todo = self._panels[0].get_selected()
            if todo:
                self.dm.delete_todo(todo["id"])
                self._panels[0].refresh_list()
                self._update_detail()
                self._update_status_bar()
        elif idx == 1:
            entry = self._panels[1].get_selected()
            if entry:
                self.dm.delete_journal_entry(entry["id"])
                self._panels[1].refresh_list()
                self._update_detail()
        elif idx == 2:
            mood = self._panels[2].get_selected()
            if mood:
                self.dm.delete_mood(mood["id"])
                self._panels[2].refresh_list()
                self._update_detail()
        elif idx == 3:
            goal = self._panels[3].get_selected()
            if goal:
                self.dm.delete_goal(goal["id"])
                self._panels[3].refresh_list()
                self._update_detail()
        elif idx == 4:
            ev = self._panels[4].get_selected()
            if ev:
                self.dm.delete_event(ev["id"])
                self._panels[4].refresh_list()
                self._update_detail()

    # ── Toggle / Space ───────────────────────────────────

    def action_toggle_item(self) -> None:
        idx = self.active_panel
        if idx == 0:
            todo = self._panels[0].get_selected()
            if todo:
                self.dm.toggle_todo(todo["id"])
                self._panels[0].refresh_list()
                self._update_detail()
                self._update_status_bar()
        elif idx == 3:  # Goals — check in for today
            goal = self._panels[3].get_selected()
            if goal:
                self.dm.check_in_goal(goal["id"])
                self._panels[3].refresh_list()
                self._update_detail()
        elif idx == 4:  # Timeline — end current activity
            active = self.dm.get_active_event()
            if active:
                self.dm.end_event(active["id"])
                self._panels[4].refresh_list()
                self._update_detail()
                self._update_status_bar()

    # ── Cycle priority ───────────────────────────────────

    def action_cycle_priority(self) -> None:
        if self.active_panel == 0:
            todo = self._panels[0].get_selected()
            if todo:
                self.dm.cycle_priority(todo["id"])
                self._panels[0].refresh_list()
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

    # ── Help ─────────────────────────────────────────────

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())
