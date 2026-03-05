"""Command-line interface for LazyTool — manage data without launching the TUI."""
import argparse
import sys
from datetime import date

from lazytool.data import DataManager


# ── Priority helpers ─────────────────────────────────────────
_PRIORITY_MAP = {"H": "high", "M": "medium", "L": "low", "h": "high", "m": "medium", "l": "low",
                 "high": "high", "medium": "medium", "low": "low"}
_PRIORITY_LABEL = {"high": "H", "medium": "M", "low": "L"}


def _resolve_priority(value: str) -> str:
    p = _PRIORITY_MAP.get(value)
    if p is None:
        print(f"Error: Unknown priority '{value}'. Use H, M, or L.")
        sys.exit(1)
    return p


# ── Output formatting ───────────────────────────────────────

def _table(rows: list[list[str]], headers: list[str]) -> str:
    """Simple ASCII table formatter."""
    if not rows:
        return "  (none)"
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    sep = "  ".join("─" * w for w in widths)
    hdr = "  ".join(h.ljust(w) for h, w in zip(headers, widths))
    lines = [hdr, sep]
    for row in rows:
        lines.append("  ".join(cell.ljust(w) for cell, w in zip(row, widths)))
    return "\n".join(lines)


def _short_id(full_id: str) -> str:
    return full_id[:8]


def _fmt_time_short(iso: str) -> str:
    """Extract HH:MM from ISO timestamp."""
    if not iso:
        return ""
    try:
        return iso[11:16]
    except Exception:
        return iso


# ── Subcommand handlers ─────────────────────────────────────

def handle_todo(args, dm: DataManager):
    if args.add:
        priority = _resolve_priority(args.priority) if args.priority else "medium"
        todo = dm.add_todo(args.add, priority=priority)
        print(f"✓ Added todo [{_short_id(todo['id'])}]: {todo['text']}  (priority: {_PRIORITY_LABEL[priority]})")
        return

    if args.list:
        todos = dm.get_sorted_todos()
        if not todos:
            print("No todos.")
            return
        rows = []
        for t in todos:
            status = "✓" if t["done"] else "○"
            pri = _PRIORITY_LABEL.get(t.get("priority", "medium"), "M")
            rows.append([_short_id(t["id"]), status, pri, t["text"]])
        print(_table(rows, ["ID", "Done", "Pri", "Text"]))
        return

    # ID-based operations
    if not args.id:
        print("Error: Provide --add, --list, or --id <id> with an action.")
        sys.exit(1)

    todo_id = _resolve_id(args.id, [t["id"] for t in dm.todos])

    if args.done:
        dm.toggle_todo(todo_id)
        t = next((t for t in dm.todos if t["id"] == todo_id), None)
        state = "done ✓" if (t and t["done"]) else "not done ○"
        print(f"✓ Todo [{_short_id(todo_id)}] marked as {state}")
    elif args.edit:
        dm.edit_todo(todo_id, args.edit)
        print(f"✓ Todo [{_short_id(todo_id)}] updated: {args.edit}")
    elif args.priority:
        # Set priority directly instead of cycling
        priority = _resolve_priority(args.priority)
        for t in dm.todos:
            if t["id"] == todo_id:
                t["priority"] = priority
                break
        dm._save()
        print(f"✓ Todo [{_short_id(todo_id)}] priority set to {_PRIORITY_LABEL[priority]}")
    elif args.delete:
        dm.delete_todo(todo_id)
        print(f"✓ Deleted todo [{_short_id(todo_id)}]")
    else:
        print("Error: Provide an action: --edit, --priority, --done, or --delete")
        sys.exit(1)


def handle_timeline(args, dm: DataManager):
    if args.start:
        ev = dm.start_event(args.start)
        print(f"✓ Started [{_short_id(ev['id'])}]: {ev['name']} at {_fmt_time_short(ev['start_time'])}")
        return

    if args.stop:
        active = dm.get_active_event()
        if not active:
            print("No active event to stop.")
            return
        dm.end_event(active["id"])
        print(f"✓ Stopped [{_short_id(active['id'])}]: {active['name']}")
        return

    if args.list:
        today = date.today().isoformat()
        events = dm.get_events_for_date(today)
        if not events:
            print(f"No events for today ({today}).")
            return
        rows = []
        for ev in events:
            start = _fmt_time_short(ev.get("_day_start", ev.get("start_time", "")))
            end_raw = ev.get("end_time")
            end = _fmt_time_short(ev.get("_day_end", end_raw)) if end_raw else "active"
            dur = dm.get_event_day_duration_minutes(ev)
            dur_str = f"{int(dur)}m" if dur < 60 else f"{dur / 60:.1f}h"
            rows.append([_short_id(ev["id"]), ev["name"], start, end, dur_str])
        print(_table(rows, ["ID", "Event", "Start", "End", "Duration"]))
        return

    if not args.id:
        print("Error: Provide --start, --stop, --list, or --id <id> with an action.")
        sys.exit(1)

    event_id = _resolve_id(args.id, [ev["id"] for ev in dm.timeline])

    if args.rename:
        dm.edit_event_name(event_id, args.rename)
        print(f"✓ Renamed event [{_short_id(event_id)}] to: {args.rename}")
    elif args.delete:
        dm.delete_event(event_id)
        print(f"✓ Deleted event [{_short_id(event_id)}]")
    else:
        print("Error: Provide an action: --rename or --delete")
        sys.exit(1)


