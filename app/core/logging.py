import logging
from app.middleware.request_id import get_request_id

class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


class RequestIdFormatter(logging.Formatter):
    """Formatter that guarantees a request_id field for every record."""

    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "request_id"):
            record.request_id = get_request_id()
        return super().format(record)


def setup_logging():
    log_format = "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"
    logging.basicConfig(level=logging.INFO, format=log_format)

    formatter = RequestIdFormatter(log_format)
    request_id_filter = RequestIdFilter()

    # Ensure any handler using request_id format can safely process third-party logs.
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.setFormatter(formatter)
        handler.addFilter(request_id_filter)

    for name in ("uvicorn.access", "uvicorn.error", "sqlalchemy.engine"):
        logger = logging.getLogger(name)
        logger.addFilter(request_id_filter)
        for handler in logger.handlers:
            handler.setFormatter(formatter)
            handler.addFilter(request_id_filter)
