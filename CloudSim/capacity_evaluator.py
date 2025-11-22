"""
CapacityEvaluator - Evaluates capacity and resource utilization across the storage network
Provides insights into current usage, available capacity, and capacity planning
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import time
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
    
    def calculate_storage_growth_rate(self, node_id: Optional[str] = None, hours: int = 24) -> Optional[Dict]:
        """
        Calculate storage growth rate from historical data
        
        Args:
            node_id: Specific node ID, or None for overall network
            hours: Number of hours of history to analyze (default: 24)
            
        Returns:
            Dictionary with growth rate metrics, or None if insufficient data
        """
        if len(self.capacity_history) < 2:
            return None
        
        # Filter history by time window
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_history = [
            snap for snap in self.capacity_history
            if datetime.fromisoformat(snap["timestamp"]) >= cutoff_time
        ]
        
        if len(recent_history) < 2:
            return None
        
        # Extract storage usage over time
        data_points = []
        for snapshot in recent_history:
            timestamp = datetime.fromisoformat(snapshot["timestamp"])
            timestamp_seconds = timestamp.timestamp()
            
            if node_id:
                # Node-specific data
                node_data = snapshot.get("nodes_capacity", {}).get(node_id, {})
                storage_data = node_data.get("storage", {})
                used_gb = storage_data.get("used_gb", 0)
            else:
                # Overall network data
                total_capacity = snapshot.get("total_capacity", {})
                storage_data = total_capacity.get("storage_capacity", {})
                used_gb = storage_data.get("used_gb", 0)
            
            if used_gb is not None:
                data_points.append((timestamp_seconds, used_gb))
        
        if len(data_points) < 2:
            return None
        
        # Calculate linear growth rate (GB per hour)
        # Simple linear regression: y = mx + b
        n = len(data_points)
        sum_x = sum(x for x, y in data_points)
        sum_y = sum(y for x, y in data_points)
        sum_xy = sum(x * y for x, y in data_points)
        sum_x2 = sum(x * x for x, y in data_points)
        
        # Calculate slope (growth rate in GB per second)
        denominator = n * sum_x2 - sum_x * sum_x
        if denominator == 0:
            return None
        
        slope = (n * sum_xy - sum_x * sum_y) / denominator
        intercept = (sum_y - slope * sum_x) / n
        
        # Convert to GB per hour
        growth_rate_gb_per_hour = slope * 3600
        growth_rate_gb_per_day = growth_rate_gb_per_hour * 24
        
        # Get current usage
        current_usage = data_points[-1][1]
        
        # Calculate R-squared (coefficient of determination) for quality assessment
        y_mean = sum_y / n
        ss_tot = sum((y - y_mean) ** 2 for x, y in data_points)
        ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in data_points)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        return {
            "growth_rate_gb_per_hour": round(growth_rate_gb_per_hour, 4),
            "growth_rate_gb_per_day": round(growth_rate_gb_per_day, 4),
            "current_usage_gb": round(current_usage, 2),
            "data_points_analyzed": n,
            "time_window_hours": hours,
            "r_squared": round(r_squared, 4),  # Quality of fit (0-1, higher is better)
            "node_id": node_id,
            "calculation_timestamp": datetime.now().isoformat()
        }
    
    def predict_time_to_capacity(
        self,
        target_utilization: float = 100.0,
        node_id: Optional[str] = None,
        hours: int = 24
    ) -> Optional[Dict]:
        """
        Predict when storage capacity will reach a target utilization percentage
        
        Args:
            target_utilization: Target utilization percentage (default: 100.0 for full capacity)
            node_id: Specific node ID, or None for overall network
            hours: Number of hours of history to analyze (default: 24)
            
        Returns:
            Dictionary with time-to-capacity prediction, or None if insufficient data
        """
        if not self.node_factory:
            return None
        
        # Calculate growth rate
        growth_data = self.calculate_storage_growth_rate(node_id=node_id, hours=hours)
        if not growth_data or growth_data["growth_rate_gb_per_hour"] <= 0:
            return {
                "error": "Insufficient growth data or negative growth rate",
                "growth_rate_data": growth_data
            }
        
        # Get current capacity and usage
        if node_id:
            node_capacity = self.evaluate_node_capacity(node_id)
            if not node_capacity:
                return None
            total_capacity_gb = node_capacity.get("storage", {}).get("capacity_gb", 0)
            current_usage_gb = growth_data["current_usage_gb"]
        else:
            total_capacity = self.evaluate_total_capacity()
            storage_cap = total_capacity.get("storage_capacity", {})
            total_capacity_gb = storage_cap.get("total_gb", 0)
            current_usage_gb = growth_data["current_usage_gb"]
        
        if total_capacity_gb <= 0:
            return None
        
        # Calculate target usage
        target_usage_gb = total_capacity_gb * (target_utilization / 100.0)
        remaining_capacity_gb = target_usage_gb - current_usage_gb
        
        if remaining_capacity_gb <= 0:
            return {
                "status": "already_at_or_above_target",
                "current_utilization_percent": (current_usage_gb / total_capacity_gb) * 100,
                "target_utilization_percent": target_utilization,
                "current_usage_gb": round(current_usage_gb, 2),
                "total_capacity_gb": round(total_capacity_gb, 2)
            }
        
        # Calculate time to reach target (hours)
        growth_rate_gb_per_hour = growth_data["growth_rate_gb_per_hour"]
        if growth_rate_gb_per_hour <= 0:
            return {
                "status": "no_growth",
                "message": "Storage is not growing or growth rate is zero"
            }
        
        hours_to_target = remaining_capacity_gb / growth_rate_gb_per_hour
        days_to_target = hours_to_target / 24
        
        # Calculate predicted date
        predicted_datetime = datetime.now() + timedelta(hours=hours_to_target)
        
        return {
            "status": "prediction_available",
            "current_usage_gb": round(current_usage_gb, 2),
            "total_capacity_gb": round(total_capacity_gb, 2),
            "current_utilization_percent": round((current_usage_gb / total_capacity_gb) * 100, 2),
            "target_utilization_percent": target_utilization,
            "remaining_capacity_gb": round(remaining_capacity_gb, 2),
            "growth_rate_gb_per_hour": growth_rate_gb_per_hour,
            "hours_to_target": round(hours_to_target, 2),
            "days_to_target": round(days_to_target, 2),
            "predicted_datetime": predicted_datetime.isoformat(),
            "predicted_date": predicted_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            "confidence": "high" if growth_data["r_squared"] > 0.7 else "medium" if growth_data["r_squared"] > 0.4 else "low",
            "r_squared": growth_data["r_squared"],
            "node_id": node_id,
            "calculation_timestamp": datetime.now().isoformat()
        }
    
    def predict_storage_usage(
        self,
        hours_ahead: float,
        node_id: Optional[str] = None,
        history_hours: int = 24
    ) -> Optional[Dict]:
        """
        Predict storage usage at a future time
        
        Args:
            hours_ahead: Number of hours into the future to predict
            node_id: Specific node ID, or None for overall network
            history_hours: Number of hours of history to analyze (default: 24)
            
        Returns:
            Dictionary with predicted usage, or None if insufficient data
        """
        growth_data = self.calculate_storage_growth_rate(node_id=node_id, hours=history_hours)
        if not growth_data:
            return None
        
        # Get current capacity
        if node_id:
            node_capacity = self.evaluate_node_capacity(node_id)
            if not node_capacity:
                return None
            total_capacity_gb = node_capacity.get("storage", {}).get("capacity_gb", 0)
        else:
            total_capacity = self.evaluate_total_capacity()
            storage_cap = total_capacity.get("storage_capacity", {})
            total_capacity_gb = storage_cap.get("total_gb", 0)
        
        # Calculate predicted usage
        current_usage_gb = growth_data["current_usage_gb"]
        growth_rate_gb_per_hour = growth_data["growth_rate_gb_per_hour"]
        predicted_usage_gb = current_usage_gb + (growth_rate_gb_per_hour * hours_ahead)
        
        # Calculate predicted utilization
        predicted_utilization_percent = (predicted_usage_gb / total_capacity_gb * 100) if total_capacity_gb > 0 else 0
        
        # Calculate predicted datetime
        predicted_datetime = datetime.now() + timedelta(hours=hours_ahead)
        
        return {
            "current_usage_gb": round(current_usage_gb, 2),
            "predicted_usage_gb": round(predicted_usage_gb, 2),
            "total_capacity_gb": round(total_capacity_gb, 2),
            "current_utilization_percent": round((current_usage_gb / total_capacity_gb) * 100, 2) if total_capacity_gb > 0 else 0,
            "predicted_utilization_percent": round(predicted_utilization_percent, 2),
            "growth_rate_gb_per_hour": growth_rate_gb_per_hour,
            "hours_ahead": hours_ahead,
            "predicted_datetime": predicted_datetime.isoformat(),
            "predicted_date": predicted_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            "confidence": "high" if growth_data["r_squared"] > 0.7 else "medium" if growth_data["r_squared"] > 0.4 else "low",
            "r_squared": growth_data["r_squared"],
            "node_id": node_id,
            "calculation_timestamp": datetime.now().isoformat()
        }
    
    def get_storage_trends(self, node_id: Optional[str] = None, hours: int = 24) -> Dict:
        """
        Get comprehensive storage trends and predictions
        
        Args:
            node_id: Specific node ID, or None for overall network
            hours: Number of hours of history to analyze (default: 24)
            
        Returns:
            Dictionary with trends, predictions, and recommendations
        """
        growth_data = self.calculate_storage_growth_rate(node_id=node_id, hours=hours)
        time_to_full = self.predict_time_to_capacity(node_id=node_id, hours=hours)
        prediction_24h = self.predict_storage_usage(24, node_id=node_id, history_hours=hours)
        prediction_7d = self.predict_storage_usage(24 * 7, node_id=node_id, history_hours=hours)
        
        trends = {
            "growth_analysis": growth_data,
            "time_to_full_capacity": time_to_full,
            "prediction_24_hours": prediction_24h,
            "prediction_7_days": prediction_7d,
            "node_id": node_id,
            "analysis_timestamp": datetime.now().isoformat()
        }
        
        # Add recommendations
        recommendations = []
        if growth_data and growth_data["growth_rate_gb_per_hour"] > 0:
            if time_to_full and time_to_full.get("status") == "prediction_available":
                days_to_full = time_to_full.get("days_to_target", 0)
                if days_to_full < 7:
                    recommendations.append("CRITICAL: Storage will be full within 7 days. Immediate action required.")
                elif days_to_full < 30:
                    recommendations.append("WARNING: Storage will be full within 30 days. Plan for capacity expansion.")
                elif days_to_full < 90:
                    recommendations.append("INFO: Storage will be full within 90 days. Consider capacity planning.")
        
        trends["recommendations"] = recommendations
        
        return trends
    
    def __repr__(self):
        """String representation of CapacityEvaluator"""
        node_count = self.node_factory.get_node_count() if self.node_factory else 0
        history_count = len(self.capacity_history)
        return f"CapacityEvaluator(nodes={node_count}, history_snapshots={history_count})"

