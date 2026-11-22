import sys


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
        from .window import StudioWindow
    except ModuleNotFoundError as error:
        if error.name and error.name.startswith("PySide6"):
            print("Instale requirements-desktop.txt no ambiente virtual.", file=sys.stderr)
            return 1
        raise

    app = QApplication(sys.argv)
    app.setApplicationName("Arvertes Studio")
    app.setOrganizationName("Arvertes")
    window = StudioWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
