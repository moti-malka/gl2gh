"""Logging utilities with structured logging and masking"""

import logging
import sys
from pythonjsonlogger import jsonlogger
from app.utils.security import mask_sensitive_data


class MaskingFormatter(jsonlogger.JsonFormatter):
    """JSON formatter that masks sensitive data"""
    
    def format(self, record):
        # Mask the message
        if hasattr(record, 'msg'):
            record.msg = mask_sensitive_data(str(record.msg))
        
        # Format to JSON
        return super().format(record)


def setup_logging(level=logging.INFO):
    """Set up structured logging with masking"""
    
    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    
    # Create formatter - simple format without rename to avoid KeyError
    formatter = MaskingFormatter(
        '%(asctime)s %(levelname)s %(name)s %(message)s'
    )
    handler.setFormatter(formatter)
    
    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(handler)
    
    # Reduce noise from libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    return root_logger


def get_logger(name: str):
    """Get a logger instance"""
    return logging.getLogger(name)
