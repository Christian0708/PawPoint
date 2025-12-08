// CloudSim Client Portal - With Authentication
// No technical details (nodes, chunks, replication) - all handled automatically

const app = document.getElementById('app')

// Auth state management
let currentUser = null
let authToken = null

function loadAuthState() {
  const stored = localStorage.getItem('cloudsim_auth')
  if (stored) {
    try {
      const data = JSON.parse(stored)
      currentUser = data.username
      authToken = data.token
      return true
    } catch (e) {
      localStorage.removeItem('cloudsim_auth')
    }
  }
  return false
}

function saveAuthState(username, token) {
  currentUser = username
  authToken = token
  localStorage.setItem('cloudsim_auth', JSON.stringify({ username, token }))
}

function clearAuthState() {
  currentUser = null
  authToken = null
  localStorage.removeItem('cloudsim_auth')
}

function isLoggedIn() {
  return currentUser && authToken
}

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
    max-width: 400px;
  `
  document.body.appendChild(notification)
  setTimeout(() => notification.remove(), 4000)
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

// ==================== AUTH PAGES ====================

function renderLoginPage() {
  app.innerHTML = `
    <div style="min-height: 100vh; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);">
      <div class="card" style="width: 100%; max-width: 400px; margin: 20px;">
        <div style="text-align: center; margin-bottom: 24px;">
          <h1 style="margin: 0; color: #1a1a2e;">CloudSim</h1>
          <p class="muted">Secure Cloud Storage</p>
        </div>
        
        <form id="loginForm">
          <div style="margin-bottom: 16px;">
            <label style="display: block; margin-bottom: 6px; font-weight: 500;">Username</label>
            <input type="text" id="loginUsername" placeholder="Enter your username" 
                   style="width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 16px;" required />
          </div>
          
          <div style="margin-bottom: 20px;">
            <label style="display: block; margin-bottom: 6px; font-weight: 500;">Password</label>
            <input type="password" id="loginPassword" placeholder="Enter your password" 
                   style="width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 16px;" required />
          </div>
          
          <button type="submit" class="primary" style="width: 100%; padding: 14px; font-size: 16px;">
            Login
          </button>
        </form>
        
        <div style="text-align: center; margin-top: 20px;">
          <span class="muted">Don't have an account?</span>
          <a href="#/register" style="color: #1a1a2e; font-weight: 500; margin-left: 4px;">Sign Up Free</a>
        </div>
        
        <div style="text-align: center; margin-top: 12px;">
          <span class="muted" style="font-size: 13px;">Free 1GB storage for new accounts!</span>
        </div>
      </div>
    </div>
  `
  
  document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault()
    const username = document.getElementById('loginUsername').value.trim()
    const password = document.getElementById('loginPassword').value
    
    if (!username || !password) {
      showNotification('Please enter username and password', 'error')
      return
    }
    
    const btn = e.target.querySelector('button[type="submit"]')
    btn.disabled = true
    btn.textContent = 'Logging in...'
    
    try {
      const response = await fetch('/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      })
      
      const data = await response.json()
      
      if (response.ok && data.ok) {
        showNotification('OTP sent to your email!', 'success')
        // Store pending info and go to OTP page
        sessionStorage.setItem('otp_pending', JSON.stringify({
          username,
          pending_id: data.pending_id
        }))
        window.location.hash = '#/verify-otp'
      } else {
        showNotification(data.detail || 'Invalid username or password', 'error')
      }
    } catch (err) {
      showNotification('Login failed. Please try again.', 'error')
    } finally {
      btn.disabled = false
      btn.textContent = 'Login'
    }
  })
}

function renderRegisterPage() {
  app.innerHTML = `
    <div style="min-height: 100vh; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);">
      <div class="card" style="width: 100%; max-width: 400px; margin: 20px;">
        <div style="text-align: center; margin-bottom: 24px;">
          <h1 style="margin: 0; color: #1a1a2e;">Create Account</h1>
          <p class="muted">Get 1GB free storage</p>
        </div>
        
        <form id="registerForm">
          <div style="margin-bottom: 16px;">
            <label style="display: block; margin-bottom: 6px; font-weight: 500;">Username</label>
            <input type="text" id="regUsername" placeholder="Choose a username" 
                   style="width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 16px;" required />
          </div>
          
          <div style="margin-bottom: 16px;">
            <label style="display: block; margin-bottom: 6px; font-weight: 500;">Email</label>
            <input type="email" id="regEmail" placeholder="your@email.com" 
                   style="width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 16px;" required />
            <small class="muted" style="display: block; margin-top: 4px;">OTP verification codes will be sent here</small>
          </div>
          
          <div style="margin-bottom: 16px;">
            <label style="display: block; margin-bottom: 6px; font-weight: 500;">Password</label>
            <input type="password" id="regPassword" placeholder="Create a password" 
                   style="width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 16px;" required minlength="6" />
          </div>
          
          <div style="margin-bottom: 20px;">
            <label style="display: block; margin-bottom: 6px; font-weight: 500;">Confirm Password</label>
            <input type="password" id="regPasswordConfirm" placeholder="Confirm your password" 
                   style="width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 16px;" required />
          </div>
          
          <div style="background: #f0f9f4; border: 1px solid #0a7; border-radius: 6px; padding: 12px; margin-bottom: 20px;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span style="font-size: 20px;">🎁</span>
              <div>
                <strong style="color: #0a7;">Free Tier: 1GB Storage</strong>
                <div class="muted" style="font-size: 13px;">Automatically assigned to new accounts</div>
              </div>
            </div>
          </div>
          
          <button type="submit" class="primary" style="width: 100%; padding: 14px; font-size: 16px;">
            Create Account
          </button>
        </form>
        
        <div style="text-align: center; margin-top: 20px;">
          <span class="muted">Already have an account?</span>
          <a href="#/login" style="color: #1a1a2e; font-weight: 500; margin-left: 4px;">Login</a>
        </div>
      </div>
    </div>
  `
  
  document.getElementById('registerForm').addEventListener('submit', async (e) => {
    e.preventDefault()
    const username = document.getElementById('regUsername').value.trim()
    const email = document.getElementById('regEmail').value.trim()
    const password = document.getElementById('regPassword').value
    const confirmPassword = document.getElementById('regPasswordConfirm').value
    
    if (!username || !email || !password) {
      showNotification('Please fill in all fields', 'error')
      return
    }
    
    if (password !== confirmPassword) {
      showNotification('Passwords do not match', 'error')
      return
    }
    
    if (password.length < 6) {
      showNotification('Password must be at least 6 characters', 'error')
      return
    }
    
    const btn = e.target.querySelector('button[type="submit"]')
    btn.disabled = true
    btn.textContent = 'Creating account...'
    
    try {
      const response = await fetch('/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, email, password, quota_gb: 1 })
      })
      
      const data = await response.json()
      
      if (response.ok && data.ok) {
        showNotification('Account created! Please login.', 'success')
        window.location.hash = '#/login'
      } else {
        showNotification(data.detail || data.message || 'Registration failed', 'error')
      }
    } catch (err) {
      showNotification('Registration failed. Please try again.', 'error')
    } finally {
      btn.disabled = false
      btn.textContent = 'Create Account'
    }
  })
}

function renderOtpPage() {
  const pending = sessionStorage.getItem('otp_pending')
  if (!pending) {
    window.location.hash = '#/login'
    return
  }
  
  const { username, pending_id } = JSON.parse(pending)
  
  app.innerHTML = `
    <div style="min-height: 100vh; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);">
      <div class="card" style="width: 100%; max-width: 400px; margin: 20px;">
        <div style="text-align: center; margin-bottom: 24px;">
          <h1 style="margin: 0; color: #1a1a2e;">Verify OTP</h1>
          <p class="muted">Enter the code sent to your email</p>
        </div>
        
        <div style="background: #f0f4ff; border-radius: 6px; padding: 12px; margin-bottom: 20px; text-align: center;">
          <span class="muted">Logging in as</span>
          <strong style="display: block; margin-top: 4px;">${username}</strong>
        </div>
        
        <form id="otpForm">
          <div style="margin-bottom: 20px;">
            <label style="display: block; margin-bottom: 6px; font-weight: 500;">OTP Code</label>
            <input type="text" id="otpCode" placeholder="Enter 6-digit code" 
                   style="width: 100%; padding: 16px; border: 1px solid #ddd; border-radius: 6px; font-size: 24px; text-align: center; letter-spacing: 8px;" 
                   maxlength="6" pattern="[0-9]{6}" required />
          </div>
          
          <button type="submit" class="primary" style="width: 100%; padding: 14px; font-size: 16px;">
            Verify & Login
          </button>
        </form>
        
        <div style="text-align: center; margin-top: 20px;">
          <a href="#/login" style="color: #666;">← Back to Login</a>
        </div>
        
        <div style="text-align: center; margin-top: 12px;">
          <span class="muted" style="font-size: 13px;">Code expires in 5 minutes</span>
        </div>
      </div>
    </div>
  `
  
  document.getElementById('otpForm').addEventListener('submit', async (e) => {
    e.preventDefault()
    const otp = document.getElementById('otpCode').value.trim()
    
    if (!otp || otp.length !== 6) {
      showNotification('Please enter a valid 6-digit OTP', 'error')
      return
    }
    
    const btn = e.target.querySelector('button[type="submit"]')
    btn.disabled = true
    btn.textContent = 'Verifying...'
    
    try {
      const response = await fetch('/auth/verify-otp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, pending_id, otp })
      })
      
      const data = await response.json()
      
      if (response.ok && data.ok && data.token) {
        saveAuthState(username, data.token)
        sessionStorage.removeItem('otp_pending')
        showNotification('Login successful!', 'success')
        window.location.hash = '#/dashboard'
      } else {
        showNotification(data.detail || 'Invalid or expired OTP', 'error')
      }
    } catch (err) {
      showNotification('Verification failed. Please try again.', 'error')
    } finally {
      btn.disabled = false
      btn.textContent = 'Verify & Login'
    }
  })
}

// ==================== MAIN APP SHELL ====================

function renderShell() {
  const head = `
    <header>
      <div class="row">
        <strong>CloudSim Client Portal</strong>
        <span class="muted" id="summary"></span>
      </div>
      <nav>
        <a href="#/dashboard" data-route="dashboard">Dashboard</a>
        <a href="#/upload" data-route="upload">Upload</a>
        <a href="#/files" data-route="files">Files</a>
        <a href="#/profile" data-route="profile">Profile</a>
        <a href="#/logout" data-route="logout" style="color: #c22;">Logout</a>
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

