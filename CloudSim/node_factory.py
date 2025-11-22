"""
NodeFactory - Factory class for creating and managing multiple storage nodes
Enables dynamic creation of nodes from configuration files
"""

import json
import os
from typing import Dict, List, Optional
from storage_virtual_node import StorageVirtualNode


class NodeFactory:
    """
    Factory class for creating and managing multiple storage nodes
    Supports creating nodes from configuration and managing their lifecycle
    """
    
    def __init__(self):
        """Initialize the NodeFactory"""
        self.nodes: Dict[str, StorageVirtualNode] = {}
        self.node_configs: Dict[str, Dict] = {}
        print("[NodeFactory] Initialized")
    
    def create_node(
        self,
        node_id: str,
        cpu_capacity: int,
        memory_capacity: int,
        storage_capacity: int,
        bandwidth: int,
        host: str = "localhost",
        port: Optional[int] = None
    ) -> Optional[StorageVirtualNode]:
        """
        Create a single storage node
        
        Args:
            node_id: Unique identifier for the node
            cpu_capacity: CPU capacity in vCPUs
            memory_capacity: Memory capacity in GB
            storage_capacity: Storage capacity in GB
            bandwidth: Network bandwidth in Mbps
            host: Host address (default: localhost)
            port: Port number (if None, will be auto-assigned)
            
        Returns:
            Created StorageVirtualNode instance, or None if creation failed
        """
        # Check if node already exists
        if node_id in self.nodes:
            print(f"[NodeFactory] Node {node_id} already exists")
            return self.nodes[node_id]
        
        # Auto-assign port if not provided
        if port is None:
            port = self._get_next_available_port()
            print(f"[NodeFactory] Auto-assigned port {port} to node {node_id}")
        
        # Check if port is already in use
        if self._is_port_in_use(port):
            print(f"[NodeFactory] Port {port} is already in use")
            return None
        
        try:
            # Create the node
            node = StorageVirtualNode(
                node_id=node_id,
                cpu_capacity=cpu_capacity,
                memory_capacity=memory_capacity,
                storage_capacity=storage_capacity,
                bandwidth=bandwidth,
                host=host,
                port=port
            )
            
            # Store node and configuration
            self.nodes[node_id] = node
            self.node_configs[node_id] = {
                "node_id": node_id,
                "cpu_capacity": cpu_capacity,
                "memory_capacity": memory_capacity,
                "storage_capacity": storage_capacity,
                "bandwidth": bandwidth,
                "host": host,
                "port": port
            }
            
            print(f"[NodeFactory] Created node {node_id} on {host}:{port}")
            return node
            
        except Exception as e:
            print(f"[NodeFactory] Error creating node {node_id}: {e}")
            return None
    
    def _get_next_available_port(self, start_port: int = 5000) -> int:
        """
        Get the next available port number
        
        Args:
            start_port: Starting port number to check from
            
        Returns:
            Next available port number
        """
        port = start_port
        max_port = start_port + 1000  # Check up to 1000 ports
        
        while port < max_port:
            if not self._is_port_in_use(port):
                return port
            port += 1
        
        # If no port found, raise error
        raise RuntimeError(f"No available ports in range {start_port}-{max_port}")
    
    def _is_port_in_use(self, port: int) -> bool:
        """
        Check if a port is already in use by existing nodes
        
        Args:
            port: Port number to check
            
        Returns:
            True if port is in use, False otherwise
        """
        for node_id, config in self.node_configs.items():
            if config.get("port") == port:
                return True
        return False
    
    def get_node(self, node_id: str) -> Optional[StorageVirtualNode]:
        """
        Get a node by its ID
        
        Args:
            node_id: ID of the node to retrieve
            
        Returns:
            StorageVirtualNode instance, or None if not found
        """
        return self.nodes.get(node_id)
    
    def get_all_nodes(self) -> List[StorageVirtualNode]:
        """
        Get all created nodes
        
        Returns:
            List of all StorageVirtualNode instances
        """
        return list(self.nodes.values())
    
    def get_node_count(self) -> int:
        """
        Get the total number of created nodes
        
        Returns:
            Number of nodes
        """
        return len(self.nodes)
    
    def remove_node(self, node_id: str) -> bool:
        """
        Remove a node from the factory
        
        Args:
            node_id: ID of the node to remove
            
        Returns:
            True if node was removed, False if not found
        """
        if node_id not in self.nodes:
            print(f"[NodeFactory] Node {node_id} not found")
            return False
        
        node = self.nodes[node_id]
        
        # Stop the node if it's running
        if node.is_alive() or node.running:
            node.stop(graceful=True, timeout=5.0)
            node.join(timeout=3.0)
        
        # Remove from dictionaries
        del self.nodes[node_id]
        del self.node_configs[node_id]
        
        print(f"[NodeFactory] Removed node {node_id}")
        return True
    
    def start_all_nodes(self):
        """Start all nodes"""
        print(f"[NodeFactory] Starting {len(self.nodes)} nodes...")
        for node_id, node in self.nodes.items():
            try:
                node.start()
                print(f"[NodeFactory] Started node {node_id}")
            except Exception as e:
                print(f"[NodeFactory] Error starting node {node_id}: {e}")
    
    def stop_all_nodes(self, graceful: bool = True, timeout: float = 10.0):
        """
        Stop all nodes
        
        Args:
            graceful: If True, wait for operations to complete
            timeout: Maximum time to wait for graceful shutdown
        """
        print(f"[NodeFactory] Stopping {len(self.nodes)} nodes...")
        for node_id, node in self.nodes.items():
            try:
                node.stop(graceful=graceful, timeout=timeout)
                node.join(timeout=3.0)
                print(f"[NodeFactory] Stopped node {node_id}")
            except Exception as e:
                print(f"[NodeFactory] Error stopping node {node_id}: {e}")
    
    def get_factory_stats(self) -> Dict:
        """
        Get statistics about the factory
        
        Returns:
            Dictionary with factory statistics
        """
        running_count = sum(1 for node in self.nodes.values() if node.is_alive() or node.running)
        
        return {
            "total_nodes": len(self.nodes),
            "running_nodes": running_count,
            "stopped_nodes": len(self.nodes) - running_count,
            "node_ids": list(self.nodes.keys())
        }
    
    def load_config_from_file(self, config_path: str) -> Optional[Dict]:
        """
        Load node configuration from a JSON file
        
        Args:
            config_path: Path to the JSON configuration file
            
        Returns:
            Parsed configuration dictionary, or None if error
        """
        if not os.path.exists(config_path):
            print(f"[NodeFactory] Configuration file not found: {config_path}")
            return None
        
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            print(f"[NodeFactory] Loaded configuration from {config_path}")
            return config
            
        except json.JSONDecodeError as e:
            print(f"[NodeFactory] Invalid JSON in configuration file: {e}")
            return None
        except Exception as e:
            print(f"[NodeFactory] Error loading configuration file: {e}")
            return None
    
    def validate_node_config(self, node_config: Dict) -> bool:
        """
        Validate a node configuration dictionary
        
        Args:
            node_config: Node configuration dictionary
            
        Returns:
            True if configuration is valid, False otherwise
        """
        required_fields = ["id", "cpu_capacity", "memory_gb", "storage_gb", "bandwidth_mbps"]
        
        for field in required_fields:
            if field not in node_config:
                print(f"[NodeFactory] Missing required field: {field}")
                return False
        
        # Validate data types and values
        if not isinstance(node_config["id"], str):
            print(f"[NodeFactory] Node ID must be a string")
            return False
        
        if not isinstance(node_config["cpu_capacity"], int) or node_config["cpu_capacity"] <= 0:
            print(f"[NodeFactory] cpu_capacity must be a positive integer")
            return False
        
        if not isinstance(node_config["memory_gb"], int) or node_config["memory_gb"] <= 0:
            print(f"[NodeFactory] memory_gb must be a positive integer")
            return False
        
        if not isinstance(node_config["storage_gb"], int) or node_config["storage_gb"] <= 0:
            print(f"[NodeFactory] storage_gb must be a positive integer")
            return False
        
        if not isinstance(node_config["bandwidth_mbps"], int) or node_config["bandwidth_mbps"] <= 0:
            print(f"[NodeFactory] bandwidth_mbps must be a positive integer")
            return False
        
        return True
    
    def create_nodes_from_config(self, config_path: str) -> List[StorageVirtualNode]:
        """
        Create nodes from a JSON configuration file
        
        Args:
            config_path: Path to the JSON configuration file
            
        Returns:
            List of created StorageVirtualNode instances
        """
        # Load configuration
        config = self.load_config_from_file(config_path)
        if config is None:
            return []
        
        # Get nodes array
        if "nodes" not in config:
            print(f"[NodeFactory] Configuration file missing 'nodes' array")
            return []
        
        nodes_list = config["nodes"]
        if not isinstance(nodes_list, list):
            print(f"[NodeFactory] 'nodes' must be an array")
            return []
        
        created_nodes = []
        
        # Create each node
        for node_config in nodes_list:
            if not isinstance(node_config, dict):
                print(f"[NodeFactory] Skipping invalid node configuration (not a dict)")
                continue
            
            # Validate configuration
            if not self.validate_node_config(node_config):
                print(f"[NodeFactory] Skipping invalid node: {node_config.get('id', 'unknown')}")
                continue
            
            # Extract configuration values
            node_id = node_config["id"]
            cpu_capacity = node_config["cpu_capacity"]
            memory_gb = node_config["memory_gb"]
            storage_gb = node_config["storage_gb"]
            bandwidth_mbps = node_config["bandwidth_mbps"]
            host = node_config.get("host", "localhost")
            port = node_config.get("port", None)  # None = auto-assign
            
            # Create the node
            node = self.create_node(
                node_id=node_id,
                cpu_capacity=cpu_capacity,
                memory_capacity=memory_gb,
                storage_capacity=storage_gb,
                bandwidth=bandwidth_mbps,
                host=host,
                port=port
            )
            
            if node:
                created_nodes.append(node)
        
        print(f"[NodeFactory] Created {len(created_nodes)} nodes from configuration")
        return created_nodes
    
    def __repr__(self):
        """String representation of NodeFactory"""
        return f"NodeFactory(nodes={len(self.nodes)})"

