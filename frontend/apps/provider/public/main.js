// CloudSim Provider Portal - Administrator Interface
// Full control over infrastructure with all management features

const app = document.getElementById('app')

// Utility functions
function formatBytes(bytes) {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

function showNotification(message, type = 'info') {
  const notification = document.createElement('div')
  notification.className = `notification ${type}`
  notification.textContent = message
  notification.style.cssText = `
    position: fixed; top: 20px; right: 20px; padding: 12px 20px;
    background: ${type === 'error' ? '#c22' : type === 'success' ? '#0a7' : '#1a1a2e'};
    color: white; border-radius: 6px; z-index: 1000; box-shadow: 0 2px 8px rgba(0,0,0,0.2);
  `
  document.body.appendChild(notification)
  setTimeout(() => notification.remove(), 3000)
}

function setLoading(element, loading) {
  if (loading) {
    element.style.opacity = '0.6'
    element.style.pointerEvents = 'none'
  } else {
    element.style.opacity = '1'
    element.style.pointerEvents = 'auto'
  }
}

function renderShell() {
  const head = `
    <header>
      <div class="row">
        <strong>CloudSim Provider Portal</strong>
        <span class="muted" id="summary"></span>
      </div>
      <nav>
        <a href="#/dashboard" data-route="dashboard">Dashboard</a>
        <a href="#/nodes" data-route="nodes">Nodes</a>
        <a href="#/metrics" data-route="metrics">Metrics</a>
        <a href="#/users" data-route="users">Users</a>
      </nav>
    </header>
  `
  const main = `<main id="view"></main>`
  app.innerHTML = head + main
}

function setActive(route) {
  document.querySelectorAll('nav a').forEach(a => {
    if (a.getAttribute('data-route') === route) a.classList.add('active')
    else a.classList.remove('active')
  })
}

// Enhanced Dashboard
function renderDashboard() {
  setActive('dashboard')
  const view = document.getElementById('view')
  view.innerHTML = `
    <div class="row" style="justify-content: space-between; margin-bottom: 20px;">
      <h2>System Dashboard</h2>
      <button id="refresh" class="primary">Refresh</button>
    </div>
    
    <div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 16px; margin-bottom: 20px;">
      <div class="card">
        <h3>Nodes</h3>
        <div id="nodesCard" class="loading">Loading...</div>
      </div>
      <div class="card">
        <h3>Storage</h3>
        <div id="storageCard" class="loading">Loading...</div>
      </div>
      <div class="card">
        <h3>Network Service</h3>
        <div id="networkCard" class="loading">Loading...</div>
      </div>
      <div class="card">
        <h3>System Health</h3>
        <div id="healthCard" class="loading">Loading...</div>
      </div>
    </div>
    
    <div class="card">
      <h3>Quick Actions</h3>
      <div class="row" style="flex-wrap: wrap; gap: 8px; margin-top: 12px;">
        <button id="startAll" class="start">Start All Nodes</button>
        <button id="stopAll" class="stop">Stop All Nodes</button>
        <button id="restartAll" class="restart">Restart All Nodes</button>
        <button id="startNetwork" class="primary">Start Network Service</button>
        <button id="stopNetwork" class="stop">Stop Network Service</button>
      </div>
    </div>
    
    <div class="card">
      <h3>Resource Summary</h3>
      <div id="resourceSummary" class="loading">Loading...</div>
    </div>
    
    <div class="card">
      <h3>Alerts</h3>
      <div id="alerts" class="loading">Loading...</div>
    </div>
  `
  
  function load() {
    const viewEl = document.getElementById('view')
    setLoading(viewEl, true)
    
    fetch('/status')
      .then(r => r.json())
      .then(data => {
        // Nodes Card
        document.getElementById('nodesCard').innerHTML = `
          <div style="font-size: 32px; font-weight: bold; margin: 8px 0;">${data.total_nodes}</div>
          <div class="muted">Total Nodes</div>
          <div style="margin-top: 12px;">
            <span style="color: #0a7;">${data.running_nodes} Running</span> • 
            <span style="color: #c22;">${data.stopped_nodes} Stopped</span>
          </div>
        `
        
        // Storage Card - Calculate correctly from system info
        fetch('/system/info')
          .then(r => r.json())
          .then(systemInfo => {
            const storageCard = document.getElementById('storageCard')
            if (systemInfo.resources) {
              const totalStorageGB = systemInfo.resources.total_storage_gb || 0
              const usedStorageGB = systemInfo.resources.used_storage_gb || 0
              const storageUtil = systemInfo.resources.storage_utilization_percent || 0
              
              storageCard.innerHTML = `
                <div style="font-size: 32px; font-weight: bold; margin: 8px 0;">${storageUtil.toFixed(1)}%</div>
                <div class="muted">Storage Utilization</div>
                <div style="margin-top: 12px; height: 8px; background: #f0f0f0; border-radius: 4px; overflow: hidden;">
                  <div style="height: 100%; width: ${Math.min(storageUtil, 100)}%; background: ${storageUtil > 75 ? '#c22' : storageUtil > 50 ? '#fa0' : '#0a7'};"></div>
                </div>
                <div class="muted" style="font-size: 12px; margin-top: 8px;">
                  ${usedStorageGB.toFixed(2)} GB / ${totalStorageGB.toFixed(2)} GB
                </div>
              `
            } else {
              // Fallback: calculate from nodes if system info not available
              const totalStorage = data.nodes?.reduce((sum, n) => sum + (n.storage_utilization_percent || 0), 0) / (data.nodes?.length || 1) || 0
              storageCard.innerHTML = `
                <div style="font-size: 32px; font-weight: bold; margin: 8px 0;">${totalStorage.toFixed(1)}%</div>
                <div class="muted">Storage Utilization</div>
                <div style="margin-top: 12px; height: 8px; background: #f0f0f0; border-radius: 4px; overflow: hidden;">
                  <div style="height: 100%; width: ${totalStorage}%; background: ${totalStorage > 75 ? '#c22' : totalStorage > 50 ? '#fa0' : '#0a7'};"></div>
                </div>
              `
            }
      })
      .catch(() => {
            // Fallback if system/info fails
            const totalStorage = data.nodes?.reduce((sum, n) => sum + (n.storage_utilization_percent || 0), 0) / (data.nodes?.length || 1) || 0
            document.getElementById('storageCard').innerHTML = `
              <div style="font-size: 32px; font-weight: bold; margin: 8px 0;">${totalStorage.toFixed(1)}%</div>
              <div class="muted">Storage Utilization</div>
              <div style="margin-top: 12px; height: 8px; background: #f0f0f0; border-radius: 4px; overflow: hidden;">
                <div style="height: 100%; width: ${totalStorage}%; background: ${totalStorage > 75 ? '#c22' : totalStorage > 50 ? '#fa0' : '#0a7'};"></div>
              </div>
            `
          })
        
        // Network Card
        fetch('/network/status')
          .then(r => r.json())
          .then(networkData => {
            const networkCard = document.getElementById('networkCard')
            networkCard.innerHTML = `
              <div style="display: flex; align-items: center; gap: 8px; margin: 8px 0;">
                <span style="width: 12px; height: 12px; border-radius: 50%; background: ${networkData.running ? '#0a7' : '#c22'};"></span>
                <strong>${networkData.running ? 'Running' : 'Stopped'}</strong>
              </div>
              <div class="muted">${networkData.network_name || 'Network'}</div>
              <div class="muted" style="font-size: 12px;">Port: ${networkData.discovery_port || 9999} • ${networkData.registered_nodes || 0} registered</div>
            `
          })
          .catch(() => {
            document.getElementById('networkCard').innerHTML = `
              <div class="muted">Network status unavailable</div>
            `
          })
        
        // Health Card
        const healthy = data.running_nodes
        const healthPercent = data.total_nodes > 0 ? (healthy / data.total_nodes * 100) : 0
        document.getElementById('healthCard').innerHTML = `
          <div style="font-size: 32px; font-weight: bold; margin: 8px 0; color: ${healthPercent > 80 ? '#0a7' : healthPercent > 50 ? '#fa0' : '#c22'};">
            ${healthPercent.toFixed(0)}%
          </div>
          <div class="muted">System Health</div>
        `
        
        // Resource Summary
        fetch('/system/info')
          .then(r => r.json())
          .then(systemInfo => {
            const resourceSummary = document.getElementById('resourceSummary')
            if (systemInfo.resources) {
              resourceSummary.innerHTML = `
                <div class="row" style="flex-wrap: wrap; gap: 24px; margin-bottom: 12px;">
                  <div><strong>Total CPU:</strong> ${systemInfo.resources.total_cpu || 0} vCPUs</div>
                  <div><strong>Total Memory:</strong> ${systemInfo.resources.total_memory_gb || 0} GB</div>
                  <div><strong>Total Storage:</strong> ${systemInfo.resources.total_storage_gb?.toFixed(2) || 0} GB</div>
                  <div><strong>Total Bandwidth:</strong> ${systemInfo.resources.total_bandwidth_mbps || 0} Mbps</div>
                </div>
                ${systemInfo.averages ? `
                <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #eee;">
                  <div class="muted" style="margin-bottom: 8px;">Averages per Node:</div>
                  <div class="row" style="flex-wrap: wrap; gap: 24px;">
                    <div><strong>CPU:</strong> ${systemInfo.averages.cpu || 0} vCPUs</div>
                    <div><strong>Memory:</strong> ${systemInfo.averages.memory_gb || 0} GB</div>
                    <div><strong>Storage:</strong> ${systemInfo.averages.storage_gb || 0} GB</div>
                    <div><strong>Bandwidth:</strong> ${systemInfo.averages.bandwidth_mbps || 0} Mbps</div>
                  </div>
                </div>
                ` : ''}
              `
            }
          })
          .catch(() => {
            document.getElementById('resourceSummary').innerHTML = `
              <div class="muted">System information unavailable</div>
            `
          })
        
        // Alerts (placeholder)
        document.getElementById('alerts').innerHTML = `
          <div class="muted">No alerts at this time</div>
        `
        
        // Update summary
        const summary = document.getElementById('summary')
        summary.textContent = `${data.running_nodes}/${data.total_nodes} nodes running`
        
        setLoading(viewEl, false)
      })
      .catch(err => {
        showNotification('Failed to load dashboard', 'error')
        setLoading(viewEl, false)
      })
  }
  
  // Quick actions - use setTimeout to ensure DOM is ready
  setTimeout(() => {
    const startAllBtn = document.getElementById('startAll')
    if (startAllBtn) {
      startAllBtn.addEventListener('click', (e) => {
        e.preventDefault()
        e.stopPropagation()
        console.log('Start All Nodes clicked')
        showNotification('Checking node status...', 'info')
        fetch('/status')
          .then(r => {
            if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`)
            return r.json()
          })
          .then(d => {
            console.log('Status response:', d)
            const stopped = (d.nodes || []).filter(n => !n.running)
            console.log('Stopped nodes:', stopped)
            if (stopped.length === 0) {
              showNotification('No stopped nodes to start', 'info')
              return Promise.resolve([])
            }
            showNotification(`Starting ${stopped.length} node(s)...`, 'info')
            return Promise.all(stopped.map(n => {
              console.log(`Starting node ${n.node_id}`)
              return fetch(`/nodes/${n.node_id}/start`, { method: 'POST' })
                .then(r => {
                  if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`)
                  return r.json()
                })
                .then(result => {
                  console.log(`Node ${n.node_id} start result:`, result)
                  return { node: n.node_id, success: result.ok || false }
                })
                .catch(err => {
                  console.error(`Node ${n.node_id} start error:`, err)
                  return { node: n.node_id, success: false, error: err.message }
                })
            }))
          })
          .then(results => {
            if (!results || results.length === 0) return
            console.log('All start results:', results)
            const successCount = results.filter(r => r.success).length
            const failCount = results.length - successCount
            if (successCount > 0) {
              showNotification(`${successCount} node(s) started successfully`, 'success')
            }
            if (failCount > 0) {
              showNotification(`${failCount} node(s) failed to start`, 'error')
            }
            load()
          })
          .catch(err => {
            showNotification('Failed to start nodes: ' + err.message, 'error')
            console.error('Start all error:', err)
          })
      })
      console.log('Start All button event listener attached')
    } else {
      console.error('startAll button not found!')
    }
  }, 100)
  
  document.getElementById('stopAll').addEventListener('click', () => {
    if (confirm('Stop all nodes?')) {
      fetch('/status')
        .then(r => r.json())
        .then(d => {
          const running = (d.nodes || []).filter(n => n.running)
          if (running.length === 0) {
            showNotification('No running nodes to stop', 'info')
            return
          }
          showNotification(`Stopping ${running.length} node(s)...`, 'info')
          Promise.all(running.map(n => 
            fetch(`/nodes/${n.node_id}/stop?force=true`, { method: 'POST' })
              .then(r => r.json())
              .then(result => ({ node: n.node_id, success: result.ok || false }))
              .catch(err => ({ node: n.node_id, success: false, error: err.message }))
          ))
            .then(results => {
              const successCount = results.filter(r => r.success).length
              const failCount = results.length - successCount
              if (successCount > 0) {
                showNotification(`${successCount} node(s) stopped successfully`, 'success')
              }
              if (failCount > 0) {
                showNotification(`${failCount} node(s) failed to stop`, 'error')
              }
              load()
            })
            .catch(err => {
              showNotification('Failed to stop nodes: ' + err.message, 'error')
              console.error('Stop all error:', err)
            })
        })
        .catch(err => {
          showNotification('Failed to load node status: ' + err.message, 'error')
          console.error('Status fetch error:', err)
        })
    }
  })
  
  document.getElementById('restartAll').addEventListener('click', () => {
    if (confirm('Restart all nodes?')) {
      fetch('/status')
        .then(r => r.json())
        .then(d => {
          const running = (d.nodes || []).filter(n => n.running)
          if (running.length === 0) {
            showNotification('No running nodes to restart', 'info')
            return
          }
          showNotification(`Restarting ${running.length} node(s)...`, 'info')
          Promise.all(running.map(n => 
            fetch(`/nodes/${n.node_id}/stop?force=true`, { method: 'POST' })
              .then(r => r.json())
              .then(() => fetch(`/nodes/${n.node_id}/start`, { method: 'POST' }))
              .then(r => r.json())
              .then(result => ({ node: n.node_id, success: result.ok || false }))
              .catch(err => ({ node: n.node_id, success: false, error: err.message }))
          ))
            .then(results => {
              const successCount = results.filter(r => r.success).length
              const failCount = results.length - successCount
              if (successCount > 0) {
                showNotification(`${successCount} node(s) restarted successfully`, 'success')
              }
              if (failCount > 0) {
                showNotification(`${failCount} node(s) failed to restart`, 'error')
              }
  load()
            })
            .catch(err => {
              showNotification('Failed to restart nodes: ' + err.message, 'error')
              console.error('Restart all error:', err)
            })
        })
        .catch(err => {
          showNotification('Failed to load node status: ' + err.message, 'error')
          console.error('Status fetch error:', err)
        })
    }
  })
  
  document.getElementById('startNetwork').addEventListener('click', () => {
    fetch('/network/start', { method: 'POST' })
      .then(r => r.json())
      .then(data => {
        if (data.ok) {
          showNotification('Network service started', 'success')
          load()
        } else {
          showNotification('Failed to start network service', 'error')
        }
      })
      .catch(() => showNotification('Failed to start network service', 'error'))
  })
  
  document.getElementById('stopNetwork').addEventListener('click', () => {
    if (confirm('Stop network service?')) {
      fetch('/network/stop', { method: 'POST' })
        .then(r => r.json())
        .then(data => {
          if (data.ok) {
            showNotification('Network service stopped', 'success')
            load()
          } else {
            showNotification('Failed to stop network service', 'error')
          }
        })
        .catch(() => showNotification('Failed to stop network service', 'error'))
    }
  })
  
  document.getElementById('refresh').addEventListener('click', load)
  load()
}

