"""Entry point for LazyTool — run with `python -m lazytool` or `lazytool`."""
import sys
import traceback


def main():
    try:
        from lazytool.app import LazyToolApp
        app = LazyToolApp()
        app.run()
    except Exception:
        traceback.print_exc()
        if getattr(sys, 'frozen', False):
            input("\nPress Enter to exit...")
        sys.exit(1)


if __name__ == "__main__":
    main()