// ==================== DASHBOARD ====================

function renderDashboard() {
  setActive('dashboard')
  const view = document.getElementById('view')
  view.innerHTML = `
    <div class="row" style="justify-content: space-between; margin-bottom: 20px;">
      <h2>Welcome, ${currentUser}!</h2>
      <button id="refreshDash" class="primary">Refresh</button>
    </div>
    <div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 20px;">
      <div class="card">
        <h3>System Status</h3>
        <div id="systemStatus" style="margin-top: 12px;">
          <div class="loading">Loading...</div>
        </div>
      </div>
      <div class="card">
        <h3>Your Storage</h3>
        <div id="userStorage" style="margin-top: 12px;">
          <div class="loading">Loading...</div>
        </div>
      </div>
    </div>
    <div class="card">
      <h3>Your Files</h3>
      <div id="fileStats" style="margin-top: 12px;">
        <div class="loading">Loading...</div>
      </div>
    </div>
  `
  
  async function load() {
    const viewEl = document.getElementById('view')
    setLoading(viewEl, true)
    
    try {
      const [statusRes, profileRes, filesRes] = await Promise.all([
        fetch('/status').then(r => r.json()),
        fetch(`/auth/profile/${currentUser}`).then(r => r.json()),
        fetch(`/auth/files/${currentUser}`).then(r => r.json())
      ])
      
      // System Status
      const systemStatus = document.getElementById('systemStatus')
      const isAvailable = statusRes.running_nodes > 0
      systemStatus.innerHTML = `
        <div style="display: flex; align-items: center; gap: 8px;">
          <span style="width: 12px; height: 12px; border-radius: 50%; background: ${isAvailable ? '#0a7' : '#c22'};"></span>
          <strong>${isAvailable ? 'System Available' : 'System Maintenance'}</strong>
        </div>
        <p class="muted" style="margin-top: 8px; font-size: 14px;">
          ${isAvailable ? 'All systems operational' : 'System is currently unavailable.'}
        </p>
      `
      
      // User Storage (with real quota data)
      const userStorage = document.getElementById('userStorage')
      if (profileRes.ok) {
        const usagePercent = profileRes.usage_percent || 0
        const usageColor = usagePercent > 90 ? '#c22' : usagePercent > 70 ? '#fa0' : '#0a7'
        userStorage.innerHTML = `
          <div style="margin-bottom: 12px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
              <span>${formatBytes(profileRes.used_bytes)} used</span>
              <span>${formatBytes(profileRes.quota_bytes)} total</span>
            </div>
            <div style="height: 8px; background: #f0f0f0; border-radius: 4px; overflow: hidden;">
              <div style="height: 100%; width: ${usagePercent}%; background: ${usageColor};"></div>
            </div>
          </div>
          <div class="muted">${usagePercent.toFixed(1)}% used • ${formatBytes(profileRes.quota_bytes - profileRes.used_bytes)} remaining</div>
        `
      } else {
        userStorage.innerHTML = `<div class="muted">Could not load storage info</div>`
      }
      
      // File Stats
      const fileStats = document.getElementById('fileStats')
      const files = filesRes.files || []
      const totalSize = files.reduce((sum, f) => sum + (f.size || 0), 0)
      fileStats.innerHTML = `
        <div class="row" style="gap: 24px; flex-wrap: wrap;">
          <div>
            <strong style="font-size: 24px;">${files.length}</strong>
            <div class="muted">Total Files</div>
          </div>
          <div>
            <strong style="font-size: 24px;">${formatBytes(totalSize)}</strong>
            <div class="muted">Total Size</div>
          </div>
        </div>
        ${files.length > 0 ? `
          <div style="margin-top: 16px;">
            <a href="#/files" style="color: #1a1a2e;">View all files →</a>
          </div>
        ` : `
          <div style="margin-top: 16px;">
            <a href="#/upload" style="color: #1a1a2e;">Upload your first file →</a>
          </div>
        `}
      `
      
      // Update summary
        const summary = document.getElementById('summary')
      summary.textContent = `${files.length} files • ${formatBytes(totalSize)}`
      
    } catch (err) {
      showNotification('Failed to load dashboard data', 'error')
    } finally {
      setLoading(viewEl, false)
    }
  }
  
  document.getElementById('refreshDash').addEventListener('click', load)
  load()
}

