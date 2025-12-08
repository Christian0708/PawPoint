from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Body
from pydantic import BaseModel
from typing import Optional
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import os
import sys
import socket
import time
import json
import hashlib
from collections import deque

# Ensure CloudSim module path is available
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'CloudSim'))
if os.path.exists(base_dir) and base_dir not in sys.path:
    sys.path.append(base_dir)

from config_loader import ConfigLoader
from node_factory import NodeFactory
from metrics_collector import MetricsCollector
from capacity_evaluator import CapacityEvaluator
from storage_virtual_node import StorageVirtualNode
# Note: NetworkService is NOT imported here - use gRPC cloudrpc server for network operations

# Import gRPC client to use cloudrpc server
import grpc
import sys
cloudrpc_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'cloudrpc'))
if os.path.exists(cloudrpc_dir) and cloudrpc_dir not in sys.path:
    sys.path.append(cloudrpc_dir)
import cloudsim_pb2
import cloudsim_pb2_grpc

app = FastAPI(title="CloudSim REST Gateway (gRPC-backed)")

loader = ConfigLoader(os.path.join(base_dir, 'config.yaml'))
loader.load()
start_port = loader.get("node_factory.start_port", 5000)
port_range = loader.get("node_factory.port_range_size", 1000)
storage_root = os.path.abspath(loader.get("storage.base_directory", "storage"))
state_file = loader.get("nodes_state_file", "nodes_state.json")
# Use absolute path to ensure we use the same state file as CLI
if not os.path.isabs(state_file):
    state_file = os.path.join(base_dir, state_file)
factory = NodeFactory(start_port=start_port, port_range_size=port_range, state_file=state_file, storage_base_dir=storage_root)

# Network service is handled by gRPC cloudrpc server ONLY
# Do NOT create a duplicate NetworkService here - it causes port conflicts on port 9999
# All network operations should go through gRPC endpoints

# Initialize metrics and capacity evaluators
metrics_collector = MetricsCollector(factory)
capacity_evaluator = CapacityEvaluator(factory)

# ==================== NETWORK CLIENT HELPERS ====================
# These functions allow the backend to act as a client and send/receive data
# over the network to nodes, simulating a real cloud storage system

def send_chunk_to_node_via_network(node_host: str, node_port: int, file_id: str, 
                                   chunk_id: int, chunk_data: bytes) -> bool:
    """
    Send a chunk to a node over TCP network (cloud simulation)
    
    Args:
        node_host: Host address of target node
        node_port: Port number of target node
        file_id: Unique file identifier
        chunk_id: Chunk index
        chunk_data: Chunk binary data
        
    Returns:
        bool: True if chunk sent successfully, False otherwise
    """
    client_socket = None
    try:
        # Connect to node
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        client_socket.settimeout(10.0)  # 10 second timeout
        client_socket.connect((node_host, node_port))
        
        # Calculate checksum
        checksum = hashlib.md5(chunk_data).hexdigest()
        
        # Create chunk data message (following NetworkManager protocol)
        chunk_message = {
            "type": "CHUNK_DATA",
            "file_id": file_id,
            "chunk_id": chunk_id,
            "chunk_size": len(chunk_data),
            "checksum": checksum,
            "timestamp": time.time(),
            "sender_node_id": "backend_api"  # Backend acts as client
        }
        
        # Send message header (length-prefixed JSON)
        json_data = json.dumps(chunk_message).encode('utf-8')
        length_header = len(json_data).to_bytes(4, byteorder='big')
        client_socket.sendall(length_header)
        client_socket.sendall(json_data)
        
        # Send chunk data
        client_socket.sendall(chunk_data)
        
        # Wait for acknowledgment
        client_socket.settimeout(5.0)
        length_header = client_socket.recv(4)
        if len(length_header) != 4:
            return False
        
        msg_length = int.from_bytes(length_header, byteorder='big')
        json_bytes = client_socket.recv(msg_length)
        if len(json_bytes) != msg_length:
            return False
        
        ack = json.loads(json_bytes.decode('utf-8'))
        if ack.get('type') == 'CHUNK_ACK' and ack.get('success') and ack.get('file_id') == file_id:
            print(f"[NETWORK-UPLOAD] Chunk {chunk_id} sent to {node_host}:{node_port} successfully")
            return True
        else:
            print(f"[NETWORK-UPLOAD] Chunk {chunk_id} acknowledgment failed: {ack}")
            return False
            
    except socket.timeout:
        print(f"[NETWORK-UPLOAD] Timeout sending chunk {chunk_id} to {node_host}:{node_port}")
        return False
    except ConnectionRefusedError:
        print(f"[NETWORK-UPLOAD] Connection refused by {node_host}:{node_port}")
        return False
    except Exception as e:
        print(f"[NETWORK-UPLOAD] Error sending chunk {chunk_id} to {node_host}:{node_port}: {e}")
        return False
    finally:
        if client_socket:
            try:
                client_socket.close()
            except:
                pass

def request_chunk_from_node_via_network(node_host: str, node_port: int, file_id: str, 
                                        chunk_id: int) -> Optional[bytes]:
    """
    Request a chunk from a node over TCP network (cloud simulation)
    
    Args:
        node_host: Host address of source node
        node_port: Port number of source node
        file_id: Unique file identifier
        chunk_id: Chunk index
        
    Returns:
        bytes: Chunk data if successful, None otherwise
    """
    client_socket = None
    try:
        # Connect to node
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        client_socket.settimeout(3.0)  # Shorter timeout for faster failure
        client_socket.connect((node_host, node_port))
        
        # Create chunk request message
        request_message = {
            "type": "CHUNK_REQUEST",
            "file_id": file_id,
            "chunk_id": chunk_id,
            "timestamp": time.time(),
            "sender_node_id": "backend_api"
        }
        print(f"[NETWORK-DOWNLOAD] Sending CHUNK_REQUEST to {node_host}:{node_port} for file_id={file_id}, chunk_id={chunk_id}")
        
        # Send request
        json_data = json.dumps(request_message).encode('utf-8')
        length_header = len(json_data).to_bytes(4, byteorder='big')
        client_socket.sendall(length_header)
        client_socket.sendall(json_data)
        
        # Receive chunk data message or error
        client_socket.settimeout(5.0)  # Reasonable timeout
        try:
            length_header = client_socket.recv(4)
            if len(length_header) != 4:
                print(f"[NETWORK-DOWNLOAD] Failed to receive length header for chunk {chunk_id}")
                return None
            
            msg_length = int.from_bytes(length_header, byteorder='big')
            if msg_length > 10 * 1024 * 1024:  # Sanity check: max 10MB message
                print(f"[NETWORK-DOWNLOAD] Message too large: {msg_length} bytes")
                return None
            
            json_bytes = b''
            while len(json_bytes) < msg_length:
                chunk = client_socket.recv(min(8192, msg_length - len(json_bytes)))
                if not chunk:
                    print(f"[NETWORK-DOWNLOAD] Connection closed while receiving message")
                    return None
                json_bytes += chunk
            
            chunk_info = json.loads(json_bytes.decode('utf-8'))
            
            # Handle error response (chunk not found)
            if chunk_info.get('type') == 'ERROR':
                print(f"[NETWORK-DOWNLOAD] Chunk {chunk_id} not found on {node_host}:{node_port}: {chunk_info.get('error_message', '')}")
                return None
            
            # Must be CHUNK_DATA message
            if chunk_info.get('type') != 'CHUNK_DATA' or chunk_info.get('file_id') != file_id:
                print(f"[NETWORK-DOWNLOAD] Unexpected message type: {chunk_info.get('type')}, expected CHUNK_DATA")
                return None
        except socket.timeout:
            print(f"[NETWORK-DOWNLOAD] Timeout receiving message for chunk {chunk_id}")
            return None
        except Exception as e:
            print(f"[NETWORK-DOWNLOAD] Error receiving message for chunk {chunk_id}: {e}")
            return None
        
        chunk_size = chunk_info.get('chunk_size', 0)
        expected_checksum = chunk_info.get('checksum', '')
        
        # Receive chunk data
        chunk_data = b''
        client_socket.settimeout(10.0)  # Longer timeout for receiving data
        try:
            while len(chunk_data) < chunk_size:
                remaining = chunk_size - len(chunk_data)
                data = client_socket.recv(min(8192, remaining))
                if not data:
                    print(f"[NETWORK-DOWNLOAD] Connection closed while receiving chunk data (got {len(chunk_data)}/{chunk_size} bytes)")
                    return None
                chunk_data += data
            
            # Verify checksum
            actual_checksum = hashlib.md5(chunk_data).hexdigest()
            if actual_checksum != expected_checksum:
                print(f"[NETWORK-DOWNLOAD] Checksum mismatch for chunk {chunk_id} (expected {expected_checksum}, got {actual_checksum})")
                return None
            
            # Send acknowledgment
            ack = {
                "type": "CHUNK_ACK",
                "file_id": file_id,
                "chunk_id": chunk_id,
                "success": True,
                "checksum_verified": True,
                "timestamp": time.time()
            }
            ack_json = json.dumps(ack).encode('utf-8')
            ack_length = len(ack_json).to_bytes(4, byteorder='big')
            client_socket.sendall(ack_length)
            client_socket.sendall(ack_json)
            
            print(f"[NETWORK-DOWNLOAD] Chunk {chunk_id} received from {node_host}:{node_port} ({len(chunk_data)} bytes)")
            return chunk_data
        except socket.timeout:
            print(f"[NETWORK-DOWNLOAD] Timeout receiving chunk data for chunk {chunk_id}")
            return None
        except Exception as e:
            print(f"[NETWORK-DOWNLOAD] Error receiving chunk data for chunk {chunk_id}: {e}")
            return None
        
    except socket.timeout:
        print(f"[NETWORK-DOWNLOAD] Timeout requesting chunk {chunk_id} from {node_host}:{node_port}")
        return None
    except ConnectionRefusedError:
        print(f"[NETWORK-DOWNLOAD] Connection refused by {node_host}:{node_port}")
        return None
    except Exception as e:
        print(f"[NETWORK-DOWNLOAD] Error requesting chunk {chunk_id} from {node_host}:{node_port}: {e}")
        return None
    finally:
        if client_socket:
            try:
                client_socket.close()
            except:
                pass

