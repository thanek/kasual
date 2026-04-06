import logging
import sys
from pathlib import Path

import yaml
from PyQt6.QtWidgets import QApplication

from gamepad_manager import GamepadManager
from desktop import Desktop


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s  [%(name)-22s]  %(levelname)-8s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler()],
    )


def _load_apps() -> list[dict]:
    cfg_path = Path(__file__).parent / "apps.yml"
    with open(cfg_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("apps", [])


def main() -> None:
    _setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Uruchamiam Console Desktop")

    apps = _load_apps()
    logger.info("Załadowano %d aplikacji", len(apps))

    app = QApplication(sys.argv)
    app.setApplicationName("Console Desktop")

    gamepad = GamepadManager()
    desktop = Desktop(apps=apps, gamepad=gamepad)  # noqa: F841

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
