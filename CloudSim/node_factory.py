"""
NodeFactory - Factory class for creating and managing multiple storage nodes
Enables dynamic creation of nodes from configuration files
"""

import json
import os
import socket
from typing import Dict, List, Optional
from storage_virtual_node import StorageVirtualNode


class NodeFactory:
    """
    Factory class for creating and managing multiple storage nodes
    Supports creating nodes from configuration and managing their lifecycle
    """
    
    def __init__(self, start_port: int = 5000, port_range_size: int = 1000):
        """
        Initialize the NodeFactory
        
        Args:
            start_port: Starting port number for auto-assignment (default: 5000)
            port_range_size: Number of ports to check for availability (default: 1000)
        """
        self.nodes: Dict[str, StorageVirtualNode] = {}
        self.node_configs: Dict[str, Dict] = {}
        self.start_port = start_port
        self.port_range_size = port_range_size
        self.reserved_ports: set = set()  # Ports reserved but not yet used
        print(f"[NodeFactory] Initialized (port range: {start_port}-{start_port + port_range_size - 1})")
    
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
        port_was_auto_assigned = False
        if port is None:
            try:
                port = self._get_next_available_port(host=host)
                port_was_auto_assigned = True
                print(f"[NodeFactory] Auto-assigned port {port} to node {node_id} on {host}")
            except RuntimeError as e:
                print(f"[NodeFactory] {e}")
                return None
        
        # Check if port is already in use (double-check before creating)
        if self._is_port_in_use(port, host):
            print(f"[NodeFactory] Port {port} on {host} is already in use")
            if port_was_auto_assigned:
                self._release_reserved_port(port)
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
            
            # Release reserved port (node creation succeeded)
            if port_was_auto_assigned:
                self._release_reserved_port(port)
            
            print(f"[NodeFactory] Created node {node_id} on {host}:{port}")
            return node
            
        except Exception as e:
            print(f"[NodeFactory] Error creating node {node_id}: {e}")
            # Release reserved port if node creation failed
            if port_was_auto_assigned:
                self._release_reserved_port(port)
            return None
    
    def _get_next_available_port(self, host: str = "localhost") -> int:
        """
        Get the next available port number by checking both tracked nodes and system ports
        
        Args:
            host: Host address to check ports on
            
        Returns:
            Next available port number
        """
        port = self.start_port
        max_port = self.start_port + self.port_range_size
        
        while port < max_port:
            # Check if port is reserved
            if port in self.reserved_ports:
                port += 1
                continue
            
            # Check if port is in use
            if not self._is_port_in_use(port, host):
                # Reserve the port temporarily
                self.reserved_ports.add(port)
                return port
            port += 1
        
        # If no port found, raise error
        raise RuntimeError(f"No available ports in range {self.start_port}-{max_port}")
    
    def _release_reserved_port(self, port: int):
        """
        Release a reserved port (called after node creation succeeds or fails)
        
        Args:
            port: Port number to release
        """
        self.reserved_ports.discard(port)
    
    def _is_port_in_use(self, port: int, host: str = "localhost") -> bool:
        """
        Check if a port is already in use (by tracked nodes, reserved, or system)
        
        Args:
            port: Port number to check
            host: Host address to check
            
        Returns:
            True if port is in use, False otherwise
        """
        # Check if port is reserved
        if port in self.reserved_ports:
            return True
        
        # Check if port is used by our tracked nodes
        for node_id, config in self.node_configs.items():
            if config.get("port") == port and config.get("host") == host:
                return True
        
        # Then check if port is actually in use on the system
        return self._check_system_port(port, host)
    
    def _check_system_port(self, port: int, host: str = "localhost") -> bool:
        """
        Check if a port is actually in use on the system by attempting to bind to it
        
        Args:
            port: Port number to check
            host: Host address to check
            
        Returns:
            True if port is in use, False if available
        """
        try:
            # Create a test socket
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Try to bind to the port
            try:
                test_socket.bind((host, port))
                test_socket.close()
                return False  # Port is available
            except OSError:
                # Port is in use
                test_socket.close()
                return True
        except Exception as e:
            # On error, assume port might be in use (safer)
            print(f"[NodeFactory] Error checking port {port}: {e}")
            return True
    
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
    
    def get_port_info(self) -> Dict:
        """
        Get information about port usage and availability
        
        Returns:
            Dictionary with port information
        """
        used_ports = [config.get("port") for config in self.node_configs.values() if config.get("port")]
        
        return {
            "port_range": f"{self.start_port}-{self.start_port + self.port_range_size - 1}",
            "used_ports": sorted(used_ports),
            "reserved_ports": sorted(list(self.reserved_ports)),
            "total_used": len(used_ports),
            "total_reserved": len(self.reserved_ports)
        }
    
    def create_nodes_batch(
        self,
        node_configs: List[Dict],
        start_port: Optional[int] = None
    ) -> List[StorageVirtualNode]:
        """
        Create multiple nodes from a list of configuration dictionaries
        
        Args:
            node_configs: List of node configuration dictionaries
            start_port: Optional starting port for auto-assignment (uses factory default if None)
            
        Returns:
            List of successfully created StorageVirtualNode instances
        """
        created_nodes = []
        failed_nodes = []
        
        print(f"[NodeFactory] Creating {len(node_configs)} nodes in batch...")
        
        for node_config in node_configs:
            if not isinstance(node_config, dict):
                print(f"[NodeFactory] Skipping invalid node config (not a dict)")
                failed_nodes.append(node_config)
                continue
            
            # Validate configuration
            if not self.validate_node_config(node_config):
                node_id = node_config.get("id", "unknown")
                print(f"[NodeFactory] Skipping invalid node: {node_id}")
                failed_nodes.append(node_config)
                continue
            
            # Extract configuration values
            node_id = node_config["id"]
            cpu_capacity = node_config["cpu_capacity"]
            memory_gb = node_config["memory_gb"]
            storage_gb = node_config["storage_gb"]
            bandwidth_mbps = node_config["bandwidth_mbps"]
            host = node_config.get("host", "localhost")
            port = node_config.get("port", None)
            
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
            else:
                failed_nodes.append(node_config)
        
        print(f"[NodeFactory] Batch creation complete: {len(created_nodes)} succeeded, {len(failed_nodes)} failed")
        return created_nodes
    
    def remove_nodes_batch(self, node_ids: List[str], graceful: bool = True, timeout: float = 5.0) -> Dict[str, bool]:
        """
        Remove multiple nodes at once
        
        Args:
            node_ids: List of node IDs to remove
            graceful: If True, wait for operations to complete
            timeout: Maximum time to wait for graceful shutdown
            
        Returns:
            Dictionary mapping node_id to removal success status
        """
        results = {}
        
        print(f"[NodeFactory] Removing {len(node_ids)} nodes in batch...")
        
        for node_id in node_ids:
            results[node_id] = self.remove_node(node_id)
        
        success_count = sum(1 for success in results.values() if success)
        print(f"[NodeFactory] Batch removal complete: {success_count}/{len(node_ids)} succeeded")
        
        return results
    
    def get_nodes_by_status(self, running: bool = True) -> List[StorageVirtualNode]:
        """
        Get nodes filtered by running status
        
        Args:
            running: If True, return running nodes; if False, return stopped nodes
            
        Returns:
            List of nodes matching the status
        """
        filtered = []
        for node in self.nodes.values():
            is_running = node.is_alive() or node.running
            if (running and is_running) or (not running and not is_running):
                filtered.append(node)
        return filtered
    
    def get_nodes_by_host(self, host: str) -> List[StorageVirtualNode]:
        """
        Get all nodes running on a specific host
        
        Args:
            host: Host address to filter by
            
        Returns:
            List of nodes on the specified host
        """
        filtered = []
        for node_id, config in self.node_configs.items():
            if config.get("host") == host:
                filtered.append(self.nodes[node_id])
        return filtered
    
    def get_aggregated_resources(self) -> Dict:
        """
        Get aggregated resource statistics across all nodes
        
        Returns:
            Dictionary with total capacity, used resources, and averages
        """
        if not self.nodes:
            return {
                "total_nodes": 0,
                "total_cpu": 0,
                "total_memory_gb": 0,
                "total_storage_gb": 0,
                "total_bandwidth_mbps": 0,
                "used_storage_gb": 0,
                "available_storage_gb": 0,
                "storage_utilization_percent": 0.0,
                "average_cpu": 0,
                "average_memory_gb": 0,
                "average_storage_gb": 0,
                "average_bandwidth_mbps": 0
            }
        
        total_cpu = 0
        total_memory = 0
        total_storage = 0
        total_bandwidth = 0
        used_storage = 0
        
        for node_id, config in self.node_configs.items():
            total_cpu += config.get("cpu_capacity", 0)
            total_memory += config.get("memory_capacity", 0)
            total_storage += config.get("storage_capacity", 0)
            total_bandwidth += config.get("bandwidth", 0)
            
            # Get actual used storage from node
            node = self.nodes[node_id]
            try:
                storage_util = node.get_storage_utilization()
                used_storage += storage_util.get("used_bytes", 0) / (1024 ** 3)  # Convert to GB
            except Exception:
                pass
        
        node_count = len(self.nodes)
        available_storage = total_storage - used_storage
        storage_utilization = (used_storage / total_storage * 100) if total_storage > 0 else 0.0
        
        return {
            "total_nodes": node_count,
            "total_cpu": total_cpu,
            "total_memory_gb": total_memory,
            "total_storage_gb": total_storage,
            "total_bandwidth_mbps": total_bandwidth,
            "used_storage_gb": round(used_storage, 2),
            "available_storage_gb": round(available_storage, 2),
            "storage_utilization_percent": round(storage_utilization, 2),
            "average_cpu": round(total_cpu / node_count, 2) if node_count > 0 else 0,
            "average_memory_gb": round(total_memory / node_count, 2) if node_count > 0 else 0,
            "average_storage_gb": round(total_storage / node_count, 2) if node_count > 0 else 0,
            "average_bandwidth_mbps": round(total_bandwidth / node_count, 2) if node_count > 0 else 0
        }
    
    def check_all_nodes_health(self) -> Dict[str, Dict]:
        """
        Check health status of all nodes
        
        Returns:
            Dictionary mapping node_id to health status information
        """
        health_status = {}
        
        for node_id, node in self.nodes.items():
            try:
                is_running = node.is_alive() or node.running
                storage_util = node.get_storage_utilization() if is_running else {}
                performance = node.get_performance_metrics() if is_running else {}
                
                health_status[node_id] = {
                    "status": "running" if is_running else "stopped",
                    "is_alive": is_running,
                    "storage_used_bytes": storage_util.get("used_bytes", 0),
                    "storage_capacity_bytes": storage_util.get("capacity_bytes", 0),
                    "active_transfers": len(node.active_transfers) if hasattr(node, "active_transfers") else 0,
                    "total_transfers": performance.get("total_transfers", 0) if performance else 0,
                    "host": self.node_configs[node_id].get("host", "unknown"),
                    "port": self.node_configs[node_id].get("port", "unknown")
                }
            except Exception as e:
                health_status[node_id] = {
                    "status": "error",
                    "error": str(e)
                }
        
        return health_status
    
    def restart_all_nodes(self, graceful: bool = True, timeout: float = 5.0):
        """
        Restart all nodes (stop then start)
        
        Args:
            graceful: If True, wait for operations to complete before stopping
            timeout: Maximum time to wait for graceful shutdown
        """
        print(f"[NodeFactory] Restarting {len(self.nodes)} nodes...")
        self.stop_all_nodes(graceful=graceful, timeout=timeout)
        self.start_all_nodes()
        print(f"[NodeFactory] Restart complete")
    
    def get_nodes_summary(self) -> Dict:
        """
        Get a comprehensive summary of all nodes
        
        Returns:
            Dictionary with node summaries, resource totals, and health status
        """
        running_nodes = self.get_nodes_by_status(running=True)
        stopped_nodes = self.get_nodes_by_status(running=False)
        resources = self.get_aggregated_resources()
        health = self.check_all_nodes_health()
        
        return {
            "factory_stats": self.get_factory_stats(),
            "resource_summary": resources,
            "health_summary": {
                "healthy_nodes": sum(1 for h in health.values() if h.get("status") == "running"),
                "stopped_nodes": sum(1 for h in health.values() if h.get("status") == "stopped"),
                "error_nodes": sum(1 for h in health.values() if h.get("status") == "error")
            },
            "node_details": health,
            "port_info": self.get_port_info()
        }
    
    def __repr__(self):
        """String representation of NodeFactory"""
        return f"NodeFactory(nodes={len(self.nodes)})"

