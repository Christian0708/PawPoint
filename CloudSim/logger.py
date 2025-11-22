"""
Logger - Centralized logging system for CloudSim
Configures Python logging with file and console handlers
"""

import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Optional
from config_loader import ConfigLoader


class CloudSimLogger:
    """
    Centralized logging system for CloudSim
    Configures logging with file and console handlers based on configuration
    """
    
    _configured = False
    _loggers: dict = {}
    
    @classmethod
    def setup_logging(cls, config: Optional[ConfigLoader] = None, config_path: str = "config.yaml"):
        """
        Setup logging system based on configuration
        
        Args:
            config: Optional ConfigLoader instance
            config_path: Path to configuration file if config not provided
        """
        if cls._configured:
            return
        
        # Load config if not provided
        if config is None:
            config = ConfigLoader(config_path)
            config.load()
        
        # Get logging configuration
        logging_enabled = config.get("logging.enabled", True)
        if not logging_enabled:
            return
        
        log_level_str = config.get("logging.level", "INFO")
        log_level = getattr(logging, log_level_str.upper(), logging.INFO)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Console handler
        console_config = config.get_section("logging.console")
        if console_config.get("enabled", True):
            console_handler = logging.StreamHandler()
            console_handler.setLevel(log_level)
            console_format = console_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            console_formatter = logging.Formatter(console_format)
            console_handler.setFormatter(console_formatter)
            root_logger.addHandler(console_handler)
        
        # File handler
        file_config = config.get_section("logging.file")
        if file_config.get("enabled", True):
            log_dir = file_config.get("directory", "logs")
            os.makedirs(log_dir, exist_ok=True)
            
            # Generate filename with timestamp if needed
            filename_template = file_config.get("filename", "cloudsim_{timestamp}.log")
            if "{timestamp}" in filename_template:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = filename_template.replace("{timestamp}", timestamp)
            else:
                filename = filename_template
            
            log_file = os.path.join(log_dir, filename)
            
            # Create rotating file handler
            max_bytes = file_config.get("max_bytes", 10485760)  # 10MB default
            backup_count = file_config.get("backup_count", 5)
            
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count
            )
            file_handler.setLevel(log_level)
            file_format = file_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s")
            file_formatter = logging.Formatter(file_format)
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)
        
        cls._configured = True
        logger = logging.getLogger("CloudSim")
        logger.info("Logging system initialized")
    
    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """
        Get a logger instance for a specific module/component
        
        Args:
            name: Logger name (typically module name)
            
        Returns:
            Logger instance
        """
        # Setup logging if not already configured
        if not cls._configured:
            cls.setup_logging()
        
        # Cache loggers
        if name not in cls._loggers:
            logger = logging.getLogger(name)
            cls._loggers[name] = logger
        
        return cls._loggers[name]
    
    @classmethod
    def set_level(cls, level: str):
        """
        Set logging level for all loggers
        
        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        log_level = getattr(logging, level.upper(), logging.INFO)
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        # Update all handlers
        for handler in root_logger.handlers:
            handler.setLevel(log_level)
    
    @classmethod
    def disable_logging(cls):
        """Disable all logging"""
        logging.disable(logging.CRITICAL)
    
    @classmethod
    def enable_logging(cls):
        """Enable logging"""
        logging.disable(logging.NOTSET)


# Convenience function for getting loggers
def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module/component
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    return CloudSimLogger.get_logger(name)


# Setup logging on import if config exists
def _auto_setup():
    """Auto-setup logging if config file exists"""
    if os.path.exists("config.yaml"):
        try:
            CloudSimLogger.setup_logging()
        except Exception:
            pass  # Silently fail if config can't be loaded


# Auto-setup on import (optional, can be disabled)
# _auto_setup()

