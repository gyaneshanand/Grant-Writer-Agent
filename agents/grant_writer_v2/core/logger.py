import logging


def get_logger(name: str) -> logging.Logger:
    """Return a logger using the repo's existing basicConfig format."""
    return logging.getLogger(f"grant_writer_v2.{name}")