// ==================== UPLOAD ====================

function renderUpload() {
  setActive('upload')
  const view = document.getElementById('view')
  view.innerHTML = `
    <h2>Upload File</h2>
    <div class="card">
      <div id="quotaInfo" style="margin-bottom: 20px;">
        <div class="loading">Checking available storage...</div>
      </div>
      
      <div id="uploadArea" style="border: 2px dashed #ddd; border-radius: 8px; padding: 40px; text-align: center; margin-bottom: 20px;">
        <div style="font-size: 48px; margin-bottom: 16px;">📁</div>
        <p style="margin: 0 0 16px 0; color: #666;">Drag and drop a file here, or click to select</p>
        <input type="file" id="fileInput" style="display: none;" />
        <button id="selectFile" class="primary">Select File</button>
      </div>
      
      <div id="selectedFile" style="display: none; background: #f9f9f9; border-radius: 8px; padding: 16px; margin-bottom: 20px;">
        <div class="row" style="justify-content: space-between;">
          <div>
            <strong id="fileName"></strong>
            <div class="muted" id="fileSize"></div>
          </div>
          <button id="clearFile" style="padding: 6px 12px;">Clear</button>
        </div>
      </div>
      
      <button id="uploadBtn" class="primary" style="width: 100%; padding: 14px; font-size: 16px;" disabled>
        Upload File
      </button>
      
      <div id="uploadProgress" style="display: none; margin-top: 16px;">
        <div style="height: 8px; background: #f0f0f0; border-radius: 4px; overflow: hidden;">
          <div id="progressBar" style="height: 100%; width: 0%; background: #0a7; transition: width 0.3s;"></div>
        </div>
        <div class="muted" style="text-align: center; margin-top: 8px;" id="progressText">Uploading...</div>
      </div>
    </div>
  `
  
  let selectedFile = null
  
  // Load quota info
  fetch(`/auth/profile/${currentUser}`)
    .then(r => r.json())
    .then(data => {
      if (data.ok) {
        const remaining = data.quota_bytes - data.used_bytes
        document.getElementById('quotaInfo').innerHTML = `
          <div style="display: flex; align-items: center; gap: 12px;">
            <span style="font-size: 24px;">💾</span>
            <div>
              <strong>Available Storage: ${formatBytes(remaining)}</strong>
              <div class="muted">${formatBytes(data.used_bytes)} of ${formatBytes(data.quota_bytes)} used</div>
            </div>
          </div>
        `
      }
    })
  
  const fileInput = document.getElementById('fileInput')
  const selectFileBtn = document.getElementById('selectFile')
  const uploadArea = document.getElementById('uploadArea')
  const selectedFileDiv = document.getElementById('selectedFile')
  const uploadBtn = document.getElementById('uploadBtn')
  
  selectFileBtn.addEventListener('click', () => fileInput.click())
  uploadArea.addEventListener('click', (e) => {
    if (e.target === uploadArea || e.target.tagName === 'P' || e.target.tagName === 'DIV') {
      fileInput.click()
    }
  })
  
  uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault()
    uploadArea.style.borderColor = '#1a1a2e'
    uploadArea.style.background = '#f9f9f9'
  })
  
  uploadArea.addEventListener('dragleave', () => {
    uploadArea.style.borderColor = '#ddd'
    uploadArea.style.background = 'transparent'
  })
  
  uploadArea.addEventListener('drop', (e) => {
    e.preventDefault()
    uploadArea.style.borderColor = '#ddd'
    uploadArea.style.background = 'transparent'
    if (e.dataTransfer.files.length > 0) {
      selectFile(e.dataTransfer.files[0])
    }
  })
  
  fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) {
      selectFile(fileInput.files[0])
    }
  })
  
  function selectFile(file) {
    selectedFile = file
    document.getElementById('fileName').textContent = file.name
    document.getElementById('fileSize').textContent = formatBytes(file.size)
    selectedFileDiv.style.display = 'block'
    uploadBtn.disabled = false
  }
  
  document.getElementById('clearFile').addEventListener('click', () => {
    selectedFile = null
    fileInput.value = ''
    selectedFileDiv.style.display = 'none'
    uploadBtn.disabled = true
  })
  
  uploadBtn.addEventListener('click', async () => {
    if (!selectedFile) return
    
    uploadBtn.disabled = true
    uploadBtn.textContent = 'Uploading...'
    document.getElementById('uploadProgress').style.display = 'block'
    
    try {
      // Check quota first
      const quotaCheck = await fetch(`/auth/check-quota/${currentUser}?file_size=${selectedFile.size}`, { method: 'POST' })
      const quotaData = await quotaCheck.json()
      
      if (!quotaData.allowed) {
        showNotification(`Not enough storage! You need ${formatBytes(selectedFile.size)} but only have ${formatBytes(quotaData.remaining_bytes)} available.`, 'error')
        uploadBtn.disabled = false
        uploadBtn.textContent = 'Upload File'
        document.getElementById('uploadProgress').style.display = 'none'
        return
      }
      
      // Upload file
      const formData = new FormData()
      formData.append('file', selectedFile)
      formData.append('user', currentUser)
      
      const response = await fetch('/files', {
        method: 'POST',
        body: formData
      })
      
      const data = await response.json()
      
      if (data.ok) {
        document.getElementById('progressBar').style.width = '100%'
        document.getElementById('progressText').textContent = 'Upload complete!'
        showNotification('File uploaded successfully!', 'success')
        setTimeout(() => window.location.hash = '#/files', 1500)
      } else {
        showNotification(data.message || 'Upload failed', 'error')
      }
    } catch (err) {
      showNotification('Upload failed. Please try again.', 'error')
    } finally {
      uploadBtn.disabled = false
      uploadBtn.textContent = 'Upload File'
    }
  })
}