// Nodes Management - Enhanced with create, delete, restart, details
function renderNodes() {
  setActive('nodes')
  const view = document.getElementById('view')
  view.innerHTML = `
    <div class="row" style="justify-content: space-between; margin-bottom: 20px;">
      <h2>Nodes Management</h2>
    </div>
    
    <div id="createNodeForm" class="card" style="display: none; margin-bottom: 20px;">
      <h3>Create New Node</h3>
      <div class="row" style="flex-wrap: wrap; gap: 12px; margin-top: 12px;">
        <div style="flex: 1; min-width: 200px;">
          <label style="display: block; margin-bottom: 4px; font-weight: 500;">Node ID</label>
          <input type="text" id="nodeId" placeholder="node1" style="width: 100%;" />
        </div>
        <div style="flex: 1; min-width: 120px;">
          <label style="display: block; margin-bottom: 4px; font-weight: 500;">CPU (vCPUs)</label>
          <input type="number" id="nodeCpu" value="2" min="1" style="width: 100%;" />
        </div>
        <div style="flex: 1; min-width: 120px;">
          <label style="display: block; margin-bottom: 4px; font-weight: 500;">Memory (GB)</label>
          <input type="number" id="nodeMemory" value="4" min="1" style="width: 100%;" />
        </div>
        <div style="flex: 1; min-width: 120px;">
          <label style="display: block; margin-bottom: 4px; font-weight: 500;">Storage (GB)</label>
          <input type="number" id="nodeStorage" value="10" min="1" style="width: 100%;" />
        </div>
        <div style="flex: 1; min-width: 120px;">
          <label style="display: block; margin-bottom: 4px; font-weight: 500;">Bandwidth (Mbps)</label>
          <input type="number" id="nodeBandwidth" value="100" min="1" style="width: 100%;" />
        </div>
      </div>
      <div class="row" style="margin-top: 12px; gap: 8px;">
        <button id="createNodeSubmit" class="primary">Create Node</button>
        <button id="createNodeCancel">Cancel</button>
        <label style="display: flex; align-items: center; gap: 8px; margin-left: auto;">
          <input type="checkbox" id="autoStart" />
          <span>Start after creation</span>
        </label>
      </div>
    </div>
    
    <div id="batchCreateForm" class="card" style="display: none; margin-bottom: 20px;">
      <h3>Create Multiple Nodes</h3>
      <div class="row" style="flex-wrap: wrap; gap: 12px; margin-top: 12px;">
        <div style="flex: 1; min-width: 150px;">
          <label style="display: block; margin-bottom: 4px; font-weight: 500;">Count</label>
          <input type="number" id="batchCount" value="3" min="1" style="width: 100%;" />
        </div>
        <div style="flex: 1; min-width: 150px;">
          <label style="display: block; margin-bottom: 4px; font-weight: 500;">Base ID Prefix</label>
          <input type="text" id="batchBaseId" value="node" style="width: 100%;" />
        </div>
        <div style="flex: 1; min-width: 120px;">
          <label style="display: block; margin-bottom: 4px; font-weight: 500;">CPU (vCPUs)</label>
          <input type="number" id="batchCpu" value="2" min="1" style="width: 100%;" />
        </div>
        <div style="flex: 1; min-width: 120px;">
          <label style="display: block; margin-bottom: 4px; font-weight: 500;">Memory (GB)</label>
          <input type="number" id="batchMemory" value="4" min="1" style="width: 100%;" />
        </div>
        <div style="flex: 1; min-width: 120px;">
          <label style="display: block; margin-bottom: 4px; font-weight: 500;">Storage (GB)</label>
          <input type="number" id="batchStorage" value="10" min="1" style="width: 100%;" />
        </div>
        <div style="flex: 1; min-width: 120px;">
          <label style="display: block; margin-bottom: 4px; font-weight: 500;">Bandwidth (Mbps)</label>
          <input type="number" id="batchBandwidth" value="100" min="1" style="width: 100%;" />
        </div>
      </div>
      <div class="row" style="margin-top: 12px; gap: 8px;">
        <button id="batchCreateSubmit" class="primary">Create Nodes</button>
        <button id="batchCreateCancel">Cancel</button>
        <label style="display: flex; align-items: center; gap: 8px; margin-left: auto;">
          <input type="checkbox" id="batchAutoStart" />
          <span>Start after creation</span>
        </label>
      </div>
    </div>
    
    <div class="row" style="gap: 8px; margin-bottom: 12px;">
      <button id="showCreateForm">+ Create Single Node</button>
      <button id="showBatchForm">+ Create Multiple Nodes</button>
    </div>
    
    <div id="nodesGrid" class="grid" style="grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); align-items: start;">
      <div class="loading">Loading nodes...</div>
    </div>
  `
  
  // Form toggles
  document.getElementById('showCreateForm').addEventListener('click', () => {
    document.getElementById('createNodeForm').style.display = 
      document.getElementById('createNodeForm').style.display === 'none' ? 'block' : 'none'
    document.getElementById('batchCreateForm').style.display = 'none'
  })
  
  document.getElementById('showBatchForm').addEventListener('click', () => {
    document.getElementById('batchCreateForm').style.display = 
      document.getElementById('batchCreateForm').style.display === 'none' ? 'block' : 'none'
    document.getElementById('createNodeForm').style.display = 'none'
  })
  
  document.getElementById('createNodeCancel').addEventListener('click', () => {
    document.getElementById('createNodeForm').style.display = 'none'
  })
  
  document.getElementById('batchCreateCancel').addEventListener('click', () => {
    document.getElementById('batchCreateForm').style.display = 'none'
  })
  
  // Create single node
  document.getElementById('createNodeSubmit').addEventListener('click', () => {
    const nodeId = document.getElementById('nodeId').value
    if (!nodeId) {
      showNotification('Node ID is required', 'error')
      return
    }
    
    const nodeData = {
      node_id: nodeId,
      cpu: parseInt(document.getElementById('nodeCpu').value),
      memory: parseInt(document.getElementById('nodeMemory').value),
      storage: parseInt(document.getElementById('nodeStorage').value),
      bandwidth: parseInt(document.getElementById('nodeBandwidth').value)
    }
    
    fetch('/nodes', { 
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        node_id: nodeId,
        cpu: parseInt(document.getElementById('nodeCpu').value),
        memory: parseInt(document.getElementById('nodeMemory').value),
        storage: parseInt(document.getElementById('nodeStorage').value),
        bandwidth: parseInt(document.getElementById('nodeBandwidth').value),
        host: 'localhost'
      })
    })
      .then(r => r.json())
      .then(data => {
        if (data.ok) {
          showNotification(`Node ${nodeId} created successfully`, 'success')
          if (document.getElementById('autoStart').checked) {
            fetch(`/nodes/${nodeId}/start`, { method: 'POST' })
              .then(() => showNotification(`Node ${nodeId} started`, 'success'))
          }
          document.getElementById('createNodeForm').style.display = 'none'
          load()
        } else {
          showNotification(data.message || 'Failed to create node', 'error')
        }
      })
      .catch(() => showNotification('Failed to create node', 'error'))
  })
  
  // Batch create
  document.getElementById('batchCreateSubmit').addEventListener('click', () => {
    const count = parseInt(document.getElementById('batchCount').value)
    const baseId = document.getElementById('batchBaseId').value || 'node'
    
    fetch('/nodes/batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        count: count,
        base_id: baseId,
        cpu: parseInt(document.getElementById('batchCpu').value),
        memory: parseInt(document.getElementById('batchMemory').value),
        storage: parseInt(document.getElementById('batchStorage').value),
        bandwidth: parseInt(document.getElementById('batchBandwidth').value),
        host: 'localhost'
      })
    })
      .then(r => r.json())
      .then(data => {
        if (data.ok) {
          showNotification(`Created ${data.nodes?.length || 0} node(s)`, 'success')
          if (document.getElementById('batchAutoStart').checked && data.nodes) {
            Promise.all(data.nodes.map(n => 
              fetch(`/nodes/${n.node_id}/start`, { method: 'POST' })
            )).then(() => showNotification('All nodes started', 'success'))
          }
          document.getElementById('batchCreateForm').style.display = 'none'
          load()
        } else {
          showNotification(data.message || 'Failed to create nodes', 'error')
        }
      })
      .catch(() => showNotification('Failed to create nodes', 'error'))
  })
  
  function load() {
    fetch('/status')
      .then(r => r.json())
      .then(data => {
        const grid = document.getElementById('nodesGrid')
        if (!data.nodes || data.nodes.length === 0) {
          grid.innerHTML = '<div class="card"><div class="muted">No nodes found. Create your first node above.</div></div>'
          return
        }
        
        grid.innerHTML = data.nodes.map(n => {
          const util = Number(n.storage_utilization_percent || 0).toFixed(1)
          const statusColor = n.running ? '#0a7' : '#c22'
          return `
            <div class="card" data-id="${n.node_id}">
              <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 12px;">
                <div>
                  <strong style="font-size: 18px;">${n.node_id}</strong>
                  <div class="muted" style="font-size: 13px;">${n.host}:${n.port}</div>
                </div>
                <div style="display: flex; align-items: center; gap: 6px;">
                  <span style="width: 10px; height: 10px; border-radius: 50%; background: ${statusColor};"></span>
                  <span style="font-size: 12px; font-weight: 600; color: ${statusColor};">
                    ${n.running ? 'RUNNING' : 'STOPPED'}
                  </span>
                </div>
              </div>
              
              <div style="margin-bottom: 12px;">
                <div class="muted" style="font-size: 13px; margin-bottom: 4px;">Storage Utilization</div>
                <div style="display: flex; align-items: center; gap: 8px;">
                  <div style="flex: 1; height: 8px; background: #f0f0f0; border-radius: 4px; overflow: hidden;">
                    <div style="height: 100%; width: ${util}%; background: ${util > 75 ? '#c22' : util > 50 ? '#fa0' : '#0a7'};"></div>
                  </div>
                  <span style="font-size: 14px; font-weight: 600;">${util}%</span>
                </div>
                <div class="muted" style="font-size: 12px; margin-top: 4px;">${n.files_stored || 0} files stored</div>
              </div>
              
              <div class="row" style="flex-wrap: wrap; gap: 6px;">
                <button class="start" data-node-id="${n.node_id}" style="flex: 1; min-width: 80px;">Start</button>
                <button class="stop" data-node-id="${n.node_id}" style="flex: 1; min-width: 80px;">Stop</button>
                <button class="restart" data-node-id="${n.node_id}" style="flex: 1; min-width: 80px;">Restart</button>
                <button class="details" data-node-id="${n.node_id}" style="flex: 1; min-width: 80px;">Details</button>
                <button class="delete" data-node-id="${n.node_id}" style="flex: 1; min-width: 80px; background: #c22; color: white; border-color: #c22;">Delete</button>
              </div>
              
              <div class="node-details" style="display: none; margin-top: 12px; padding-top: 12px; border-top: 1px solid #eee;">
                <div class="loading">Loading details...</div>
              </div>
            </div>
          `
        }).join('')
        
        // Use event delegation - attach single listener to grid container
        // This prevents duplicate listeners when grid is refreshed
        if (!grid.hasAttribute('data-listeners-attached')) {
          grid.setAttribute('data-listeners-attached', 'true')
          
          grid.addEventListener('click', (e) => {
            const btn = e.target.closest('button')
            if (!btn) return
            
            const nodeId = btn.getAttribute('data-node-id')
            if (!nodeId) return
            
            // Handle Details button
            if (btn.classList.contains('details')) {
              e.preventDefault()
              e.stopPropagation()
              
              // Find the card using the node ID
              const card = grid.querySelector(`.card[data-id="${nodeId}"]`)
              if (!card) return
              
              // Find the details element within THIS specific card only
              const detailsEl = card.querySelector('.node-details')
              if (!detailsEl) return
              
              // Check if currently visible using computed style
              const computedStyle = window.getComputedStyle(detailsEl)
              const isVisible = computedStyle.display !== 'none' && detailsEl.style.display !== 'none'
              
              // FIRST: Hide ALL details elements in ALL cards (force hide)
              Array.from(grid.querySelectorAll('.node-details')).forEach(el => {
                el.style.display = 'none'
                // Also clear any inline styles that might override
                el.removeAttribute('style')
                el.setAttribute('style', 'display: none; margin-top: 12px; padding-top: 12px; border-top: 1px solid #eee;')
              })
              
              if (!isVisible) {
                // Show this one only
                detailsEl.style.display = 'block'
                
                // Load detailed info
                fetch(`/nodes/${nodeId}/details`)
                  .then(r => r.json())
                  .then(details => {
                    // Re-find the element to ensure we're updating the right one
                    const currentCard = grid.querySelector(`.card[data-id="${nodeId}"]`)
                    if (!currentCard) return
                    const currentDetailsEl = currentCard.querySelector('.node-details')
                    if (!currentDetailsEl) return
                    
                    // Double-check: hide all others again before updating
                    Array.from(grid.querySelectorAll('.node-details')).forEach(el => {
                      if (el !== currentDetailsEl) {
                        el.style.display = 'none'
                      }
                    })
                    
                    currentDetailsEl.innerHTML = `
                      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px;">
                        <div>
                          <strong>Node Information</strong>
                          <div class="muted" style="font-size: 13px; margin-top: 4px;">
                            Node ID: ${details.node_id || 'N/A'}<br>
                            Host: ${details.host || 'N/A'}<br>
                            Port: ${details.port || 'N/A'}<br>
                            IP Address: ${details.ip_address || 'N/A'}<br>
                            MAC Address: ${details.mac_address || 'N/A'}<br>
                            Status: ${details.running ? '<span style="color: #0a7;">Running</span>' : '<span style="color: #c22;">Stopped</span>'}
                          </div>
                        </div>
                        <div>
                          <strong>Resources</strong>
                          <div class="muted" style="font-size: 13px; margin-top: 4px;">
                            CPU: ${details.cpu_capacity || 0} vCPUs<br>
                            Memory: ${details.memory_capacity || 0} GB<br>
                            Storage: ${details.storage_capacity || 0} GB<br>
                            Bandwidth: ${details.bandwidth || 0} Mbps<br>
                            Network Check: ${details.enable_network_check ? 'Enabled' : 'Disabled'}
                          </div>
                        </div>
                        ${details.storage ? `
                        <div>
                          <strong>Storage</strong>
                          <div class="muted" style="font-size: 13px; margin-top: 4px;">
                            Total: ${(details.storage.total_bytes / (1024**3)).toFixed(2)} GB<br>
                            Used: ${(details.storage.used_bytes / (1024**3)).toFixed(2)} GB<br>
                            Available: ${(details.storage.available_bytes / (1024**3)).toFixed(2)} GB<br>
                            Files: ${details.storage.files_stored || 0}
                          </div>
                        </div>
                        ` : ''}
                        ${details.network ? `
                        <div>
                          <strong>Network</strong>
                          <div class="muted" style="font-size: 13px; margin-top: 4px;">
                            Utilization: ${details.network.utilization_percent?.toFixed(1) || 0}%<br>
                            Connections: ${details.network.connections?.length || 0}
                          </div>
                        </div>
                        ` : ''}
                        ${details.performance ? `
                        <div>
                          <strong>Performance</strong>
                          <div class="muted" style="font-size: 13px; margin-top: 4px;">
                            Transfers: ${details.performance.total_transfers || 0}<br>
                            Successful: ${details.performance.successful_transfers || 0}<br>
                            Failed: ${details.performance.failed_transfers || 0}<br>
                            Active: ${details.performance.active_transfers || 0}
                          </div>
                        </div>
                        ` : ''}
                      </div>
                    `
                  })
                  .catch(() => {
                    const currentCard = grid.querySelector(`.card[data-id="${nodeId}"]`)
                    if (currentCard) {
                      const currentDetailsEl = currentCard.querySelector('.node-details')
                      if (currentDetailsEl) {
                        currentDetailsEl.innerHTML = '<div class="muted">Failed to load details</div>'
                      }
                    }
                  })
              }
              return
            }
            
            // Handle Start button
            if (btn.classList.contains('start')) {
              fetch(`/nodes/${nodeId}/start`, { method: 'POST' })
                .then(() => {
                  showNotification(`Node ${nodeId} started`, 'success')
                  load()
                })
                .catch(() => showNotification('Failed to start node', 'error'))
              return
            }
            
            // Handle Stop button
            if (btn.classList.contains('stop')) {
              if (confirm(`Stop node ${nodeId}?`)) {
                fetch(`/nodes/${nodeId}/stop?force=true`, { method: 'POST' })
                  .then(() => {
                    showNotification(`Node ${nodeId} stopped`, 'success')
                    load()
                  })
                  .catch(() => showNotification('Failed to stop node', 'error'))
              }
              return
            }
            
            // Handle Restart button
            if (btn.classList.contains('restart')) {
              if (confirm(`Restart node ${nodeId}?`)) {
                fetch(`/nodes/${nodeId}/stop?force=true`, { method: 'POST' })
                  .then(() => fetch(`/nodes/${nodeId}/start`, { method: 'POST' }))
                  .then(() => {
                    showNotification(`Node ${nodeId} restarted`, 'success')
                    load()
          })
                  .catch(() => showNotification('Failed to restart node', 'error'))
              }
              return
            }
            
            // Handle Delete button
            if (btn.classList.contains('delete')) {
              if (confirm(`Delete node ${nodeId}? This action cannot be undone.`)) {
                fetch(`/nodes/${nodeId}`, { method: 'DELETE' })
                  .then(r => r.json())
                  .then(data => {
                    if (data.ok) {
                      showNotification(`Node ${nodeId} deleted`, 'success')
                      load()
                    } else {
                      showNotification('Failed to delete node', 'error')
                    }
                  })
                  .catch(() => showNotification('Failed to delete node', 'error'))
              }
              return
            }
          })
        }
      })
      .catch(() => {
        document.getElementById('nodesGrid').innerHTML = '<div class="card"><div class="error">Failed to load nodes</div></div>'
      })
  }
  
  load()
}