# gRPC client connection to cloudrpc server
grpc_channel = None
grpc_stub = None
grpc_port = 50051

def get_grpc_stub():
    """Get or create gRPC stub connection to cloudrpc server"""
    global grpc_channel, grpc_stub
    if grpc_channel is None or grpc_stub is None:
        try:
            grpc_channel = grpc.insecure_channel(f'localhost:{grpc_port}')
            grpc_stub = cloudsim_pb2_grpc.CloudSimStub(grpc_channel)
            # Test connection
            grpc_channel.subscribe(lambda x: None, try_to_connect=True)
        except Exception as e:
            print(f"Warning: Could not connect to gRPC server on port {grpc_port}: {e}")
            print("REST API will use direct factory calls instead")
            return None
    return grpc_stub

# AuthService gRPC client connection
auth_grpc_channel = None
auth_grpc_stub = None
auth_grpc_port = 51234  # AuthService port

# Import AuthService protobuf modules ONCE at startup to avoid duplicate symbol errors
auth_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'AuthService'))
if auth_dir not in sys.path:
    sys.path.insert(0, auth_dir)

# Import with try/except to handle missing modules gracefully
try:
    import cloudsecurity_pb2 as auth_pb2
    import cloudsecurity_pb2_grpc as auth_grpc
    AUTH_SERVICE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: AuthService protobuf modules not found: {e}")
    AUTH_SERVICE_AVAILABLE = False
    auth_pb2 = None
    auth_grpc = None

def get_auth_stub():
    """Get or create gRPC stub connection to AuthService"""
    global auth_grpc_channel, auth_grpc_stub
    
    if not AUTH_SERVICE_AVAILABLE:
        return None
        
    if auth_grpc_channel is None or auth_grpc_stub is None:
        try:
            auth_grpc_channel = grpc.insecure_channel(f'localhost:{auth_grpc_port}')
            auth_grpc_stub = auth_grpc.UserServiceStub(auth_grpc_channel)
        except Exception as e:
            print(f"Warning: Could not connect to AuthService on port {auth_grpc_port}: {e}")
            return None
    return auth_grpc_stub

# Pydantic models for auth requests
class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    quota_gb: Optional[int] = 1  # Default 1GB free quota

class LoginRequest(BaseModel):
    username: str
    password: str

class VerifyOtpRequest(BaseModel):
    username: str
    pending_id: str
    otp: str

class ProfileRequest(BaseModel):
    username: str

# Serve frontend static apps
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
client_dir = os.path.join(root_dir, 'frontend', 'apps', 'client', 'public')
provider_dir = os.path.join(root_dir, 'frontend', 'apps', 'provider', 'public')
if os.path.isdir(client_dir):
    app.mount('/client', StaticFiles(directory=client_dir, html=True), name='client')
if os.path.isdir(provider_dir):
    app.mount('/provider', StaticFiles(directory=provider_dir, html=True), name='provider')


@app.get("/status")
def get_status():
    """Get system status - uses gRPC cloudrpc server"""
    stub = get_grpc_stub()
    if stub:
        try:
            response = stub.GetStatus(cloudsim_pb2.StatusRequest())
            return {
                "total_nodes": response.total_nodes,
                "running_nodes": response.running_nodes,
                "stopped_nodes": response.stopped_nodes,
                "nodes": [
                    {
                        "node_id": n.node_id,
                        "host": n.host,
                        "port": n.port,
                        "running": n.running,
                        "storage_utilization_percent": n.storage_utilization_percent,
                        "files_stored": n.files_stored,
                        "ip_address": n.ip_address,
                        "mac_address": n.mac_address
                    }
                    for n in response.nodes
                ]
            }
        except Exception as e:
            print(f"gRPC call failed, falling back to direct: {e}")
    
    # Fallback to direct factory access if gRPC unavailable
    nodes = []
    for node_id, node in factory.nodes.items():
        host = node.host
        port = node.port
        running = bool(getattr(node, 'running', False))
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.3)
            s.connect((host, port))
            s.close()
            running = True
        except Exception:
            pass
        su = 0.0
        fc = 0
        try:
            storage_util = node.get_storage_utilization()
            su = float(storage_util.get('utilization_percent', 0.0))
            fc = int(storage_util.get('files_stored', 0))
        except Exception:
            pass
        ip_address = getattr(node, 'ip_address', '')
        mac_address = getattr(node, 'mac_address', '')
        nodes.append({
            "node_id": node_id,
            "host": host,
            "port": port,
            "running": running,
            "storage_utilization_percent": su,
            "files_stored": fc,
            "ip_address": ip_address,
            "mac_address": mac_address
        })
    return {
        "total_nodes": len(nodes),
        "running_nodes": sum(1 for n in nodes if n["running"]),
        "stopped_nodes": sum(1 for n in nodes if not n["running"]),
        "nodes": nodes
    }


@app.get("/test/imports")
def test_imports():
    """Test endpoint to verify imports work"""
    try:
        test_node = StorageVirtualNode(
            node_id="test",
            cpu_capacity=1,
            memory_capacity=1,
            storage_capacity=1,
            bandwidth=10,
            host="localhost",
            port=9998,
            enable_network_check=False,
            storage_root=os.path.abspath(loader.get("storage.base_directory", "storage"))
        )
        return {"ok": True, "message": "StorageVirtualNode import and creation successful"}
    except Exception as e:
        import traceback
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e), "traceback": traceback.format_exc()}
        )

@app.post("/nodes/{node_id}/start")
def start_node(node_id: str):
    """Start a node - uses gRPC cloudrpc server"""
    stub = get_grpc_stub()
    if stub:
        try:
            response = stub.StartNode(cloudsim_pb2.NodeRequest(node_id=node_id, force=False))
            if response.ok:
                return {"ok": True, "message": response.message}
            else:
                raise HTTPException(status_code=500, detail=response.message)
        except Exception as e:
            print(f"gRPC call failed, falling back to direct: {e}")
    
    # Fallback to direct implementation
    node = factory.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="node not found")
    
    # Check if already running
    if node.is_alive() or node.running:
        return {"ok": True, "message": "node already running"}
    
    # Node is stopped - need to recreate it
    config = factory.node_configs.get(node_id, {})
    if not config:
        raise HTTPException(status_code=404, detail="node configuration not found")
    
    # Remove old node instance
    if node_id in factory.nodes:
        old_node = factory.nodes[node_id]
        try:
            if old_node.is_alive():
                old_node.stop(graceful=False, timeout=1.0)
                old_node.join(timeout=2.0)
        except Exception:
            pass
        del factory.nodes[node_id]
    
    time.sleep(0.5)
    
    storage_root = os.path.abspath(loader.get("storage.base_directory", "storage"))
    new_node = StorageVirtualNode(
        node_id=node_id,
        cpu_capacity=config.get('cpu_capacity', 2),
        memory_capacity=config.get('memory_capacity', 4),
        storage_capacity=config.get('storage_capacity', 10),
        bandwidth=config.get('bandwidth', 100),
        host=config.get('host', 'localhost'),
        port=config.get('port', 5000),
        enable_network_check=config.get('enable_network_check', True),
        storage_root=storage_root
    )
    
    # Update IP and MAC addresses in config
    config['ip_address'] = new_node.ip_address
    config['mac_address'] = new_node.mac_address
    
    factory.nodes[node_id] = new_node
    new_node.start()
    
    return {"ok": True, "message": "started"}


@app.get("/files")
def list_files():
    try:
        nodes = factory.get_all_nodes()
        seen = {}
        for node in nodes:
            try:
                for fname in os.listdir(node.chunks_path):
                    if fname.endswith('.bin') and '_chunk_' in fname:
                        fid = fname.split('_chunk_')[0]
                        idx_part = fname.split('_chunk_')[-1].split('.bin')[0]
                        try:
                            idx = int(idx_part)
                        except Exception:
                            idx = 0
                        entry = seen.get(fid)
                        if not entry:
                            entry = {"file_id": fid, "nodes": set(), "chunks": set(), "size_bytes": 0}
                            seen[fid] = entry
                        entry["nodes"].add(node.node_id)
                        entry["chunks"].add(idx)
                        p = os.path.join(node.chunks_path, fname)
                        try:
                            entry["size_bytes"] += os.path.getsize(p)
                        except Exception:
                            pass
            except Exception:
                continue
        files = []
        for fid, entry in seen.items():
            files.append({
                "file_id": fid,
                "nodes": sorted(list(entry["nodes"])),
                "chunks": len(entry["chunks"]),
                "size_bytes": entry["size_bytes"],
            })
        return {"files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/nodes/{node_id}/stop")
