"""
Test script to verify node state persistence
Tests that nodes are saved and loaded correctly across CLI invocations
"""

import os
import json
import sys

# Add CloudSim to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from node_factory import NodeFactory


def test_state_persistence():
    """Test that nodes are saved and loaded correctly"""
    print("="*80)
    print("Testing Node State Persistence")
    print("="*80)
    print()
    
    state_file = "nodes_state.json"
    
    # Step 1: Check if state file exists
    print("[1/5] Checking for existing state file...")
    if os.path.exists(state_file):
        print(f"[OK] State file exists: {state_file}")
        with open(state_file, 'r') as f:
            existing_state = json.load(f)
            existing_nodes = existing_state.get("nodes", [])
            print(f"      Found {len(existing_nodes)} existing node(s) in state file")
            for node in existing_nodes:
                print(f"        - {node.get('node_id')}: {node.get('host')}:{node.get('port')}")
    else:
        print(f"[INFO] No existing state file (will be created on first node creation)")
    print()
    
    # Step 2: Create a new NodeFactory (should load existing state)
    print("[2/5] Creating NodeFactory (should load existing nodes)...")
    factory1 = NodeFactory()
    loaded_nodes = factory1.get_all_nodes()
    print(f"[OK] NodeFactory created, loaded {len(loaded_nodes)} node(s)")
    for node in loaded_nodes:
        config = factory1.node_configs.get(node.node_id, {})
        print(f"      - {node.node_id}: {config.get('host')}:{config.get('port')} "
              f"(CPU: {config.get('cpu_capacity')}, Memory: {config.get('memory_capacity')}GB, "
              f"Storage: {config.get('storage_capacity')}GB, Bandwidth: {config.get('bandwidth')}Mbps)")
    print()
    
    # Step 3: Create a new test node
    print("[3/5] Creating a new test node...")
    test_node_id = "test_persistence_node"
    
    # Remove test node if it already exists
    if factory1.get_node(test_node_id):
        print(f"[INFO] Test node {test_node_id} already exists, removing it first...")
        factory1.remove_node(test_node_id)
    
    test_node = factory1.create_node(
        node_id=test_node_id,
        cpu_capacity=2,
        memory_capacity=4,
        storage_capacity=20,
        bandwidth=100,
        host="localhost",
        port=None,  # Auto-assign port
        enable_network_check=False  # Disable for testing
    )
    
    if test_node:
        config = factory1.node_configs.get(test_node_id, {})
        print(f"[OK] Test node created: {test_node_id}")
        print(f"      Host: {config.get('host')}, Port: {config.get('port')}")
        print(f"      CPU: {config.get('cpu_capacity')}, Memory: {config.get('memory_capacity')}GB")
        print(f"      Storage: {config.get('storage_capacity')}GB, Bandwidth: {config.get('bandwidth')}Mbps")
    else:
        print("[ERROR] Failed to create test node")
        return False
    print()
    
    # Step 4: Verify state file was updated
    print("[4/5] Verifying state file was saved...")
    if os.path.exists(state_file):
        with open(state_file, 'r') as f:
            saved_state = json.load(f)
            saved_nodes = saved_state.get("nodes", [])
            test_node_found = any(n.get("node_id") == test_node_id for n in saved_nodes)
            
            if test_node_found:
                print(f"[OK] State file contains {len(saved_nodes)} node(s), including test node")
                test_node_data = next(n for n in saved_nodes if n.get("node_id") == test_node_id)
                print(f"      Test node data: {test_node_data}")
            else:
                print(f"[ERROR] Test node not found in state file")
                return False
    else:
        print(f"[ERROR] State file not found after node creation")
        return False
    print()
    
    # Step 5: Create a new NodeFactory instance (simulating new CLI invocation)
    print("[5/5] Creating new NodeFactory instance (simulating new CLI command)...")
    factory2 = NodeFactory()
    reloaded_nodes = factory2.get_all_nodes()
    
    # Check if test node is loaded
    reloaded_test_node = factory2.get_node(test_node_id)
    if reloaded_test_node:
        reloaded_config = factory2.node_configs.get(test_node_id, {})
        print(f"[OK] Test node successfully loaded in new factory instance")
        print(f"      Node ID: {reloaded_test_node.node_id}")
        print(f"      Host: {reloaded_config.get('host')}, Port: {reloaded_config.get('port')}")
        print(f"      CPU: {reloaded_config.get('cpu_capacity')}, Memory: {reloaded_config.get('memory_capacity')}GB")
        print(f"      Storage: {reloaded_config.get('storage_capacity')}GB, Bandwidth: {reloaded_config.get('bandwidth')}Mbps")
        
        # Verify all attributes match
        original_config = factory1.node_configs.get(test_node_id, {})
        matches = (
            reloaded_config.get('cpu_capacity') == original_config.get('cpu_capacity') and
            reloaded_config.get('memory_capacity') == original_config.get('memory_capacity') and
            reloaded_config.get('storage_capacity') == original_config.get('storage_capacity') and
            reloaded_config.get('bandwidth') == original_config.get('bandwidth') and
            reloaded_config.get('host') == original_config.get('host') and
            reloaded_config.get('port') == original_config.get('port')
        )
        
        if matches:
            print(f"[OK] All node attributes match correctly")
        else:
            print(f"[ERROR] Node attributes don't match!")
            print(f"      Original: {original_config}")
            print(f"      Reloaded: {reloaded_config}")
            return False
    else:
        print(f"[ERROR] Test node not found in new factory instance")
        return False
    
    print()
    print("="*80)
    print("[SUCCESS] All persistence tests passed!")
    print("="*80)
    print()
    print("Summary:")
    print(f"  - State file: {state_file}")
    print(f"  - Total nodes in state: {len(saved_nodes)}")
    print(f"  - Test node created and persisted: {test_node_id}")
    print(f"  - Test node successfully reloaded: [OK]")
    print()
    print("Note: Test node will remain in state file.")
    print()
    
    return True


if __name__ == "__main__":
    try:
        success = test_state_persistence()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

