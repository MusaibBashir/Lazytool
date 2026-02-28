import subprocess
import sys

def main():
    command = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--console",
        "--collect-all", "textual",
        "--collect-all", "rich",
        "--add-data", "lazytool/app.tcss:lazytool",
        "--name", "lazytool",
        "--clean",
        "lazytool/__main__.py"
    ]

    print("Running PyInstaller command:")
    print(" ".join(command))

    try:
        subprocess.run(command, check=True)
        print("\nBuild completed successfully!")
        print("Binary located at: dist/lazytool")
    except subprocess.CalledProcessError as e:
        print(f"\nBuild failed with exit code {e.returncode}")
        sys.exit(e.returncode)

if __name__ == "__main__":
    main()
