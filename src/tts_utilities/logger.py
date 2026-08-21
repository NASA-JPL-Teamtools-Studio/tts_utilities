import logging
import os
import sys
from pathlib import Path
from typing import Union, Optional

from rich.logging import RichHandler
from rich.console import Console

UTC_FMT_TRUNCATED = "%Y-%jT%H:%M:%S"

_MANAGED_LOGGERS: dict = {}
_SHARED_HANDLERS: list = []


def register_shared_handler(handler: logging.Handler) -> None:
    """
    Register a handler to be added to all loggers managed by create_logger.

    Adds the handler immediately to all currently managed loggers and to any
    future loggers created by create_logger.

    This mechanism was introduced to solve a problem in ``tts_tower``: Tower's
    ``log_to_file`` function attaches a file handler to the ``'tower'`` logger
    hierarchy, but most modules use ``create_logger`` from this library, which
    produces isolated loggers (``propagate=False``) outside that hierarchy.
    Without this registry, those loggers' output would never reach the log
    file. ``log_to_file`` now calls this function so the file handler is
    pushed to every ``create_logger``-managed logger automatically, both
    retroactively and for any loggers created afterward.

    This is not Tower-specific and may be useful for any downstream library
    that needs to inject a handler into all managed loggers at runtime. For
    example, ``tts_dexter`` could call ``register_shared_handler`` at the start
    of a procedure run, passing a ``FileHandler`` pointed at a per-procedure
    log file. Every module that participates in that run (data utils, input
    clients, dispositioners, etc.) would then automatically write to that file
    without any of them needing to know the log path.

    Parameters
    ----------
    handler:
        The handler instance to share across all managed loggers.
    """
    if handler not in _SHARED_HANDLERS:
        _SHARED_HANDLERS.append(handler)
    for logger in _MANAGED_LOGGERS.values():
        if handler not in logger.handlers:
            logger.addHandler(handler)


def unregister_shared_handlers_by_type(handler_type: type) -> None:
    """
    Remove all shared handlers of the given type from the registry and all
    managed loggers.

    This is the counterpart to ``register_shared_handler`` and is intended to
    be called before registering a replacement handler of the same type — for
    example, when ``tts_tower``'s ``log_to_file`` is invoked a second time to
    redirect output to a new file. Calling this first ensures the old
    ``FileHandler`` is cleanly removed from every managed logger before the
    new one is registered, preventing duplicate or stale file handles.

    Parameters
    ----------
    handler_type:
        The handler class to remove (e.g., ``logging.FileHandler``).
    """
    to_remove = [h for h in _SHARED_HANDLERS if isinstance(h, handler_type)]
    for h in to_remove:
        _SHARED_HANDLERS.remove(h)
    for logger in _MANAGED_LOGGERS.values():
        for h in [x for x in logger.handlers if isinstance(x, handler_type)]:
            logger.removeHandler(h)


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

    for handler in _SHARED_HANDLERS:
        if handler not in logger.handlers:
            logger.addHandler(handler)

    _MANAGED_LOGGERS[name] = logger
    return logger
