"""
MetricsCollector - Collects and aggregates performance metrics from storage nodes
Provides real-time and historical performance data tracking
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
import time
import threading
import json
import csv
import os
from collections import deque
from node_factory import NodeFactory
from storage_virtual_node import StorageVirtualNode


class MetricType(Enum):
    """Types of metrics that can be collected"""
    THROUGHPUT = "throughput"  # Data transfer rate (MB/s)
    LATENCY = "latency"  # Transfer latency (ms)
    RTT = "rtt"  # Round-trip time (ms)
    STORAGE_UTILIZATION = "storage_utilization"  # Storage usage percentage
    NETWORK_UTILIZATION = "network_utilization"  # Network usage percentage
    TRANSFER_COUNT = "transfer_count"  # Number of transfers
    ERROR_RATE = "error_rate"  # Error percentage
    DATA_TRANSFERRED = "data_transferred"  # Total data transferred (bytes)


@dataclass
class MetricSample:
    """Represents a single metric sample at a point in time"""
    timestamp: datetime
    node_id: Optional[str]
    metric_type: MetricType
    value: float
    unit: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "node_id": self.node_id,
            "metric_type": self.metric_type.value,
            "value": self.value,
            "unit": self.unit,
            "metadata": self.metadata
        }


@dataclass
class TransferMetrics:
    """Metrics for a specific file transfer"""
    transfer_id: str
    file_id: str
    source_node: str
    target_node: str
    file_size_bytes: int
    start_time: datetime
    user_id: Optional[str] = None  # Track which user performed the transfer
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    throughput_mbps: Optional[float] = None
    latency_ms: Optional[float] = None
    chunks_transferred: int = 0
    total_chunks: int = 0
    success: bool = False
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "transfer_id": self.transfer_id,
            "file_id": self.file_id,
            "source_node": self.source_node,
            "target_node": self.target_node,
            "file_size_bytes": self.file_size_bytes,
            "user_id": self.user_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "throughput_mbps": self.throughput_mbps,
            "latency_ms": self.latency_ms,
            "chunks_transferred": self.chunks_transferred,
            "total_chunks": self.total_chunks,
            "success": self.success,
            "error_message": self.error_message
        }


@dataclass
class NodeMetrics:
    """Aggregated metrics for a single node"""
    node_id: str
    timestamp: datetime
    throughput_mbps: float = 0.0
    average_latency_ms: float = 0.0
    average_rtt_ms: float = 0.0
    storage_utilization_percent: float = 0.0
    network_utilization_percent: float = 0.0
    total_transfers: int = 0
    successful_transfers: int = 0
    failed_transfers: int = 0
    error_rate_percent: float = 0.0
    total_data_transferred_bytes: int = 0
    active_transfers: int = 0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "node_id": self.node_id,
            "timestamp": self.timestamp.isoformat(),
            "throughput_mbps": self.throughput_mbps,
            "average_latency_ms": self.average_latency_ms,
            "average_rtt_ms": self.average_rtt_ms,
            "storage_utilization_percent": self.storage_utilization_percent,
            "network_utilization_percent": self.network_utilization_percent,
            "total_transfers": self.total_transfers,
            "successful_transfers": self.successful_transfers,
            "failed_transfers": self.failed_transfers,
            "error_rate_percent": self.error_rate_percent,
            "total_data_transferred_bytes": self.total_data_transferred_bytes,
            "active_transfers": self.active_transfers
        }


@dataclass
class NetworkMetrics:
    """Aggregated metrics for the entire network"""
    timestamp: datetime
    total_nodes: int
    total_throughput_mbps: float = 0.0
    average_latency_ms: float = 0.0
    average_rtt_ms: float = 0.0
    total_storage_utilization_percent: float = 0.0
    total_network_utilization_percent: float = 0.0
    total_transfers: int = 0
    total_successful_transfers: int = 0
    total_failed_transfers: int = 0
    overall_error_rate_percent: float = 0.0
    total_data_transferred_bytes: int = 0
    total_active_transfers: int = 0
    node_metrics: List[NodeMetrics] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "total_nodes": self.total_nodes,
            "total_throughput_mbps": self.total_throughput_mbps,
            "average_latency_ms": self.average_latency_ms,
            "average_rtt_ms": self.average_rtt_ms,
            "total_storage_utilization_percent": self.total_storage_utilization_percent,
            "total_network_utilization_percent": self.total_network_utilization_percent,
            "total_transfers": self.total_transfers,
            "total_successful_transfers": self.total_successful_transfers,
            "total_failed_transfers": self.total_failed_transfers,
            "overall_error_rate_percent": self.overall_error_rate_percent,
            "total_data_transferred_bytes": self.total_data_transferred_bytes,
            "total_active_transfers": self.total_active_transfers,
            "node_metrics": [nm.to_dict() for nm in self.node_metrics]
        }


class MetricsCollector:
    """
    Collects and aggregates performance metrics from storage nodes
    Maintains historical data and provides real-time metrics
    """
    
    def __init__(self, node_factory: Optional[NodeFactory] = None, max_history: int = 1000):
        """
        Initialize MetricsCollector
        
        Args:
            node_factory: Optional NodeFactory instance to collect metrics from
            max_history: Maximum number of metric samples to keep in history
        """
        self.node_factory = node_factory
        self.max_history = max_history
        
        # Metric samples history {metric_type: deque of MetricSample}
        self.metric_samples: Dict[MetricType, deque] = {
            metric_type: deque(maxlen=max_history)
            for metric_type in MetricType
        }
        
        # Transfer metrics {transfer_id: TransferMetrics}
        self.transfer_metrics: Dict[str, TransferMetrics] = {}
        
        # Node metrics history {node_id: deque of NodeMetrics}
        self.node_metrics_history: Dict[str, deque] = {}
        
        # Network metrics history (deque of NetworkMetrics)
        self.network_metrics_history: deque = deque(maxlen=max_history)
        
        # Thread safety
        self.collection_lock = threading.Lock()
        
        # Collection interval (seconds)
        self.collection_interval = 5.0  # Default: collect every 5 seconds
        
        # Auto-collection thread
        self.collection_thread: Optional[threading.Thread] = None
        self.running = False
        
        # Real-time throughput tracking {node_id: deque of (timestamp, bytes_transferred)}
        self.throughput_windows: Dict[str, deque] = {}  # For calculating real-time throughput
        self.throughput_window_size = 60  # Track last 60 seconds by default
        
        # Moving average configurations
        self.sma_window_size = 10  # Simple Moving Average window (number of samples)
        self.ema_alpha = 0.3  # Exponential Moving Average smoothing factor (0-1)
        
        # Latency and RTT tracking {node_id: deque of (timestamp, latency_ms)}
        self.latency_samples: Dict[str, deque] = {}  # Per-node latency samples
        self.rtt_samples: Dict[str, deque] = {}  # Per-node RTT samples
        
        print("[MetricsCollector] Initialized")
    
    def set_node_factory(self, node_factory: NodeFactory):
        """
        Set or update the NodeFactory to collect metrics from
        
        Args:
            node_factory: NodeFactory instance
        """
        self.node_factory = node_factory
        print(f"[MetricsCollector] NodeFactory set ({node_factory.get_node_count()} nodes)")
    
    def calculate_realtime_throughput(self, node_id: str, window_seconds: int = 60) -> float:
        """
        Calculate real-time throughput for a node based on recent transfers
        
        Args:
            node_id: ID of the node
            window_seconds: Time window in seconds to calculate throughput over (default: 60)
            
        Returns:
            Throughput in MB/s
        """
        current_time = time.time()
        cutoff_time = current_time - window_seconds
        
        # Get recent throughput samples for this node
        throughput_samples = self.get_metric_samples(
            MetricType.THROUGHPUT,
            node_id=node_id,
            limit=1000  # Get enough samples to cover the window
        )
        
        if not throughput_samples:
            return 0.0
        
        # Filter samples within the time window
        recent_samples = [
            s for s in throughput_samples
            if s.timestamp.timestamp() >= cutoff_time
        ]
        
        if not recent_samples:
            return 0.0
        
        # Calculate average throughput over the window
        total_throughput = sum(s.value for s in recent_samples)
        average_throughput = total_throughput / len(recent_samples)
        
        return round(average_throughput, 2)
    
    def calculate_average_latency(self, node_id: str, window_seconds: int = 300) -> float:
        """
        Calculate average latency for a node from recent samples
        
        Args:
            node_id: ID of the node
            window_seconds: Time window in seconds to calculate average over (default: 300 = 5 minutes)
            
        Returns:
            Average latency in milliseconds
        """
        latency_samples = self.get_metric_samples(
            MetricType.LATENCY,
            node_id=node_id,
            limit=1000
        )
        
        if not latency_samples:
            return 0.0
        
        # Filter by time window
        cutoff_time = datetime.now() - timedelta(seconds=window_seconds)
        recent_samples = [
            s for s in latency_samples
            if s.timestamp >= cutoff_time
        ]
        
        if not recent_samples:
            return 0.0
        
        avg_latency = sum(s.value for s in recent_samples) / len(recent_samples)
        return round(avg_latency, 2)
    
    def calculate_average_rtt(self, node_id: str, window_seconds: int = 300) -> float:
        """
        Calculate average round-trip time for a node from recent samples
        
        Args:
            node_id: ID of the node
            window_seconds: Time window in seconds to calculate average over (default: 300 = 5 minutes)
            
        Returns:
            Average RTT in milliseconds
        """
        rtt_samples = self.get_metric_samples(
            MetricType.RTT,
            node_id=node_id,
            limit=1000
        )
        
        if not rtt_samples:
            return 0.0
        
        # Filter by time window
        cutoff_time = datetime.now() - timedelta(seconds=window_seconds)
        recent_samples = [
            s for s in rtt_samples
            if s.timestamp >= cutoff_time
        ]
        
        if not recent_samples:
            return 0.0
        
        avg_rtt = sum(s.value for s in recent_samples) / len(recent_samples)
        return round(avg_rtt, 2)
    
    def get_latency_stats(self, node_id: Optional[str] = None) -> Dict:
        """
        Get latency statistics
        
        Args:
            node_id: Optional node ID, or None for network-wide stats
            
        Returns:
            Dictionary with latency statistics
        """
        if node_id:
            samples = self.get_metric_samples(MetricType.LATENCY, node_id=node_id, limit=1000)
            if not samples:
                return {"node_id": node_id, "average_latency_ms": 0.0, "min_latency_ms": 0.0, "max_latency_ms": 0.0, "sample_count": 0}
            
            values = [s.value for s in samples]
            avg = self.calculate_average_latency(node_id)
            
            return {
                "node_id": node_id,
                "average_latency_ms": avg,
                "min_latency_ms": round(min(values), 2),
                "max_latency_ms": round(max(values), 2),
                "sample_count": len(values),
                "timestamp": datetime.now().isoformat()
            }
        else:
            # Network-wide stats
            if not self.node_factory:
                return {}
            
            node_stats = []
            total_avg = 0.0
            
            for nid in self.node_factory.node_configs.keys():
                stats = self.get_latency_stats(node_id=nid)
                if stats and stats.get("sample_count", 0) > 0:
                    node_stats.append(stats)
                    total_avg += stats.get("average_latency_ms", 0)
            
            return {
                "network_wide": True,
                "average_latency_ms": round(total_avg / len(node_stats), 2) if node_stats else 0.0,
                "node_count": len(node_stats),
                "node_stats": node_stats,
                "timestamp": datetime.now().isoformat()
            }
    
    def get_rtt_stats(self, node_id: Optional[str] = None) -> Dict:
        """
        Get RTT statistics
        
        Args:
            node_id: Optional node ID, or None for network-wide stats
            
        Returns:
            Dictionary with RTT statistics
        """
        if node_id:
            samples = self.get_metric_samples(MetricType.RTT, node_id=node_id, limit=1000)
            if not samples:
                return {"node_id": node_id, "average_rtt_ms": 0.0, "min_rtt_ms": 0.0, "max_rtt_ms": 0.0, "sample_count": 0}
            
            values = [s.value for s in samples]
            avg = self.calculate_average_rtt(node_id)
            
            return {
                "node_id": node_id,
                "average_rtt_ms": avg,
                "min_rtt_ms": round(min(values), 2),
                "max_rtt_ms": round(max(values), 2),
                "sample_count": len(values),
                "timestamp": datetime.now().isoformat()
            }
        else:
            # Network-wide stats
            if not self.node_factory:
                return {}
            
            node_stats = []
            total_avg = 0.0
            
            for nid in self.node_factory.node_configs.keys():
                stats = self.get_rtt_stats(node_id=nid)
                if stats and stats.get("sample_count", 0) > 0:
                    node_stats.append(stats)
                    total_avg += stats.get("average_rtt_ms", 0)
            
            return {
                "network_wide": True,
                "average_rtt_ms": round(total_avg / len(node_stats), 2) if node_stats else 0.0,
                "node_count": len(node_stats),
                "node_stats": node_stats,
                "timestamp": datetime.now().isoformat()
            }
    
    def calculate_moving_average_throughput(
        self,
        node_id: str,
        window_size: Optional[int] = None,
        use_ema: bool = False
    ) -> float:
        """
        Calculate moving average throughput for a node
        
        Args:
            node_id: ID of the node
            window_size: Number of samples for SMA (None = use default)
            use_ema: If True, use Exponential Moving Average; if False, use Simple Moving Average
            
        Returns:
            Moving average throughput in MB/s
        """
        throughput_samples = self.get_metric_samples(
            MetricType.THROUGHPUT,
            node_id=node_id,
            limit=1000
        )
        
        if not throughput_samples:
            return 0.0
        
        if use_ema:
            # Exponential Moving Average
            if not throughput_samples:
                return 0.0
            
            # Start with first value
            ema = throughput_samples[0].value
            
            # Apply EMA formula: EMA = alpha * current + (1 - alpha) * previous_EMA
            for sample in throughput_samples[1:]:
                ema = self.ema_alpha * sample.value + (1 - self.ema_alpha) * ema
            
            return round(ema, 2)
        else:
            # Simple Moving Average
            window = window_size or self.sma_window_size
            recent_samples = throughput_samples[-window:] if len(throughput_samples) >= window else throughput_samples
            
            if not recent_samples:
                return 0.0
            
            avg = sum(s.value for s in recent_samples) / len(recent_samples)
            return round(avg, 2)
    
    def get_realtime_throughput_stats(self, node_id: Optional[str] = None) -> Dict:
        """
        Get real-time throughput statistics
        
        Args:
            node_id: Optional node ID, or None for network-wide stats
            
        Returns:
            Dictionary with throughput statistics
        """
        if node_id:
            # Node-specific stats
            current = self.calculate_realtime_throughput(node_id, window_seconds=10)
            sma = self.calculate_moving_average_throughput(node_id, use_ema=False)
            ema = self.calculate_moving_average_throughput(node_id, use_ema=True)
            
            # Get min/max from recent samples
            samples = self.get_metric_samples(MetricType.THROUGHPUT, node_id=node_id, limit=100)
            values = [s.value for s in samples] if samples else []
            
            return {
                "node_id": node_id,
                "current_throughput_mbps": current,
                "sma_throughput_mbps": sma,
                "ema_throughput_mbps": ema,
                "min_throughput_mbps": round(min(values), 2) if values else 0.0,
                "max_throughput_mbps": round(max(values), 2) if values else 0.0,
                "sample_count": len(values),
                "timestamp": datetime.now().isoformat()
            }
        else:
            # Network-wide stats
            if not self.node_factory:
                return {}
            
            node_stats = []
            total_current = 0.0
            total_sma = 0.0
            total_ema = 0.0
            
            for nid in self.node_factory.node_configs.keys():
                stats = self.get_realtime_throughput_stats(node_id=nid)
                if stats:
                    node_stats.append(stats)
                    total_current += stats.get("current_throughput_mbps", 0)
                    total_sma += stats.get("sma_throughput_mbps", 0)
                    total_ema += stats.get("ema_throughput_mbps", 0)
            
            return {
                "network_wide": True,
                "total_current_throughput_mbps": round(total_current, 2),
                "total_sma_throughput_mbps": round(total_sma, 2),
                "total_ema_throughput_mbps": round(total_ema, 2),
                "average_current_throughput_mbps": round(total_current / len(node_stats), 2) if node_stats else 0.0,
                "average_sma_throughput_mbps": round(total_sma / len(node_stats), 2) if node_stats else 0.0,
                "average_ema_throughput_mbps": round(total_ema / len(node_stats), 2) if node_stats else 0.0,
                "node_count": len(node_stats),
                "node_stats": node_stats,
                "timestamp": datetime.now().isoformat()
            }
    
    def collect_node_metrics(self, node_id: str) -> Optional[NodeMetrics]:
        """
        Collect current metrics from a specific node
        
        Args:
            node_id: ID of the node to collect metrics from
            
        Returns:
            NodeMetrics instance, or None if node not found
        """
        if not self.node_factory:
            return None
        
        node = self.node_factory.get_node(node_id)
        if not node:
            return None
        
        try:
            # Get node performance data
            performance = node.get_performance_metrics()
            storage_util = node.get_storage_utilization()
            network_util = node.get_network_utilization()
            
            # Calculate metrics
            total_transfers = performance.get("total_requests_processed", 0)
            failed_transfers = performance.get("failed_transfers", 0)
            successful_transfers = total_transfers - failed_transfers
            error_rate = (failed_transfers / total_transfers * 100) if total_transfers > 0 else 0.0
            
            # Calculate real-time throughput
            realtime_throughput = self.calculate_realtime_throughput(node_id, window_seconds=60)
            
            # Calculate average latency
            average_latency = self.calculate_average_latency(node_id)
            
            # Calculate average RTT
            average_rtt = self.calculate_average_rtt(node_id)
            
            node_metrics = NodeMetrics(
                node_id=node_id,
                timestamp=datetime.now(),
                throughput_mbps=realtime_throughput,  # Use real-time throughput
                average_latency_ms=average_latency,
                average_rtt_ms=average_rtt,
                storage_utilization_percent=storage_util.get("utilization_percent", 0.0),
                network_utilization_percent=network_util.get("utilization_percent", 0.0),
                total_transfers=total_transfers,
                successful_transfers=successful_transfers,
                failed_transfers=failed_transfers,
                error_rate_percent=error_rate,
                total_data_transferred_bytes=performance.get("total_data_transferred_bytes", 0),
                active_transfers=performance.get("current_active_transfers", 0)
            )
            
            # Store in history
            with self.collection_lock:
                if node_id not in self.node_metrics_history:
                    self.node_metrics_history[node_id] = deque(maxlen=self.max_history)
                self.node_metrics_history[node_id].append(node_metrics)
            
            return node_metrics
            
        except Exception as e:
            print(f"[MetricsCollector] Error collecting metrics from {node_id}: {e}")
            return None
    
    def collect_all_nodes_metrics(self) -> NetworkMetrics:
        """
        Collect metrics from all nodes and aggregate into network metrics
        
        Returns:
            NetworkMetrics instance with aggregated data
        """
        if not self.node_factory:
            return NetworkMetrics(
                timestamp=datetime.now(),
                total_nodes=0
            )
        
        node_metrics_list = []
        total_throughput = 0.0
        total_latency = 0.0
        total_rtt = 0.0
        total_storage_capacity_bytes = 0
        total_storage_used_bytes = 0
        total_network_util = 0.0
        total_transfers = 0
        total_successful = 0
        total_failed = 0
        total_data = 0
        total_active = 0
        
        # Collect metrics from each node
        for node_id in self.node_factory.node_configs.keys():
            node_metrics = self.collect_node_metrics(node_id)
            if node_metrics:
                node_metrics_list.append(node_metrics)
                
                total_throughput += node_metrics.throughput_mbps
                total_latency += node_metrics.average_latency_ms
                total_rtt += node_metrics.average_rtt_ms
                total_network_util += node_metrics.network_utilization_percent
                total_transfers += node_metrics.total_transfers
                total_successful += node_metrics.successful_transfers
                total_failed += node_metrics.failed_transfers
                total_data += node_metrics.total_data_transferred_bytes
                total_active += node_metrics.active_transfers
                
                # Get actual storage capacity and used from node
                node = self.node_factory.get_node(node_id)
                if node:
                    try:
                        storage_util = node.get_storage_utilization()
                        total_storage_capacity_bytes += storage_util.get('total_bytes', 0)
                        total_storage_used_bytes += storage_util.get('used_bytes', 0)
                    except Exception:
                        pass
        
        node_count = len(node_metrics_list)
        
        # Calculate storage utilization correctly: total used / total capacity * 100
        total_storage_utilization_percent = (total_storage_used_bytes / total_storage_capacity_bytes * 100) if total_storage_capacity_bytes > 0 else 0.0
        
        # Calculate averages
        network_metrics = NetworkMetrics(
            timestamp=datetime.now(),
            total_nodes=node_count,
            total_throughput_mbps=total_throughput,
            average_latency_ms=total_latency / node_count if node_count > 0 else 0.0,
            average_rtt_ms=total_rtt / node_count if node_count > 0 else 0.0,
            total_storage_utilization_percent=total_storage_utilization_percent,
            total_network_utilization_percent=total_network_util / node_count if node_count > 0 else 0.0,
            total_transfers=total_transfers,
            total_successful_transfers=total_successful,
            total_failed_transfers=total_failed,
            overall_error_rate_percent=(total_failed / total_transfers * 100) if total_transfers > 0 else 0.0,
            total_data_transferred_bytes=total_data,
            total_active_transfers=total_active,
            node_metrics=node_metrics_list
        )
        
        # Store in history
        with self.collection_lock:
            self.network_metrics_history.append(network_metrics)
        
        return network_metrics
    
    def record_transfer_start(
        self,
        transfer_id: str,
        file_id: str,
        source_node: str,
        target_node: str,
        file_size_bytes: int,
        total_chunks: int,
        user_id: Optional[str] = None
    ):
        """
        Record the start of a file transfer
        
        Args:
            transfer_id: Unique transfer identifier
            file_id: File identifier
            source_node: Source node ID
            target_node: Target node ID
            file_size_bytes: Size of file in bytes
            total_chunks: Total number of chunks
        """
        # Get timestamp before creating TransferMetrics
        try:
            start_time = datetime.now()
        except Exception as e:
            print(f"Warning: datetime.now() failed: {e}, using fallback")
            import time
            start_time = datetime.fromtimestamp(time.time())
        
        # Create TransferMetrics object
        try:
            transfer_metrics = TransferMetrics(
                transfer_id=transfer_id,
                file_id=file_id,
                source_node=source_node,
                target_node=target_node,
                file_size_bytes=file_size_bytes,
                start_time=start_time,
                total_chunks=total_chunks,
                user_id=user_id
            )
        except Exception as e:
            print(f"Error creating TransferMetrics: {e}")
            return
        
        # Acquire lock and store metrics
        try:
            with self.collection_lock:
                self.transfer_metrics[transfer_id] = transfer_metrics
        except Exception as e:
            print(f"Error recording transfer start for {transfer_id}: {e}")
            import traceback
            traceback.print_exc()
    
    def record_transfer_end(
        self,
        transfer_id: str,
        success: bool,
        chunks_transferred: int = 0,
        error_message: Optional[str] = None,
        first_chunk_latency_ms: Optional[float] = None,
        average_chunk_rtt_ms: Optional[float] = None
    ):
        """
        Record the end of a file transfer
        
        Args:
            transfer_id: Transfer identifier
            success: Whether transfer was successful
            chunks_transferred: Number of chunks transferred
            error_message: Error message if transfer failed
            first_chunk_latency_ms: Latency to receive first chunk (ms)
            average_chunk_rtt_ms: Average round-trip time per chunk (ms)
        """
        try:
            with self.collection_lock:
                if transfer_id not in self.transfer_metrics:
                    return
                
                transfer = self.transfer_metrics[transfer_id]
                transfer.end_time = datetime.now()
                transfer.duration_seconds = (transfer.end_time - transfer.start_time).total_seconds()
                transfer.chunks_transferred = chunks_transferred
                transfer.success = success
                transfer.error_message = error_message
                
                if first_chunk_latency_ms is not None:
                    transfer.latency_ms = first_chunk_latency_ms
                if average_chunk_rtt_ms is not None:
                    # Calculate throughput if we have duration and size
                    if transfer.duration_seconds and transfer.duration_seconds > 0:
                        # Throughput in Mbps: (bytes * 8 bits/byte) / (seconds * 1,000,000 bits/Mbps)
                        transfer.throughput_mbps = (transfer.file_size_bytes * 8) / (transfer.duration_seconds * 1000000)
                # If throughput wasn't set above but we have duration, calculate it
                if transfer.throughput_mbps is None and transfer.duration_seconds and transfer.duration_seconds > 0:
                    transfer.throughput_mbps = (transfer.file_size_bytes * 8) / (transfer.duration_seconds * 1000000)
                # If latency wasn't set but we have duration, use it as latency
                if transfer.latency_ms is None and transfer.duration_seconds:
                    transfer.latency_ms = transfer.duration_seconds * 1000  # Convert seconds to ms
        except Exception as e:
            print(f"Error recording transfer end for {transfer_id}: {e}")
            import traceback
            traceback.print_exc()
    
    def record_latency(self, node_id: str, latency_ms: float, metadata: Optional[Dict] = None):
        """
        Record a latency measurement for a node
        
        Args:
            node_id: Node ID
            latency_ms: Latency in milliseconds
            metadata: Optional metadata
        """
        self._record_metric_sample(
            MetricType.LATENCY,
            latency_ms,
            "ms",
            node_id=node_id,
            metadata=metadata or {}
        )
    
    def record_rtt(self, node_id: str, rtt_ms: float, metadata: Optional[Dict] = None):
        """
        Record a round-trip time measurement for a node
        
        Args:
            node_id: Node ID
            rtt_ms: Round-trip time in milliseconds
            metadata: Optional metadata
        """
        self._record_metric_sample(
            MetricType.RTT,
            rtt_ms,
            "ms",
            node_id=node_id,
            metadata=metadata or {}
        )
    
    def _record_metric_sample(
        self,
        metric_type: MetricType,
        value: float,
        unit: str,
        node_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        """
        Record a metric sample
        
        Args:
            metric_type: Type of metric
            value: Metric value
            unit: Unit of measurement
            node_id: Optional node ID
            metadata: Optional metadata
        """
        sample = MetricSample(
            timestamp=datetime.now(),
            node_id=node_id,
            metric_type=metric_type,
            value=value,
            unit=unit,
            metadata=metadata or {}
        )
        
        with self.collection_lock:
            self.metric_samples[metric_type].append(sample)
    
    def get_metric_samples(
        self,
        metric_type: MetricType,
        node_id: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[MetricSample]:
        """
        Get metric samples for a specific metric type
        
        Args:
            metric_type: Type of metric to retrieve
            node_id: Optional node ID to filter by
            limit: Maximum number of samples to return
            
        Returns:
            List of MetricSample instances
        """
        with self.collection_lock:
            samples = list(self.metric_samples[metric_type])
        
        # Filter by node_id if specified
        if node_id:
            samples = [s for s in samples if s.node_id == node_id]
        
        # Apply limit
        if limit:
            samples = samples[-limit:]
        
        return samples
    
    def get_node_metrics_history(
        self,
        node_id: str,
        limit: Optional[int] = None
    ) -> List[NodeMetrics]:
        """
        Get historical metrics for a specific node
        
        Args:
            node_id: Node ID
            limit: Maximum number of samples to return
            
        Returns:
            List of NodeMetrics instances
        """
        with self.collection_lock:
            if node_id not in self.node_metrics_history:
                return []
            
            metrics = list(self.node_metrics_history[node_id])
        
        if limit:
            metrics = metrics[-limit:]
        
        return metrics
    
    def get_network_metrics_history(self, limit: Optional[int] = None) -> List[NetworkMetrics]:
        """
        Get historical network metrics
        
        Args:
            limit: Maximum number of samples to return
            
        Returns:
            List of NetworkMetrics instances
        """
        with self.collection_lock:
            metrics = list(self.network_metrics_history)
        
        if limit:
            metrics = metrics[-limit:]
        
        return metrics
    
    def get_latest_metrics(self, node_id: Optional[str] = None) -> Dict:
        """
        Get the latest metrics for a node or the entire network
        
        Args:
            node_id: Optional node ID, or None for network-wide metrics
            
        Returns:
            Dictionary with latest metrics
        """
        if node_id:
            history = self.get_node_metrics_history(node_id, limit=1)
            if history:
                return history[-1].to_dict()
            return {}
        else:
            history = self.get_network_metrics_history(limit=1)
            if history:
                return history[-1].to_dict()
            return {}
    
    def start_auto_collection(self, interval: float = 5.0):
        """
        Start automatic metric collection at regular intervals
        
        Args:
            interval: Collection interval in seconds (default: 5.0)
        """
        if self.running:
            print("[MetricsCollector] Auto-collection already running")
            return
        
        self.collection_interval = interval
        self.running = True
        
        self.collection_thread = threading.Thread(
            target=self._collection_loop,
            name="MetricsCollector",
            daemon=True
        )
        self.collection_thread.start()
        print(f"[MetricsCollector] Auto-collection started (interval: {interval}s)")
    
    def stop_auto_collection(self):
        """Stop automatic metric collection"""
        if not self.running:
            return
        
        self.running = False
        
        if self.collection_thread:
            self.collection_thread.join(timeout=2.0)
        
        print("[MetricsCollector] Auto-collection stopped")
    
    def _collection_loop(self):
        """Main loop for automatic metric collection"""
        while self.running:
            try:
                self.collect_all_nodes_metrics()
                time.sleep(self.collection_interval)
            except Exception as e:
                print(f"[MetricsCollector] Error in collection loop: {e}")
                time.sleep(self.collection_interval)
    
    def get_recent_transfers(self, limit: int = 50, aggregate_by_file: bool = True) -> List[Dict]:
        """
        Get recent transfer history with user information
        
        Args:
            limit: Maximum number of file-level transfers to return
            aggregate_by_file: If True, aggregate chunks by file_id; if False, return individual chunks
            
        Returns:
            List of transfer dictionaries with user_id, file_size_bytes, latency_ms, throughput_mbps
            If aggregate_by_file=True, includes 'chunks' array with chunk-level details
        """
        with self.collection_lock:
            transfers = list(self.transfer_metrics.values())
        
        # Filter out transfers that don't have end_time (incomplete transfers)
        completed_transfers = [t for t in transfers if t.end_time is not None]
        
        print(f"[get_recent_transfers] Total transfers: {len(transfers)}, Completed: {len(completed_transfers)}")
        
        if not aggregate_by_file:
            # Return individual chunk transfers (old behavior)
            completed_transfers.sort(key=lambda t: t.start_time, reverse=True)
            result = []
            for transfer in completed_transfers[:limit]:
                try:
                    transfer_dict = transfer.to_dict()
                    latency = transfer_dict.get("latency_ms")
                    throughput = transfer_dict.get("throughput_mbps")
                    
                    if latency is None and transfer.duration_seconds:
                        latency = transfer.duration_seconds * 1000
                    if throughput is None and transfer.duration_seconds and transfer.duration_seconds > 0:
                        throughput = (transfer.file_size_bytes * 8) / (transfer.duration_seconds * 1000000)
                    
                    result.append({
                        "user_id": transfer_dict.get("user_id") or "N/A",
                        "file_size_bytes": transfer_dict.get("file_size_bytes", 0),
                        "file_size_gb": round(transfer_dict.get("file_size_bytes", 0) / (1024**3), 4),
                        "latency_ms": latency if latency is not None else 0.0,
                        "throughput_mbps": throughput if throughput is not None else 0.0,
                        "start_time": transfer_dict.get("start_time"),
                        "success": transfer_dict.get("success", False),
                        "source_node": transfer_dict.get("source_node", "N/A"),
                        "target_node": transfer_dict.get("target_node", "N/A")
                    })
                except Exception as e:
                    print(f"Error processing transfer {transfer.transfer_id}: {e}")
                    continue
            return result
        
        # Aggregate by file_id
        file_transfers = {}  # {file_id: {metadata, chunks}}
        
        for transfer in completed_transfers:
            try:
                file_id = transfer.file_id
                user_id = transfer.user_id or "N/A"
                
                # Create file-level entry if not exists
                if file_id not in file_transfers:
                    file_transfers[file_id] = {
                        "file_id": file_id,
                        "user_id": user_id,
                        "total_size_bytes": 0,
                        "chunks": [],
                        "start_time": transfer.start_time,
                        "end_time": transfer.end_time,
                        "successful_chunks": 0,
                        "failed_chunks": 0,
                        "total_latency_ms": 0.0,
                        "total_throughput_mbps": 0.0,
                        "chunk_count": 0
                    }
                
                file_transfer = file_transfers[file_id]
                
                # Update earliest start time and latest end time
                if transfer.start_time < file_transfer["start_time"]:
                    file_transfer["start_time"] = transfer.start_time
                if transfer.end_time and (file_transfer["end_time"] is None or transfer.end_time > file_transfer["end_time"]):
                    file_transfer["end_time"] = transfer.end_time
                
                # Add chunk details
                transfer_dict = transfer.to_dict()
                latency = transfer_dict.get("latency_ms")
                throughput = transfer_dict.get("throughput_mbps")
                
                if latency is None and transfer.duration_seconds:
                    latency = transfer.duration_seconds * 1000
                if throughput is None and transfer.duration_seconds and transfer.duration_seconds > 0:
                    throughput = (transfer.file_size_bytes * 8) / (transfer.duration_seconds * 1000000)
                
                chunk_data = {
                    "chunk_id": transfer.transfer_id,  # Use transfer_id as chunk identifier
                    "size_bytes": transfer.file_size_bytes,
                    "latency_ms": latency if latency is not None else 0.0,
                    "throughput_mbps": throughput if throughput is not None else 0.0,
                    "success": transfer.success,
                    "source_node": transfer.source_node,
                    "target_node": transfer.target_node,
                    "start_time": transfer.start_time.isoformat() if transfer.start_time else None,
                    "duration_ms": transfer.duration_seconds * 1000 if transfer.duration_seconds else 0.0
                }
                file_transfer["chunks"].append(chunk_data)
                
                # Aggregate file-level metrics
                file_transfer["total_size_bytes"] += transfer.file_size_bytes
                file_transfer["chunk_count"] += 1
                if transfer.success:
                    file_transfer["successful_chunks"] += 1
                    file_transfer["total_latency_ms"] += (latency if latency is not None else 0.0)
                    file_transfer["total_throughput_mbps"] += (throughput if throughput is not None else 0.0)
                else:
                    file_transfer["failed_chunks"] += 1
                    
            except Exception as e:
                print(f"Error processing transfer {transfer.transfer_id} for aggregation: {e}")
                continue
        
        # Convert to list and calculate averages
        result = []
        for file_id, file_data in file_transfers.items():
            successful_chunks = file_data["successful_chunks"]
            total_chunks = file_data["chunk_count"]
            
            # Calculate average latency and throughput (only from successful chunks)
            avg_latency = file_data["total_latency_ms"] / successful_chunks if successful_chunks > 0 else 0.0
            avg_throughput = file_data["total_throughput_mbps"] / successful_chunks if successful_chunks > 0 else 0.0
            
            # Overall success (all chunks succeeded)
            overall_success = file_data["failed_chunks"] == 0
            
            result.append({
                "file_id": file_id,
                "user_id": file_data["user_id"],
                "file_size_bytes": file_data["total_size_bytes"],
                "file_size_gb": round(file_data["total_size_bytes"] / (1024**3), 4),
                "latency_ms": round(avg_latency, 2),
                "throughput_mbps": round(avg_throughput, 2),
                "start_time": file_data["start_time"].isoformat() if hasattr(file_data["start_time"], 'isoformat') else str(file_data["start_time"]),
                "success": overall_success,
                "chunk_count": total_chunks,
                "successful_chunks": successful_chunks,
                "failed_chunks": file_data["failed_chunks"],
                "chunks": sorted(file_data["chunks"], key=lambda c: c.get("start_time", ""))  # Sort chunks by start time
            })
        
        # Sort by start_time (most recent first)
        result.sort(key=lambda x: x.get("start_time", ""), reverse=True)
        
        return result[:limit]
    
    def get_user_metrics(self, username: Optional[str] = None) -> Dict:
        """
        Get metrics aggregated by user
        
        Args:
            username: Optional username to filter by, or None for all users
            
        Returns:
            Dictionary with user metrics
        """
        with self.collection_lock:
            transfers = list(self.transfer_metrics.values())
        
        # Filter by user if specified
        if username:
            transfers = [t for t in transfers if t.user_id == username]
        
        # Aggregate user metrics
        user_stats = {}
        for transfer in transfers:
            if not transfer.user_id:
                continue
            
            user_id = transfer.user_id
            if user_id not in user_stats:
                user_stats[user_id] = {
                    "username": user_id,
                    "total_transfers": 0,
                    "successful_transfers": 0,
                    "failed_transfers": 0,
                    "total_data_transferred_bytes": 0,
                    "total_uploads": 0,
                    "total_downloads": 0,
                    "upload_data_bytes": 0,
                    "download_data_bytes": 0
                }
            
            stats = user_stats[user_id]
            stats["total_transfers"] += 1
            stats["total_data_transferred_bytes"] += transfer.file_size_bytes
            
            if transfer.success:
                stats["successful_transfers"] += 1
            else:
                stats["failed_transfers"] += 1
            
            # Determine if upload or download based on source_node
            if transfer.source_node == "backend_api":
                stats["total_uploads"] += 1
                stats["upload_data_bytes"] += transfer.file_size_bytes
            else:
                stats["total_downloads"] += 1
                stats["download_data_bytes"] += transfer.file_size_bytes
        
        # Calculate success rates
        for user_id, stats in user_stats.items():
            if stats["total_transfers"] > 0:
                stats["success_rate_percent"] = (stats["successful_transfers"] / stats["total_transfers"]) * 100
            else:
                stats["success_rate_percent"] = 0.0
        
        if username:
            return user_stats.get(username, {})
        else:
            return {
                "users": list(user_stats.values()),
                "total_users": len(user_stats),
                "total_transfers_all_users": sum(s["total_transfers"] for s in user_stats.values()),
                "total_data_all_users": sum(s["total_data_transferred_bytes"] for s in user_stats.values())
            }
    
    def clear_history(self):
        """Clear all metric history"""
        with self.collection_lock:
            for metric_type in MetricType:
                self.metric_samples[metric_type].clear()
            self.transfer_metrics.clear()
            self.node_metrics_history.clear()
            self.network_metrics_history.clear()
        
        print("[MetricsCollector] History cleared")
    
    def export_metric_samples_to_csv(
        self,
        metric_type: MetricType,
        output_dir: str = "metrics",
        node_id: Optional[str] = None
    ) -> str:
        """
        Export metric samples to CSV file
        
        Args:
            metric_type: Type of metric to export
            output_dir: Output directory (default: "metrics")
            node_id: Optional node ID to filter by
            
        Returns:
            Path to exported CSV file
        """
        os.makedirs(output_dir, exist_ok=True)
        
        samples = self.get_metric_samples(metric_type, node_id=node_id)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        node_suffix = f"_{node_id}" if node_id else ""
        filename = f"metric_samples_{metric_type.value}{node_suffix}_{timestamp}.csv"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', newline='') as csvfile:
            fieldnames = ['timestamp', 'node_id', 'metric_type', 'value', 'unit', 'metadata']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for sample in samples:
                writer.writerow({
                    'timestamp': sample.timestamp.isoformat(),
                    'node_id': sample.node_id or '',
                    'metric_type': sample.metric_type.value,
                    'value': sample.value,
                    'unit': sample.unit,
                    'metadata': json.dumps(sample.metadata)
                })
        
        return filepath
    
    def export_metric_samples_to_json(
        self,
        metric_type: MetricType,
        output_dir: str = "metrics",
        node_id: Optional[str] = None
    ) -> str:
        """
        Export metric samples to JSON file
        
        Args:
            metric_type: Type of metric to export
            output_dir: Output directory (default: "metrics")
            node_id: Optional node ID to filter by
            
        Returns:
            Path to exported JSON file
        """
        os.makedirs(output_dir, exist_ok=True)
        
        samples = self.get_metric_samples(metric_type, node_id=node_id)
        
        # Early return if no samples
        if not samples:
            # Still create an empty file for consistency
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            node_suffix = f"_{node_id}" if node_id else ""
            filename = f"metric_samples_{metric_type.value}{node_suffix}_{timestamp}.json"
            filepath = os.path.join(output_dir, filename)
            data = {
                "export_timestamp": datetime.now().isoformat(),
                "metric_type": metric_type.value,
                "node_id": node_id,
                "sample_count": 0,
                "samples": []
            }
            with open(filepath, 'w') as jsonfile:
                json.dump(data, jsonfile, indent=2)
            return filepath
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        node_suffix = f"_{node_id}" if node_id else ""
        filename = f"metric_samples_{metric_type.value}{node_suffix}_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)
        
        data = {
            "export_timestamp": datetime.now().isoformat(),
            "metric_type": metric_type.value,
            "node_id": node_id,
            "sample_count": len(samples),
            "samples": [s.to_dict() for s in samples]
        }
        
        try:
            with open(filepath, 'w') as jsonfile:
                json.dump(data, jsonfile, indent=2)
        except Exception as e:
            raise Exception(f"Failed to write JSON file {filepath}: {e}")
        
        return filepath
    
    def export_node_metrics_to_csv(
        self,
        node_id: str,
        output_dir: str = "metrics",
        limit: Optional[int] = None
    ) -> str:
        """
        Export node metrics history to CSV file
        
        Args:
            node_id: Node ID to export
            output_dir: Output directory (default: "metrics")
            limit: Maximum number of samples to export
            
        Returns:
            Path to exported CSV file
        """
        os.makedirs(output_dir, exist_ok=True)
        
        metrics = self.get_node_metrics_history(node_id, limit=limit)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"node_metrics_{node_id}_{timestamp}.csv"
        filepath = os.path.join(output_dir, filename)
        
        if not metrics:
            print(f"[MetricsCollector] No metrics found for node {node_id}")
            return filepath
        
        with open(filepath, 'w', newline='') as csvfile:
            fieldnames = list(metrics[0].to_dict().keys())
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for metric in metrics:
                writer.writerow(metric.to_dict())
        
        return filepath
    
    def export_node_metrics_to_json(
        self,
        node_id: str,
        output_dir: str = "metrics",
        limit: Optional[int] = None
    ) -> str:
        """
        Export node metrics history to JSON file
        
        Args:
            node_id: Node ID to export
            output_dir: Output directory (default: "metrics")
            limit: Maximum number of samples to export
            
        Returns:
            Path to exported JSON file
        """
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception:
            pass
        
        try:
            metrics = self.get_node_metrics_history(node_id, limit=limit)
        except Exception:
            metrics = []
        
        # Generate filename with timestamp
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        except Exception:
            timestamp = "unknown"
        filename = f"node_metrics_{node_id}_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)
        
        # Serialize metrics with error handling
        metrics_data = []
        for m in metrics:
            try:
                metrics_data.append(m.to_dict())
            except Exception:
                # Skip problematic metrics
                continue
        
        # Early return if no metrics
        if not metrics_data:
            try:
                export_timestamp = datetime.now().isoformat()
            except Exception:
                export_timestamp = "unknown"
            
            data = {
                "export_timestamp": export_timestamp,
                "node_id": node_id,
                "sample_count": 0,
                "metrics": []
            }
            try:
                with open(filepath, 'w', encoding='utf-8') as jsonfile:
                    json.dump(data, jsonfile, ensure_ascii=False)
            except Exception:
                pass
            return filepath
        
        try:
            export_timestamp = datetime.now().isoformat()
        except Exception:
            export_timestamp = "unknown"
        
        data = {
            "export_timestamp": export_timestamp,
            "node_id": node_id,
            "sample_count": len(metrics_data),
            "metrics": metrics_data
        }
        
        # Write file with error handling - use no indent for faster serialization
        try:
            with open(filepath, 'w', encoding='utf-8') as jsonfile:
                json.dump(data, jsonfile, ensure_ascii=False)
        except Exception:
            # If write fails, return path anyway
            pass
        
        return filepath
    
    def export_network_metrics_to_csv(
        self,
        output_dir: str = "metrics",
        limit: Optional[int] = None
    ) -> str:
        """
        Export network metrics history to CSV file
        
        Args:
            output_dir: Output directory (default: "metrics")
            limit: Maximum number of samples to export
            
        Returns:
            Path to exported CSV file
        """
        os.makedirs(output_dir, exist_ok=True)
        
        metrics = self.get_network_metrics_history(limit=limit)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"network_metrics_{timestamp}.csv"
        filepath = os.path.join(output_dir, filename)
        
        if not metrics:
            print(f"[MetricsCollector] No network metrics found")
            return filepath
        
        with open(filepath, 'w', newline='') as csvfile:
            # Flatten network metrics (excluding node_metrics list)
            fieldnames = [k for k in metrics[0].to_dict().keys() if k != 'node_metrics']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for metric in metrics:
                metric_dict = metric.to_dict()
                # Remove node_metrics from CSV (too complex for flat CSV)
                metric_dict.pop('node_metrics', None)
                writer.writerow(metric_dict)
        
        return filepath
    
    def export_network_metrics_to_json(
        self,
        output_dir: str = "metrics",
        limit: Optional[int] = None
    ) -> str:
        """
        Export network metrics history to JSON file
        
        Args:
            output_dir: Output directory (default: "metrics")
            limit: Maximum number of samples to export
            
        Returns:
            Path to exported JSON file
        """
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception:
            pass
        
        try:
            metrics = self.get_network_metrics_history(limit=limit)
        except Exception:
            metrics = []
        
        # Generate filename with timestamp
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        except Exception:
            timestamp = "unknown"
        filename = f"network_metrics_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)
        
        # Serialize metrics with error handling
        metrics_data = []
        for m in metrics:
            try:
                metrics_data.append(m.to_dict())
            except Exception:
                # Skip problematic metrics
                continue
        
        try:
            export_timestamp = datetime.now().isoformat()
        except Exception:
            export_timestamp = "unknown"
        
        data = {
            "export_timestamp": export_timestamp,
            "sample_count": len(metrics_data),
            "metrics": metrics_data
        }
        
        # Write file with error handling - use no indent for faster serialization
        try:
            with open(filepath, 'w', encoding='utf-8') as jsonfile:
                json.dump(data, jsonfile, ensure_ascii=False)
        except Exception:
            # If write fails, return path anyway
            pass
        
        return filepath
    
    def export_transfer_metrics_to_csv(
        self,
        output_dir: str = "metrics"
    ) -> str:
        """
        Export transfer metrics to CSV file
        
        Args:
            output_dir: Output directory (default: "metrics")
            
        Returns:
            Path to exported CSV file
        """
        os.makedirs(output_dir, exist_ok=True)
        
        with self.collection_lock:
            transfers = list(self.transfer_metrics.values())
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"transfer_metrics_{timestamp}.csv"
        filepath = os.path.join(output_dir, filename)
        
        if not transfers:
            print(f"[MetricsCollector] No transfer metrics found")
            return filepath
        
        with open(filepath, 'w', newline='') as csvfile:
            fieldnames = list(transfers[0].to_dict().keys())
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for transfer in transfers:
                writer.writerow(transfer.to_dict())
        
        return filepath
    
    def export_transfer_metrics_to_json(
        self,
        output_dir: str = "metrics"
    ) -> str:
        """
        Export transfer metrics to JSON file
        
        Args:
            output_dir: Output directory (default: "metrics")
            
        Returns:
            Path to exported JSON file
        """
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception:
            pass
        
        # Get transfers quickly with lock
        transfers = []
        try:
            with self.collection_lock:
                transfers = list(self.transfer_metrics.values())
        except Exception:
            transfers = []
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"transfer_metrics_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)
        
        # Serialize transfers outside of lock - use simple dict conversion
        transfers_data = []
        for t in transfers:
            try:
                # Use direct attribute access instead of to_dict() to avoid any serialization issues
                transfer_dict = {
                    "transfer_id": str(t.transfer_id),
                    "file_id": str(t.file_id),
                    "source_node": str(t.source_node),
                    "target_node": str(t.target_node),
                    "file_size_bytes": int(t.file_size_bytes) if t.file_size_bytes else 0,
                    "start_time": t.start_time.isoformat() if t.start_time else None,
                    "end_time": t.end_time.isoformat() if t.end_time else None,
                    "duration_seconds": float(t.duration_seconds) if t.duration_seconds else None,
                    "throughput_mbps": float(t.throughput_mbps) if t.throughput_mbps else None,
                    "latency_ms": float(t.latency_ms) if t.latency_ms else None,
                    "chunks_transferred": int(t.chunks_transferred) if t.chunks_transferred else 0,
                    "total_chunks": int(t.total_chunks) if t.total_chunks else 0,
                    "success": bool(t.success),
                    "error_message": str(t.error_message) if t.error_message else None
                }
                transfers_data.append(transfer_dict)
            except Exception:
                # Skip problematic transfers
                continue
        
        # Create minimal data structure
        try:
            export_time = datetime.now()
            data = {
                "export_timestamp": export_time.isoformat(),
                "transfer_count": len(transfers_data),
                "transfers": transfers_data
            }
        except Exception:
            # If timestamp fails, use simple string
            data = {
                "export_timestamp": "unknown",
                "transfer_count": len(transfers_data),
                "transfers": transfers_data
            }
        
        # Write file with minimal JSON (no indent to make it faster)
        # Use context manager for automatic cleanup
        try:
            # Open file in write mode - use 'x' mode first to avoid overwriting locked files
            # If that fails, fall back to 'w' mode
            try:
                with open(filepath, 'x', encoding='utf-8') as jsonfile:
                    json.dump(data, jsonfile, ensure_ascii=False)
            except FileExistsError:
                # File exists, use 'w' mode to overwrite
                with open(filepath, 'w', encoding='utf-8') as jsonfile:
                    json.dump(data, jsonfile, ensure_ascii=False)
        except (IOError, OSError, PermissionError, TypeError) as e:
            # Handle specific errors related to file I/O or serialization
            print(f"Error writing to {filepath}: {e}")
            # If write fails, return path anyway
            pass
        
        return filepath
    
    def export_all_metrics(
        self,
        output_dir: str = "metrics",
        format: str = "json"
    ) -> Dict[str, str]:
        """
        Export all metrics to files
        
        Args:
            output_dir: Output directory (default: "metrics")
            format: Export format - "json" or "csv" (default: "json")
            
        Returns:
            Dictionary mapping metric type to file path
        """
        exported_files = {}
        
        # Create output directory once - with timeout protection
        try:
            abs_output_dir = os.path.abspath(output_dir)
            # Use a simple check to avoid hanging on invalid paths
            if not os.path.exists(abs_output_dir):
                os.makedirs(abs_output_dir, exist_ok=True)
        except (OSError, ValueError, Exception) as e:
            # If directory creation fails, return early to avoid hanging
            print(f"Error creating directory {output_dir}: {e}")
            return exported_files

        # Acquire lock - use context manager for safety
        # Note: If this hangs, it means another thread is holding the lock
        try:
            with self.collection_lock:
                has_transfer_metrics = bool(self.transfer_metrics)
                has_network_metrics = bool(self.network_metrics_history)
                nodes_with_metrics = list(self.node_metrics_history.keys())
        except Exception as e:
            print(f"Error acquiring lock: {e}")
            return exported_files

        # Export transfer metrics
        if has_transfer_metrics:
            try:
                if format == "csv":
                    filepath = self.export_transfer_metrics_to_csv(abs_output_dir)
                else:
                    filepath = self.export_transfer_metrics_to_json(abs_output_dir)
                exported_files["transfer_metrics"] = filepath
            except Exception as e:
                print(f"Error exporting transfer metrics: {e}")

        # Export network metrics
        if has_network_metrics:
            try:
                limit = 100  # Export at most 100 recent samples
                if format == "csv":
                    filepath = self.export_network_metrics_to_csv(abs_output_dir, limit=limit)
                else:
                    filepath = self.export_network_metrics_to_json(abs_output_dir, limit=limit)
                exported_files["network_metrics"] = filepath
            except Exception as e:
                print(f"Error exporting network metrics: {e}")

        # Export node metrics
        for node_id in nodes_with_metrics[:10]:  # Limit to first 10 nodes
            try:
                if format == "csv":
                    filepath = self.export_node_metrics_to_csv(node_id, abs_output_dir)
                else:
                    filepath = self.export_node_metrics_to_json(node_id, abs_output_dir)
                exported_files[f"node_metrics_{node_id}"] = filepath
            except Exception as e:
                print(f"Error exporting metrics for node {node_id}: {e}")
        
        return exported_files
    
    def __repr__(self):
        """String representation of MetricsCollector"""
        node_count = self.node_factory.get_node_count() if self.node_factory else 0
        transfer_count = len(self.transfer_metrics)
        return f"MetricsCollector(nodes={node_count}, transfers={transfer_count}, running={self.running})"

