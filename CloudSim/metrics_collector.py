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
        
        print("[MetricsCollector] Initialized")
    
    def set_node_factory(self, node_factory: NodeFactory):
        """
        Set or update the NodeFactory to collect metrics from
        
        Args:
            node_factory: NodeFactory instance
        """
        self.node_factory = node_factory
        print(f"[MetricsCollector] NodeFactory set ({node_factory.get_node_count()} nodes)")
    
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
            
            node_metrics = NodeMetrics(
                node_id=node_id,
                timestamp=datetime.now(),
                throughput_mbps=0.0,  # Will be calculated from transfer metrics
                average_latency_ms=0.0,  # Will be calculated from transfer metrics
                average_rtt_ms=0.0,  # Will be calculated from transfer metrics
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
        total_storage_util = 0.0
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
                total_storage_util += node_metrics.storage_utilization_percent
                total_network_util += node_metrics.network_utilization_percent
                total_transfers += node_metrics.total_transfers
                total_successful += node_metrics.successful_transfers
                total_failed += node_metrics.failed_transfers
                total_data += node_metrics.total_data_transferred_bytes
                total_active += node_metrics.active_transfers
        
        node_count = len(node_metrics_list)
        
        # Calculate averages
        network_metrics = NetworkMetrics(
            timestamp=datetime.now(),
            total_nodes=node_count,
            total_throughput_mbps=total_throughput,
            average_latency_ms=total_latency / node_count if node_count > 0 else 0.0,
            average_rtt_ms=total_rtt / node_count if node_count > 0 else 0.0,
            total_storage_utilization_percent=total_storage_util / node_count if node_count > 0 else 0.0,
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
        total_chunks: int
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
        transfer_metrics = TransferMetrics(
            transfer_id=transfer_id,
            file_id=file_id,
            source_node=source_node,
            target_node=target_node,
            file_size_bytes=file_size_bytes,
            start_time=datetime.now(),
            total_chunks=total_chunks
        )
        
        with self.collection_lock:
            self.transfer_metrics[transfer_id] = transfer_metrics
    
    def record_transfer_end(
        self,
        transfer_id: str,
        success: bool,
        chunks_transferred: int = 0,
        error_message: Optional[str] = None
    ):
        """
        Record the end of a file transfer
        
        Args:
            transfer_id: Transfer identifier
            success: Whether transfer was successful
            chunks_transferred: Number of chunks transferred
            error_message: Error message if transfer failed
        """
        with self.collection_lock:
            if transfer_id not in self.transfer_metrics:
                return
            
            transfer = self.transfer_metrics[transfer_id]
            transfer.end_time = datetime.now()
            transfer.duration_seconds = (transfer.end_time - transfer.start_time).total_seconds()
            transfer.chunks_transferred = chunks_transferred
            transfer.success = success
            transfer.error_message = error_message
            
            # Calculate throughput if successful
            if success and transfer.duration_seconds > 0:
                transfer.throughput_mbps = (
                    transfer.file_size_bytes / (1024 * 1024) / transfer.duration_seconds
                )
            
            # Record metric samples
            if success:
                self._record_metric_sample(
                    MetricType.THROUGHPUT,
                    transfer.throughput_mbps if transfer.throughput_mbps else 0.0,
                    "MB/s",
                    node_id=transfer.target_node,
                    metadata={"transfer_id": transfer_id, "file_id": transfer.file_id}
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
    
    def clear_history(self):
        """Clear all metric history"""
        with self.collection_lock:
            for metric_type in MetricType:
                self.metric_samples[metric_type].clear()
            self.transfer_metrics.clear()
            self.node_metrics_history.clear()
            self.network_metrics_history.clear()
        
        print("[MetricsCollector] History cleared")
    
    def __repr__(self):
        """String representation of MetricsCollector"""
        node_count = self.node_factory.get_node_count() if self.node_factory else 0
        transfer_count = len(self.transfer_metrics)
        return f"MetricsCollector(nodes={node_count}, transfers={transfer_count}, running={self.running})"

