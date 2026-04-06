import logging
import pytest

from tts_utilities.logger import create_logger


@pytest.mark.ai
def test_stream_logger_outputs_to_stdout(capsys):
    logger = create_logger(
        "test_logger_stdout", stream_level=logging.INFO, propagate=False, console_width=120
    )

    logger.info("Hello, stdout!")

    captured = capsys.readouterr()
    assert "Hello, stdout!" in captured.out


@pytest.mark.ai
def test_stream_logger_skipped_when_propagating(capsys):
    """
    If propagation_double_msg_checking is True, child logger should not
    print to stdout, since only the parent should.
    """
    parent_logger = logging.getLogger("parent_logger")
    parent_logger.addHandler(logging.StreamHandler())
    parent_logger.setLevel(logging.INFO)

    child_logger = create_logger(
        "parent_logger.child",
        stream_level=logging.INFO,
        propagate=True,
        propagation_double_msg_checking=True, 
        console_width=120
    )

    child_logger.info("Should only show once")

    captured = capsys.readouterr()

    # because parent's StreamHandler shouldn't be captured here
    assert "Should only show once" not in captured.out


@pytest.mark.ai
def test_logger_writes_to_file(tmp_path):
    log_file = tmp_path / "test_log.log"
    logger = create_logger("test_file_logger", log_path=log_file, propagate=False, console_width=120)

    logger.info("Writing to file")

    with open(log_file, "r") as f:
        contents = f.read()

    assert "Writing to file" in contents


@pytest.mark.ai
def test_logger_respects_log_level(capsys):
    logger = create_logger(
        "test_log_level", stream_level=logging.WARNING, propagate=False, console_width=120
    )

    logger.info("This should not appear")
    logger.warning("This should appear")

    captured = capsys.readouterr()
    assert "This should not appear" not in captured.out
    assert "This should appear" in captured.out


@pytest.mark.ai
def test_logger_applies_formatter(capsys):
    custom_format = logging.Formatter("%(levelname)s:%(name)s:%(message)s")
    logger = create_logger("test_formatter", formatter=custom_format, propagate=False, console_width=120)

    logger.warning("Formatted message")

    captured = capsys.readouterr()
    assert "WARNING:test_formatter:Formatted message" in captured.out
