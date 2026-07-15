import uuid

from app_logging import LOG_PATH, logger


def test_logger_writes_to_configured_file():
    marker = f"test-marker-{uuid.uuid4()}"
    logger.info("smoke test message {}", marker)

    assert LOG_PATH.exists()
    assert marker in LOG_PATH.read_text()