// Metrics Page
function renderMetrics() {
  setActive('metrics')
  const view = document.getElementById('view')
  view.innerHTML = `
    <div class="row" style="justify-content: space-between; margin-bottom: 20px;">
      <h2>Metrics & Monitoring</h2>
      <button id="refreshMetrics" class="primary">Refresh</button>
    </div>
    
    <div class="grid" style="grid-template-columns: repeat(3, 1fr); gap: 20px;">
      <!-- Card 1: Storage Overview -->
      <div class="card">
        <h3>Storage Overview</h3>
        <div id="storageOverview" class="loading">Loading...</div>
      </div>
      
      <!-- Card 2: Node Details Table -->
      <div class="card" style="grid-column: span 2;">
        <h3>Node Details</h3>
        <div id="nodeDetailsTable" class="loading">Loading...</div>
      </div>
      
      <!-- Card 3: Transfer History -->
      <div class="card" style="grid-column: span 3;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <h3 style="margin: 0;">Transfer History</h3>
          <button id="clearTransferHistoryBtn" class="secondary" style="padding: 6px 12px; font-size: 13px;">Clear History</button>
        </div>
        <div id="transferHistory" class="loading">Loading...</div>
      </div>
    </div>
  `
  
  function load() {
    const viewEl = document.getElementById('view')
    setLoading(viewEl, true)
    
    fetch('/metrics').then(r => {
      if (!r.ok) {
        console.error('[FRONTEND] Metrics request failed:', r.status, r.statusText)
        return r.json().then(data => { throw new Error(data.detail || 'Request failed') })
      }
      return r.json()
    })
    .then((metricsData) => {
      console.log('[FRONTEND] Full metrics response received')
      console.log('[FRONTEND] Transfer history key exists:', 'transfer_history' in metricsData)
      console.log('[FRONTEND] Transfer history value:', metricsData.transfer_history)
      console.log('[FRONTEND] Transfer history type:', typeof metricsData.transfer_history)
      // Card 1: Storage Overview
      const totalGB = metricsData.total_storage_gb || 0
      const usedGB = metricsData.used_storage_gb || 0
      const storageUtil = metricsData.storage_utilization_percent || 0
      const totalFiles = metricsData.total_files || 0
      
      // Determine capacity alert
      let capacityAlert = null
      let alertLevel = 'info'
      if (storageUtil >= 95) {
        capacityAlert = { level: 'CRITICAL', message: 'Storage utilization is at 95% or higher!' }
        alertLevel = 'error'
      } else if (storageUtil >= 90) {
        capacityAlert = { level: 'CRITICAL', message: 'Storage utilization is at 90% or higher!' }
        alertLevel = 'error'
      } else if (storageUtil >= 75) {
        capacityAlert = { level: 'WARNING', message: 'Storage utilization is at 75% or higher' }
        alertLevel = 'warning'
      } else if (storageUtil >= 50) {
        capacityAlert = { level: 'INFO', message: 'Storage utilization is at 50%' }
        alertLevel = 'info'
      }
      
      document.getElementById('storageOverview').innerHTML = `
        <div style="margin-bottom: 16px;">
          <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
            <span><strong>Total Storage:</strong></span>
            <span>${totalGB.toFixed(2)} GB</span>
          </div>
          <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
            <span><strong>Used Storage:</strong></span>
            <span>${usedGB.toFixed(2)} GB</span>
          </div>
          <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
            <span><strong>Storage Utilization:</strong></span>
            <span style="font-weight: bold; color: ${storageUtil > 75 ? '#c22' : storageUtil > 50 ? '#fa0' : '#0a7'};">
              ${storageUtil.toFixed(2)}%
            </span>
          </div>
          <div style="height: 12px; background: #f0f0f0; border-radius: 6px; overflow: hidden; margin-bottom: 12px;">
            <div style="height: 100%; width: ${Math.min(storageUtil, 100)}%; background: ${storageUtil > 75 ? '#c22' : storageUtil > 50 ? '#fa0' : '#0a7'};"></div>
          </div>
          <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
            <span><strong>Total Files:</strong></span>
            <span>${totalFiles}</span>
          </div>
          ${capacityAlert ? `
          <div style="padding: 12px; background: ${alertLevel === 'error' ? '#f8d7da' : alertLevel === 'warning' ? '#fff3cd' : '#d1ecf1'}; 
                      border-left: 4px solid ${alertLevel === 'error' ? '#c22' : alertLevel === 'warning' ? '#fa0' : '#0a7'}; 
                      border-radius: 4px; margin-top: 12px;">
            <strong>${capacityAlert.level}</strong>: ${capacityAlert.message}
          </div>
          ` : '<div style="padding: 12px; background: #d1ecf1; border-left: 4px solid #0a7; border-radius: 4px; margin-top: 12px;"><strong>OK</strong>: Storage capacity is healthy</div>'}
        </div>
      `
      
      // Card 2: Node Details Table
      const nodeDetails = metricsData.node_details || []
      if (nodeDetails.length > 0) {
        document.getElementById('nodeDetailsTable').innerHTML = `
          <div style="overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse;">
              <thead>
                <tr style="border-bottom: 2px solid #e0e0e0;">
                  <th style="text-align: left; padding: 12px;">Node</th>
                  <th style="text-align: center; padding: 12px;">Status</th>
                  <th style="text-align: right; padding: 12px;">Total Capacity</th>
                  <th style="text-align: right; padding: 12px;">Used Storage</th>
                  <th style="text-align: right; padding: 12px;">Number of Files</th>
                  <th style="text-align: center; padding: 12px;">Storage Utilization %</th>
                </tr>
              </thead>
              <tbody>
                ${nodeDetails.map(n => {
                  const util = n.utilization_percent || 0
                  const usedGB = n.used_gb || 0
                  return `
                  <tr style="border-bottom: 1px solid #f0f0f0;">
                    <td style="padding: 12px; font-weight: bold;">${n.node_id}</td>
                    <td style="text-align: center; padding: 12px;">
                      <span style="display: inline-block; width: 12px; height: 12px; border-radius: 50%; background: ${n.running ? '#0a7' : '#c22'};"></span>
                      <span style="margin-left: 6px; font-size: 13px;">${n.running ? 'Running' : 'Stopped'}</span>
                    </td>
                    <td style="text-align: right; padding: 12px;">${n.storage_capacity_gb.toFixed(2)} GB</td>
                    <td style="text-align: right; padding: 12px;">${usedGB.toFixed(2)} GB</td>
                    <td style="text-align: right; padding: 12px;">${n.files_count || 0}</td>
                    <td style="text-align: center; padding: 12px;">
                      <div style="display: flex; align-items: center; gap: 8px; justify-content: center;">
                        <div style="flex: 1; max-width: 120px; height: 8px; background: #f0f0f0; border-radius: 4px; overflow: hidden;">
                          <div style="height: 100%; width: ${Math.min(util, 100)}%; background: ${util > 75 ? '#c22' : util > 50 ? '#fa0' : '#0a7'};"></div>
                        </div>
                        <span style="font-size: 13px; color: #666; min-width: 50px;">${util.toFixed(1)}%</span>
                      </div>
                    </td>
                  </tr>
                `
                }).join('')}
              </tbody>
            </table>
          </div>
        `
      } else {
        document.getElementById('nodeDetailsTable').innerHTML = '<div class="muted">No node data available</div>'
      }
      
      // Card 3: Transfer History
      const transferHistory = metricsData.transfer_history || []
      console.log('[FRONTEND] Transfer history data:', transferHistory.length, 'transfers')
      
      const transferHistoryElement = document.getElementById('transferHistory')
      if (!transferHistoryElement) {
        console.error('[FRONTEND] transferHistory element not found!')
        setLoading(viewEl, false)
        return
      }
      
      if (transferHistory && Array.isArray(transferHistory) && transferHistory.length > 0) {
        transferHistoryElement.innerHTML = `
          <div style="overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse;">
              <thead>
                <tr style="border-bottom: 2px solid #e0e0e0;">
                  <th style="text-align: left; padding: 12px; width: 30px;"></th>
                  <th style="text-align: left; padding: 12px;">User ID</th>
                  <th style="text-align: right; padding: 12px;">Transfer Size</th>
                  <th style="text-align: right; padding: 12px;">Network Latency (ms)</th>
                  <th style="text-align: right; padding: 12px;">Network Throughput (Mbps)</th>
                  <th style="text-align: center; padding: 12px;">Status</th>
                  <th style="text-align: left; padding: 12px;">Time</th>
                </tr>
              </thead>
              <tbody>
                ${transferHistory.map((t, index) => {
                  const sizeGB = t.file_size_gb || 0
                  const sizeBytes = t.file_size_bytes || 0
                  const sizeDisplay = sizeGB >= 1 ? `${sizeGB.toFixed(2)} GB` : 
                                     sizeGB >= 0.001 ? `${(sizeGB * 1024).toFixed(2)} MB` : 
                                     sizeBytes >= 1024 ? `${(sizeBytes / 1024).toFixed(2)} KB` :
                                     `${sizeBytes.toLocaleString()} bytes`
                  const latency = t.latency_ms || 0
                  const throughput = t.throughput_mbps || 0
                  const timeStr = t.start_time ? new Date(t.start_time).toLocaleString() : 'N/A'
                  const hasChunks = t.chunks && Array.isArray(t.chunks) && t.chunks.length > 0
                  const chunkCount = t.chunk_count || (hasChunks ? t.chunks.length : 0)
                  const fileId = t.file_id || `file_${index}`
                  
                  return `
                  <tr style="border-bottom: 1px solid #f0f0f0; cursor: ${hasChunks ? 'pointer' : 'default'};" 
                      data-file-id="${fileId}" 
                      ${hasChunks ? `class="file-transfer-row"` : ''}>
                    <td style="padding: 12px;">
                      ${hasChunks ? `<span id="expand-${fileId}" style="display: inline-block; width: 20px; text-align: center; font-weight: bold; color: #666;">+</span>` : ''}
                    </td>
                    <td style="padding: 12px;"><strong>${t.user_id || 'N/A'}</strong></td>
                    <td style="text-align: right; padding: 12px;">
                      ${sizeDisplay}
                      ${chunkCount > 0 ? `<div style="font-size: 11px; color: #999; margin-top: 2px;">${chunkCount} chunk${chunkCount !== 1 ? 's' : ''}</div>` : ''}
                    </td>
                    <td style="text-align: right; padding: 12px;">${latency > 0 ? latency.toFixed(2) : 'N/A'}</td>
                    <td style="text-align: right; padding: 12px;">${throughput > 0 ? throughput.toFixed(2) : 'N/A'}</td>
                    <td style="text-align: center; padding: 12px;">
                      <span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: ${t.success ? '#0a7' : '#c22'};"></span>
                      <span style="margin-left: 6px; font-size: 13px;">${t.success ? 'Success' : 'Failed'}</span>
                    </td>
                    <td style="padding: 12px; font-size: 13px; color: #666;">${timeStr}</td>
                  </tr>
                  ${hasChunks ? `
                  <tr id="chunks-${fileId}" style="display: none; background: #f9f9f9;">
                    <td colspan="7" style="padding: 0;">
                      <div style="padding: 16px; margin-left: 40px;">
                        <div style="font-weight: 600; margin-bottom: 12px; color: #666;">Chunk Details (${t.chunks.length} chunks):</div>
                        <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                          <thead>
                            <tr style="border-bottom: 1px solid #e0e0e0;">
                              <th style="text-align: left; padding: 8px;">Chunk ID</th>
                              <th style="text-align: right; padding: 8px;">Size</th>
                              <th style="text-align: right; padding: 8px;">Latency (ms)</th>
                              <th style="text-align: right; padding: 8px;">Throughput (Mbps)</th>
                              <th style="text-align: center; padding: 8px;">Status</th>
                              <th style="text-align: left; padding: 8px;">Source → Target</th>
                            </tr>
                          </thead>
                          <tbody>
                            ${t.chunks.map(chunk => {
                              const chunkSizeBytes = chunk.size_bytes || 0
                              const chunkSizeDisplay = chunkSizeBytes >= 1024 ? `${(chunkSizeBytes / 1024).toFixed(2)} KB` : `${chunkSizeBytes} bytes`
                              return `
                              <tr style="border-bottom: 1px solid #f0f0f0;">
                                <td style="padding: 8px; font-family: monospace; font-size: 11px;">${chunk.chunk_id.substring(0, 30)}...</td>
                                <td style="text-align: right; padding: 8px;">${chunkSizeDisplay}</td>
                                <td style="text-align: right; padding: 8px;">${chunk.latency_ms ? chunk.latency_ms.toFixed(2) : 'N/A'}</td>
                                <td style="text-align: right; padding: 8px;">${chunk.throughput_mbps ? chunk.throughput_mbps.toFixed(2) : 'N/A'}</td>
                                <td style="text-align: center; padding: 8px;">
                                  <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: ${chunk.success ? '#0a7' : '#c22'};"></span>
                                </td>
                                <td style="padding: 8px; font-size: 11px; color: #666;">${chunk.source_node} → ${chunk.target_node}</td>
                              </tr>
                              `
                            }).join('')}
                          </tbody>
                        </table>
                      </div>
                    </td>
                  </tr>
                  ` : ''}
                  `
                }).join('')}
              </tbody>
            </table>
          </div>
        `
        
        // Add event delegation for expanding/collapsing chunks
        // Use event delegation on the table container to handle clicks
        const transferTableContainer = transferHistoryElement.querySelector('div[style*="overflow-x"]')
        if (transferTableContainer) {
          transferTableContainer.addEventListener('click', (e) => {
            // Check if clicking on the expand icon or the row
            const expandIcon = e.target.closest(`[id^="expand-"]`)
            const row = e.target.closest('.file-transfer-row')
            
            if (row || expandIcon) {
              e.preventDefault()
              e.stopPropagation()
              
              const fileId = row ? row.getAttribute('data-file-id') : expandIcon.id.replace('expand-', '')
              if (fileId) {
                const chunksRow = document.getElementById(`chunks-${fileId}`)
                const icon = document.getElementById(`expand-${fileId}`)
                if (chunksRow && icon) {
                  // Check current state using computed style
                  const currentDisplay = window.getComputedStyle(chunksRow).display
                  const isHidden = currentDisplay === 'none'
                  
                  if (isHidden) {
                    chunksRow.style.display = 'table-row'
                    icon.textContent = '−'
                  } else {
                    chunksRow.style.display = 'none'
                    icon.textContent = '+'
                  }
                }
              }
            }
          })
        }
        
        // Add clear history button handler
        const clearBtn = document.getElementById('clearTransferHistoryBtn')
        if (clearBtn) {
          clearBtn.addEventListener('click', async () => {
            // Show confirmation dialog
            const confirmed = confirm('Are you sure you want to clear all transfer history? This action cannot be undone.')
            if (!confirmed) {
              return
            }
            
            clearBtn.disabled = true
            clearBtn.textContent = 'Clearing...'
            
            try {
              const response = await fetch('/metrics/transfers', {
                method: 'DELETE'
              })
              const data = await response.json()
              
              if (data.ok) {
                showNotification(data.message || 'Transfer history cleared successfully', 'success')
                // Reload metrics to refresh the display
                renderMetrics()
              } else {
                showNotification(data.message || 'Failed to clear transfer history', 'error')
                clearBtn.disabled = false
                clearBtn.textContent = 'Clear History'
              }
            } catch (error) {
              console.error('Error clearing transfer history:', error)
              showNotification('Failed to clear transfer history. Please check backend services.', 'error')
              clearBtn.disabled = false
              clearBtn.textContent = 'Clear History'
            }
          })
        }
      } else {
        console.log('[FRONTEND] No transfers to display')
        const msg = transferHistory === undefined || transferHistory === null 
          ? 'Transfer history data not available. Check backend logs.' 
          : transferHistory.length === 0 
            ? 'No transfer history available. Perform file uploads or downloads to see transfer history.' 
            : 'Transfer history format error.'
        transferHistoryElement.innerHTML = `<div class="muted">${msg}</div>`
      }
      
      setLoading(viewEl, false)
    }).catch(err => {
      console.error('Metrics error:', err)
      showNotification('Failed to load metrics', 'error')
      setLoading(viewEl, false)
    })
  }
  
  document.getElementById('refreshMetrics').addEventListener('click', load)
  load()
}

