"""
CapacityEvaluator - Evaluates capacity and resource utilization across the storage network
Provides insights into current usage, available capacity, and capacity planning
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from node_factory import NodeFactory
from storage_virtual_node import StorageVirtualNode


class CapacityEvaluator:
    """
    Evaluates capacity and resource utilization across multiple storage nodes
    Provides capacity planning and evaluation capabilities
    """
    
    def __init__(self, node_factory: Optional[NodeFactory] = None):
        """
        Initialize the CapacityEvaluator
        
        Args:
            node_factory: Optional NodeFactory instance to evaluate
        """
        self.node_factory = node_factory
        self.capacity_history: List[Dict] = []  # Historical capacity snapshots
        print("[CapacityEvaluator] Initialized")
    
    def set_node_factory(self, node_factory: NodeFactory):
        """
        Set or update the NodeFactory to evaluate
        
        Args:
            node_factory: NodeFactory instance
        """
        self.node_factory = node_factory
        print(f"[CapacityEvaluator] NodeFactory set ({node_factory.get_node_count()} nodes)")
    
    def evaluate_total_capacity(self) -> Dict:
        """
        Calculate total capacity across all nodes in the factory
        
        Returns:
            Dictionary with total capacity metrics
        """
        if not self.node_factory:
            return {
                "error": "No NodeFactory set. Call set_node_factory() first."
            }
        
        # Get aggregated resources from factory
        resources = self.node_factory.get_aggregated_resources()
        
        # Calculate additional metrics
        total_capacity = {
            "total_nodes": resources["total_nodes"],
            "cpu_capacity": {
                "total_vcpus": resources["total_cpu"],
                "average_per_node": resources["average_cpu"]
            },
            "memory_capacity": {
                "total_gb": resources["total_memory_gb"],
                "average_per_node": resources["average_memory_gb"]
            },
            "storage_capacity": {
                "total_gb": resources["total_storage_gb"],
                "used_gb": resources["used_storage_gb"],
                "available_gb": resources["available_storage_gb"],
                "utilization_percent": resources["storage_utilization_percent"]
            },
            "bandwidth_capacity": {
                "total_mbps": resources["total_bandwidth_mbps"],
                "average_per_node": resources["average_bandwidth_mbps"]
            },
            "evaluation_timestamp": datetime.now().isoformat()
        }
        
        return total_capacity
    
    def evaluate_node_capacity(self, node_id: str) -> Optional[Dict]:
        """
        Evaluate capacity for a specific node
        
        Args:
            node_id: ID of the node to evaluate
            
        Returns:
            Dictionary with node capacity metrics, or None if node not found
        """
        if not self.node_factory:
            return None
        
        node = self.node_factory.get_node(node_id)
        if not node:
            return None
        
        # Get node configuration
        config = self.node_factory.node_configs.get(node_id, {})
        
        # Get current utilization
        storage_util = node.get_storage_utilization()
        network_util = node.get_network_utilization()
        performance = node.get_performance_metrics()
        
        # Storage capacity is stored in GB in config, but node uses bytes
        storage_capacity_gb = config.get("storage_capacity", 0)
        storage_total_bytes = storage_util.get("total_bytes", 0)
        storage_used_bytes = storage_util.get("used_bytes", 0)
        storage_available_bytes = storage_total_bytes - storage_used_bytes
        
        # Bandwidth is stored in Mbps in config, but node uses bits per second
        bandwidth_mbps = config.get("bandwidth", 0)
        bandwidth_current_bps = network_util.get("current_utilization_bps", 0)
        
        node_capacity = {
            "node_id": node_id,
            "host": config.get("host", "unknown"),
            "port": config.get("port", "unknown"),
            "cpu": {
                "capacity_vcpus": config.get("cpu_capacity", 0),
                "utilization_percent": 0.0  # CPU utilization not tracked yet
            },
            "memory": {
                "capacity_gb": config.get("memory_capacity", 0),
                "utilization_percent": 0.0  # Memory utilization not tracked yet
            },
            "storage": {
                "capacity_gb": storage_capacity_gb,
                "used_gb": round(storage_used_bytes / (1024 ** 3), 2),
                "available_gb": round(storage_available_bytes / (1024 ** 3), 2),
                "utilization_percent": round(storage_util.get("utilization_percent", 0.0), 2),
                "files_stored": storage_util.get("files_stored", 0),
                "chunk_count": storage_util.get("chunk_count", 0)
            },
            "bandwidth": {
                "capacity_mbps": bandwidth_mbps,
                "current_utilization_mbps": round(bandwidth_current_bps / 1000000, 2),
                "utilization_percent": round(network_util.get("utilization_percent", 0.0), 2),
                "connections": network_util.get("connections", [])
            },
            "performance": {
                "total_transfers": performance.get("total_transfers", 0),
                "total_data_transferred_gb": round(performance.get("total_data_transferred", 0) / (1024 ** 3), 2),
                "failed_transfers": performance.get("failed_transfers", 0)
            },
            "status": "running" if (node.is_alive() or node.running) else "stopped",
            "evaluation_timestamp": datetime.now().isoformat()
        }
        
        return node_capacity
    
    def evaluate_all_nodes_capacity(self) -> Dict[str, Dict]:
        """
        Evaluate capacity for all nodes
        
        Returns:
            Dictionary mapping node_id to capacity metrics
        """
        if not self.node_factory:
            return {}
        
        all_nodes_capacity = {}
        
        for node_id in self.node_factory.node_configs.keys():
            node_capacity = self.evaluate_node_capacity(node_id)
            if node_capacity:
                all_nodes_capacity[node_id] = node_capacity
        
        return all_nodes_capacity
    
    def get_capacity_summary(self) -> Dict:
        """
        Get a comprehensive capacity summary
        
        Returns:
            Dictionary with overall capacity summary
        """
        if not self.node_factory:
            return {
                "error": "No NodeFactory set. Call set_node_factory() first."
            }
        
        total_capacity = self.evaluate_total_capacity()
        all_nodes = self.evaluate_all_nodes_capacity()
        
        # Calculate additional statistics
        nodes_by_utilization = sorted(
            all_nodes.items(),
            key=lambda x: x[1].get("storage", {}).get("utilization_percent", 0),
            reverse=True
        )
        
        # Find nodes with highest/lowest utilization
        highest_utilization_node = nodes_by_utilization[0] if nodes_by_utilization else None
        lowest_utilization_node = nodes_by_utilization[-1] if nodes_by_utilization else None
        
        summary = {
            "overall_capacity": total_capacity,
            "node_count": len(all_nodes),
            "nodes_evaluated": list(all_nodes.keys()),
            "utilization_statistics": {
                "highest_utilization": {
                    "node_id": highest_utilization_node[0] if highest_utilization_node else None,
                    "utilization_percent": highest_utilization_node[1].get("storage", {}).get("utilization_percent", 0) if highest_utilization_node else 0
                },
                "lowest_utilization": {
                    "node_id": lowest_utilization_node[0] if lowest_utilization_node else None,
                    "utilization_percent": lowest_utilization_node[1].get("storage", {}).get("utilization_percent", 0) if lowest_utilization_node else 0
                },
                "average_utilization": total_capacity.get("storage_capacity", {}).get("utilization_percent", 0)
            },
            "evaluation_timestamp": datetime.now().isoformat()
        }
        
        return summary
    
    def take_capacity_snapshot(self) -> Dict:
        """
        Take a snapshot of current capacity state for historical tracking
        
        Returns:
            Dictionary with capacity snapshot
        """
        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "total_capacity": self.evaluate_total_capacity(),
            "nodes_capacity": self.evaluate_all_nodes_capacity()
        }
        
        self.capacity_history.append(snapshot)
        
        # Keep only last 100 snapshots to prevent memory bloat
        if len(self.capacity_history) > 100:
            self.capacity_history = self.capacity_history[-100:]
        
        return snapshot
    
    def get_capacity_history(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Get historical capacity snapshots
        
        Args:
            limit: Maximum number of snapshots to return (None = all)
            
        Returns:
            List of capacity snapshots
        """
        if limit:
            return self.capacity_history[-limit:]
        return self.capacity_history
    
    def clear_capacity_history(self):
        """Clear all historical capacity snapshots"""
        self.capacity_history.clear()
        print("[CapacityEvaluator] Capacity history cleared")
    
    def __repr__(self):
        """String representation of CapacityEvaluator"""
        node_count = self.node_factory.get_node_count() if self.node_factory else 0
        history_count = len(self.capacity_history)
        return f"CapacityEvaluator(nodes={node_count}, history_snapshots={history_count})"

