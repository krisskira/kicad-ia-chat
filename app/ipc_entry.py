import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))


def main() -> None:
    from kicad_ia.server.app import serve

    serve(open_browser=True)


if __name__ == "__main__":
    main()
