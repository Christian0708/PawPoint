"""
ConfigLoader - Loads and validates system-wide configuration from YAML files
Provides configuration management for the distributed storage system
"""

import yaml
import os
from typing import Dict, Optional, Any
from pathlib import Path


class ConfigLoader:
    """
    Loads and manages system-wide configuration from YAML files
    Provides validation and default values
    """
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize ConfigLoader
        
        Args:
            config_path: Path to configuration YAML file
        """
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self.loaded = False
        
    def load(self) -> bool:
        """
        Load configuration from YAML file
        
        Returns:
            True if loaded successfully, False otherwise
        """
        if not os.path.exists(self.config_path):
            print(f"[ConfigLoader] Configuration file not found: {self.config_path}")
            print(f"[ConfigLoader] Using default configuration")
            self.config = self._get_default_config()
            self.loaded = True
            return True
        
        try:
            with open(self.config_path, 'r') as f:
                self.config = yaml.safe_load(f) or {}
            
            # Merge with defaults to ensure all keys exist
            defaults = self._get_default_config()
            self.config = self._merge_config(defaults, self.config)
            
            # Validate configuration
            if self._validate_config():
                self.loaded = True
                print(f"[ConfigLoader] Configuration loaded from {self.config_path}")
                return True
            else:
                print(f"[ConfigLoader] Configuration validation failed, using defaults")
                self.config = defaults
                self.loaded = True
                return False
                
        except yaml.YAMLError as e:
            print(f"[ConfigLoader] Error parsing YAML: {e}")
            self.config = self._get_default_config()
            self.loaded = True
            return False
        except Exception as e:
            print(f"[ConfigLoader] Error loading configuration: {e}")
            self.config = self._get_default_config()
            self.loaded = True
            return False
    
    def _merge_config(self, default: Dict, user: Dict) -> Dict:
        """
        Recursively merge user config into default config
        
        Args:
            default: Default configuration
            user: User configuration
            
        Returns:
            Merged configuration
        """
        result = default.copy()
        
        for key, value in user.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _validate_config(self) -> bool:
        """
        Validate configuration values
        
        Returns:
            True if valid, False otherwise
        """
        # Validate port ranges
        if "node_factory" in self.config:
            nf = self.config["node_factory"]
            if nf.get("start_port", 0) < 1024 or nf.get("start_port", 0) > 65535:
                print("[ConfigLoader] Invalid start_port (must be 1024-65535)")
                return False
            if nf.get("port_range_size", 0) <= 0:
                print("[ConfigLoader] Invalid port_range_size (must be > 0)")
                return False
        
        # Validate thresholds
        if "capacity" in self.config and "thresholds" in self.config["capacity"]:
            for threshold in self.config["capacity"]["thresholds"].get("global", []):
                percent = threshold.get("percent", 0)
                if percent < 0 or percent > 100:
                    print(f"[ConfigLoader] Invalid threshold percent: {percent}")
                    return False
        
        return True
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            "network": {
                "name": "CloudSim_Storage_Network",
                "discovery": {
                    "enabled": True,
                    "port": 9999,
                    "broadcast_interval_seconds": 30.0,
                    "node_timeout_seconds": 90.0
                }
            },
            "node_factory": {
                "start_port": 5000,
                "port_range_size": 1000,
                "auto_start_nodes": False,
                "graceful_shutdown_timeout": 5.0
            },
            "storage": {
                "base_directory": "storage",
                "chunk_size_mb": 1,
                "create_directories": True
            },
            "metrics": {
                "enabled": True,
                "collection_interval_seconds": 5.0,
                "max_history": 1000,
                "export_directory": "metrics",
                "auto_export": False,
                "export_format": "json",
                "export_interval_seconds": 300
            },
            "capacity": {
                "enabled": True,
                "snapshot_interval_seconds": 60.0,
                "history_limit": 100,
                "thresholds": {
                    "global": [
                        {"percent": 50.0, "level": "INFO", "description": "Storage utilization reached 50%"},
                        {"percent": 75.0, "level": "WARNING", "description": "Storage utilization reached 75%"},
                        {"percent": 90.0, "level": "CRITICAL", "description": "Storage utilization reached 90%"},
                        {"percent": 95.0, "level": "CRITICAL", "description": "Storage utilization reached 95%"}
                    ]
                }
            },
            "logging": {
                "enabled": True,
                "level": "INFO",
                "console": {
                    "enabled": True,
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                },
                "file": {
                    "enabled": True,
                    "directory": "logs",
                    "filename": "cloudsim_{timestamp}.log",
                    "max_bytes": 10485760,
                    "backup_count": 5,
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
                }
            },
            "performance": {
                "max_concurrent_transfers": 10,
                "transfer_timeout_seconds": 300,
                "connection_timeout_seconds": 5.0,
                "socket_timeout_seconds": 30.0
            },
            "throughput": {
                "window_seconds": 60,
                "sma_window_size": 10,
                "ema_alpha": 0.3
            },
            "latency": {
                "window_seconds": 300,
                "rtt_window_seconds": 300
            },
            "nodes": {
                # Nodes are created via CLI, no config file needed
                "auto_load": True
            }
        }
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-separated key path
        
        Args:
            key_path: Dot-separated path (e.g., "network.discovery.port")
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        if not self.loaded:
            self.load()
        
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def get_section(self, section: str) -> Dict:
        """
        Get entire configuration section
        
        Args:
            section: Section name (e.g., "network", "metrics")
            
        Returns:
            Configuration section dictionary
        """
        if not self.loaded:
            self.load()
        
        return self.config.get(section, {})
    
    def set(self, key_path: str, value: Any):
        """
        Set configuration value by dot-separated key path
        
        Args:
            key_path: Dot-separated path (e.g., "network.discovery.port")
            value: Value to set
        """
        if not self.loaded:
            self.load()
        
        keys = key_path.split('.')
        config = self.config
        
        # Navigate to the parent dict
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        # Set the value
        config[keys[-1]] = value
    
    def save(self, output_path: Optional[str] = None) -> bool:
        """
        Save current configuration to YAML file
        
        Args:
            output_path: Optional output path (default: original config_path)
            
        Returns:
            True if saved successfully, False otherwise
        """
        if not self.loaded:
            self.load()
        
        path = output_path or self.config_path
        
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
            
            with open(path, 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)
            
            print(f"[ConfigLoader] Configuration saved to {path}")
            return True
            
        except Exception as e:
            print(f"[ConfigLoader] Error saving configuration: {e}")
            return False
    
    def reload(self) -> bool:
        """
        Reload configuration from file
        
        Returns:
            True if reloaded successfully, False otherwise
        """
        self.loaded = False
        return self.load()
    
    def __repr__(self):
        """String representation of ConfigLoader"""
        status = "loaded" if self.loaded else "not loaded"
        return f"ConfigLoader(path={self.config_path}, status={status})"

