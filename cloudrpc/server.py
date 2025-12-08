import grpc
from concurrent import futures
import os
import sys
import time
import hashlib

import cloudsim_pb2
import cloudsim_pb2_grpc

# Ensure CloudSim module path is available
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'CloudSim'))
if os.path.exists(base_dir) and base_dir not in sys.path:
    sys.path.append(base_dir)

from config_loader import ConfigLoader
from node_factory import NodeFactory
from network_service import NetworkService


class CloudSimServicer(cloudsim_pb2_grpc.CloudSimServicer):
    def __init__(self):
        # Use absolute path to config.yaml (same as REST API)
        config_path = os.path.join(base_dir, 'config.yaml')
        self.loader = ConfigLoader(config_path)
        self.loader.load()
        start_port = self.loader.get("node_factory.start_port", 5000)
        port_range = self.loader.get("node_factory.port_range_size", 1000)
        storage_root = os.path.abspath(self.loader.get("storage.base_directory", "storage"))
        state_file = self.loader.get("nodes_state_file", "nodes_state.json")
        # Use absolute path to ensure we use the same state file as CLI and REST API
        if not os.path.isabs(state_file):
            state_file = os.path.join(base_dir, state_file)
        self.factory = NodeFactory(start_port=start_port, port_range_size=port_range, state_file=state_file, storage_base_dir=storage_root)
        
        # Initialize NetworkService
        discovery_port = self.loader.get("network.discovery.port", 9999)
        broadcast_interval = self.loader.get("network.discovery.broadcast_interval_seconds", 30.0)
        network_name = self.loader.get("network.name", "CloudSim_Storage_Network")
        node_timeout = self.loader.get("network.discovery.node_timeout_seconds", 90.0)
        self.network_service = NetworkService(
            discovery_port=discovery_port,
            broadcast_interval=broadcast_interval,
            network_name=network_name,
            node_timeout=node_timeout
        )

    def GetStatus(self, request, context):
        # Reload state to ensure we have the latest nodes
        # This will load any new nodes that were created after server started
        # Use verbose=False to avoid spamming logs on every status check
        self.factory._load_state(verbose=False)
        
        nodes = []
        for node_id, node in self.factory.nodes.items():
            host = node.host
            port = node.port
            running = bool(getattr(node, 'running', False))
            try:
                import socket
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
            nodes.append(cloudsim_pb2.NodeInfo(
                node_id=node_id, 
                host=host, 
                port=port, 
                running=running, 
                storage_utilization_percent=su, 
                files_stored=fc,
                ip_address=ip_address,
                mac_address=mac_address
            ))
        total = len(nodes)
        running_count = sum(1 for n in nodes if n.running)
        stopped_count = total - running_count
        return cloudsim_pb2.StatusResponse(total_nodes=total, running_nodes=running_count, stopped_nodes=stopped_count, nodes=nodes)

    def StartNode(self, request, context):
        """Start a node. If the node thread is not alive, recreate it first."""
        node = self.factory.get_node(request.node_id)
        if not node:
            return cloudsim_pb2.OpResponse(ok=False, message="node not found")
        
        # Check if already running
        if node.is_alive() or node.running:
            return cloudsim_pb2.OpResponse(ok=True, message="node already running")
        
        # Node is stopped - need to recreate it
        config = self.factory.node_configs.get(request.node_id, {})
        if not config:
            return cloudsim_pb2.OpResponse(ok=False, message="node configuration not found")
        
        # Remove old node instance
        if request.node_id in self.factory.nodes:
            old_node = self.factory.nodes[request.node_id]
            try:
                if old_node.is_alive():
                    old_node.stop(graceful=False, timeout=1.0)
                    old_node.join(timeout=2.0)
            except Exception:
                pass
            del self.factory.nodes[request.node_id]
        
        # Wait for port to be released
        time.sleep(0.5)
        
        # Recreate node using the same approach as CLI and REST API
        from storage_virtual_node import StorageVirtualNode
        storage_root = os.path.abspath(self.loader.get("storage.base_directory", "storage"))
        new_node = StorageVirtualNode(
            node_id=request.node_id,
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
        
        # Add to factory
        self.factory.nodes[request.node_id] = new_node
        
        # Start the node
        try:
            new_node.start()
            return cloudsim_pb2.OpResponse(ok=True, message="started")
        except Exception as e:
            return cloudsim_pb2.OpResponse(ok=False, message=str(e))

    def StopNode(self, request, context):
        node = self.factory.get_node(request.node_id)
        if node and (node.is_alive() or node.running):
            try:
                node.stop(graceful=True, timeout=5.0)
                node.join(timeout=3.0)
                return cloudsim_pb2.OpResponse(ok=True, message="stopped")
            except Exception as e:
                return cloudsim_pb2.OpResponse(ok=False, message=str(e))
        cfg = self.factory.node_configs.get(request.node_id, {})
        host = cfg.get('host', 'localhost')
        port = int(cfg.get('port', 0) or 0)
        if not port:
            return cloudsim_pb2.OpResponse(ok=False, message="no port configured")
        try:
            import socket, json
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.0)
            s.connect((host, port))
            msg = { 'type': 'SHUTDOWN', 'reason': 'grpc_stop', 'timestamp': time.time(), 'sender_node_id': 'grpc' }
            data = json.dumps(msg).encode('utf-8')
            s.sendall(len(data).to_bytes(4, byteorder='big'))
            s.sendall(data)
            try:
                s.close()
            except Exception:
                pass
            deadline = time.time() + (15.0 if request.force else 5.0)
            while time.time() < deadline:
                try:
                    chk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    chk.settimeout(0.5)
                    chk.connect((host, port))
                    chk.close()
                    time.sleep(0.5)
                    continue
                except Exception:
                    return cloudsim_pb2.OpResponse(ok=True, message="stopped remotely")
            return cloudsim_pb2.OpResponse(ok=False, message="remote shutdown failed")
        except Exception as e:
            return cloudsim_pb2.OpResponse(ok=False, message=str(e))

    def StoreFile(self, request, context):
        try:
            path = request.file_path
            user = request.user
            replication = int(request.replication or 0)
            if not os.path.isfile(path):
                return cloudsim_pb2.StoreFileResponse(ok=False, file_id="", message="file not found")
            file_size = os.path.getsize(path)
            if user:
                try:
                    import grpc as grpcmod
                    sys.path.append(os.path.abspath('AuthService'))
                    import cloudsecurity_pb2 as pb
                    import cloudsecurity_pb2_grpc as grpcpb
                    channel = grpcmod.insecure_channel('localhost:51234')
                    stub = grpcpb.UserServiceStub(channel)
                    pre = stub.PrecheckStore(pb.PrecheckStoreRequest(login=user, file_size=file_size))
                    if not pre.allowed:
                        return cloudsim_pb2.StoreFileResponse(ok=False, file_id="", message=f"quota exceeded, remaining {pre.remaining_bytes}")
                except Exception:
                    pass
            nodes = self.factory.get_all_nodes()
            if not nodes:
                return cloudsim_pb2.StoreFileResponse(ok=False, file_id="", message="no nodes available")
            rep_factor = replication or 1
            rep_factor = max(1, min(rep_factor, len(nodes)))
            file_name = os.path.basename(path)
            file_id = hashlib.md5(f"{file_name}-{time.time()}".encode()).hexdigest()
            primary = nodes[0]
            chunk_size = max(256 * 1024, min(5 * 1024 * 1024, int(file_size / max(1, primary.max_concurrent_transfers))))
            num_chunks = (file_size + chunk_size - 1) // chunk_size
            assigned = []
            for i in range(num_chunks):
                targets = []
                for r in range(rep_factor):
                    targets.append(nodes[(i + r) % len(nodes)])
                assigned.append(targets)
            with open(path, 'rb') as f:
                for idx in range(num_chunks):
                    data = f.read(chunk_size)
                    for tgt in assigned[idx]:
                        ok, checksum = tgt.write_chunk_to_disk(file_id, idx, data)
                        if not ok:
                            return cloudsim_pb2.StoreFileResponse(ok=False, file_id="", message=f"failed chunk {idx} on {tgt.node_id}")
            if user:
                try:
                    import grpc as grpcmod
                    import cloudsecurity_pb2 as pb
                    import cloudsecurity_pb2_grpc as grpcpb
                    channel = grpcmod.insecure_channel('localhost:51234')
                    stub = grpcpb.UserServiceStub(channel)
                    node_ids = [n.node_id for group in assigned for n in group]
                    rec = pb.FileRecord(file_id=file_id, name=file_name, size=file_size, nodes=node_ids)
                    stub.AddFileRecord(pb.AddFileRecordRequest(login=user, record=rec))
                except Exception:
                    pass
            return cloudsim_pb2.StoreFileResponse(ok=True, file_id=file_id, message="stored")
        except Exception as e:
            return cloudsim_pb2.StoreFileResponse(ok=False, file_id="", message=str(e))

    def DownloadFile(self, request, context):
        nodes = self.factory.get_all_nodes()
        prefix = f"{request.file_id}_chunk_"
        for node in nodes:
            try:
                files = [f for f in os.listdir(node.chunks_path) if f.startswith(prefix) and f.endswith('.bin')]
                if not files:
                    continue
                def _chunk_index(name: str) -> int:
                    try:
                        return int(name.split('_chunk_')[-1].split('.bin')[0])
                    except Exception:
                        return 0
                files.sort(key=_chunk_index)
                for fname in files:
                    idx = _chunk_index(fname)
                    p = os.path.join(node.chunks_path, fname)
                    with open(p, 'rb') as fh:
                        data = fh.read()
                    yield cloudsim_pb2.FileChunk(data=data, index=idx)
                return
            except Exception:
                continue
        return

    def DeleteFile(self, request, context):
        file_id = request.file_id
        nodes = self.factory.get_all_nodes()
        if not nodes:
            return cloudsim_pb2.OpResponse(ok=False, message="no nodes available")
        total_removed = 0
        for node in nodes:
            try:
                total_removed += node.delete_file_by_id(file_id)
            except Exception:
                pass
        if request.user:
            try:
                import grpc as grpcmod
                sys.path.append(os.path.abspath('AuthService'))
                import cloudsecurity_pb2 as pb
                import cloudsecurity_pb2_grpc as grpcpb
                channel = grpcmod.insecure_channel('localhost:51234')
                stub = grpcpb.UserServiceStub(channel)
                lf = stub.ListFiles(pb.ListFilesRequest(login=request.user))
                file_size = 0
                for r in lf.records:
                    if r.file_id == file_id:
                        file_size = r.size
                        break
                if file_size > 0:
                    stub.RemoveFileRecord(pb.RemoveFileRecordRequest(login=request.user, file_id=file_id, size=file_size))
            except Exception:
                pass
        return cloudsim_pb2.OpResponse(ok=True, message=f"deleted bytes={total_removed}")

    def ReplicateFile(self, request, context):
        try:
            src = self.factory.get_node(request.source_node_id)
            dst = self.factory.get_node(request.dest_node_id)
            if not src or not dst:
                return cloudsim_pb2.OpResponse(ok=False, message="source or dest not found")
            try:
                src.network_manager.connect_to_node(dst.node_id, dst.host, dst.port)
            except Exception:
                pass
            chunks_dir = src.chunks_path
            prefix = f"{request.file_id}_chunk_"
            files = [f for f in os.listdir(chunks_dir) if f.startswith(prefix) and f.endswith('.bin')]
            if not files:
                return cloudsim_pb2.OpResponse(ok=False, message="no chunks found on source node")
            def _chunk_index(name: str) -> int:
                try:
                    return int(name.split('_chunk_')[-1].split('.bin')[0])
                except Exception:
                    return 0
            files.sort(key=_chunk_index)
            total_size = 0
            for fname in files:
                idx = _chunk_index(fname)
                try:
                    total_size += os.path.getsize(os.path.join(chunks_dir, fname))
                except Exception:
                    pass
                ok = src.send_chunk_to_node(dst.node_id, request.file_id, idx)
                if not ok:
                    return cloudsim_pb2.OpResponse(ok=False, message=f"failed transfer chunk {idx}")
            if request.user:
                try:
                    import grpc as grpcmod
                    sys.path.append(os.path.abspath('AuthService'))
                    import cloudsecurity_pb2 as pb
                    import cloudsecurity_pb2_grpc as grpcpb
                    channel = grpcmod.insecure_channel('localhost:51234')
                    stub = grpcpb.UserServiceStub(channel)
                    listed = stub.ListFiles(pb.ListFilesRequest(login=request.user))
                    existing = None
                    for rec in listed.records:
                        if rec.file_id == request.file_id:
                            existing = rec
                            break
                    if existing:
                        nodes = list(existing.nodes)
                        if dst.node_id not in nodes:
                            nodes.append(dst.node_id)
                        stub.RemoveFileRecord(pb.RemoveFileRecordRequest(login=request.user, file_id=request.file_id, size=existing.size))
                        newrec = pb.FileRecord(file_id=request.file_id, name=existing.name, size=existing.size, nodes=nodes)
                        add = stub.AddFileRecord(pb.AddFileRecordRequest(login=request.user, record=newrec))
                        if not add.ok:
                            return cloudsim_pb2.OpResponse(ok=False, message="failed to update file record in AuthService")
                    else:
                        node_ids = [dst.node_id]
                        newrec = pb.FileRecord(file_id=request.file_id, name=request.file_id, size=total_size, nodes=node_ids)
                        add = stub.AddFileRecord(pb.AddFileRecordRequest(login=request.user, record=newrec))
                        if not add.ok:
                            return cloudsim_pb2.OpResponse(ok=False, message="failed to add file record to AuthService")
                except Exception as e:
                    return cloudsim_pb2.OpResponse(ok=False, message=f"AuthService indexing failed: {e}")
            return cloudsim_pb2.OpResponse(ok=True, message="replicated")
        except Exception as e:
            return cloudsim_pb2.OpResponse(ok=False, message=str(e))

    def ListFiles(self, request, context):
        try:
            import grpc as grpcmod
            sys.path.append(os.path.abspath('AuthService'))
            import cloudsecurity_pb2 as pb
            import cloudsecurity_pb2_grpc as grpcpb
            channel = grpcmod.insecure_channel('localhost:51234')
            stub = grpcpb.UserServiceStub(channel)
            lf = stub.ListFiles(pb.ListFilesRequest(login=request.user))
            records = []
            for r in lf.records:
                records.append(cloudsim_pb2.FileRecord(
                    file_id=r.file_id,
                    name=r.name,
                    size=int(r.size),
                    nodes=list(r.nodes)
                ))
            return cloudsim_pb2.ListFilesResponse(records=records)
        except Exception as e:
            return cloudsim_pb2.ListFilesResponse(records=[])

    def GetProfile(self, request, context):
        try:
            import grpc as grpcmod
            sys.path.append(os.path.abspath('AuthService'))
            import cloudsecurity_pb2 as pb
            import cloudsecurity_pb2_grpc as grpcpb
            channel = grpcmod.insecure_channel('localhost:51234')
            stub = grpcpb.UserServiceStub(channel)
            prof = stub.GetProfile(pb.ProfileRequest(login=request.user))
            return cloudsim_pb2.ProfileResponse(
                used_bytes=int(prof.used_bytes),
                quota_bytes=int(prof.quota_bytes)
            )
        except Exception as e:
            return cloudsim_pb2.ProfileResponse(used_bytes=0, quota_bytes=0)

    def StartNetwork(self, request, context):
        """Start the network service"""
        try:
            # Check actual status, not just the flag
            status = self.network_service.get_network_status()
            if status.get('running', False):
                return cloudsim_pb2.OpResponse(ok=True, message="network service already running")
            
            # If not running, start it
            self.network_service.start()
            
            # Give it a moment to initialize
            import time
            time.sleep(0.2)
            
            # Check status again
            status = self.network_service.get_network_status()
            if status.get('running', False):
                return cloudsim_pb2.OpResponse(ok=True, message="network service started")
            else:
                return cloudsim_pb2.OpResponse(ok=False, message="failed to start network service - check logs")
        except Exception as e:
            import traceback
            traceback.print_exc()
            return cloudsim_pb2.OpResponse(ok=False, message=f"Error starting network: {str(e)}")

    def StopNetwork(self, request, context):
        """Stop the network service"""
        try:
            if not self.network_service.running:
                return cloudsim_pb2.OpResponse(ok=True, message="network service already stopped")
            self.network_service.stop()
            return cloudsim_pb2.OpResponse(ok=True, message="network service stopped")
        except Exception as e:
            return cloudsim_pb2.OpResponse(ok=False, message=str(e))

    def GetNetworkStatus(self, request, context):
        """Get network service status"""
        try:
            # Always return network_name and discovery_port from the service instance
            default_network_name = self.network_service.network_name if hasattr(self, 'network_service') else ''
            default_discovery_port = self.network_service.discovery_port if hasattr(self, 'network_service') else 0
            
            status = self.network_service.get_network_status()
            # Convert to protobuf response
            nodes_dict = {}
            for node_id, node_info in status.get('nodes', {}).items():
                # Convert last_seen to string if it's a float (timestamp)
                last_seen = node_info.get('last_seen', '')
                if isinstance(last_seen, (int, float)):
                    import datetime
                    last_seen = datetime.datetime.fromtimestamp(last_seen).isoformat()
                else:
                    last_seen = str(last_seen) if last_seen else ''
                
                registered_at = node_info.get('registered_at', '')
                registered_at = str(registered_at) if registered_at else ''
                
                nodes_dict[node_id] = cloudsim_pb2.NetworkNodeInfo(
                    host=str(node_info.get('host', '')),
                    port=int(node_info.get('port', 0)),
                    last_seen=last_seen,
                    registered_at=registered_at
                )
            
            return cloudsim_pb2.NetworkStatusResponse(
                running=status.get('running', False),
                network_name=status.get('network_name', default_network_name),
                discovery_port=status.get('discovery_port', default_discovery_port),
                registered_nodes=status.get('registered_nodes', 0),
                nodes=nodes_dict
            )
        except Exception as e:
            import traceback
            print(f"[CloudSimServicer] Error getting network status: {e}")
            traceback.print_exc()
            # Return status with network service defaults even on error
            default_network_name = self.network_service.network_name if hasattr(self, 'network_service') else ''
            default_discovery_port = self.network_service.discovery_port if hasattr(self, 'network_service') else 0
            return cloudsim_pb2.NetworkStatusResponse(
                running=False,
                network_name=default_network_name,
                discovery_port=default_discovery_port,
                registered_nodes=0,
                nodes={}
            )

    def DeleteNode(self, request, context):
        """Delete a node"""
        try:
            success = self.factory.remove_node(request.node_id)
            if not success:
                return cloudsim_pb2.OpResponse(ok=False, message="node not found")
            return cloudsim_pb2.OpResponse(ok=True, message="node deleted")
        except Exception as e:
            return cloudsim_pb2.OpResponse(ok=False, message=str(e))


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    cloudsim_pb2_grpc.add_CloudSimServicer_to_server(CloudSimServicer(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == '__main__':
    serve()
