#!/usr/bin/env python3
"""
Script to clear all transfer history records from MetricsCollector
"""
import os
import sys
import io

# Fix Unicode encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add parent directory to path (for backend)
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Add backend to path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
if os.path.exists(backend_dir) and backend_dir not in sys.path:
    sys.path.append(backend_dir)

try:
    # Import the metrics_collector from backend/api.py
    # Note: This will work if the backend is not running, or if we can access the same instance
    import api
    if hasattr(api, 'metrics_collector') and api.metrics_collector:
        with api.metrics_collector.collection_lock:
            count = len(api.metrics_collector.transfer_metrics)
            api.metrics_collector.transfer_metrics.clear()
            api.metrics_collector.throughput_windows.clear()
        print(f"✓ Cleared {count} transfer records from MetricsCollector")
    else:
        print("✗ MetricsCollector not found in backend API")
        sys.exit(1)
except Exception as e:
    print(f"✗ Error clearing transfer history: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

