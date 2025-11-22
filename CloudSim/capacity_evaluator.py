"""
CapacityEvaluator - Evaluates capacity and resource utilization across the storage network
Provides insights into current usage, available capacity, and capacity planning
"""

from typing import Dict, List, Optional, Tuple, Callable
from datetime import datetime, timedelta
import time
from enum import Enum
from dataclasses import dataclass, field
from node_factory import NodeFactory
from storage_virtual_node import StorageVirtualNode


class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class CapacityThreshold:
    """Represents a capacity threshold configuration"""
    threshold_percent: float
    alert_level: AlertLevel
    description: str = ""
    enabled: bool = True


@dataclass
class CapacityAlert:
    """Represents a capacity alert"""
    alert_id: str
    timestamp: datetime
    level: AlertLevel
    node_id: Optional[str]
    threshold_percent: float
    current_utilization_percent: float
    message: str
    details: Dict = field(default_factory=dict)


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
        
        # Threshold configuration {node_id: [CapacityThreshold]} or "global": [CapacityThreshold]
        self.thresholds: Dict[str, List[CapacityThreshold]] = {
            "global": [
                CapacityThreshold(50.0, AlertLevel.INFO, "Storage utilization reached 50%"),
                CapacityThreshold(75.0, AlertLevel.WARNING, "Storage utilization reached 75%"),
                CapacityThreshold(90.0, AlertLevel.CRITICAL, "Storage utilization reached 90%"),
                CapacityThreshold(95.0, AlertLevel.CRITICAL, "Storage utilization reached 95%")
            ]
        }
        
        # Alert history
        self.alert_history: List[CapacityAlert] = []
        self.max_alert_history = 1000  # Keep last 1000 alerts
        
        # Track which thresholds have been triggered (to avoid duplicate alerts)
        self.triggered_thresholds: Dict[str, set] = {}  # {node_id: set of threshold_percent}
        
        # Alert callbacks {AlertLevel: [callable]}
        self.alert_callbacks: Dict[AlertLevel, List[Callable]] = {
            AlertLevel.INFO: [],
            AlertLevel.WARNING: [],
            AlertLevel.CRITICAL: []
        }
        
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
    
    def take_capacity_snapshot(self, check_thresholds: bool = True) -> Dict:
        """
        Take a snapshot of current capacity state for historical tracking
        
        Args:
            check_thresholds: If True, automatically check thresholds and generate alerts
            
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
        
        # Check thresholds if requested
        if check_thresholds:
            alerts = self.check_thresholds()
            if alerts:
                snapshot["alerts_generated"] = len(alerts)
        
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
    
    def add_threshold(
        self,
        threshold_percent: float,
        alert_level: AlertLevel,
        description: str = "",
        node_id: Optional[str] = None
    ):
        """
        Add a capacity threshold
        
        Args:
            threshold_percent: Utilization percentage threshold
            alert_level: Alert level when threshold is reached
            description: Description of the threshold
            node_id: Specific node ID, or None for global threshold
        """
        key = node_id if node_id else "global"
        if key not in self.thresholds:
            self.thresholds[key] = []
        
        threshold = CapacityThreshold(threshold_percent, alert_level, description)
        self.thresholds[key].append(threshold)
        
        # Sort thresholds by percentage
        self.thresholds[key].sort(key=lambda t: t.threshold_percent)
        
        print(f"[CapacityEvaluator] Added {alert_level.value} threshold at {threshold_percent}% for {key}")
    
    def remove_threshold(self, threshold_percent: float, node_id: Optional[str] = None) -> bool:
        """
        Remove a capacity threshold
        
        Args:
            threshold_percent: Threshold percentage to remove
            node_id: Specific node ID, or None for global threshold
            
        Returns:
            True if threshold was removed, False if not found
        """
        key = node_id if node_id else "global"
        if key not in self.thresholds:
            return False
        
        original_count = len(self.thresholds[key])
        self.thresholds[key] = [
            t for t in self.thresholds[key]
            if t.threshold_percent != threshold_percent
        ]
        
        removed = len(self.thresholds[key]) < original_count
        if removed:
            print(f"[CapacityEvaluator] Removed threshold at {threshold_percent}% for {key}")
        
        return removed
    
    def check_thresholds(self, node_id: Optional[str] = None) -> List[CapacityAlert]:
        """
        Check current utilization against configured thresholds and generate alerts
        
        Args:
            node_id: Specific node ID to check, or None for all nodes
            
        Returns:
            List of generated alerts
        """
        alerts = []
        
        if not self.node_factory:
            return alerts
        
        # Get nodes to check
        if node_id:
            nodes_to_check = [node_id]
        else:
            nodes_to_check = list(self.node_factory.node_configs.keys())
            nodes_to_check.append(None)  # Add global check
        
        for check_node_id in nodes_to_check:
            # Get utilization
            if check_node_id:
                node_capacity = self.evaluate_node_capacity(check_node_id)
                if not node_capacity:
                    continue
                utilization_percent = node_capacity.get("storage", {}).get("utilization_percent", 0)
            else:
                total_capacity = self.evaluate_total_capacity()
                utilization_percent = total_capacity.get("storage_capacity", {}).get("utilization_percent", 0)
            
            # Get thresholds for this node/global
            key = check_node_id if check_node_id else "global"
            thresholds = self.thresholds.get(key, [])
            
            # Check each threshold
            for threshold in thresholds:
                if not threshold.enabled:
                    continue
                
                # Check if threshold is crossed
                if utilization_percent >= threshold.threshold_percent:
                    # Check if we've already alerted for this threshold
                    threshold_key = f"{key}:{threshold.threshold_percent}"
                    if key not in self.triggered_thresholds:
                        self.triggered_thresholds[key] = set()
                    
                    if threshold_key not in self.triggered_thresholds[key]:
                        # Generate alert
                        alert = self._create_alert(
                            threshold=threshold,
                            node_id=check_node_id,
                            utilization_percent=utilization_percent
                        )
                        alerts.append(alert)
                        
                        # Mark threshold as triggered
                        self.triggered_thresholds[key].add(threshold_key)
                        
                        # Call registered callbacks
                        self._trigger_alert_callbacks(alert)
                else:
                    # Utilization dropped below threshold, reset trigger
                    threshold_key = f"{key}:{threshold.threshold_percent}"
                    if key in self.triggered_thresholds:
                        self.triggered_thresholds[key].discard(threshold_key)
        
        return alerts
    
    def _create_alert(
        self,
        threshold: CapacityThreshold,
        node_id: Optional[str],
        utilization_percent: float
    ) -> CapacityAlert:
        """Create a capacity alert"""
        alert_id = f"{node_id or 'global'}_{threshold.threshold_percent}_{datetime.now().timestamp()}"
        
        message = threshold.description or f"Storage utilization ({utilization_percent:.2f}%) reached threshold ({threshold.threshold_percent}%)"
        if node_id:
            message = f"[{node_id}] {message}"
        
        alert = CapacityAlert(
            alert_id=alert_id,
            timestamp=datetime.now(),
            level=threshold.alert_level,
            node_id=node_id,
            threshold_percent=threshold.threshold_percent,
            current_utilization_percent=utilization_percent,
            message=message,
            details={
                "threshold_description": threshold.description
            }
        )
        
        # Add to alert history
        self.alert_history.append(alert)
        
        # Keep only last N alerts
        if len(self.alert_history) > self.max_alert_history:
            self.alert_history = self.alert_history[-self.max_alert_history:]
        
        return alert
    
    def _trigger_alert_callbacks(self, alert: CapacityAlert):
        """Trigger registered callbacks for an alert"""
        callbacks = self.alert_callbacks.get(alert.level, [])
        for callback in callbacks:
            try:
                callback(alert)
            except Exception as e:
                print(f"[CapacityEvaluator] Error in alert callback: {e}")
    
    def register_alert_callback(self, alert_level: AlertLevel, callback: Callable[[CapacityAlert], None]):
        """
        Register a callback function to be called when an alert is generated
        
        Args:
            alert_level: Alert level to register callback for
            callback: Function that takes a CapacityAlert as parameter
        """
        if alert_level not in self.alert_callbacks:
            self.alert_callbacks[alert_level] = []
        
        self.alert_callbacks[alert_level].append(callback)
        print(f"[CapacityEvaluator] Registered callback for {alert_level.value} alerts")
    
    def get_alert_history(
        self,
        node_id: Optional[str] = None,
        alert_level: Optional[AlertLevel] = None,
        limit: Optional[int] = None
    ) -> List[CapacityAlert]:
        """
        Get alert history
        
        Args:
            node_id: Filter by node ID, or None for all
            alert_level: Filter by alert level, or None for all
            limit: Maximum number of alerts to return
            
        Returns:
            List of alerts
        """
        alerts = self.alert_history
        
        # Filter by node_id
        if node_id is not None:
            alerts = [a for a in alerts if a.node_id == node_id]
        
        # Filter by alert level
        if alert_level is not None:
            alerts = [a for a in alerts if a.level == alert_level]
        
        # Sort by timestamp (newest first)
        alerts.sort(key=lambda a: a.timestamp, reverse=True)
        
        # Apply limit
        if limit:
            alerts = alerts[:limit]
        
        return alerts
    
    def generate_capacity_report(
        self,
        include_predictions: bool = True,
        include_alerts: bool = True,
        include_history: bool = False
    ) -> Dict:
        """
        Generate a comprehensive capacity report
        
        Args:
            include_predictions: Include prediction data
            include_alerts: Include recent alerts
            include_history: Include historical trends
            
        Returns:
            Dictionary with comprehensive capacity report
        """
        if not self.node_factory:
            return {"error": "No NodeFactory set"}
        
        report = {
            "report_timestamp": datetime.now().isoformat(),
            "summary": self.get_capacity_summary(),
            "total_capacity": self.evaluate_total_capacity(),
            "nodes_capacity": self.evaluate_all_nodes_capacity()
        }
        
        # Add predictions
        if include_predictions:
            report["predictions"] = {
                "overall": self.get_storage_trends(),
                "time_to_full": self.predict_time_to_capacity()
            }
            
            # Add node-specific predictions
            node_predictions = {}
            for node_id in self.node_factory.node_configs.keys():
                node_predictions[node_id] = self.get_storage_trends(node_id=node_id)
            report["predictions"]["nodes"] = node_predictions
        
        # Add alerts
        if include_alerts:
            recent_alerts = self.get_alert_history(limit=50)
            report["alerts"] = {
                "recent": [
                    {
                        "alert_id": a.alert_id,
                        "timestamp": a.timestamp.isoformat(),
                        "level": a.level.value,
                        "node_id": a.node_id,
                        "message": a.message,
                        "utilization_percent": a.current_utilization_percent,
                        "threshold_percent": a.threshold_percent
                    }
                    for a in recent_alerts
                ],
                "summary": {
                    "total_alerts": len(self.alert_history),
                    "critical_count": len([a for a in self.alert_history if a.level == AlertLevel.CRITICAL]),
                    "warning_count": len([a for a in self.alert_history if a.level == AlertLevel.WARNING]),
                    "info_count": len([a for a in self.alert_history if a.level == AlertLevel.INFO])
                }
            }
        
        # Add history summary
        if include_history:
            report["history"] = {
                "snapshot_count": len(self.capacity_history),
                "latest_snapshot": self.capacity_history[-1] if self.capacity_history else None
            }
        
        # Add threshold configuration
        report["thresholds"] = {
            key: [
                {
                    "threshold_percent": t.threshold_percent,
                    "alert_level": t.alert_level.value,
                    "description": t.description,
                    "enabled": t.enabled
                }
                for t in thresholds
            ]
            for key, thresholds in self.thresholds.items()
        }
        
        return report
    
    def __repr__(self):
        """String representation of CapacityEvaluator"""
        node_count = self.node_factory.get_node_count() if self.node_factory else 0
        history_count = len(self.capacity_history)
        alert_count = len(self.alert_history)
        return f"CapacityEvaluator(nodes={node_count}, history={history_count}, alerts={alert_count})"