def handle_mood(args, dm: DataManager):
    VALID_MOODS = {"amazing", "great", "good", "okay", "bad", "terrible"}

    if args.add:
        if args.add not in VALID_MOODS:
            print(f"Error: Mood must be one of: {', '.join(sorted(VALID_MOODS))}")
            sys.exit(1)
        note = args.note or ""
        entry = dm.add_mood(args.add, note=note)
        print(f"✓ Logged mood [{_short_id(entry['id'])}]: {args.add}" + (f" — {note}" if note else ""))
        return

    if args.list:
        moods = list(reversed(dm.moods))  # newest first
        if not moods:
            print("No moods logged.")
            return
        rows = []
        for m in moods[:20]:  # show last 20
            note_preview = (m.get("note", "") or "")[:30]
            rows.append([_short_id(m["id"]), m.get("date", ""), m["mood"], note_preview])
        print(_table(rows, ["ID", "Date", "Mood", "Note"]))
        return

    if not args.id:
        print("Error: Provide --add, --list, or --id <id> --delete.")
        sys.exit(1)

    mood_id = _resolve_id(args.id, [m["id"] for m in dm.moods])

    if args.delete:
        dm.delete_mood(mood_id)
        print(f"✓ Deleted mood [{_short_id(mood_id)}]")
    else:
        print("Error: Provide --delete for mood entries.")
        sys.exit(1)


def handle_journal(args, dm: DataManager):
    if args.add:
        name = args.name or "Untitled"
        content = args.content or ""
        entry = dm.add_journal_entry(name, content)
        print(f"✓ Added journal entry [{_short_id(entry['id'])}]: {name}")
        return

    if args.list:
        entries = list(reversed(dm.journal))  # newest first
        if not entries:
            print("No journal entries.")
            return
        rows = []
        for e in entries[:20]:
            name = (e.get("name", "") or "Untitled")[:25]
            preview = (e.get("content", "") or "")[:40]
            rows.append([_short_id(e["id"]), e.get("date", ""), name, preview])
        print(_table(rows, ["ID", "Date", "Name", "Content"]))
        return

    if not args.id:
        print("Error: Provide --add, --list, or --id <id> with an action.")
        sys.exit(1)

    entry_id = _resolve_id(args.id, [e["id"] for e in dm.journal])

    if args.edit:
        name = args.name
        content = args.content
        if name is None and content is None:
            print("Error: Provide --name and/or --content to edit.")
            sys.exit(1)
        # Get current values for fields not being updated
        entry = next((e for e in dm.journal if e["id"] == entry_id), None)
        if entry is None:
            print(f"Error: Entry [{args.id}] not found.")
            sys.exit(1)
        new_name = name if name is not None else entry.get("name", "")
        new_content = content if content is not None else entry.get("content", "")
        dm.edit_journal_entry(entry_id, new_name, new_content)
        print(f"✓ Updated journal entry [{_short_id(entry_id)}]")
    elif args.delete:
        dm.delete_journal_entry(entry_id)
        print(f"✓ Deleted journal entry [{_short_id(entry_id)}]")
    else:
        print("Error: Provide an action: --edit or --delete")
        sys.exit(1)


def handle_goal(args, dm: DataManager):
    if args.add:
        desc = args.desc or ""
        goal = dm.add_goal(args.add, description=desc)
        print(f"✓ Added goal [{_short_id(goal['id'])}]: {args.add}")
        return

    if args.list:
        goals = dm.goals
        if not goals:
            print("No goals.")
            return
        rows = []
        today = date.today().isoformat()
        for g in goals:
            streak = dm.get_goal_streak(g)
            checked = "✓" if today in g.get("check_ins", []) else "○"
            streak_str = f"{streak}d 🔥" if streak > 0 else "—"
            rows.append([_short_id(g["id"]), checked, g["title"], streak_str])
        print(_table(rows, ["ID", "Today", "Title", "Streak"]))
        return

    if not args.id:
        print("Error: Provide --add, --list, or --id <id> with an action.")
        sys.exit(1)

    goal_id = _resolve_id(args.id, [g["id"] for g in dm.goals])

    if args.checkin:
        result = dm.check_in_goal(goal_id)
        state = "checked in ✓" if result else "unchecked ○"
        print(f"✓ Goal [{_short_id(goal_id)}] {state} for today")
    elif args.edit:
        title = args.edit if args.edit is not True else None
        desc = args.desc
        if title is None and desc is None:
            print("Error: Provide a title with --edit and/or --desc.")
            sys.exit(1)
        dm.edit_goal(goal_id, title=title, description=desc)
        print(f"✓ Updated goal [{_short_id(goal_id)}]")
    elif args.delete:
        dm.delete_goal(goal_id)
        print(f"✓ Deleted goal [{_short_id(goal_id)}]")
    else:
        print("Error: Provide an action: --checkin, --edit, or --delete")
        sys.exit(1)