def stop_node(node_id: str, force: bool = False):
    """Stop a node - uses gRPC cloudrpc server"""
    stub = get_grpc_stub()
    if stub:
        try:
            response = stub.StopNode(cloudsim_pb2.NodeRequest(node_id=node_id, force=force))
            if response.ok:
                return {"ok": True, "message": response.message}
            else:
                raise HTTPException(status_code=500, detail=response.message)
        except Exception as e:
            print(f"gRPC call failed, falling back to direct: {e}")
    
    # Fallback to direct implementation
    node = factory.get_node(node_id)
    if node and (node.is_alive() or node.running):
        try:
            node.stop(graceful=True, timeout=5.0)
            node.join(timeout=3.0)
            return {"ok": True, "message": "stopped"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    cfg = factory.node_configs.get(node_id, {})
    host = cfg.get('host', 'localhost')
    port = int(cfg.get('port', 0) or 0)
    if not port:
        raise HTTPException(status_code=400, detail="no port configured")
    try:
        import json
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        s.connect((host, port))
        msg = { 'type': 'SHUTDOWN', 'reason': 'rest_stop', 'timestamp': time.time(), 'sender_node_id': 'rest' }
        data = json.dumps(msg).encode('utf-8')
        s.sendall(len(data).to_bytes(4, byteorder='big'))
        s.sendall(data)
        try:
            s.close()
        except Exception:
            pass
        deadline = time.time() + (15.0 if force else 5.0)
        while time.time() < deadline:
            try:
                chk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                chk.settimeout(0.5)
                chk.connect((host, port))
                chk.close()
                time.sleep(0.5)
                continue
            except Exception:
                return {"ok": True, "message": "stopped remotely"}
        raise HTTPException(status_code=500, detail="remote shutdown failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/files")
def upload_file(file: UploadFile = File(...), replication: int | None = Form(None), user: str = Form("")):
    try:
        data = file.file.read()
        file_size = len(data)
        
        # Reload factory state to get latest node instances
        factory._load_state(verbose=False)
        nodes = factory.get_all_nodes()
        
        print(f"[UPLOAD-DEBUG] Factory nodes after reload: {len(nodes)}")
        print(f"[UPLOAD-DEBUG] Node configs: {list(factory.node_configs.keys())}")
        
        if not nodes:
            raise HTTPException(status_code=400, detail="No nodes available. Create nodes first from the provider portal.")
        
        # Check if nodes are running by verifying socket connection
        # (Nodes started via gRPC may not be in this factory's node instances)
        running_nodes = []
        for node_id, node_config in factory.node_configs.items():
            try:
                node_host = node_config.get('host', 'localhost')
                node_port = node_config.get('port', 5000)
                # Verify node is listening on its port
                test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_socket.settimeout(0.5)
                test_socket.connect((node_host, node_port))
                test_socket.close()
                # Node is running - find or create node object for this config
                if node_id in factory.nodes:
                    running_nodes.append(factory.nodes[node_id])
                else:
                    # Create a temporary node object for network operations
                    # We'll use the config to send chunks
                    running_nodes.append({'node_id': node_id, 'host': node_host, 'port': node_port})
            except Exception:
                pass
        
        if not running_nodes:
            raise HTTPException(status_code=400, detail="No nodes are running. Start nodes first from the provider portal.")
        
        # Get replication factor from config (default 3 for fault tolerance)
        try:
            default_replication = int(loader.get("replication.default_factor", 3))
            min_replication = int(loader.get("replication.min_factor", 2))
        except Exception:
            default_replication = 3
            min_replication = 2
        
        chosen_rep = replication if replication is not None else default_replication
        # Ensure minimum replication for fault tolerance
        rep_factor = max(min_replication, min(int(chosen_rep or default_replication), len(running_nodes)))
        
        import hashlib, time as t
        file_name = file.filename or "upload.bin"
        file_id = hashlib.md5(f"{file_name}-{t.time()}".encode()).hexdigest()
        
        # Calculate chunk size (256KB to 1MB for better distribution)
        chunk_size = max(256 * 1024, min(1024 * 1024, file_size // max(1, len(running_nodes))))
        if chunk_size > file_size:
            chunk_size = file_size
        num_chunks = max(1, (file_size + chunk_size - 1) // chunk_size)
        
        # Filter out full nodes before distribution
        # Check capacity for each running node
        available_nodes = []
        for node in running_nodes:
            try:
                if isinstance(node, dict):
                    # Temporary node object - we can't check capacity directly
                    # Will rely on node rejecting the chunk if full
                    available_nodes.append(node)
                else:
                    # Real node object - check storage capacity
                    storage_util = node.get_storage_utilization()
                    available_bytes = storage_util.get('total_bytes', 0) - storage_util.get('used_bytes', 0)
                    utilization_percent = storage_util.get('utilization_percent', 0.0)
                    
                    # Consider node available if it has at least 1MB free and is under 99% full
                    if available_bytes >= 1024 * 1024 and utilization_percent < 99.0:
                        available_nodes.append(node)
                    else:
                        print(f"[UPLOAD] Skipping node {node.node_id}: {utilization_percent:.1f}% full, {available_bytes} bytes available")
            except Exception as e:
                print(f"[UPLOAD] Error checking capacity for node: {e}, including it anyway")
                available_nodes.append(node)  # Include on error to avoid blocking uploads
        
        if not available_nodes:
            raise HTTPException(status_code=400, detail="No nodes with available storage. All nodes are full or nearly full.")
        
        if len(available_nodes) < rep_factor:
            print(f"[UPLOAD] Warning: Only {len(available_nodes)} nodes available, but replication factor is {rep_factor}. Reducing replication to {len(available_nodes)}")
            rep_factor = len(available_nodes)
        
        # Distribute chunks across available nodes using round-robin with offset
        # This ensures even distribution across all available running nodes
        assigned = []
        node_ids_used = set()
        # Create node_id mapping for chunks_per_node
        node_ids_list = []
        for n in available_nodes:
            if isinstance(n, dict):
                node_ids_list.append(n.get('node_id', 'unknown'))
            else:
                node_ids_list.append(n.node_id)
        chunks_per_node = {node_id: 0 for node_id in node_ids_list}
        
        for i in range(num_chunks):
            targets = []
            # Start from different node for each chunk to spread load
            start_idx = i % len(available_nodes)
            for r in range(rep_factor):
                node_idx = (start_idx + r) % len(available_nodes)
                node = available_nodes[node_idx]
                targets.append(node)
                # Get node_id
                if isinstance(node, dict):
                    node_id = node.get('node_id', 'unknown')
                else:
                    node_id = node.node_id
                node_ids_used.add(node_id)
                chunks_per_node[node_id] += 1
            assigned.append(targets)
        
        # Send chunks to assigned nodes via network (cloud simulation)
        # Check network status via gRPC
        
        # Check network status via gRPC
        try:
            stub = get_grpc_stub()
            if stub:
                net_status = stub.GetNetworkStatus(cloudsim_pb2.NetworkRequest())
                if not net_status.running:
                    print(f"[UPLOAD] Warning: Network service reports not running, but proceeding with upload")
                    # Don't block upload - nodes can receive chunks directly
        except Exception as e:
            print(f"Warning: Could not verify network status: {e}, proceeding anyway")
        
        # Record transfer start for metrics
        import uuid
        transfer_id = str(uuid.uuid4())
        upload_start_time = time.time()
        
        # Record transfer start for each target node
        for idx in range(num_chunks):
            for tgt in assigned[idx]:
                if isinstance(tgt, dict):
                    tgt_node_id = tgt.get('node_id', 'unknown')
                else:
                    tgt_node_id = tgt.node_id
                
                chunk_transfer_id = f"{transfer_id}_chunk_{idx}_to_{tgt_node_id}"
                chunk_size_bytes = len(data[idx*chunk_size:(idx+1)*chunk_size])
                print(f"[UPLOAD] Recording transfer start: {chunk_transfer_id}, user={user}, size={chunk_size_bytes}")
                metrics_collector.record_transfer_start(
                    transfer_id=chunk_transfer_id,
                    file_id=file_id,
                    source_node="backend_api",
                    target_node=tgt_node_id,
                    file_size_bytes=chunk_size_bytes,
                    total_chunks=1,
                    user_id=user if user else None
                )
        
        # Send chunks over network
        failed_chunks = []
        chunk_timings = {}  # Track timing for each chunk transfer
        
        for idx in range(num_chunks):
            chunk = data[idx*chunk_size:(idx+1)*chunk_size]
            for tgt in assigned[idx]:
                # Get node host and port
                if isinstance(tgt, dict):
                    # Temporary node object from config
                    node_host = tgt.get('host', 'localhost')
                    node_port = tgt.get('port', 5000)
                    tgt_node_id = tgt.get('node_id', 'unknown')
                else:
                    # Actual node object
                    node_config = factory.node_configs.get(tgt.node_id, {})
                    node_host = node_config.get('host', 'localhost')
                    node_port = node_config.get('port', 5000)
                    tgt_node_id = tgt.node_id
                
                # Record chunk transfer start time
                chunk_start_time = time.time()
                chunk_transfer_id = f"{transfer_id}_chunk_{idx}_to_{tgt_node_id}"
                
                # Send chunk via network
                success = send_chunk_to_node_via_network(node_host, node_port, file_id, idx, chunk)
                
                # Record chunk transfer end time and metrics
                chunk_end_time = time.time()
                chunk_duration = (chunk_end_time - chunk_start_time) * 1000  # Convert to ms
                
                if success:
                    # Calculate throughput (MB/s)
                    throughput_mbps = (chunk_size_bytes * 8) / (chunk_duration / 1000) / 1000000 if chunk_duration > 0 else 0
                    
                    print(f"[UPLOAD] Recording transfer end: {chunk_transfer_id}, duration={chunk_duration}ms, success=True")
                    metrics_collector.record_transfer_end(
                        transfer_id=chunk_transfer_id,
                        success=True,
                        chunks_transferred=1,
                        first_chunk_latency_ms=chunk_duration,
                        average_chunk_rtt_ms=chunk_duration
                    )
                    # Verify it was recorded
                    with metrics_collector.collection_lock:
                        if chunk_transfer_id in metrics_collector.transfer_metrics:
                            transfer = metrics_collector.transfer_metrics[chunk_transfer_id]
                            print(f"[UPLOAD] ✓ Transfer recorded: end_time={transfer.end_time}, success={transfer.success}, user_id={transfer.user_id}")
                        else:
                            print(f"[UPLOAD] ✗ ERROR: Transfer {chunk_transfer_id} not found after recording!")
                    
                    # Record throughput and latency using the collector's methods
                    from metrics_collector import MetricType
                    metrics_collector.record_latency(tgt_node_id, chunk_duration)
                    metrics_collector.record_rtt(tgt_node_id, chunk_duration)
                    
                    # Record throughput by tracking data transferred
                    # The collector will calculate throughput from this
                    if chunk_size_bytes > 0:
                        current_time = time.time()
                        with metrics_collector.collection_lock:
                            if tgt_node_id not in metrics_collector.throughput_windows:
                                metrics_collector.throughput_windows[tgt_node_id] = deque(maxlen=metrics_collector.throughput_window_size)
                            metrics_collector.throughput_windows[tgt_node_id].append((current_time, chunk_size_bytes))
                else:
                    failed_chunks.append((idx, tgt_node_id))
                    print(f"[UPLOAD] Recording transfer end: {chunk_transfer_id}, success=False")
                    metrics_collector.record_transfer_end(
                        transfer_id=chunk_transfer_id,
                        success=False,
                        chunks_transferred=0,
                        error_message="Network send failed"
                    )
        
        if failed_chunks:
            raise HTTPException(status_code=500, detail=f"Failed to send {len(failed_chunks)} chunks via network. Ensure nodes are running and network is active.")
        
        print(f"[UPLOAD] File {file_name}: {num_chunks} chunks, replication={rep_factor}, distributed to: {chunks_per_node}")
        
        # Record file in user's AuthService account
        if user and AUTH_SERVICE_AVAILABLE:
            try:
                channel = grpc.insecure_channel(f'localhost:{auth_grpc_port}')
                stub = auth_grpc.UserServiceStub(channel)
                file_record = auth_pb2.FileRecord(
                    file_id=file_id,
                    name=file_name,
                    size=file_size,
                    nodes=list(node_ids_used)
                )
                grpc_request = auth_pb2.AddFileRecordRequest(login=user, record=file_record)
                stub.AddFileRecord(grpc_request)
            except Exception as e:
                print(f"Warning: Could not record file in AuthService: {e}")
        
        return {"ok": True, "file_id": file_id, "file_name": file_name, "size": file_size, "message": "File uploaded successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/files/{file_id}/download")
def download_file(file_id: str, filename: str = "download", user: str = ""):
    try:
        print(f"[DOWNLOAD-ENDPOINT] Download request for file {file_id}, user: {user}")
        
        # Reload factory state to get latest node instances
        factory._load_state(verbose=False)
        nodes = factory.get_all_nodes()
        
        print(f"[DOWNLOAD-ENDPOINT] Factory has {len(nodes)} nodes, {len(factory.node_configs)} configs")
        print(f"[DOWNLOAD-ENDPOINT] Node IDs in configs: {list(factory.node_configs.keys())}")
        
        if not nodes and not factory.node_configs:
            raise HTTPException(status_code=404, detail="no nodes available")
        
        # Check if nodes are running by verifying socket connection
        running_nodes = []
        for node_id, node_config in factory.node_configs.items():
            try:
                node_host = node_config.get('host', 'localhost')
                node_port = node_config.get('port', 5000)
                test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_socket.settimeout(0.5)
                test_socket.connect((node_host, node_port))
                test_socket.close()
                # Node is running
                if node_id in factory.nodes:
                    running_nodes.append(factory.nodes[node_id])
                else:
                    running_nodes.append({'node_id': node_id, 'host': node_host, 'port': node_port})
                print(f"[DOWNLOAD-ENDPOINT] Node {node_id} is running on {node_host}:{node_port}")
            except Exception as e:
                print(f"[DOWNLOAD-ENDPOINT] Node {node_id} not responding: {e}")
                pass
        
        print(f"[DOWNLOAD-ENDPOINT] Found {len(running_nodes)} running nodes")
        
        if not running_nodes:
            raise HTTPException(status_code=400, detail="No nodes are running. Start nodes first from the provider portal.")
        
        # Request chunks from nodes via network (cloud simulation)
        all_chunks = {}  # chunk_index -> data
        
        # Try to get file info from AuthService to know expected chunk count
        estimated_chunks = None
        file_size = None
        if AUTH_SERVICE_AVAILABLE:
            try:
                stub = get_auth_stub()
                if stub:
                    # Try with user if provided, otherwise try to find file in any user's files
                    if user:
                        profile = stub.GetProfile(auth_pb2.GetProfileRequest(login=user))
                        for file_record in profile.files:
                            if file_record.file_id == file_id:
                                file_size = file_record.size
                                break
                    else:
                        # If no user provided, we can't get file info, will use default estimation
                        pass
                    
                    if file_size:
                        # Get chunk size from config (default 512KB if not specified)
                        chunk_size_bytes = loader.get("storage.chunk_size_bytes", 512 * 1024)
                        if chunk_size_bytes == 0:
                            chunk_size_bytes = 512 * 1024  # Default to 512KB
                        estimated_chunks = max(1, (file_size + chunk_size_bytes - 1) // chunk_size_bytes)
                        print(f"[DOWNLOAD] File size: {file_size} bytes, chunk size: {chunk_size_bytes} bytes, estimated chunks: {estimated_chunks}")
            except Exception as e:
                print(f"[DOWNLOAD] Could not get file info from AuthService: {e}")
        
        # Check network status via gRPC (non-blocking)
        try:
            stub = get_grpc_stub()
            if stub:
                net_status = stub.GetNetworkStatus(cloudsim_pb2.NetworkRequest())
                if not net_status.running:
                    print(f"[DOWNLOAD] Warning: Network service reports not running, but proceeding with download")
        except Exception as e:
            print(f"[DOWNLOAD] Warning: Could not verify network status: {e}, proceeding anyway")
        
        # Try chunks sequentially, stopping after 3 consecutive failures
        max_chunks_to_check = estimated_chunks if estimated_chunks else 50
        consecutive_failures = 0
        max_consecutive_failures = 3
        # REMOVED: should_stop_after_this flag - was causing incomplete downloads
        
        print(f"[DOWNLOAD] Requesting chunks via network (checking up to {max_chunks_to_check} chunks)")
        print(f"[DOWNLOAD] Available running nodes: {len(running_nodes)}")
        
        if len(running_nodes) == 0:
            print(f"[DOWNLOAD] ERROR: No running nodes available for download!")
            raise HTTPException(status_code=400, detail="No nodes are running. Start nodes first from the provider portal.")
        
        for chunk_id in range(max_chunks_to_check):
            # REMOVED: should_stop_after_this check - was causing incomplete downloads
            # We now rely on consecutive failures and estimated chunk count
            chunk_found = False
            
            # Try each running node
            for node in running_nodes:
                try:
                    if isinstance(node, dict):
                        node_host = node.get('host', 'localhost')
                        node_port = node.get('port', 5000)
                        node_id_str = node.get('node_id', 'unknown')
                    else:
                        node_config = factory.node_configs.get(node.node_id, {})
                        node_host = node_config.get('host', 'localhost')
                        node_port = node_config.get('port', 5000)
                        node_id_str = node.node_id
                    
                    print(f"[DOWNLOAD] Requesting chunk {chunk_id} from {node_id_str} ({node_host}:{node_port})")
                    
                    # Record chunk request start time for metrics
                    chunk_request_start = time.time()
                    
                    # Request chunk via network
                    chunk_data = request_chunk_from_node_via_network(node_host, node_port, file_id, chunk_id)
                    
                    # Record chunk request end time and metrics
                    chunk_request_end = time.time()
                    chunk_request_duration = (chunk_request_end - chunk_request_start) * 1000  # Convert to ms
                    
                    if chunk_data is not None:
                        all_chunks[chunk_id] = chunk_data
                        chunk_found = True
                        consecutive_failures = 0
                        print(f"[DOWNLOAD] ✓ Found chunk {chunk_id} from {node_id_str} ({len(chunk_data)} bytes)")
                        
                        # Record metrics for successful download
                        chunk_size_bytes = len(chunk_data)
                        
                        # Record latency and RTT
                        metrics_collector.record_latency(node_id_str, chunk_request_duration)
                        metrics_collector.record_rtt(node_id_str, chunk_request_duration)
                        
                        # Record throughput by tracking data transferred
                        if chunk_size_bytes > 0:
                            current_time = time.time()
                            from collections import deque
                            with metrics_collector.collection_lock:
                                if node_id_str not in metrics_collector.throughput_windows:
                                    metrics_collector.throughput_windows[node_id_str] = deque(maxlen=metrics_collector.throughput_window_size)
                                metrics_collector.throughput_windows[node_id_str].append((current_time, chunk_size_bytes))
                        
                        # Record transfer metrics
                        download_transfer_id = f"download_{file_id}_chunk_{chunk_id}_from_{node_id_str}"
                        print(f"[DOWNLOAD] Recording transfer start: {download_transfer_id}, user={user}, size={chunk_size_bytes}")
                        metrics_collector.record_transfer_start(
                            transfer_id=download_transfer_id,
                            file_id=file_id,
                            source_node=node_id_str,
                            target_node="backend_api",
                            file_size_bytes=chunk_size_bytes,
                            total_chunks=1,
                            user_id=user if user else None
                        )
                        print(f"[DOWNLOAD] Recording transfer end: {download_transfer_id}, duration={chunk_request_duration}ms")
                        metrics_collector.record_transfer_end(
                            transfer_id=download_transfer_id,
                            success=True,
                            chunks_transferred=1,
                            first_chunk_latency_ms=chunk_request_duration,
                            average_chunk_rtt_ms=chunk_request_duration
                        )
                        # Verify it was recorded
                        with metrics_collector.collection_lock:
                            if download_transfer_id in metrics_collector.transfer_metrics:
                                transfer = metrics_collector.transfer_metrics[download_transfer_id]
                                print(f"[DOWNLOAD] Transfer recorded: end_time={transfer.end_time}, success={transfer.success}, user_id={transfer.user_id}")
                            else:
                                print(f"[DOWNLOAD] ERROR: Transfer {download_transfer_id} not found after recording!")
                        
                        # REMOVED aggressive end-of-file detection that was causing incomplete downloads
                        # The previous logic would check for the next chunk when a small chunk was found,
                        # but network errors/timeouts would incorrectly trigger end-of-file detection,
                        # causing the download to stop prematurely.
                        # 
                        # Now we rely on:
                        # 1. File size from AuthService to calculate expected chunk count
                        # 2. Consecutive failures mechanism (3 consecutive failures = stop)
                        # This is safer and prevents false positives from network errors
                        
                        break  # Found chunk, move to next chunk_id
                    else:
                        print(f"[DOWNLOAD] ✗ Chunk {chunk_id} not found on {node_id_str} (node may not have this chunk)")
                except Exception as e:
                    print(f"[DOWNLOAD] ✗ Error requesting chunk {chunk_id} from {node_id_str}: {e}")
                    import traceback
                    traceback.print_exc()
                    # Continue to next node
                    continue
            
            if not chunk_found:
                consecutive_failures += 1
                print(f"[DOWNLOAD] Chunk {chunk_id} not found on any node (consecutive failures: {consecutive_failures})")
                
                # Special case: If we only have chunk 0 and it's smaller than chunk size, 
                # and we're looking for chunk 1, this is likely a single-chunk file
                if chunk_id == 1 and len(all_chunks) == 1 and 0 in all_chunks:
                    chunk_size_bytes = loader.get("storage.chunk_size_bytes", 512 * 1024)
                    if chunk_size_bytes == 0:
                        chunk_size_bytes = 512 * 1024
                    if len(all_chunks[0]) < chunk_size_bytes:
                        print(f"[DOWNLOAD] Chunk 0 is {len(all_chunks[0])} bytes (< {chunk_size_bytes} bytes) and chunk 1 doesn't exist - single-chunk file detected")
                        break
                
                # If we have an estimated chunk count and we've found that many chunks, we're done
                if estimated_chunks and len(all_chunks) >= estimated_chunks:
                    print(f"[DOWNLOAD] ✓ Found all {estimated_chunks} expected chunks, stopping")
                    break
                
                # If we've found chunks before and have consecutive failures, we're done
                # This is the primary mechanism for detecting end of file
                if len(all_chunks) > 0 and consecutive_failures >= max_consecutive_failures:
                    print(f"[DOWNLOAD] ✓ Stopping after {consecutive_failures} consecutive failures, found {len(all_chunks)} chunks")
                    break
                
                # If we haven't found any chunks and have tried 10, give up
                if len(all_chunks) == 0 and chunk_id >= 9:
                    print(f"[DOWNLOAD] No chunks found after checking 10 chunk IDs")
                    break
            
            # REMOVED: should_stop_after_this check - was causing premature stopping
            # We now rely on consecutive failures and estimated chunk count instead
        
        print(f"[DOWNLOAD] Found {len(all_chunks)} chunks via network: {sorted(all_chunks.keys())}")
        
        if not all_chunks:
            raise HTTPException(status_code=404, detail="file not found")
        
        # Combine chunks in order
        def iter_bytes():
            for idx in sorted(all_chunks.keys()):
                yield all_chunks[idx]
        
        # Set proper headers for download with original filename
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
        return StreamingResponse(iter_bytes(), media_type="application/octet-stream", headers=headers)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/files/{file_id}")
def delete_file(file_id: str, user: str = ""):
    try:
        nodes = factory.get_all_nodes()
        if not nodes:
            raise HTTPException(status_code=404, detail="no nodes available")
        
        prefix = f"{file_id}_chunk_"
        total_removed = 0
        file_size = 0
        chunks_deleted = 0
        
        # Delete chunk files directly from all nodes
        for node in nodes:
            try:
                chunk_files = [f for f in os.listdir(node.chunks_path) if f.startswith(prefix) and f.endswith('.bin')]
                for fname in chunk_files:
                    fpath = os.path.join(node.chunks_path, fname)
                    try:
                        size = os.path.getsize(fpath)
                        os.remove(fpath)
                        total_removed += size
                        chunks_deleted += 1
                        # Count unique chunk size (first occurrence only)
                        chunk_idx = fname.split('_chunk_')[-1].split('.bin')[0]
                        print(f"[DELETE] Removed {fname} from {node.node_id} ({size} bytes)")
                    except Exception as e:
                        print(f"[DELETE] Error removing {fname}: {e}")
            except Exception as e:
                print(f"[DELETE] Error accessing {node.node_id}: {e}")
        
        # Calculate original file size (sum of unique chunks, not replicas)
        # For simplicity, we'll use the total_removed / replication_factor estimate
        # or get it from AuthService
        
        # Remove file record from AuthService
        if user and AUTH_SERVICE_AVAILABLE:
            try:
                channel = grpc.insecure_channel(f'localhost:{auth_grpc_port}')
                stub = auth_grpc.UserServiceStub(channel)
                # Get actual file size from user's file list
                profile_req = auth_pb2.ListFilesRequest(login=user)
                files_resp = stub.ListFiles(profile_req)
                for record in files_resp.records:
                    if record.file_id == file_id:
                        file_size = record.size
                        break
                
                grpc_request = auth_pb2.RemoveFileRecordRequest(
                    login=user,
                    file_id=file_id,
                    size=file_size
                )
                result = stub.RemoveFileRecord(grpc_request)
                print(f"[DELETE] AuthService record removed: {result.ok}")
            except Exception as e:
                print(f"Warning: Could not remove file record from AuthService: {e}")
        
        if chunks_deleted == 0:
            return {"ok": False, "message": "No chunks found to delete"}
        
        return {"ok": True, "message": f"Deleted {chunks_deleted} chunk(s), {total_removed} bytes removed"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[DELETE] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/files/{file_id}/replicate")
def replicate_file(file_id: str, source_node_id: str = Form(...), dest_node_id: str = Form(...)):
    try:
        src = factory.get_node(source_node_id)
        dst = factory.get_node(dest_node_id)
        if not src or not dst:
            raise HTTPException(status_code=404, detail="source or dest not found")
        try:
            src.network_manager.connect_to_node(dst.node_id, dst.host, dst.port)
        except Exception:
            pass
        prefix = f"{file_id}_chunk_"
        def _chunk_index(name: str) -> int:
            try:
                return int(name.split('_chunk_')[-1].split('.bin')[0])
            except Exception:
                return 0
        files = [f for f in os.listdir(src.chunks_path) if f.startswith(prefix) and f.endswith('.bin')]
        files.sort(key=_chunk_index)
        if not files:
            raise HTTPException(status_code=404, detail="no chunks on source")
        for fname in files:
            idx = _chunk_index(fname)
            ok = src.send_chunk_to_node(dst.node_id, file_id, idx)
            if not ok:
                raise HTTPException(status_code=500, detail=f"failed transfer chunk {idx}")
        return {"ok": True, "message": "replicated"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== NEW ENDPOINTS =====

class NodeCreateRequest(BaseModel):
    node_id: str
    cpu: int = 2
    memory: int = 4
    storage: int = 10
    bandwidth: int = 100
    host: str = "localhost"
    port: Optional[int] = None

class BatchCreateRequest(BaseModel):
    count: int
    base_id: str = "node"
    cpu: int = 2
    memory: int = 4
    storage: int = 10
    bandwidth: int = 100
    host: str = "localhost"


@app.post("/nodes")
def create_node(node_data: NodeCreateRequest):
    """Create a new node"""
    try:
        node = factory.create_node(
            node_id=node_data.node_id,
            cpu_capacity=node_data.cpu,
            memory_capacity=node_data.memory,
            storage_capacity=node_data.storage,
            bandwidth=node_data.bandwidth,
            host=node_data.host,
            port=node_data.port
        )
        
        if not node:
            raise HTTPException(status_code=500, detail="failed to create node")
        
        return {"ok": True, "message": "node created", "node_id": node_data.node_id, "port": node.port}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/nodes/{node_id}")
def delete_node(node_id: str):
    """Delete a node - uses gRPC cloudrpc server"""
    stub = get_grpc_stub()
    if stub:
        try:
            response = stub.DeleteNode(cloudsim_pb2.NodeRequest(node_id=node_id, force=False))
            if response.ok:
                return {"ok": True, "message": response.message}
            else:
                raise HTTPException(status_code=500, detail=response.message)
        except Exception as e:
            print(f"gRPC call failed, falling back to direct: {e}")
    
    # Fallback to direct implementation
    try:
        success = factory.remove_node(node_id)
        if not success:
            raise HTTPException(status_code=404, detail="node not found")
        return {"ok": True, "message": "node deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/nodes/{node_id}/restart")
def restart_node(node_id: str):
    """Restart a node"""
    try:
        node = factory.get_node(node_id)
        if not node:
            raise HTTPException(status_code=404, detail="node not found")
        
        # Stop first
        if node.is_alive() or node.running:
            node.stop(graceful=True, timeout=5.0)
            node.join(timeout=3.0)
        
        # Start again
        node.start()
        return {"ok": True, "message": "node restarted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/nodes/{node_id}/details")
def get_node_details(node_id: str):
    """Get detailed information about a node"""
    try:
        node = factory.get_node(node_id)
        if not node:
            raise HTTPException(status_code=404, detail="node not found")
        
        config = factory.node_configs.get(node_id, {})
        is_running = bool(node.is_alive() or node.running)
        
        # Check via TCP if not running locally
        if not is_running:
            host = config.get('host', 'localhost')
            port = int(config.get('port', 0) or 0)
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.5)
                s.connect((host, port))
                s.close()
                is_running = True
            except Exception:
                pass
        
        # Get IP and MAC from node if available, otherwise from config
        ip_address = getattr(node, 'ip_address', '') or config.get('ip_address', '')
        mac_address = getattr(node, 'mac_address', '') or config.get('mac_address', '')
        
        details = {
            "node_id": node_id,
            "host": config.get('host', 'localhost'),
            "port": config.get('port', 0),
            "ip_address": ip_address,
            "mac_address": mac_address,
            "running": is_running,
            "cpu_capacity": config.get('cpu_capacity', 0),
            "memory_capacity": config.get('memory_capacity', 0),
            "storage_capacity": config.get('storage_capacity', 0),
            "bandwidth": config.get('bandwidth', 0),
            "enable_network_check": config.get('enable_network_check', True),
        }
        
        if is_running:
            try:
                storage_util = node.get_storage_utilization()
                network_util = node.get_network_utilization()
                performance = node.get_performance_metrics()
                
                details["storage"] = {
                    "total_bytes": storage_util.get('total_bytes', 0),
                    "used_bytes": storage_util.get('used_bytes', 0),
                    "available_bytes": storage_util.get('total_bytes', 0) - storage_util.get('used_bytes', 0),
                    "utilization_percent": storage_util.get('utilization_percent', 0.0),
                    "files_stored": storage_util.get('files_stored', 0),
                    "chunk_count": storage_util.get('chunk_count', 0)
                }
                
                details["network"] = {
                    "utilization_percent": network_util.get('utilization_percent', 0.0),
                    "connections": network_util.get('connections', [])
                }
                
                details["performance"] = {
                    "total_transfers": performance.get('total_requests_processed', 0),
                    "successful_transfers": performance.get('total_requests_processed', 0) - performance.get('failed_transfers', 0),
                    "failed_transfers": performance.get('failed_transfers', 0),
                    "active_transfers": performance.get('current_active_transfers', 0),
                    "data_transferred_bytes": performance.get('total_data_transferred_bytes', 0)
                }
            except Exception:
                pass
        
        return details
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/nodes/batch")
def batch_create_nodes(batch_data: BatchCreateRequest):
    """Create multiple nodes with same specifications"""
    try:
        created = []
        for i in range(batch_data.count):
            node_id = f"{batch_data.base_id}{i+1}"
            try:
                node = factory.create_node(
                    node_id=node_id,
                    cpu_capacity=batch_data.cpu,
                    memory_capacity=batch_data.memory,
                    storage_capacity=batch_data.storage,
                    bandwidth=batch_data.bandwidth,
                    host=batch_data.host,
                    port=None  # Auto-assign
                )
                if node:
                    created.append({"node_id": node_id, "port": node.port})
            except Exception as e:
                return {"ok": False, "message": f"Failed to create {node_id}: {str(e)}", "created": created}
        
        return {"ok": True, "message": f"Created {len(created)} node(s)", "nodes": created}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/system/info")
def get_system_info():
    """Get aggregated system information"""
    try:
        stats = factory.get_factory_stats()
        resources = factory.get_aggregated_resources()
        
        return {
            "nodes": {
                "total": stats['total_nodes'],
                "running": stats['running_nodes'],
                "stopped": stats['stopped_nodes']
            },
            "resources": {
                "total_cpu": resources['total_cpu'],
                "total_memory_gb": resources['total_memory_gb'],
                "total_storage_gb": resources['total_storage_gb'],
                "total_bandwidth_mbps": resources['total_bandwidth_mbps'],
                "used_storage_gb": resources['used_storage_gb'],
                "available_storage_gb": resources['available_storage_gb'],
                "storage_utilization_percent": resources['storage_utilization_percent']
            },
            "averages": {
                "cpu": resources['average_cpu'],
                "memory_gb": resources['average_memory_gb'],
                "storage_gb": resources['average_storage_gb'],
                "bandwidth_mbps": resources['average_bandwidth_mbps']
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/nodes/health")
def get_nodes_health():
    """Get health status for all nodes"""
    try:
        health = factory.check_all_nodes_health()
        nodes = []
        for node_id, health_data in health.items():
            nodes.append({
                "node_id": node_id,
                "status": health_data.get('status', 'unknown'),
                "healthy": health_data.get('status') == 'running'
            })
        return {"nodes": nodes, "healthy_count": sum(1 for n in nodes if n['healthy']), "total_count": len(nodes)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/network/start")
def start_network_service():
    """Start the network service - uses gRPC cloudrpc server"""
    stub = get_grpc_stub()
    if not stub:
        raise HTTPException(status_code=503, detail="CloudRPC server not available. Start the gRPC server first.")
    
    try:
        response = stub.StartNetwork(cloudsim_pb2.NetworkRequest())
        if response.ok:
            return {"ok": True, "message": response.message}
        else:
            raise HTTPException(status_code=500, detail=response.message)
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"gRPC error: {e.details() if hasattr(e, 'details') else str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/network/stop")
def stop_network_service():
    """Stop the network service - uses gRPC cloudrpc server"""
    stub = get_grpc_stub()
    if not stub:
        raise HTTPException(status_code=503, detail="CloudRPC server not available. Start the gRPC server first.")
    
    try:
        response = stub.StopNetwork(cloudsim_pb2.NetworkRequest())
        if response.ok:
            return {"ok": True, "message": response.message}
        else:
            raise HTTPException(status_code=500, detail=response.message)
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"gRPC error: {e.details() if hasattr(e, 'details') else str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/network/status")
def get_network_status():
    """Get network service status - uses gRPC cloudrpc server"""
    stub = get_grpc_stub()
    if not stub:
        # Return default status if gRPC unavailable
        return {
            "running": False,
            "network_name": "CloudSim_Storage_Network",
            "discovery_port": 9999,
            "registered_nodes": 0,
            "nodes": {},
            "error": "CloudRPC server not available"
        }
    
    try:
        response = stub.GetNetworkStatus(cloudsim_pb2.StatusRequest())
        # Convert protobuf response to dict
        nodes_dict = {}
        for node_id, node_info in response.nodes.items():
            nodes_dict[node_id] = {
                "host": node_info.host,
                "port": node_info.port,
                "last_seen": node_info.last_seen,
                "registered_at": node_info.registered_at
            }
        result = {
            "running": response.running,
            "network_name": response.network_name if response.network_name else "CloudSim_Storage_Network",
            "discovery_port": response.discovery_port if response.discovery_port > 0 else 9999,
            "registered_nodes": response.registered_nodes,
            "nodes": nodes_dict
        }
        # Debug logging
        if not response.running:
            print(f"[API] Network status: running=False, network_name='{response.network_name}', discovery_port={response.discovery_port}")
        return result
    except grpc.RpcError as e:
        return {
            "running": False,
            "network_name": "CloudSim_Storage_Network",
            "discovery_port": 9999,
            "registered_nodes": 0,
            "nodes": {},
            "error": f"gRPC error: {e.details() if hasattr(e, 'details') else str(e)}"
        }
    except Exception as e:
        return {
            "running": False,
            "network_name": "CloudSim_Storage_Network",
            "discovery_port": 9999,
            "registered_nodes": 0,
            "nodes": {},
            "error": str(e)
        }


def _get_transfer_history():
    """Helper function to get transfer history with error handling"""
    try:
        if metrics_collector:
            # Check how many transfers are stored
            with metrics_collector.collection_lock:
                total_transfers = len(metrics_collector.transfer_metrics)
                # Check how many have end_time
                completed_count = sum(1 for t in metrics_collector.transfer_metrics.values() if t.end_time is not None)
                incomplete_count = total_transfers - completed_count
            print(f"[METRICS] Total transfers in collector: {total_transfers}, Completed: {completed_count}, Incomplete: {incomplete_count}")
            
            # Show sample transfer IDs
            if total_transfers > 0:
                with metrics_collector.collection_lock:
                    sample_ids = list(metrics_collector.transfer_metrics.keys())[:5]
                    print(f"[METRICS] Sample transfer IDs (first 5): {sample_ids}")
                    for tid in sample_ids:
                        t = metrics_collector.transfer_metrics[tid]
                        print(f"[METRICS]   {tid}: end_time={t.end_time is not None}, user_id={t.user_id}, success={t.success}, file_size={t.file_size_bytes}")
            
            transfers = metrics_collector.get_recent_transfers(limit=50)
            print(f"[METRICS] get_recent_transfers returned {len(transfers)} transfers")
            if transfers:
                print(f"[METRICS] Sample transfer: user_id={transfers[0].get('user_id')}, size={transfers[0].get('file_size_bytes')}, latency={transfers[0].get('latency_ms')}")
            else:
                print(f"[METRICS] WARNING: No transfers returned despite {total_transfers} total transfers in collector!")
            # Always return a list, never None
            return transfers if transfers is not None else []
        else:
            print("[METRICS] ERROR: metrics_collector is None")
            return []
    except Exception as e:
        print(f"[METRICS] ERROR getting transfer history: {e}")
        import traceback
        traceback.print_exc()
        return []


@app.delete("/metrics/transfers")
async def clear_transfer_history():
    """
    Clear all transfer history records
    """
    try:
        if metrics_collector:
            with metrics_collector.collection_lock:
                count = len(metrics_collector.transfer_metrics)
                metrics_collector.transfer_metrics.clear()
                # Also clear throughput windows
                metrics_collector.throughput_windows.clear()
            print(f"[METRICS] Cleared {count} transfer records")
            return {"ok": True, "message": f"Cleared {count} transfer records"}
        else:
            return {"ok": False, "message": "Metrics collector not available"}
    except Exception as e:
        print(f"[METRICS] Error clearing transfer history: {e}")
        import traceback
        traceback.print_exc()
        return {"ok": False, "message": str(e)}


@app.get("/metrics")
def get_metrics(node_id: Optional[str] = None):
    """Get metrics (network-wide or for specific node)"""
    try:
        # Collect fresh metrics
        metrics_collector.collect_all_nodes_metrics()
        
        if node_id:
            latest = metrics_collector.get_latest_metrics(node_id=node_id)
        else:
            latest = metrics_collector.get_latest_metrics()
        
        # Calculate comprehensive metrics from current node state
        # Reload state to ensure we have all nodes (including those started via gRPC)
        factory._load_state(verbose=False)
        nodes = factory.get_all_nodes()
        total_storage = 0
        used_storage = 0
        running_count = 0
        total_files = 0
        node_metrics = []
        
        # Also check node_configs to ensure we don't miss any nodes
        all_node_ids = set()
        for node in nodes:
            all_node_ids.add(node.node_id)
        for node_id in factory.node_configs.keys():
            all_node_ids.add(node_id)
        
        # Process all nodes (both from factory.nodes and node_configs)
        for node_id in all_node_ids:
            node = factory.get_node(node_id)
            if not node:
                # Node not in factory.nodes - create a temporary node object from config
                node_config = factory.node_configs.get(node_id, {})
                if not node_config:
                    continue
                # Use config to get storage info
                node_storage_gb = node_config.get('storage_capacity', 2)
                node_storage_bytes = node_storage_gb * 1024**3
                node_host = node_config.get('host', 'localhost')
                node_port = node_config.get('port', 5000)
                
                # Check if node is running via socket
                is_running = False
                try:
                    test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    test_socket.settimeout(0.5)
                    test_socket.connect((node_host, node_port))
                    test_socket.close()
                    is_running = True
                except Exception:
                    pass
                
                # Try to get storage utilization from disk
                try:
                    storage_root = os.path.abspath(loader.get("storage.base_directory", "storage"))
                    node_storage_path = os.path.join(storage_root, node_id, "chunks")
                    if os.path.exists(node_storage_path):
                        node_used = sum(os.path.getsize(os.path.join(node_storage_path, f)) 
                                       for f in os.listdir(node_storage_path) 
                                       if os.path.isfile(os.path.join(node_storage_path, f)))
                        node_files = len([f for f in os.listdir(node_storage_path) if f.endswith('.bin')])
                    else:
                        node_used = 0
                        node_files = 0
                except Exception:
                    node_used = 0
                    node_files = 0
                
                total_storage += node_storage_bytes
                used_storage += node_used
                total_files += node_files
                if is_running:
                    running_count += 1
                
                node_util_pct = (node_used / node_storage_bytes * 100) if node_storage_bytes > 0 else 0
                
                node_metrics.append({
                    "node_id": node_id,
                    "running": is_running,
                    "storage_capacity_gb": round(node_storage_gb, 2),
                    "used_bytes": node_used,
                    "used_gb": round(node_used / (1024**3), 4),
                    "utilization_percent": round(node_util_pct, 4),
                    "files_count": node_files,
                    "ip_address": node_config.get('ip_address', 'N/A'),
                    "port": node_port
                })
                continue
            
            # Process node from factory.nodes
            try:
                # total_storage is in bytes, convert to GB for display
                node_storage_bytes = getattr(node, 'total_storage', 10 * 1024**3)  # Default 10GB if not found
                node_storage_gb = node_storage_bytes / (1024**3)
                total_storage += node_storage_bytes
                
                util = node.get_storage_utilization()
                node_used = 0
                node_files = 0
                if isinstance(util, dict):
                    node_used = util.get('used_bytes', 0)
                    node_files = util.get('files_count', 0)
                    used_storage += node_used
                    total_files += node_files
                
                # Check if node is running - use socket check since nodes may be started via gRPC
                is_running = False
                try:
                    # First try is_alive() if it's a thread
                    if hasattr(node, 'is_alive'):
                        is_running = node.is_alive() or getattr(node, 'running', False)
                    
                    # Also verify via socket connection (nodes started via gRPC may not be in factory.nodes)
                    if not is_running:
                        node_config = factory.node_configs.get(node.node_id, {})
                        node_host = node_config.get('host', getattr(node, 'host', 'localhost'))
                        node_port = node_config.get('port', getattr(node, 'port', 5000))
                        try:
                            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            test_socket.settimeout(0.5)
                            test_socket.connect((node_host, node_port))
                            test_socket.close()
                            is_running = True
                        except Exception:
                            pass
                except Exception as e:
                    print(f"[METRICS] Error checking node {node.node_id} status: {e}")
                
                if is_running:
                    running_count += 1
                
                node_util_pct = (node_used / node_storage_bytes * 100) if node_storage_bytes > 0 else 0
                
                node_metrics.append({
                    "node_id": node.node_id,
                    "running": is_running,
                    "storage_capacity_gb": round(node_storage_gb, 2),
                    "used_bytes": node_used,
                    "used_gb": round(node_used / (1024**3), 4),
                    "utilization_percent": round(node_util_pct, 4),
                    "files_count": node_files,
                    "ip_address": getattr(node, 'ip_address', 'N/A'),
                    "port": getattr(node, 'port', 0)
                })
            except Exception as e:
                print(f"Error getting metrics for {node.node_id}: {e}")
        
        storage_util = (used_storage / total_storage * 100) if total_storage > 0 else 0
        
        # Get comprehensive metrics from MetricsCollector
        # The latest dict contains NetworkMetrics data with all network/performance metrics
        network_util = latest.get('total_network_utilization_percent', 0.0) if latest else 0.0
        throughput = latest.get('total_throughput_mbps', 0.0) if latest else 0.0
        latency = latest.get('average_latency_ms', 0.0) if latest else 0.0
        rtt = latest.get('average_rtt_ms', 0.0) if latest else 0.0
        total_transfers = latest.get('total_transfers', 0) if latest else 0
        successful_transfers = latest.get('total_successful_transfers', 0) if latest else 0
        failed_transfers = latest.get('total_failed_transfers', 0) if latest else 0
        error_rate = latest.get('overall_error_rate_percent', 0.0) if latest else 0.0
        data_transferred = latest.get('total_data_transferred_bytes', 0) if latest else 0
        active_transfers = latest.get('total_active_transfers', 0) if latest else 0
        
        # Get per-node network metrics from collector
        node_metrics_from_collector = latest.get('node_metrics', []) if latest else []
        node_metrics_dict = {nm.get('node_id'): nm for nm in node_metrics_from_collector}
        
        # Enhance node_metrics with network data from collector
        for node_metric in node_metrics:
            node_id = node_metric.get('node_id')
            collector_node_data = node_metrics_dict.get(node_id, {})
            if collector_node_data:
                node_metric['throughput_mbps'] = collector_node_data.get('throughput_mbps', 0.0)
                node_metric['latency_ms'] = collector_node_data.get('average_latency_ms', 0.0)
                node_metric['rtt_ms'] = collector_node_data.get('average_rtt_ms', 0.0)
                node_metric['network_utilization_percent'] = collector_node_data.get('network_utilization_percent', 0.0)
                node_metric['error_rate_percent'] = collector_node_data.get('error_rate_percent', 0.0)
                node_metric['total_transfers'] = collector_node_data.get('total_transfers', 0)
                node_metric['successful_transfers'] = collector_node_data.get('successful_transfers', 0)
                node_metric['failed_transfers'] = collector_node_data.get('failed_transfers', 0)
                node_metric['active_transfers'] = collector_node_data.get('active_transfers', 0)
                node_metric['data_transferred_bytes'] = collector_node_data.get('total_data_transferred_bytes', 0)
            else:
                # Set defaults if collector data not available
                node_metric['throughput_mbps'] = 0.0
                node_metric['latency_ms'] = 0.0
                node_metric['rtt_ms'] = 0.0
                node_metric['network_utilization_percent'] = 0.0
                node_metric['error_rate_percent'] = 0.0
                node_metric['total_transfers'] = 0
                node_metric['successful_transfers'] = 0
                node_metric['failed_transfers'] = 0
                node_metric['active_transfers'] = 0
                node_metric['data_transferred_bytes'] = 0
        
        # Calculate success rate
        success_rate = (successful_transfers / total_transfers * 100) if total_transfers > 0 else 0.0
        
        # Get user metrics summary
        user_metrics_summary = metrics_collector.get_user_metrics()
        total_users_with_activity = user_metrics_summary.get("total_users", 0)
        total_user_transfers = user_metrics_summary.get("total_transfers_all_users", 0)
        total_user_data = user_metrics_summary.get("total_data_all_users", 0)
        
        # Get total registered users from AuthService
        total_registered_users = 0
        total_user_quota = 0
        total_user_used = 0
        if AUTH_SERVICE_AVAILABLE:
            try:
                stub = get_auth_stub()
                if stub:
                    # We can't list all users directly, so we'll estimate from metrics
                    # For now, use the count from user metrics
                    pass
            except Exception:
                pass
        
        # Get transfer history (with error handling)
        try:
            transfer_history = _get_transfer_history()
            print(f"[METRICS] Successfully got transfer history: {len(transfer_history)} transfers")
        except Exception as e:
            print(f"[METRICS] Error getting transfer history in get_metrics: {e}")
            import traceback
            traceback.print_exc()
            transfer_history = []  # Fallback to empty list
        
        return {
            # Storage metrics
            "storage_utilization_percent": round(storage_util, 2),
            "total_storage_gb": round(total_storage / (1024**3), 2),
            "used_storage_gb": round(used_storage / (1024**3), 4),
            "available_storage_gb": round((total_storage - used_storage) / (1024**3), 2),
            "total_files": total_files,
            
            # Node metrics
            "total_nodes": len(nodes),
            "running_nodes": running_count,
            "stopped_nodes": len(nodes) - running_count,
            "replication_factor": int(loader.get("replication.default_factor", 3)),
            
            # Network performance metrics
            "throughput_mbps": round(throughput, 2),
            "average_latency_ms": round(latency, 2),
            "average_rtt_ms": round(rtt, 2),
            "network_utilization_percent": round(network_util, 2),
            
            # Transfer statistics
            "total_transfers": total_transfers,
            "successful_transfers": successful_transfers,
            "failed_transfers": failed_transfers,
            "active_transfers": active_transfers,
            "error_rate_percent": round(error_rate, 2),
            "success_rate_percent": round(success_rate, 2),
            
            # Data statistics
            "total_data_transferred_bytes": data_transferred,
            "total_data_transferred_gb": round(data_transferred / (1024**3), 2),
            
            # Per-node details (now includes network metrics)
            "node_details": node_metrics,
            
            # User metrics summary
            "user_metrics": {
                "total_users_with_activity": total_users_with_activity,
                "total_user_transfers": total_user_transfers,
                "total_user_data_transferred_bytes": total_user_data,
                "total_user_data_transferred_gb": round(total_user_data / (1024**3), 2)
            },
            
            # Transfer history (recent transfers with user info) - ALWAYS include
            "transfer_history": transfer_history if transfer_history is not None else [],
            
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        print(f"[METRICS] ERROR in get_metrics: {e}")
        import traceback
        traceback.print_exc()
        # Return partial data with empty transfer_history on error
        return {
            "storage_utilization_percent": 0,
            "total_storage_gb": 0,
            "used_storage_gb": 0,
            "available_storage_gb": 0,
            "total_files": 0,
            "total_nodes": 0,
            "running_nodes": 0,
            "stopped_nodes": 0,
            "replication_factor": 3,
            "throughput_mbps": 0,
            "average_latency_ms": 0,
            "average_rtt_ms": 0,
            "network_utilization_percent": 0,
            "total_transfers": 0,
            "successful_transfers": 0,
            "failed_transfers": 0,
            "active_transfers": 0,
            "error_rate_percent": 0,
            "success_rate_percent": 0,
            "total_data_transferred_bytes": 0,
            "total_data_transferred_gb": 0,
            "node_details": [],
            "user_metrics": {
                "total_users_with_activity": 0,
                "total_user_transfers": 0,
                "total_user_data_transferred_bytes": 0,
                "total_user_data_transferred_gb": 0
            },
            "transfer_history": [],  # Always include, even on error
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "error": str(e)
        }


@app.get("/metrics/users/{username}")
def get_user_metrics(username: str):
    """Get metrics for a specific user"""
    try:
        # Get user metrics from MetricsCollector
        user_transfer_metrics = metrics_collector.get_user_metrics(username=username)
        
        # Get user profile from AuthService
        user_profile = None
        if AUTH_SERVICE_AVAILABLE:
            try:
                stub = get_auth_stub()
                if stub:
                    profile = stub.GetProfile(auth_pb2.GetProfileRequest(login=username))
                    user_profile = {
                        "username": username,
                        "email": profile.email,
                        "quota_bytes": profile.quota_bytes,
                        "used_bytes": profile.used_bytes,
                        "quota_gb": round(profile.quota_bytes / (1024**3), 2),
                        "used_gb": round(profile.used_bytes / (1024**3), 4),
                        "available_bytes": profile.quota_bytes - profile.used_bytes,
                        "available_gb": round((profile.quota_bytes - profile.used_bytes) / (1024**3), 2),
                        "utilization_percent": round((profile.used_bytes / profile.quota_bytes * 100) if profile.quota_bytes > 0 else 0, 2)
                    }
            except Exception as e:
                print(f"Error getting user profile: {e}")
        
        # Combine transfer metrics with profile
        if not user_transfer_metrics:
            user_transfer_metrics = {
                "username": username,
                "total_transfers": 0,
                "successful_transfers": 0,
                "failed_transfers": 0,
                "total_data_transferred_bytes": 0,
                "total_uploads": 0,
                "total_downloads": 0,
                "upload_data_bytes": 0,
                "download_data_bytes": 0,
                "success_rate_percent": 0.0
            }
        
        return {
            "username": username,
            "profile": user_profile,
            "transfer_metrics": {
                "total_transfers": user_transfer_metrics.get("total_transfers", 0),
                "successful_transfers": user_transfer_metrics.get("successful_transfers", 0),
                "failed_transfers": user_transfer_metrics.get("failed_transfers", 0),
                "success_rate_percent": round(user_transfer_metrics.get("success_rate_percent", 0.0), 2),
                "total_data_transferred_bytes": user_transfer_metrics.get("total_data_transferred_bytes", 0),
                "total_data_transferred_gb": round(user_transfer_metrics.get("total_data_transferred_bytes", 0) / (1024**3), 4),
                "total_uploads": user_transfer_metrics.get("total_uploads", 0),
                "total_downloads": user_transfer_metrics.get("total_downloads", 0),
                "upload_data_bytes": user_transfer_metrics.get("upload_data_bytes", 0),
                "upload_data_gb": round(user_transfer_metrics.get("upload_data_bytes", 0) / (1024**3), 4),
                "download_data_bytes": user_transfer_metrics.get("download_data_bytes", 0),
                "download_data_gb": round(user_transfer_metrics.get("download_data_bytes", 0) / (1024**3), 4)
            },
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics/export")
def export_metrics(format: str = "json", time_range: Optional[str] = None):
    """Export metrics"""
    try:
        format_type = format.lower() if format else "json"
        output_dir = loader.get("metrics.export_directory", "metrics")
        files = metrics_collector.export_all_metrics(output_dir=output_dir, format=format_type)
        return {"ok": True, "files": files, "count": len(files)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/capacity")
def get_capacity():
    """Get capacity information"""
    try:
        summary = capacity_evaluator.get_capacity_summary()
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/capacity/report")
def get_capacity_report():
    """Generate full capacity report"""
    try:
        report = capacity_evaluator.generate_capacity_report(
            include_predictions=True,
            include_alerts=True
        )
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== AUTH ENDPOINTS (via gRPC to AuthService) ====================

@app.post("/auth/register")
def register_user(request: RegisterRequest):
    """
    Register a new user account.
    Default quota is 1GB for free tier.
    Uses gRPC to communicate with AuthService.
    """
    if not AUTH_SERVICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="AuthService not available")
    
    try:
        # Connect to AuthService
        channel = grpc.insecure_channel(f'localhost:{auth_grpc_port}')
        stub = auth_grpc.UserServiceStub(channel)
        
        # Create user with default 1GB quota
        quota = request.quota_gb if request.quota_gb else 1
        grpc_request = auth_pb2.CreateUserRequest(
            login=request.username,
            email=request.email,
            password=request.password,
            quota_gb=quota
        )
        
        response = stub.CreateUser(grpc_request)
        
        if response.created:
            return {
                "ok": True,
                "message": f"Account created successfully! You have {quota}GB free storage.",
                "username": request.username,
                "quota_gb": quota
            }
        else:
            raise HTTPException(status_code=400, detail=response.message)
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"AuthService unavailable: {e.details()}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/auth/login")
def login_user(request: LoginRequest):
    """
    Login user and send OTP to their email.
    Uses gRPC to communicate with AuthService.
    """
    if not AUTH_SERVICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="AuthService not available")
    
    try:
        # Connect to AuthService
        channel = grpc.insecure_channel(f'localhost:{auth_grpc_port}')
        stub = auth_grpc.UserServiceStub(channel)
        
        grpc_request = auth_pb2.LoginRequest(
            login=request.username,
            password=request.password
        )
        
        response = stub.Login(grpc_request)
        
        if response.result == "OTP sent":
            return {
                "ok": True,
                "message": "OTP sent to your email. Please verify to complete login.",
                "pending_id": response.pending_id,
                "username": request.username
            }
        else:
            raise HTTPException(status_code=401, detail="Invalid username or password")
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"AuthService unavailable: {e.details()}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/auth/verify-otp")
def verify_otp(request: VerifyOtpRequest):
    """
    Verify OTP code and get authentication token.
    Uses gRPC to communicate with AuthService.
    """
    if not AUTH_SERVICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="AuthService not available")
    
    try:
        # Connect to AuthService
        channel = grpc.insecure_channel(f'localhost:{auth_grpc_port}')
        stub = auth_grpc.UserServiceStub(channel)
        
        grpc_request = auth_pb2.VerifyOtpRequest(
            login=request.username,
            pending_id=request.pending_id,
            otp=request.otp
        )
        
        response = stub.VerifyOtp(grpc_request)
        
        if response.token:
            return {
                "ok": True,
                "message": "Login successful!",
                "token": response.token,
                "username": request.username
            }
        else:
            raise HTTPException(status_code=401, detail="Invalid or expired OTP")
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"AuthService unavailable: {e.details()}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/auth/profile/{username}")
def get_user_profile(username: str):
    """
    Get user profile information.
    Uses gRPC to communicate with AuthService.
    """
    if not AUTH_SERVICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="AuthService not available")
    
    try:
        # Connect to AuthService
        channel = grpc.insecure_channel(f'localhost:{auth_grpc_port}')
        stub = auth_grpc.UserServiceStub(channel)
        
        grpc_request = auth_pb2.ProfileRequest(login=username)
        response = stub.GetProfile(grpc_request)
        
        if not response.login:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "ok": True,
            "username": response.login,
            "email": response.email,
            "used_bytes": response.used_bytes,
            "quota_bytes": response.quota_bytes,
            "used_gb": round(response.used_bytes / (1024**3), 2),
            "quota_gb": round(response.quota_bytes / (1024**3), 2),
            "usage_percent": round((response.used_bytes / response.quota_bytes * 100), 1) if response.quota_bytes > 0 else 0
        }
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"AuthService unavailable: {e.details()}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/auth/files/{username}")
def get_user_files(username: str):
    """
    Get user's file list.
    Uses gRPC to communicate with AuthService.
    """
    if not AUTH_SERVICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="AuthService not available")
    
    try:
        # Connect to AuthService
        channel = grpc.insecure_channel(f'localhost:{auth_grpc_port}')
        stub = auth_grpc.UserServiceStub(channel)
        
        grpc_request = auth_pb2.ListFilesRequest(login=username)
        response = stub.ListFiles(grpc_request)
        
        files = []
        for record in response.records:
            files.append({
                "file_id": record.file_id,
                "name": record.name,
                "size": record.size,
                "nodes": list(record.nodes)
            })
        
        return {
            "ok": True,
            "username": username,
            "files": files,
            "count": len(files)
        }
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"AuthService unavailable: {e.details()}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/auth/check-quota/{username}")
def check_user_quota(username: str, file_size: int):
    """
    Check if user has enough quota for a file upload.
    Uses gRPC to communicate with AuthService.
    """
    if not AUTH_SERVICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="AuthService not available")
    
    try:
        # Connect to AuthService
        channel = grpc.insecure_channel(f'localhost:{auth_grpc_port}')
        stub = auth_grpc.UserServiceStub(channel)
        
        grpc_request = auth_pb2.PrecheckStoreRequest(login=username, file_size=file_size)
        response = stub.PrecheckStore(grpc_request)
        
        return {
            "ok": True,
            "allowed": response.allowed,
            "remaining_bytes": response.remaining_bytes,
            "remaining_gb": round(response.remaining_bytes / (1024**3), 2)
        }
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"AuthService unavailable: {e.details()}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/auth/users")
def list_all_users():
    """
    List all registered users.
    Uses gRPC to communicate with AuthService.
    """
    if not AUTH_SERVICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="AuthService not available")
    
    try:
        stub = get_auth_stub()
        if not stub:
            raise HTTPException(status_code=503, detail="Could not connect to AuthService")
        
        grpc_request = auth_pb2.ListAllUsersRequest()
        response = stub.ListAllUsers(grpc_request)
        
        users = []
        for user_info in response.users:
            users.append({
                "login": user_info.login,
                "email": user_info.email,
                "used_bytes": user_info.used_bytes,
                "quota_bytes": user_info.quota_bytes,
                "file_count": user_info.file_count
            })
        
        return {
            "ok": True,
            "users": users
        }
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"gRPC error: {e.details() if hasattr(e, 'details') else str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class UpdateQuotaRequest(BaseModel):
    quota_gb: float


@app.post("/auth/users/{username}/quota")
def update_user_quota(username: str, request: UpdateQuotaRequest):
    """
    Update user's storage quota.
    Uses gRPC to communicate with AuthService.
    """
    if not AUTH_SERVICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="AuthService not available")
    
    try:
        stub = get_auth_stub()
        if not stub:
            raise HTTPException(status_code=503, detail="Could not connect to AuthService")
        
        grpc_request = auth_pb2.UpdateUserQuotaRequest(
            login=username,
            quota_gb=int(request.quota_gb)
        )
        
        response = stub.UpdateUserQuota(grpc_request)
        
        return {
            "ok": response.ok,
            "message": response.message
        }
    except grpc.RpcError as e:
        raise HTTPException(status_code=503, detail=f"gRPC error: {e.details() if hasattr(e, 'details') else str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
