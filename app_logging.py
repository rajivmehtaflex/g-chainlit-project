from pathlib import Path

from loguru import logger

APP_DIR = Path(__file__).parent
LOG_PATH = APP_DIR / "app_events.log"

logger.remove()
logger.add(
    LOG_PATH,
    rotation="10 MB",
    retention="7 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {function}:{line} - {message}",
)

__all__ = ["logger"]