# ── ID resolution ────────────────────────────────────────────

def _resolve_id(partial: str, all_ids: list[str]) -> str:
    """Match a partial ID (prefix) to a full ID. Exit on ambiguity or no match."""
    matches = [fid for fid in all_ids if fid.startswith(partial)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) == 0:
        print(f"Error: No item found with ID starting with '{partial}'.")
        sys.exit(1)
    print(f"Error: Ambiguous ID '{partial}' matches: {', '.join(_short_id(m) for m in matches)}")
    sys.exit(1)


# ── Argument parser ──────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lazytool",
        description="LazyTool — terminal productivity, from the command line.",
    )
    parser.add_argument("--profile", "-P", help="Use a specific profile (default: active profile)")
    sub = parser.add_subparsers(dest="command")

    # ── todo ──────────────────────────────────────────────
    todo = sub.add_parser("todo", aliases=["t"], help="Manage todos")
    todo.add_argument("--add", "-a", metavar="TEXT", help="Add a new todo")
    todo.add_argument("--list", "-l", action="store_true", help="List all todos")
    todo.add_argument("--id", "-i", metavar="ID", help="ID of todo to modify")
    todo.add_argument("--edit", "-e", metavar="TEXT", help="Edit todo text")
    todo.add_argument("--priority", "-p", metavar="H|M|L", help="Set priority")
    todo.add_argument("--done", "-d", action="store_true", help="Toggle done status")
    todo.add_argument("--delete", action="store_true", help="Delete the todo")

    # ── timeline ─────────────────────────────────────────
    tl = sub.add_parser("timeline", aliases=["tl"], help="Manage timeline events")
    tl.add_argument("--start", "-s", metavar="NAME", help="Start a new event")
    tl.add_argument("--stop", action="store_true", help="Stop the active event")
    tl.add_argument("--list", "-l", action="store_true", help="List today's events")
    tl.add_argument("--id", "-i", metavar="ID", help="ID of event to modify")
    tl.add_argument("--rename", "-r", metavar="NAME", help="Rename an event")
    tl.add_argument("--delete", action="store_true", help="Delete an event")

    # ── mood ─────────────────────────────────────────────
    mood = sub.add_parser("mood", aliases=["m"], help="Log and view moods")
    mood.add_argument("--add", "-a", metavar="MOOD",
                       help="Log a mood (amazing/great/good/okay/bad/terrible)")
    mood.add_argument("--note", "-n", metavar="TEXT", help="Note for the mood entry")
    mood.add_argument("--list", "-l", action="store_true", help="List recent moods")
    mood.add_argument("--id", "-i", metavar="ID", help="ID of mood to modify")
    mood.add_argument("--delete", action="store_true", help="Delete a mood entry")

    # ── journal ──────────────────────────────────────────
    jrn = sub.add_parser("journal", aliases=["j"], help="Manage journal entries")
    jrn.add_argument("--add", "-a", action="store_true", help="Add a new entry")
    jrn.add_argument("--name", "-n", metavar="TEXT", help="Entry name/title")
    jrn.add_argument("--content", "-c", metavar="TEXT", help="Entry content")
    jrn.add_argument("--list", "-l", action="store_true", help="List journal entries")
    jrn.add_argument("--id", "-i", metavar="ID", help="ID of entry to modify")
    jrn.add_argument("--edit", "-e", action="store_true", help="Edit an entry")
    jrn.add_argument("--delete", action="store_true", help="Delete an entry")

    # ── goal ─────────────────────────────────────────────
    goal = sub.add_parser("goal", aliases=["g"], help="Manage goals")
    goal.add_argument("--add", "-a", metavar="TITLE", help="Add a new goal")
    goal.add_argument("--desc", metavar="TEXT", help="Goal description")
    goal.add_argument("--list", "-l", action="store_true", help="List all goals")
    goal.add_argument("--id", "-i", metavar="ID", help="ID of goal to modify")
    goal.add_argument("--checkin", action="store_true", help="Toggle today's check-in")
    goal.add_argument("--edit", "-e", metavar="TITLE", nargs="?", const=True,
                       help="Edit goal title")
    goal.add_argument("--delete", action="store_true", help="Delete a goal")

    return parser