// ==================== FILES ====================

function renderFiles() {
  setActive('files')
  const view = document.getElementById('view')
  view.innerHTML = `
    <div class="row" style="justify-content: space-between; margin-bottom: 20px;">
      <h2>Your Files</h2>
      <div class="row" style="gap: 8px;">
        <input type="text" id="searchInput" placeholder="Search files..." 
          style="padding: 8px 12px; border: 1px solid #ddd; border-radius: 6px;" />
        <button id="refreshFiles" class="primary">Refresh</button>
      </div>
    </div>
    <div class="card">
      <div id="filesList">
        <div class="loading">Loading files...</div>
      </div>
    </div>
  `
  
  const searchInput = document.getElementById('searchInput')
  let allFiles = []
  
  async function loadFiles() {
    const viewEl = document.getElementById('view')
    setLoading(viewEl, true)
    
    try {
      const response = await fetch(`/auth/files/${currentUser}`)
      const data = await response.json()
      allFiles = data.files || []
      displayFiles(allFiles)
    } catch (err) {
      showNotification('Failed to load files', 'error')
      document.getElementById('filesList').innerHTML = '<div class="error">Failed to load files</div>'
    } finally {
      setLoading(viewEl, false)
    }
  }
  
  function displayFiles(files) {
    const filesList = document.getElementById('filesList')
    
    if (files.length === 0) {
      filesList.innerHTML = `
        <div style="text-align: center; padding: 40px;">
          <div style="font-size: 48px; margin-bottom: 16px;">📭</div>
          <p class="muted">No files yet</p>
          <a href="#/upload" class="primary" style="display: inline-block; margin-top: 12px; padding: 10px 20px; text-decoration: none; border-radius: 6px;">Upload your first file</a>
        </div>
      `
          return
        }
    
    filesList.innerHTML = `
      <table style="width: 100%;">
        <thead>
          <tr style="border-bottom: 2px solid #eee;">
            <th style="text-align: left; padding: 12px;">File Name</th>
            <th style="text-align: right; padding: 12px;">Size</th>
            <th style="text-align: right; padding: 12px;">Actions</th>
          </tr>
        </thead>
        <tbody>
          ${files.map(f => `
            <tr style="border-bottom: 1px solid #eee;" data-id="${f.file_id}" data-name="${f.name || 'download'}">
              <td style="padding: 12px;">
                <strong>${f.name || f.file_id}</strong>
              </td>
              <td style="text-align: right; padding: 12px;">${formatBytes(f.size || 0)}</td>
              <td style="text-align: right; padding: 12px;">
                <div class="row" style="justify-content: flex-end; gap: 8px;">
                  <button class="download" style="padding: 6px 12px;">Download</button>
                  <button class="delete" style="padding: 6px 12px; background: #c22; color: white; border-color: #c22;">Delete</button>
                </div>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `
    
    // Add event listeners
    filesList.querySelectorAll('button.download').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const row = e.target.closest('tr')
        const fileId = row.getAttribute('data-id')
        const fileName = row.getAttribute('data-name')
        window.open(`/files/${fileId}/download?filename=${encodeURIComponent(fileName)}`, '_blank')
        showNotification('Download started', 'success')
      })
    })
    
    filesList.querySelectorAll('button.delete').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const fileId = e.target.closest('tr').getAttribute('data-id')
        if (confirm('Are you sure you want to delete this file?')) {
          try {
            const response = await fetch(`/files/${fileId}?user=${currentUser}`, { method: 'DELETE' })
            const data = await response.json()
            if (data.ok) {
              showNotification('File deleted successfully', 'success')
              loadFiles()
            } else {
              showNotification('Failed to delete file', 'error')
            }
          } catch (err) {
            showNotification('Failed to delete file', 'error')
          }
        }
      })
    })
  }
  
  searchInput.addEventListener('input', () => {
    const query = searchInput.value.toLowerCase()
    const filtered = allFiles.filter(f => 
      (f.name || f.file_id || '').toLowerCase().includes(query)
    )
    displayFiles(filtered)
  })
  
  document.getElementById('refreshFiles').addEventListener('click', loadFiles)
  loadFiles()
}

// ==================== PROFILE ====================

function renderProfile() {
  setActive('profile')
  const view = document.getElementById('view')
  view.innerHTML = `
    <h2>Your Profile</h2>
    <div class="card">
      <div id="profileInfo">
        <div class="loading">Loading profile...</div>
      </div>
    </div>
  `
  
  fetch(`/auth/profile/${currentUser}`)
    .then(r => r.json())
    .then(data => {
      const profileInfo = document.getElementById('profileInfo')
      
      if (data.ok) {
        const usagePercent = data.usage_percent || 0
        const usageColor = usagePercent > 90 ? '#c22' : usagePercent > 70 ? '#fa0' : '#0a7'
        
        profileInfo.innerHTML = `
          <div style="display: flex; gap: 24px; flex-wrap: wrap;">
            <div style="flex: 1; min-width: 250px;">
              <h3 style="margin-top: 0;">Account Information</h3>
              <div style="margin-bottom: 12px;">
                <label class="muted" style="display: block; margin-bottom: 4px;">Username</label>
                <strong style="font-size: 18px;">${data.username}</strong>
              </div>
              <div style="margin-bottom: 12px;">
                <label class="muted" style="display: block; margin-bottom: 4px;">Email</label>
                <span>${data.email}</span>
              </div>
            </div>
            
            <div style="flex: 1; min-width: 250px;">
              <h3 style="margin-top: 0;">Storage Usage</h3>
              <div style="margin-bottom: 16px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                  <span>Used: ${formatBytes(data.used_bytes)}</span>
                  <span>Total: ${formatBytes(data.quota_bytes)}</span>
                </div>
                <div style="height: 12px; background: #f0f0f0; border-radius: 6px; overflow: hidden;">
                  <div style="height: 100%; width: ${usagePercent}%; background: ${usageColor};"></div>
                </div>
                <div class="muted" style="text-align: center; margin-top: 8px;">
                  ${usagePercent.toFixed(1)}% used
                </div>
              </div>
              
              <div style="background: #f9f9f9; border-radius: 8px; padding: 16px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                  <span>Plan</span>
                  <strong>Free Tier</strong>
                </div>
                <div style="display: flex; justify-content: space-between;">
                  <span>Quota</span>
                  <strong>${data.quota_gb} GB</strong>
                </div>
              </div>
            </div>
          </div>
          
          <div style="margin-top: 24px; padding-top: 24px; border-top: 1px solid #eee;">
            <button id="logoutBtn" style="background: #c22; color: white; border-color: #c22; padding: 12px 24px;">
              Logout
            </button>
            </div>
          `
        
        document.getElementById('logoutBtn').addEventListener('click', () => {
          if (confirm('Are you sure you want to logout?')) {
            clearAuthState()
            window.location.hash = '#/login'
          }
        })
      } else {
        profileInfo.innerHTML = '<div class="error">Could not load profile</div>'
      }
      })
      .catch(() => {
      document.getElementById('profileInfo').innerHTML = '<div class="error">Could not load profile</div>'
    })
}

// ==================== ROUTER ====================

function route() {
  const hash = window.location.hash || '#/login'
  const path = hash.slice(1) // Remove #
  
  // Auth routes (don't require login)
  if (path === '/login') {
    renderLoginPage()
    return
  }
  if (path === '/register') {
    renderRegisterPage()
    return
  }
  if (path === '/verify-otp') {
    renderOtpPage()
    return
  }
  if (path === '/logout') {
    clearAuthState()
    window.location.hash = '#/login'
    return
  }
  
  // Protected routes (require login)
  if (!isLoggedIn()) {
    window.location.hash = '#/login'
    return
  }
  
  // Render shell for authenticated pages
renderShell()
  
  switch (path) {
    case '/dashboard':
      renderDashboard()
      break
    case '/upload':
      renderUpload()
      break
    case '/files':
      renderFiles()
      break
    case '/profile':
      renderProfile()
      break
    default:
      renderDashboard()
  }
}

// Initialize
loadAuthState()
window.addEventListener('hashchange', route)
route()
