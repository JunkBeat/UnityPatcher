import logging
from logging import LogRecord, StreamHandler


class _NoStackTraceStreamHandler(StreamHandler):
    """Does not emit caught exception stack trace to stream."""

    __doc__ += StreamHandler.__doc__

    def emit(self, record):  # noqa: D102
        try:
            if record.exc_info:
                record = LogRecord(
                    record.name,
                    record.levelname,
                    record.pathname,
                    record.lineno,
                    record.msg,
                    record.args,
                    None,
                    record.funcName,
                    record.stack_info,
                )
            super().emit(record)
        except Exception:  # pylint: disable=broad-except
            self.handleError(record)


def setup_logging(logger_name="typetree_logger", level=logging.DEBUG):
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)

    console_handler = _NoStackTraceStreamHandler() #logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter("[Typetree Generator] %(message)s")
    )

    logger.addHandler(console_handler)
    return logger


def get_logger(logger_name="typetree_logger"):
    return logging.getLogger(logger_name)