# ── Full help ────────────────────────────────────────────────

def print_full_help():
    """Print a comprehensive panel-wise command reference."""
    # Print ASCII art from file
    import os as _os
    if getattr(sys, 'frozen', False):
        base = getattr(sys, '_MEIPASS', _os.path.dirname(sys.executable))
    else:
        base = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    art_path = _os.path.join(base, "ascii-art.txt")
    if _os.path.exists(art_path):
        with open(art_path, "r", encoding="utf-8") as f:
            print(f.read())

    # Project info block
    print("─" * 60)
    print("  LazyTool — Be less lazy")
    print("  Version:      2.2.0")
    print("  Developed by: Musaib Bin Bashir")
    print("  Website:      www.lazygit.site")
    print("─" * 60)
    print("Usage: lazytool <command> [options]")
    print("       lazytool                      Launch the TUI (interactive mode)")
    print("       lazytool --help               Show this help")
    print()
    print("Global options:")
    print("  --profile, -P <name>               Use a specific profile (default: active)")
    print()

    print("=" * 60)
    print("  TODO  (command: todo | t)")
    print("=" * 60)
    print("  lazytool todo --add \"text\" --priority H   Add todo (priority: H/M/L, default M)")
    print("  lazytool todo --list                      List all todos with IDs")
    print("  lazytool todo --id <id> --done            Toggle done status")
    print("  lazytool todo --id <id> --edit \"text\"     Edit todo text")
    print("  lazytool todo --id <id> --priority H      Set priority (H/M/L)")
    print("  lazytool todo --id <id> --delete          Delete a todo")
    print()

    print("=" * 60)
    print("  TIMELINE  (command: timeline | tl)")
    print("=" * 60)
    print("  lazytool timeline --start \"name\"          Start event (stops active)")
    print("  lazytool timeline --stop                  Stop the active event")
    print("  lazytool timeline --list                  List today's events")
    print("  lazytool timeline --id <id> --rename \"n\"  Rename an event")
    print("  lazytool timeline --id <id> --delete      Delete an event")
    print()

    print("=" * 60)
    print("  MOOD  (command: mood | m)")
    print("=" * 60)
    print("  lazytool mood --add great --note \"text\"   Log mood + optional note")
    print("    moods: amazing | great | good | okay | bad | terrible")
    print("  lazytool mood --list                      List recent moods")
    print("  lazytool mood --id <id> --delete          Delete a mood entry")
    print()

    print("=" * 60)
    print("  JOURNAL  (command: journal | j)")
    print("=" * 60)
    print("  lazytool journal --add --name \"T\" --content \"C\"")
    print("                                            Add a journal entry")
    print("  lazytool journal --list                   List journal entries")
    print("  lazytool journal --id <id> --edit --name \"T\" --content \"C\"")
    print("                                            Edit an entry")
    print("  lazytool journal --id <id> --delete       Delete an entry")
    print()

    print("=" * 60)
    print("  GOAL  (command: goal | g)")
    print("=" * 60)
    print("  lazytool goal --add \"title\" --desc \"d\"    Add a goal")
    print("  lazytool goal --list                      List goals with streaks")
    print("  lazytool goal --id <id> --checkin         Toggle today's check-in")
    print("  lazytool goal --id <id> --edit \"title\"    Edit goal title")
    print("  lazytool goal --id <id> --delete          Delete a goal")
    print()

    print("─" * 60)
    print("  IDs: use first few characters (e.g. 'ab3f' instead of 'ab3f91c2')")
    print("  Short aliases: t, tl, m, j, g")
    print()


# ── Main entry point ─────────────────────────────────────────

_HANDLERS = {
    "todo": handle_todo, "t": handle_todo,
    "timeline": handle_timeline, "tl": handle_timeline,
    "mood": handle_mood, "m": handle_mood,
    "journal": handle_journal, "j": handle_journal,
    "goal": handle_goal, "g": handle_goal,
}


def cli_main(argv: list[str] | None = None):
    # Intercept --help / -help / -h before argparse to show full panel-wise help
    check = argv if argv is not None else sys.argv[1:]
    if any(h in check for h in ("--help", "-h", "-help")):
        print_full_help()
        sys.exit(0)

    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        print_full_help()
        sys.exit(0)

    dm = DataManager(profile=args.profile)
    handler = _HANDLERS.get(args.command)
    if handler:
        handler(args, dm)
    else:
        print_full_help()
        sys.exit(1)
