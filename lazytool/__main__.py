"""Entry point for LazyTool — run with `python -m lazytool` or `lazytool`."""
import sys
import traceback


def main():
    try:
        # Give LazyTool its own taskbar identity on Windows
        import platform
        if platform.system() == "Windows":
            import ctypes
            # Separate taskbar group from terminal
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "musaib.lazytool.app.1.2"
            )
            # Set the console window icon
            try:
                import sys, os
                if getattr(sys, 'frozen', False):
                    base = sys._MEIPASS
                else:
                    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                ico_path = os.path.join(base, "app_icon.ico")
                if os.path.exists(ico_path):
                    WM_SETICON = 0x0080
                    ICON_BIG = 1
                    ICON_SMALL = 0
                    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
                    icon = ctypes.windll.user32.LoadImageW(
                        0, ico_path, 1, 0, 0, 0x00000010  # LR_LOADFROMFILE
                    )
                    if hwnd and icon:
                        ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, icon)
                        ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, icon)
            except Exception:
                pass  # non-critical, don't crash

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
