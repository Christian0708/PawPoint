"""
NetworkService - Independent network service for the cloud
Manages the discovery network that nodes connect to
Can be started independently from nodes
"""

import socket
import threading
import time
import json
from typing import Dict, Optional, Set
from datetime import datetime


class NetworkService:
    """
    Independent network service that manages the cloud discovery network
    Nodes connect to this service when they boot
    """
    
    def __init__(
        self,
        discovery_port: int = 9999,
        broadcast_interval: float = 30.0,
        network_name: str = "CloudSim_Network",
        node_timeout: float = 90.0
    ):
        """
        Initialize NetworkService
        
        Args:
            discovery_port: UDP port for discovery protocol (default: 9999)
            broadcast_interval: Seconds between network announcements (default: 30)
            network_name: Name of the network/cloud
        """
        self.discovery_port = discovery_port
        self.broadcast_interval = broadcast_interval
        self.network_name = network_name
        self.node_timeout = node_timeout
        
        # Network status
        self.running = False
        self.network_available = False
        
        # Discovery socket
        self.discovery_socket: Optional[socket.socket] = None
        
        # Registered nodes {node_id: (host, port, last_seen)}
        self.registered_nodes: Dict[str, Dict] = {}
        self.registration_lock = threading.RLock()  # Use RLock (reentrant) to allow nested locks
        self.socket_lock = threading.Lock()  # Protect socket operations
        
        # Threads
        self.broadcast_thread: Optional[threading.Thread] = None
        self.listener_thread: Optional[threading.Thread] = None
        
        self.socket_lock = threading.Lock()  # Protect socket operations
        
        print(f"[NetworkService] Initialized: {network_name} (discovery port: {discovery_port})")
    
    def start(self):
        """Start the network service"""
        if self.running:
            # Verify socket is still valid
            try:
                if self.discovery_socket:
                    self.discovery_socket.getsockname()
                    print("[NetworkService] Network service already running (socket valid)")
                    return
                else:
                    print("[NetworkService] Flag says running but socket is None, restarting...")
                    self.running = False
                    self.network_available = False
            except (OSError, AttributeError):
                print("[NetworkService] Flag says running but socket is invalid, restarting...")
                self.running = False
                self.network_available = False
        
        try:
            # Close any existing socket first
            if self.discovery_socket:
                try:
                    self.discovery_socket.close()
                except:
                    pass
                self.discovery_socket = None
            
            # Create UDP socket for discovery
            self.discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.discovery_socket.bind(('', self.discovery_port))
            self.discovery_socket.settimeout(1.0)  # Non-blocking with timeout
            
            self.running = True
            self.network_available = True
            
            # Start listener thread
            self.listener_thread = threading.Thread(
                target=self._listener_loop,
                name="NetworkService-Listener",
                daemon=True
            )
            self.listener_thread.start()
            
            # Start broadcast thread
            self.broadcast_thread = threading.Thread(
                target=self._broadcast_loop,
                name="NetworkService-Broadcast",
                daemon=True
            )
            self.broadcast_thread.start()
            # Start cleanup thread
            self.cleanup_thread = threading.Thread(
                target=self._cleanup_loop,
                name="NetworkService-Cleanup",
                daemon=True
            )
            self.cleanup_thread.start()
            
            # Verify threads started
            import time
            time.sleep(0.1)  # Give threads a moment to start
            
            print(f"[NetworkService] Network service started on port {self.discovery_port}")
            print(f"[NetworkService] Network '{self.network_name}' is now available")
            print(f"[NetworkService] Listener thread alive: {self.listener_thread.is_alive() if self.listener_thread else False}")
            print(f"[NetworkService] Broadcast thread alive: {self.broadcast_thread.is_alive() if self.broadcast_thread else False}")
            
        except Exception as e:
            print(f"[NetworkService] Error starting network service: {e}")
            import traceback
            traceback.print_exc()
            self.running = False
            self.network_available = False
            if self.discovery_socket:
                try:
                    self.discovery_socket.close()
                except:
                    pass
                self.discovery_socket = None
    
    def stop(self):
        """Stop the network service - only call this explicitly via API"""
        if not self.running:
            return
        
        print("[NetworkService] Stop() called - shutting down network service...")
        self.running = False
        self.network_available = False
        
        # Close socket with lock protection
        with self.socket_lock:
            if self.discovery_socket:
                try:
                    self.discovery_socket.close()
                except Exception:
                    pass
                self.discovery_socket = None
        
        print("[NetworkService] Network service stopped")
        if hasattr(self, 'cleanup_thread') and self.cleanup_thread:
            try:
                self.cleanup_thread.join(timeout=1.0)
            except Exception:
                pass
    
    def _listener_loop(self):
        """Listen for node registration requests - NEVER exits unless self.running is False"""
        consecutive_errors = 0
        max_consecutive_errors = 50  # Increased threshold
        
        print("[NetworkService] Listener loop started")
        
        while self.running:
            try:
                # Ensure socket exists and is valid
                if not self.discovery_socket:
                    print("[NetworkService] Discovery socket is None, attempting to recreate...")
                    try:
                        self.discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        self.discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        self.discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                        self.discovery_socket.bind(('', self.discovery_port))
                        self.discovery_socket.settimeout(1.0)
                        print("[NetworkService] Socket recreated successfully")
                        consecutive_errors = 0
                    except OSError as e:
                        if "Address already in use" in str(e) or "Only one usage" in str(e):
                            print(f"[NetworkService] Port {self.discovery_port} in use, waiting...")
                            time.sleep(2.0)
                            continue
                        print(f"[NetworkService] Failed to recreate socket: {e}")
                        time.sleep(2.0)
                        consecutive_errors += 1
                        if consecutive_errors >= max_consecutive_errors:
                            print("[NetworkService] Too many socket recreation failures, will retry...")
                            consecutive_errors = 0  # Reset and keep trying
                        continue
                    except Exception as e:
                        print(f"[NetworkService] Unexpected error recreating socket: {e}")
                        time.sleep(2.0)
                        continue
                
                # Receive data - this is the critical operation
                try:
                    data, addr = self.discovery_socket.recvfrom(4096)
                    consecutive_errors = 0  # Reset on successful receive
                except OSError as e:
                    # Socket might have been closed externally
                    if "Bad file descriptor" in str(e) or "Socket operation on non-socket" in str(e):
                        print(f"[NetworkService] Socket invalid, will recreate: {e}")
                        try:
                            self.discovery_socket.close()
                        except:
                            pass
                        self.discovery_socket = None
                        continue
                    raise  # Re-raise to be handled by outer exception handler
                
                try:
                    message = json.loads(data.decode('utf-8'))
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    print(f"[NetworkService] Invalid message from {addr}: {e}")
                    continue
                
                msg_type = message.get('type')
                
                if msg_type == 'NODE_REGISTER':
                    # Node wants to register with the network
                    self._handle_node_registration(message, addr)
                elif msg_type == 'NETWORK_QUERY':
                    # Node is checking if network is available
                    self._handle_network_query(addr)
                elif msg_type == 'NODE_HEARTBEAT':
                    # Node heartbeat to stay registered
                    self._handle_heartbeat(message)
                elif msg_type == 'NODE_UNREGISTER':
                    # Node requests immediate unregister
                    self._handle_node_unregister(message)
                elif msg_type == 'NETWORK_SHUTDOWN':
                    # Request to shutdown the network service
                    self._handle_shutdown_request(message, addr)
                    
            except socket.timeout:
                consecutive_errors = 0  # Timeout is normal, reset counter
                continue
            except OSError as e:
                # Socket errors (connection reset, broken pipe, etc.) - continue running
                consecutive_errors += 1
                if self.running:
                    # Only log if it's not a normal connection reset
                    if "WinError 10054" not in str(e) and "Connection refused" not in str(e) and "Bad file descriptor" not in str(e):
                        print(f"[NetworkService] Socket error in listener (continuing): {e}")
                
                # If socket is bad, recreate it
                if "Bad file descriptor" in str(e) or "Socket operation on non-socket" in str(e):
                    try:
                        if self.discovery_socket:
                            self.discovery_socket.close()
                    except:
                        pass
                    self.discovery_socket = None  # Trigger recreation on next loop
                    consecutive_errors = 0
                    time.sleep(0.5)
                    continue
                
                if consecutive_errors >= max_consecutive_errors:
                    print(f"[NetworkService] Too many socket errors ({consecutive_errors}), attempting socket recovery...")
                    try:
                        if self.discovery_socket:
                            self.discovery_socket.close()
                        self.discovery_socket = None  # Trigger recreation on next loop
                        consecutive_errors = 0
                    except Exception:
                        pass
                time.sleep(0.5)  # Brief delay before retry
                continue  # CRITICAL: Always continue, never break
            except Exception as e:
                consecutive_errors += 1
                if self.running:
                    print(f"[NetworkService] Error in listener: {e}")
                    import traceback
                    traceback.print_exc()
                if consecutive_errors >= max_consecutive_errors:
                    print(f"[NetworkService] Too many errors ({consecutive_errors}), pausing but continuing...")
                    time.sleep(2.0)
                    consecutive_errors = 0
                else:
                    time.sleep(0.1)  # Small delay to prevent tight error loop
                continue  # CRITICAL: Always continue, never break
        
        print("[NetworkService] Listener loop exited (self.running = False)")
    
    def _handle_node_registration(self, message: Dict, addr: tuple):
        """Handle node registration request"""
        node_id = message.get('node_id')
        host = message.get('host', addr[0])
        port = message.get('port')
        
        if not node_id or not port:
            return
        
        with self.registration_lock:
            self.registered_nodes[node_id] = {
                'host': host,
                'port': port,
                'last_seen': time.time(),
                'registered_at': datetime.now().isoformat()
            }
            # Get registered nodes count and dict while we still hold the lock
            registered_count = len(self.registered_nodes)
            registered_nodes_dict = dict(self.registered_nodes)  # Copy while holding lock
        
        # Send registration confirmation (outside lock to avoid deadlock)
        response = {
            'type': 'REGISTRATION_CONFIRMED',
            'network_name': self.network_name,
            'network_available': True,
            'discovery_port': self.discovery_port,
            'registered_nodes': registered_count,
            'nodes': registered_nodes_dict
        }
        
        # Send confirmation with socket lock to prevent concurrent access issues
        with self.socket_lock:
            try:
                if self.discovery_socket:
                    self.discovery_socket.sendto(
                        json.dumps(response).encode('utf-8'),
                        addr
                    )
                    print(f"[NetworkService] Node {node_id} registered from {host}:{port}")
                else:
                    print(f"[NetworkService] Warning: Cannot send confirmation - socket is None (node {node_id} still registered)")
            except OSError as e:
                # Socket error - node is still registered, just couldn't send confirmation
                print(f"[NetworkService] Warning: Could not send registration confirmation to {node_id}: {e}")
            except Exception as e:
                print(f"[NetworkService] Error sending registration confirmation: {e}")

    def _cleanup_loop(self):
        """Remove nodes that have not sent heartbeat within timeout"""
        # Note: This cleanup is disabled by default because nodes don't send
        # heartbeats to NetworkService (they use NodeDiscovery for peer-to-peer).
        # Only enable if you implement NODE_HEARTBEAT from nodes to this service.
        while self.running:
            try:
                time.sleep(60.0)  # Check every 60 seconds instead of 5
                # Cleanup disabled - nodes stay registered until explicit unregister
                # To enable, uncomment the code below:
                #
                # now = time.time()
                # to_remove = []
                # with self.registration_lock:
                #     for nid, info in list(self.registered_nodes.items()):
                #         last_seen = info.get('last_seen', 0)
                #         if now - last_seen > self.node_timeout:
                #             to_remove.append(nid)
                #     for nid in to_remove:
                #         del self.registered_nodes[nid]
                #         print(f"[NetworkService] Removed inactive node {nid}")
            except Exception:
                time.sleep(60.0)
    
    def _handle_network_query(self, addr: tuple):
        """Handle network availability query"""
        response = {
            'type': 'NETWORK_RESPONSE',
            'network_name': self.network_name,
            'network_available': True,
            'discovery_port': self.discovery_port,
            'registered_nodes': len(self.registered_nodes)
        }
        
        with self.socket_lock:
            try:
                if self.discovery_socket:
                    self.discovery_socket.sendto(
                        json.dumps(response).encode('utf-8'),
                        addr
                    )
            except Exception as e:
                print(f"[NetworkService] Error sending network response: {e}")
    
    def _handle_heartbeat(self, message: Dict):
        """Handle node heartbeat"""
        node_id = message.get('node_id')
        if node_id and node_id in self.registered_nodes:
            with self.registration_lock:
                self.registered_nodes[node_id]['last_seen'] = time.time()

    def _handle_node_unregister(self, message: Dict):
        """Handle node unregister request"""
        node_id = message.get('node_id')
        if not node_id:
            return
        with self.registration_lock:
            if node_id in self.registered_nodes:
                del self.registered_nodes[node_id]
                print(f"[NetworkService] Node {node_id} unregistered")
    
    def _handle_shutdown_request(self, message: Dict, addr: tuple):
        """Handle network shutdown request"""
        # SECURITY: Only allow shutdown from localhost or with authentication
        # For now, we'll log but require explicit stop() call from API
        print(f"[NetworkService] WARNING: Received shutdown request from {addr[0]}:{addr[1]}")
        print(f"[NetworkService] Shutdown via network message is DISABLED for safety")
        print(f"[NetworkService] Use the API endpoint /network/stop to stop the service")
        # DO NOT call self.stop() - this prevents accidental shutdowns from nodes
    
    def _broadcast_loop(self):
        """Broadcast network availability"""
        while self.running:
            try:
                if not self.discovery_socket:
                    time.sleep(self.broadcast_interval)
                    continue
                    
                # Broadcast network availability
                broadcast_msg = {
                    'type': 'NETWORK_ANNOUNCE',
                    'network_name': self.network_name,
                    'network_available': True,
                    'discovery_port': self.discovery_port,
                    'timestamp': datetime.now().isoformat()
                }
                
                # Broadcast to all interfaces
                broadcast_addr = ('255.255.255.255', self.discovery_port)
                with self.socket_lock:
                    if self.discovery_socket:
                        self.discovery_socket.sendto(
                            json.dumps(broadcast_msg).encode('utf-8'),
                            broadcast_addr
                        )
                
                time.sleep(self.broadcast_interval)
                
            except OSError as e:
                # Socket errors - continue but don't spam logs
                if self.running:
                    pass  # Silent - socket might be temporarily unavailable
                time.sleep(self.broadcast_interval)
            except Exception as e:
                if self.running:
                    print(f"[NetworkService] Error in broadcast: {e}")
                time.sleep(self.broadcast_interval)
    
    def get_registered_nodes(self) -> Dict:
        """Get list of registered nodes"""
        with self.registration_lock:
            return dict(self.registered_nodes)
    
    def _check_port_in_use(self, port: int) -> bool:
        """Check if network is actually running by sending a query and waiting for response"""
        try:
            # Try to query the network to see if it responds
            query_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            query_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            query_socket.settimeout(1.0)  # Short timeout
            
            # Send a network query
            query_msg = {
                'type': 'NETWORK_QUERY',
                'node_id': 'status_check',
                'host': 'localhost',
                'port': 0
            }
            
            query_socket.sendto(
                json.dumps(query_msg).encode('utf-8'),
                ('127.0.0.1', port)  # Try localhost first
            )
            
            # Wait for response
            try:
                data, addr = query_socket.recvfrom(4096)
                response = json.loads(data.decode('utf-8'))
                query_socket.close()
                # If we got a valid network response, network is running
                return response.get('type') == 'NETWORK_RESPONSE' and response.get('network_available', False)
            except socket.timeout:
                # No response - network might not be running
                query_socket.close()
                return False
        except Exception:
            # On any error, assume network is not running
            return False
    
    def get_network_status(self) -> Dict:
        """Get network status"""
        # Check if listener thread is still alive - if not, restart it
        if self.running:
            if not self.listener_thread or not self.listener_thread.is_alive():
                print("[NetworkService] WARNING: Listener thread died! Restarting...")
                try:
                    # Only restart if socket is still valid
                    if self.discovery_socket:
                        self.listener_thread = threading.Thread(
                            target=self._listener_loop,
                            name="NetworkService-Listener",
                            daemon=True
                        )
                        self.listener_thread.start()
                        print("[NetworkService] Listener thread restarted")
                    else:
                        # Socket is gone, need to fully restart
                        print("[NetworkService] Socket is None, network service needs restart")
                        self.running = False
                        self.network_available = False
                except Exception as e:
                    print(f"[NetworkService] Failed to restart listener thread: {e}")
                    # Don't set running=False here - let the caller decide
                    # Only set it if socket is definitely gone
                    if not self.discovery_socket:
                        self.running = False
                        self.network_available = False
        
        # Check if socket is still valid
        socket_valid = self.discovery_socket is not None
        try:
            if self.discovery_socket:
                # Try to get socket info to verify it's still valid
                self.discovery_socket.getsockname()
        except (OSError, AttributeError) as e:
            socket_valid = False
            if self.running:
                print(f"[NetworkService] Socket is invalid ({e}), marking as not running")
                self.running = False
                self.network_available = False
        
        # Check if port is actually in use (network might be running in another process)
        port_in_use = self._check_port_in_use(self.discovery_port)
        
        # If port is in use but we think we're not running, network is running in another process
        # Only report as running if it's actually running in THIS process OR responding to queries
        # But prioritize self.running if socket is valid
        actual_running = (self.running and socket_valid) or (port_in_use and not self.running)
        remote_registered = None
        if port_in_use and not self.running:
            try:
                q = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                q.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                q.settimeout(1.0)
                msg = {
                    'type': 'NETWORK_QUERY',
                    'node_id': 'status_probe',
                    'host': 'localhost',
                    'port': 0
                }
                q.sendto(json.dumps(msg).encode('utf-8'), ('255.255.255.255', self.discovery_port))
                try:
                    data, addr = q.recvfrom(4096)
                    resp = json.loads(data.decode('utf-8'))
                    remote_registered = int(resp.get('registered_nodes', 0))
                except socket.timeout:
                    remote_registered = None
                q.close()
            except Exception:
                remote_registered = None
        
        return {
            'network_name': self.network_name,
            'running': actual_running,
            'network_available': actual_running,
            'discovery_port': self.discovery_port,
            'registered_nodes': remote_registered if (remote_registered is not None and not self.running) else len(self.registered_nodes),
            'nodes': dict(self.registered_nodes),
            'running_in_this_process': self.running and socket_valid,
            'port_in_use': port_in_use,
            'running_in_another_process': port_in_use and not self.running
        }
    
    def is_network_available(self) -> bool:
        """Check if network is available"""
        return self.network_available and self.running
