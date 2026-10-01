from kicad_ia.server.app import serve


def main() -> None:
    serve(open_browser=True)


if __name__ == "__main__":
    main()
