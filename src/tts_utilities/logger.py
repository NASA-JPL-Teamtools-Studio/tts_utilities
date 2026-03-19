import logging
import os
import sys
from pathlib import Path
from typing import Union, Optional

from rich.logging import RichHandler
from rich.console import Console

UTC_FMT_TRUNCATED = "%Y-%jT%H:%M:%S"

DEFAULT_LOGGING_FORMATTER = logging.Formatter(
    "%(asctime)s (%(levelname)s) %(name)s.%(funcName)s: %(message)s",
    datefmt=UTC_FMT_TRUNCATED,
)


def create_logger(
    name: str,
    stream_level: Union[int, str] = logging.INFO,
    file_level: Union[int, str] = logging.DEBUG,
    formatter: logging.Formatter = DEFAULT_LOGGING_FORMATTER,
    log_path: Optional[Union[str, os.PathLike, Path]] = None,
    propagate: bool = False,
    propagation_double_msg_checking: bool = True,
    console_width: Optional[int] = None
) -> logging.Logger:
    """
    Creates a logger that will log to a specified file and path and to STDOUT.
    Logger should use a common stream handler for output to the console, and
    a distinct file handler for output to individual log files.

    Parameters
    ----------
    name:
        Name of the logger.
    stream_level:
        Log level to be used for the stream handler. Accepts logging level,
        which can be const like logging.INFO, or a string like "INFO".
    file_level:
        Log level to be used for the file handler. Accepts logging level,
        which can be const like logging.INFO, or a string like "INFO".
    formatter:
        Formatter for the logger, which changes how messages look.
    log_path:
        Path to where the log file will be written, if provided. If None, no
        log file will be written. Must include file name with ".log" extension.
    propagate:
        Whether or not this logger should propagate log output up to its
        parent loggers.
    propagation_double_msg_checking:
        If True, use method for mitigating known logger double messaging bug.
    console_width:
        Width of console to force. Will default to logger default behavor
        if None, else it's that number of characters

    Returns
    -------
    logger:
        logging.Logger
    """

    logger = logging.getLogger(name)

    # Start from scratch (in case a logger of this name already exists)
    if logger.hasHandlers():
        logger.handlers.clear()

    # If this logger is propagating and has a parent that is NOT the root logger,
    # then do NOT log to the stream because it can be assumed that the parent
    # will already be logging these propagated messages to the stream. This
    # prevents bugs where messages get double printed to the console since
    # propagating can cause that if both loggers are writing to the console.
    has_parent = logger.parent is not None and logger.parent.name != "root"
    should_skip_stream = propagation_double_msg_checking and propagate and has_parent
    if not should_skip_stream:
        # Control what goes to stdout aka the console
        console = Console(
            width=console_width, 
            force_terminal=True if console_width else None
        )
        
        stream_handler = RichHandler(
            console=console, 
            rich_tracebacks=True, 
            markup=True
        )        

        stream_handler.setFormatter(formatter)
        stream_handler.setLevel(stream_level)
        logger.addHandler(stream_handler)

    # Control how the log messages are written to the file.
    if log_path is not None:
        if not isinstance(log_path, Path):
            log_path = Path(log_path)

        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_path)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(file_level)
        logger.addHandler(file_handler)

    # Final logger setup settings
    logger.setLevel(min(stream_level, file_level))
    logger.propagate = propagate

    return logger
