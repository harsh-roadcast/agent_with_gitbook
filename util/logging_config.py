import logging
import sys
from pathlib import Path

def get_logger(name):
    """
    Return a logger configured with standard settings for the application.

    Args:
        name: The name of the logger, typically __name__ from the calling module

    Returns:
        A configured logger instance
    """
    # Create logs directory if it doesn't exist
    logs_dir = Path(__file__).parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)

    # Configure the logger
    logger = logging.getLogger(name)

    # Only configure handlers if they haven't been set up already
    if not logger.handlers:
        logger.setLevel(logging.INFO)

        # Console handler with color formatting
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)

        # File handler for detailed logs
        file_handler = logging.FileHandler(logs_dir / "app.log")
        file_handler.setLevel(logging.DEBUG)

        # Create a custom formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)

        # Add handlers to logger
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

    return logger