// Users Management Page
function renderUsers() {
  setActive('users')
  const view = document.getElementById('view')
  view.innerHTML = `
    <div class="row" style="justify-content: space-between; margin-bottom: 20px;">
      <h2>User Management</h2>
      <button id="refreshUsers" class="primary">Refresh</button>
    </div>
    
    <div class="card">
      <h3>Registered Users</h3>
      <div id="usersList" class="loading">Loading users...</div>
    </div>
  `
  
  function load() {
    const viewEl = document.getElementById('view')
    setLoading(viewEl, true)
    
    fetch('/auth/users')
      .then(r => r.json())
      .then(data => {
        setLoading(viewEl, false)
        const usersList = document.getElementById('usersList')
        
        if (!data.ok || !data.users || data.users.length === 0) {
          usersList.innerHTML = '<div class="muted">No users registered yet</div>'
          return
        }
        
        usersList.innerHTML = `
          <table style="width: 100%; border-collapse: collapse;">
            <thead>
              <tr style="border-bottom: 2px solid #e0e0e0;">
                <th style="text-align: left; padding: 12px;">Username</th>
                <th style="text-align: left; padding: 12px;">Email</th>
                <th style="text-align: right; padding: 12px;">Used Storage</th>
                <th style="text-align: right; padding: 12px;">Quota</th>
                <th style="text-align: center; padding: 12px;">Usage %</th>
                <th style="text-align: right; padding: 12px;">Files</th>
                <th style="text-align: center; padding: 12px;">Actions</th>
              </tr>
            </thead>
            <tbody>
              ${data.users.map(user => {
                const usedGB = (user.used_bytes || 0) / (1024 ** 3)
                const quotaGB = (user.quota_bytes || 0) / (1024 ** 3)
                const usagePercent = quotaGB > 0 ? (usedGB / quotaGB * 100) : 0
                const usageColor = usagePercent > 90 ? '#c22' : usagePercent > 70 ? '#fa0' : '#0a7'
                
                return `
                  <tr style="border-bottom: 1px solid #f0f0f0;">
                    <td style="padding: 12px;"><strong>${user.login}</strong></td>
                    <td style="padding: 12px;">${user.email || 'N/A'}</td>
                    <td style="text-align: right; padding: 12px;">${usedGB.toFixed(2)} GB</td>
                    <td style="text-align: right; padding: 12px;">
                      <span id="quota-${user.login}">${quotaGB.toFixed(2)} GB</span>
                    </td>
                    <td style="text-align: center; padding: 12px;">
                      <div style="display: flex; align-items: center; gap: 8px; justify-content: center;">
                        <div style="flex: 1; max-width: 100px; height: 8px; background: #f0f0f0; border-radius: 4px; overflow: hidden;">
                          <div style="height: 100%; width: ${Math.min(usagePercent, 100)}%; background: ${usageColor};"></div>
                        </div>
                        <span style="font-size: 12px; color: #666; min-width: 45px;">${usagePercent.toFixed(1)}%</span>
                      </div>
                    </td>
                    <td style="text-align: right; padding: 12px;">${user.file_count || 0}</td>
                    <td style="text-align: center; padding: 12px;">
                      <button class="primary" data-username="${user.login}" data-action="update-quota" style="padding: 6px 12px; font-size: 13px;">
                        Update Quota
                      </button>
                    </td>
                  </tr>
                `
              }).join('')}
            </tbody>
          </table>
        `
        
        // Add event listeners for update quota buttons
        document.querySelectorAll('[data-action="update-quota"]').forEach(btn => {
          btn.addEventListener('click', (e) => {
            const username = e.target.getAttribute('data-username')
            const user = data.users.find(u => u.login === username)
            if (!user) return
            
            const currentQuotaGB = (user.quota_bytes || 0) / (1024 ** 3)
            const usedGB = (user.used_bytes || 0) / (1024 ** 3)
            
            // Create modal overlay
            const modal = document.createElement('div')
            modal.id = 'quotaModal'
            modal.style.cssText = `
              position: fixed;
              top: 0;
              left: 0;
              right: 0;
              bottom: 0;
              background: rgba(0, 0, 0, 0.5);
              display: flex;
              align-items: center;
              justify-content: center;
              z-index: 2000;
            `
            
            modal.innerHTML = `
              <div style="
                background: white;
                border-radius: 8px;
                padding: 24px;
                max-width: 500px;
                width: 90%;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
              ">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                  <h3 style="margin: 0;">Update Storage Quota</h3>
                  <button id="closeQuotaModal" style="
                    background: none;
                    border: none;
                    font-size: 24px;
                    cursor: pointer;
                    color: #666;
                    padding: 0;
                    width: 30px;
                    height: 30px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                  ">&times;</button>
                </div>
                
                <div style="margin-bottom: 20px;">
                  <div style="margin-bottom: 12px;">
                    <strong>User:</strong> ${username}
                  </div>
                  <div style="margin-bottom: 12px;">
                    <strong>Email:</strong> ${user.email || 'N/A'}
                  </div>
                  <div style="margin-bottom: 12px; padding: 12px; background: #f5f5f5; border-radius: 6px;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                      <span><strong>Current Quota:</strong></span>
                      <span>${currentQuotaGB.toFixed(2)} GB</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                      <span><strong>Used Storage:</strong></span>
                      <span>${usedGB.toFixed(2)} GB</span>
                    </div>
                    <div style="display: flex; justify-content: space-between;">
                      <span><strong>Available:</strong></span>
                      <span>${(currentQuotaGB - usedGB).toFixed(2)} GB</span>
                    </div>
                  </div>
                </div>
                
                <div style="margin-bottom: 20px;">
                  <label style="display: block; margin-bottom: 8px; font-weight: 500;">
                    New Quota (GB):
                  </label>
                  <input 
                    type="number" 
                    id="newQuotaInput" 
                    value="${currentQuotaGB.toFixed(2)}"
                    min="${usedGB.toFixed(2)}"
                    step="0.1"
                    style="
                      width: 100%;
                      padding: 10px;
                      border: 1px solid #ddd;
                      border-radius: 6px;
                      font-size: 16px;
                      box-sizing: border-box;
                    "
                    placeholder="Enter quota in GB"
                  />
                  <div style="margin-top: 8px; font-size: 13px; color: #666;">
                    Minimum: ${usedGB.toFixed(2)} GB (current usage)
                  </div>
                </div>
                
                <div style="display: flex; gap: 12px; justify-content: flex-end;">
                  <button id="cancelQuotaUpdate" style="
                    padding: 10px 20px;
                    background: #f0f0f0;
                    border: 1px solid #ddd;
                    border-radius: 6px;
                    cursor: pointer;
                    font-size: 14px;
                  ">Cancel</button>
                  <button id="confirmQuotaUpdate" style="
                    padding: 10px 20px;
                    background: #1a1a2e;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    cursor: pointer;
                    font-size: 14px;
                    font-weight: 500;
                  ">Update Quota</button>
                </div>
              </div>
            `
            
            document.body.appendChild(modal)
            
            // Focus input
            const input = modal.querySelector('#newQuotaInput')
            input.focus()
            input.select()
            
            // Close handlers
            const closeModal = () => {
              document.body.removeChild(modal)
            }
            
            modal.querySelector('#closeQuotaModal').addEventListener('click', closeModal)
            modal.querySelector('#cancelQuotaUpdate').addEventListener('click', closeModal)
            modal.addEventListener('click', (e) => {
              if (e.target === modal) closeModal()
            })
            
            // Update handler
            modal.querySelector('#confirmQuotaUpdate').addEventListener('click', () => {
              const quotaGB = parseFloat(input.value)
              
              if (isNaN(quotaGB) || quotaGB < 0) {
                showNotification('Invalid quota value. Please enter a positive number.', 'error')
                input.focus()
                return
              }
              
              if (quotaGB < usedGB) {
                showNotification(`Quota cannot be less than current usage (${usedGB.toFixed(2)} GB).`, 'error')
                input.focus()
                return
              }
              
              // Disable button during update
              const updateBtn = modal.querySelector('#confirmQuotaUpdate')
              updateBtn.disabled = true
              updateBtn.textContent = 'Updating...'
              
              fetch(`/auth/users/${username}/quota`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ quota_gb: quotaGB })
              })
                .then(r => r.json())
                .then(result => {
                  closeModal()
                  if (result.ok) {
                    showNotification(`Quota updated successfully to ${quotaGB.toFixed(2)} GB`, 'success')
                    load() // Reload the list
                  } else {
                    showNotification(result.message || 'Failed to update quota', 'error')
                  }
                })
                .catch(err => {
                  closeModal()
                  showNotification('Error updating quota', 'error')
                })
            })
            
            // Enter key handler
            input.addEventListener('keypress', (e) => {
              if (e.key === 'Enter') {
                modal.querySelector('#confirmQuotaUpdate').click()
              }
            })
          })
        })
      })
      .catch(err => {
        setLoading(viewEl, false)
        document.getElementById('usersList').innerHTML = `
          <div class="muted">Error loading users: ${err.message}</div>
        `
      })
  }
  
  load()
  
  document.getElementById('refreshUsers').addEventListener('click', load)
}


// Router
function router() {
  const hash = (location.hash || '#/dashboard').replace('#/', '')
  if (hash === 'nodes') return renderNodes()
  if (hash === 'metrics') return renderMetrics()
  if (hash === 'capacity') return renderCapacity()
  if (hash === 'users') return renderUsers()
  return renderDashboard()
}

// Initialize
renderShell()
router()
window.addEventListener('hashchange', router)
