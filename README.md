# CloudSim Distributed Storage System

[![Build Status](https://img.shields.io/badge/build-passing-brightgreen)](https://github.com/yourusername/cloudsim)
[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**A comprehensive distributed cloud storage simulation system with node management, file replication, and real-time metrics monitoring.**

CloudSim is an educational and research-oriented distributed storage system that simulates a cloud service provider infrastructure. It demonstrates core concepts of distributed systems including node management, file chunking, data replication, network communication, and performance monitoring.

## Table of Contents

- [What is CloudSim?](#what-is-cloudsim)
- [Key Concepts Explained](#key-concepts-explained)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start Guide](#quick-start-guide)
- [Usage](#usage)
  - [For End Users (Clients)](#for-end-users-clients)
  - [For System Administrators (Providers)](#for-system-administrators-providers)
  - [Command-Line Interface](#command-line-interface)
- [Configuration](#configuration)
- [Architecture](#architecture)
- [How It Works](#how-it-works)
- [Common Operations](#common-operations)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)
- [Testing](#testing)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

## What is CloudSim?

**For Non-Technical Users:**

Imagine you have a large file (like a video or document) that you want to store safely. Instead of putting it in one place, CloudSim splits your file into smaller pieces called "chunks" and stores multiple copies of each chunk across different storage "nodes" (think of nodes as separate storage servers). This way, if one node fails, your data is still safe because copies exist on other nodes. It's like having multiple backup copies of your important documents in different locations.

**For Technical Users:**

CloudSim is a distributed storage system simulator that implements:
- **Horizontal scaling** through multiple storage nodes
- **Data durability** via configurable replication factors
- **Fault tolerance** through redundant chunk storage
- **Network-based I/O** using TCP/IP protocols
- **Real-time monitoring** with comprehensive metrics collection
- **Microservices architecture** with gRPC inter-service communication

The system simulates real-world cloud storage providers (like AWS S3, Google Cloud Storage) by ensuring all file operations occur over network connections rather than direct disk access, providing an authentic learning environment for distributed systems concepts.

## Key Concepts Explained

Understanding these concepts will help you get the most out of CloudSim:

### Storage Nodes
**Simple Explanation:** Think of a storage node as a separate computer or server that stores your files. Each node has its own storage capacity (like a hard drive), and you can create multiple nodes to distribute your data.

**Technical Explanation:** A storage node is a virtualized storage server instance running on a specific port. Each node has configurable resources: CPU cores, memory (RAM), storage capacity (disk space), and network bandwidth. Nodes run as independent threads and communicate via TCP/IP sockets.

### File Chunking
**Simple Explanation:** When you upload a large file, CloudSim automatically splits it into smaller pieces called "chunks." This makes it easier to store the file across multiple nodes and allows for faster uploads and downloads.

**Technical Explanation:** Files are divided into fixed-size chunks (default: 1MB) or dynamically-sized chunks based on file size and available nodes. Each chunk is assigned a unique identifier and can be stored independently. Chunking enables parallel transfers and efficient storage distribution.

### Replication
**Simple Explanation:** Replication means making multiple copies of your data. If you set replication to 3, each chunk of your file will be stored on 3 different nodes. This way, if one node breaks, you still have 2 other copies of your data.

**Technical Explanation:** Replication factor determines how many copies of each chunk are stored across different nodes. Default is 3, meaning each chunk exists on 3 nodes. This provides fault tolerance: if up to 2 nodes fail, data remains accessible. Replication is automatic and transparent to users.

### Network-Based Operations
**Simple Explanation:** Instead of directly accessing files on your computer's hard drive, CloudSim sends files over the network (like the internet) to storage nodes. This simulates how real cloud storage works, where your files are stored on remote servers.

**Technical Explanation:** All file operations (upload/download) use TCP/IP socket communication. The backend API acts as a client, connecting to nodes via TCP sockets, sending/receiving chunks over the network. This ensures the system accurately simulates distributed cloud storage where clients never directly access storage hardware.

### Metrics and Monitoring
**Simple Explanation:** CloudSim tracks how well the system is performing - how fast files are being uploaded/downloaded, how much storage space is being used, and how many files are stored. This information helps administrators understand system health.

**Technical Explanation:** The system collects real-time metrics including: throughput (data transfer speed in Mbps), latency (response time in milliseconds), storage utilization (percentage of capacity used), network utilization, error rates, and per-user activity statistics. Metrics are aggregated and displayed in the provider portal.

## Description

CloudSim provides a complete simulation environment for understanding distributed storage architectures. The system allows you to create and manage multiple storage nodes, upload files that are automatically chunked and replicated across nodes, and monitor system performance through comprehensive metrics collection. It features both a command-line interface for system administration and web portals for end-users and service providers.

The system is designed with a microservices architecture using gRPC for inter-service communication, ensuring scalability and modularity. All file operations are performed over TCP/IP network connections, simulating real-world cloud storage behavior where clients interact with storage nodes through network protocols rather than direct disk access.

## Key Features

- **Distributed Node Management**: Create, start, stop, and delete storage nodes dynamically with configurable capacity, CPU, memory, and bandwidth
- **Intelligent File Chunking**: Automatic file splitting into configurable chunk sizes with dynamic sizing based on file size and node count
- **Data Replication**: Configurable replication factor (default: 3) ensuring fault tolerance and data redundancy across nodes
- **Network-Based Operations**: All file uploads and downloads occur over TCP/IP sockets, simulating real cloud storage interactions
- **Real-Time Metrics Collection**: Comprehensive monitoring of throughput, latency, storage utilization, network performance, and user activity
- **Dual Web Portals**: Separate interfaces for clients (file management) and providers (system administration)
- **User Authentication**: Secure registration and login with OTP email verification and quota management
- **gRPC Architecture**: Microservices-based design with CloudRPC server, AuthService, and REST API gateway

## Tech Stack

- **Backend**: Python 3.9+, FastAPI, gRPC, Protocol Buffers
- **Frontend**: Vanilla JavaScript, HTML5, CSS3
- **Data Storage**: JSON-based state persistence, YAML configuration
- **Networking**: TCP/IP sockets, UDP discovery protocol
- **Security**: bcrypt password hashing, OTP email verification
- **Testing**: pytest, pytest-cov
- **Code Quality**: pylint, black, flake8

## Prerequisites

Before installing CloudSim, ensure you have the following installed on your system:

- **Python 3.9 or higher** (Python 3.10+ recommended)
- **pip** (Python package manager)
- **PowerShell 5.1+** (for Windows startup scripts) or **Bash** (for Linux/Mac)
- **Gmail account with App Password** (for OTP email functionality - optional)
- **Network ports available**: 5000-5999 (nodes), 8000 (REST API), 50051 (gRPC), 51234 (AuthService), 9999 (discovery)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/cloudsim.git
cd cloudsim
```

### 2. Install Python Dependencies

```bash
# Navigate to CloudSim directory
cd CloudSim

# Install required dependencies
pip install -r requirements.txt

# For development (optional)
pip install -r requirements-dev.txt
```

### 3. Install Additional Backend Dependencies

```bash
# Install FastAPI and Uvicorn for REST API
pip install fastapi uvicorn

# Install gRPC and Protocol Buffers
pip install grpcio grpcio-tools protobuf

# Install bcrypt for password hashing
pip install bcrypt

# Install PyYAML (if not already installed)
pip install pyyaml
```

### 4. Generate Protocol Buffer Files

```bash
# Generate CloudRPC protobuf files
cd cloudrpc
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. cloudsim.proto

# Generate AuthService protobuf files
cd ../AuthService
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. cloudsecurity.proto
```

### 5. Configure Email Settings (Optional)

For OTP email functionality:

```bash
# Copy the template
cp AuthService/params.template.py AuthService/params.py

# Edit AuthService/params.py and add your Gmail credentials
# See AuthService/params.template.py for instructions on creating a Gmail App Password
```

### 6. Configure Storage Directory

Edit `CloudSim/config.yaml` and set your desired storage base directory:

```yaml
storage:
  base_directory: "A:\\"  # Change to your preferred path
```

**Note for Windows Users:** Use double backslashes (`\\`) or forward slashes (`/`) in the path. Example: `"C:\\CloudSim\\storage"` or `"C:/CloudSim/storage"`

**Note for Linux/Mac Users:** Use standard Unix paths. Example: `"/var/cloudsim/storage"` or `"~/cloudsim/storage"`

## Quick Start Guide

### First-Time Setup (5 Minutes)

1. **Start All Services** (Open 3 terminal windows):
   ```powershell
   # Terminal 1: CloudRPC Server
   .\cloudrpc\start_cloudrpc.ps1
   
   # Terminal 2: Backend API
   .\backend\start_backend.ps1
   
   # Terminal 3: AuthService
   .\AuthService\start_authservice.ps1
   ```

2. **Create Your First Storage Node**:
   ```bash
   cd CloudSim
   python cli.py create node1 --cpu 2 --memory 4 --storage 10 --bandwidth 500
   ```

3. **Start the Node**:
   ```bash
   python cli.py start node1
   ```

4. **Start the Network Service**:
   ```bash
   python cli.py network start
   ```

5. **Open the Web Interface**:
   - Open your browser and go to `http://127.0.0.1:8000`
   - You'll see the Client Portal where you can register and upload files

![Quick Start Screenshot](insert-screenshot-link-here)
*The Client Portal welcome screen after starting all services*

## Usage

### Starting the System

CloudSim requires three services to be running. Start them in separate terminals:

#### Terminal 1: Start CloudRPC Server (gRPC)

```powershell
# Windows
.\cloudrpc\start_cloudrpc.ps1

# Linux/Mac
cd cloudrpc
python server.py
```

The gRPC server will start on port **50051**.

#### Terminal 2: Start Backend API (REST Gateway)

```powershell
# Windows
.\backend\start_backend.ps1

# Linux/Mac
cd backend
python -m uvicorn api:app --host 127.0.0.1 --port 8000 --reload
```

The REST API will be available at `http://127.0.0.1:8000`.

#### Terminal 3: Start AuthService (Authentication)

```powershell
# Windows
.\AuthService\start_authservice.ps1

# Linux/Mac
cd AuthService
python cloud.py
```

The AuthService will start on port **51234**.

### Accessing Web Portals

Once all services are running:

- **Client Portal**: Open `http://127.0.0.1:8000` in your browser (defaults to client portal)
- **Provider Portal**: Navigate to `http://127.0.0.1:8000` and use the provider interface

![Web Portal Screenshot](![alt text](/screenshots/image2.png ![alt text](/screenshots/image3.png)))
*The dual-portal interface showing both client and provider views*

## For End Users (Clients)

### Creating an Account

1. Open `http://127.0.0.1:8000` in your browser
2. Click "Register" or navigate to the registration page
3. Fill in:
   - **Username**: Choose a unique username
   - **Email**: Your email address (for OTP verification)
   - **Password**: At least 6 characters
4. Click "Create Account"
5. You'll automatically receive **1GB of free storage** (this can be increased by administrators)

![Registration Screenshot](![alt text](/screenshots/image.png))
*The user registration form with free tier information*

### Logging In

1. Enter your username and password
2. Click "Login"
3. You'll receive an OTP (One-Time Password) via email
4. Enter the OTP code to complete login
5. You'll be redirected to your dashboard

**Note:** If you don't receive an OTP email, check:
- Your email spam folder
- That `AuthService/params.py` is configured with valid Gmail credentials
- That the AuthService is running

### Uploading Files

1. After logging in, click "Upload" in the navigation
2. Click "Choose File" and select a file from your computer
3. Click "Upload File"
4. The system will:
   - Split your file into chunks
   - Distribute chunks across available nodes
   - Create multiple copies (replication) for safety
   - Show upload progress

**What Happens Behind the Scenes:**
- Your file is divided into smaller chunks (default: 1MB each)
- Each chunk is sent over the network to different storage nodes
- Multiple copies of each chunk are created (default: 3 copies)
- The system tracks where each chunk is stored

![Upload Process Screenshot](![alt text](/screenshots/image4.png))
![Chunk distribution showed on provider portal](![alt text](/screenshots/image5.png))
*File upload in progress showing chunk distribution*


### Viewing Your Files

1. Click "My Files" in the navigation
2. You'll see a list of all files you've uploaded
3. For each file, you can see:
   - File name
   - File size
   - Upload date
   - Storage used

### Downloading Files

1. Go to "My Files"
2. Find the file you want to download
3. Click the "Download" button
4. The system will:
   - Locate all chunks of the file across nodes
   - Retrieve chunks over the network
   - Reassemble the file
   - Download it to your computer

**Note:** Downloads work even if some nodes are offline, as long as at least one copy of each chunk is available (thanks to replication).

### Deleting Files

1. Go to "My Files"
2. Find the file you want to delete
3. Click the "Delete" button
4. Confirm deletion
5. The system will remove all chunks and copies from all nodes

**Warning:** Deletion is permanent and cannot be undone.

### Checking Your Storage Quota

1. Click on your profile or username
2. View your storage usage:
   - **Used Storage**: How much space your files are using
   - **Total Quota**: Your storage limit
   - **Available**: Remaining space
   - **Usage Percentage**: Visual indicator of your usage

If you need more storage, contact your system administrator to increase your quota.

## For System Administrators (Providers)

The Provider Portal provides comprehensive system management tools.

### Dashboard Overview

The dashboard shows:
- **System Health**: Overall system status
- **Storage Overview**: Total capacity, used storage, utilization percentage
- **Network Status**: Whether the discovery network is running
- **Node Count**: Number of nodes and their status

![Provider Dashboard Screenshot](![alt text](/screenshots/image6.png))
*The provider dashboard showing system overview*

### Managing Storage Nodes

#### Creating Nodes

1. Navigate to "Nodes" in the provider portal
2. Click "Create Node"
3. Fill in node specifications:
   - **Node ID**: Unique identifier (e.g., `node1`, `storage-server-01`)
   - **CPU Cores**: Number of virtual CPU cores (e.g., 4)
   - **Memory (GB)**: RAM allocation (e.g., 8 GB)
   - **Storage (GB)**: Disk capacity (e.g., 100 GB)
   - **Bandwidth (Mbps)**: Network speed (e.g., 1000 Mbps)
4. Click "Create"

**Example Node Configurations:**
- **Small Node**: 2 CPU, 4GB RAM, 20GB storage, 500 Mbps
- **Medium Node**: 4 CPU, 8GB RAM, 100GB storage, 1000 Mbps
- **Large Node**: 8 CPU, 16GB RAM, 500GB storage, 2000 Mbps

#### Starting Nodes

1. Go to "Nodes"
2. Find the node you want to start
3. Click "Start" button
4. Wait for the node to initialize (you'll see status change to "Running")

**Bulk Operations:**
- Click "Start All Nodes" to start all stopped nodes at once
- This is useful after system restart

#### Stopping Nodes

1. Go to "Nodes"
2. Find the running node
3. Click "Stop" button
4. The node will gracefully shut down

**Important:** Stopping a node doesn't delete your data. Files remain stored on the node's disk and can be accessed again when the node is restarted.

#### Viewing Node Details

Click "Details" on any node to see:
- **Basic Information**: Node ID, status, IP address, MAC address
- **Resources**: CPU, memory, storage capacity
- **Current Usage**: Storage utilization, number of files stored
- **Network Information**: Host, port, network registration status

![Node Details Screenshot](![alt text](/screenshots/image7.png))
*Detailed node information panel*

#### Deleting Nodes

1. Go to "Nodes"
2. Find the node you want to delete
3. Click "Delete" button
4. Confirm deletion

**Warning:** Deleting a node will remove all files stored on that node. Make sure you have sufficient replication (copies on other nodes) before deleting.

### Managing Users

#### Viewing All Users

1. Navigate to "Users" in the provider portal
2. See a table of all registered users with:
   - Username
   - Email address
   - Storage usage
   - Storage quota
   - Usage percentage
   - Number of files

#### Updating User Quotas

1. Go to "Users"
2. Find the user whose quota you want to change
3. Click "Update Quota"
4. Enter the new quota in GB
5. Click "Update"

**Note:** The new quota must be at least as large as the user's current storage usage.

### Monitoring Metrics

The Metrics page provides comprehensive system monitoring.

#### Storage Overview Card

Shows:
- **Total Storage**: Combined capacity of all nodes
- **Used Storage**: Total space used by all files
- **Storage Utilization**: Percentage of total capacity used
- **Total Files**: Number of files stored across all nodes
- **Capacity Alerts**: Warnings when storage is getting full

#### Node Details Table

For each node, displays:
- Node ID
- Status (Running/Stopped)
- Total Capacity
- Used Storage
- Number of Files
- Storage Utilization Percentage

#### Transfer History

Shows recent file transfers with:
- **User ID**: Who performed the transfer
- **Transfer Size**: Size of the file transferred
- **Network Latency**: Response time in milliseconds
- **Network Throughput**: Transfer speed in Mbps
- **Status**: Success or failure
- **Time**: When the transfer occurred

**Expanding Transfer Details:**
- Click on any file transfer row to see individual chunk transfer details
- This shows how chunks were distributed across nodes

![Metrics Dashboard Screenshot](![alt text](/screenshots/image8.png))
*Comprehensive metrics dashboard with storage, nodes, and transfer history*

### Network Management

#### Starting the Network Service

The network service enables node discovery and communication:
1. Navigate to "Dashboard"
2. Check "Network Status"
3. If not running, use CLI: `python cli.py network start`

**What the Network Service Does:**
- Allows nodes to discover each other
- Enables inter-node communication
- Required for file replication and node coordination

#### Network Status Indicators

- **Running**: Network service is active and nodes can communicate
- **Stopped**: Network service is down, nodes operate independently

### Command-Line Interface

For system administration via CLI:

```bash
cd CloudSim
python cli.py <command> [options]
```

**Common CLI Commands:**

```bash
# Create a node
python cli.py create <node_id> --cpu 4 --memory 8 --storage 16 --bandwidth 1000

# List all nodes
python cli.py list

# Start a node
python cli.py start <node_id>

# Start all nodes
python cli.py start-all

# Stop a node
python cli.py stop <node_id>

# Get node status
python cli.py status <node_id>

# Delete a node
python cli.py delete <node_id>

# Start network service
python cli.py network start

# Get metrics
python cli.py metrics
```

**Complete CLI Command Reference:**

| Command | Description | Example |
|---------|-------------|---------|
| `create <node_id>` | Create a new storage node | `python cli.py create node1 --cpu 4 --memory 8 --storage 100 --bandwidth 1000` |
| `list` | List all configured nodes | `python cli.py list` |
| `start <node_id>` | Start a specific node | `python cli.py start node1` |
| `start-all` | Start all nodes | `python cli.py start-all` |
| `stop <node_id>` | Stop a specific node | `python cli.py stop node1` |
| `stop-all` | Stop all nodes | `python cli.py stop-all` |
| `restart <node_id>` | Restart a specific node | `python cli.py restart node1` |
| `status <node_id>` | Get detailed status of a node | `python cli.py status node1` |
| `info <node_id>` | Get comprehensive node information | `python cli.py info node1` |
| `delete <node_id>` | Delete a node (removes all data) | `python cli.py delete node1` |
| `network start` | Start the network discovery service | `python cli.py network start` |
| `network stop` | Stop the network discovery service | `python cli.py network stop` |
| `network status` | Check network service status | `python cli.py network status` |
| `metrics` | Display system metrics | `python cli.py metrics` |
| `capacity` | Show capacity planning information | `python cli.py capacity` |
| `store-file --file <path>` | Upload a file via CLI | `python cli.py store-file --file document.pdf --user myuser` |
| `delete-file --file-id <id>` | Delete a file by ID | `python cli.py delete-file --file-id abc123 --user myuser` |

### Running the Service Mode

For running CloudSim as a background service:

```bash
cd CloudSim
python main.py

# Or as daemon (Unix only)
python main.py --daemon
```

**Service Mode Features:**
- Automatically starts the network service
- Loads all configured nodes from state
- Keeps the system running for CLI operations
- Provides graceful shutdown on Ctrl+C

## How It Works

### File Upload Workflow

1. **User Initiates Upload**: Client selects a file through the web interface
2. **File Validation**: System checks user quota and file size
3. **Chunking**: File is split into smaller chunks (default: 1MB each)
4. **Node Selection**: System selects available nodes with sufficient space
5. **Network Transfer**: Each chunk is sent over TCP/IP to selected nodes
6. **Replication**: Multiple copies of each chunk are created (default: 3 copies)
7. **Metadata Storage**: File information is stored in AuthService
8. **Completion**: User receives confirmation with file ID

**Visual Flow:**
```
User File (10MB)
    ↓
[Chunking: 10 chunks × 1MB]
    ↓
[Node Selection: node1, node2, node3]
    ↓
[Network Transfer via TCP/IP]
    ↓
[Storage: Each chunk stored on 3 nodes]
    ↓
[Metadata: File record created]
    ↓
Upload Complete ✓
```

### File Download Workflow

1. **User Requests Download**: Client clicks download button
2. **File Lookup**: System retrieves file metadata from AuthService
3. **Chunk Location**: System identifies which nodes contain each chunk
4. **Network Retrieval**: System requests chunks from nodes over TCP/IP
5. **Chunk Assembly**: Received chunks are reassembled in order
6. **Checksum Verification**: Each chunk's integrity is verified
7. **File Delivery**: Complete file is sent to the user's browser

**Fault Tolerance:**
- If one node is unavailable, the system automatically retrieves the chunk from another node (thanks to replication)
- Download continues even if some nodes fail

### Replication Strategy

**How Replication Works:**
1. When a chunk is created, the system determines replication factor (default: 3)
2. The chunk is sent to 3 different nodes
3. Each node stores the chunk independently
4. The system tracks which nodes have which chunks

**Benefits:**
- **Fault Tolerance**: If 1-2 nodes fail, data is still accessible
- **Load Distribution**: Requests can be served from multiple nodes
- **Performance**: Parallel access to different chunks

**Example:**
```
File: document.pdf (5 chunks)
Chunk 1: Stored on node1, node2, node3
Chunk 2: Stored on node2, node3, node4
Chunk 3: Stored on node3, node4, node5
Chunk 4: Stored on node4, node5, node1
Chunk 5: Stored on node5, node1, node2
```

### Network Communication

**Protocol Stack:**
- **Application Layer**: gRPC (for service-to-service communication)
- **Transport Layer**: TCP/IP (for file transfers)
- **Discovery Layer**: UDP (for node discovery)

**Message Types:**
- `CHUNK_DATA`: Sending chunk data to a node
- `CHUNK_REQUEST`: Requesting a chunk from a node
- `CHUNK_ACK`: Acknowledgment of successful transfer
- `NODE_REGISTRATION`: Node joining the network
- `HEARTBEAT`: Node health check

## Common Operations

### Setting Up a New System

**Step-by-Step Guide:**

1. **Install Dependencies** (see Installation section)
2. **Configure Storage Directory**:
   ```yaml
   # Edit CloudSim/config.yaml
   storage:
     base_directory: "C:/CloudSim/storage"  # Your preferred path
   ```
3. **Create Initial Nodes**:
   ```bash
   python cli.py create node1 --cpu 4 --memory 8 --storage 50 --bandwidth 1000
   python cli.py create node2 --cpu 4 --memory 8 --storage 50 --bandwidth 1000
   python cli.py create node3 --cpu 4 --memory 8 --storage 50 --bandwidth 1000
   ```
4. **Start All Services** (3 terminals)
5. **Start Nodes and Network**:
   ```bash
   python cli.py start-all
   python cli.py network start
   ```
6. **Verify System**:
   ```bash
   python cli.py list
   python cli.py status node1
   ```

### Adding More Storage Capacity

**Scenario:** You need more storage space for users.

**Solution:**
1. Create additional nodes:
   ```bash
   python cli.py create node4 --cpu 4 --memory 8 --storage 100 --bandwidth 1000
   python cli.py create node5 --cpu 4 --memory 8 --storage 100 --bandwidth 1000
   ```
2. Start the new nodes:
   ```bash
   python cli.py start node4
   python cli.py start node5
   ```
3. New nodes are automatically included in future file uploads
4. Existing files remain on their original nodes (not automatically moved)

**Note:** To redistribute existing files, you would need to re-upload them or implement a rebalancing tool.

### Handling Node Failures

**Scenario:** A node stops responding or crashes.

**What Happens:**
- Files stored on that node remain accessible from replicated copies on other nodes
- Downloads automatically use alternative nodes
- The system continues operating normally

**Recovery Steps:**
1. **Check Node Status**:
   ```bash
   python cli.py status node1
   ```
2. **Restart the Node**:
   ```bash
   python cli.py restart node1
   ```
3. **If Node Won't Start**: Check logs and storage directory permissions
4. **If Node is Permanently Lost**: 
   - Data is safe (thanks to replication)
   - Delete the node: `python cli.py delete node1`
   - Create a replacement node

### Monitoring System Health

**Daily Checks:**
1. **Storage Utilization**: Check Metrics page for overall usage
2. **Node Status**: Verify all nodes are running
3. **Network Status**: Ensure network service is active
4. **Error Rates**: Review transfer history for failures

**Weekly Reviews:**
1. **Capacity Planning**: Check if storage is approaching limits
2. **User Quotas**: Review user storage usage
3. **Performance Metrics**: Analyze throughput and latency trends
4. **Node Health**: Review individual node metrics

### Backup and Recovery

**Current State:**
- Node configurations are stored in `CloudSim/nodes_state.json`
- User accounts are stored in `AuthService/users.json`
- File metadata is stored in AuthService
- Actual file chunks are stored in node storage directories

**Backup Strategy:**
1. **Backup Configuration Files**:
   ```bash
   cp CloudSim/nodes_state.json CloudSim/nodes_state.json.backup
   cp AuthService/users.json AuthService/users.json.backup
   cp CloudSim/config.yaml CloudSim/config.yaml.backup
   ```
2. **Backup Storage Directories**: Copy node storage directories (e.g., `A:/node1`, `A:/node2`)
3. **Regular Backups**: Schedule automated backups of configuration and storage

**Recovery:**
1. Restore configuration files
2. Restore storage directories to their original locations
3. Restart all services
4. Verify nodes can access their storage directories

## Configuration

CloudSim uses a YAML configuration file (`CloudSim/config.yaml`) for system-wide settings. This section explains all configuration options in detail.

### Configuration File Location

The main configuration file is located at: `CloudSim/config.yaml`

### Complete Configuration Reference

| Configuration Section | Key | Default | Description | Example |
|----------------------|-----|---------|-------------|---------|
| `network.discovery.port` | `port` | `9999` | UDP port for node discovery | `9999` |
| `network.discovery.broadcast_interval_seconds` | `broadcast_interval_seconds` | `30.0` | How often nodes broadcast their presence | `30.0` |
| `network.discovery.node_timeout_seconds` | `node_timeout_seconds` | `90.0` | Time before considering a node offline | `90.0` |
| `node_factory.start_port` | `start_port` | `5000` | Starting port for node assignment | `5000` |
| `node_factory.port_range_size` | `port_range_size` | `1000` | Number of ports available for nodes | `1000` |
| `storage.base_directory` | `base_directory` | `"A:\\"` | Base directory for node storage | `"C:/CloudSim/storage"` |
| `storage.chunk_size_mb` | `chunk_size_mb` | `1` | Default chunk size in MB | `2` (for 2MB chunks) |
| `replication.default_factor` | `default_factor` | `3` | Default replication factor | `3` (3 copies) |
| `replication.min_factor` | `min_factor` | `2` | Minimum replication factor | `2` |
| `replication.max_factor` | `max_factor` | `6` | Maximum replication factor | `6` |
| `metrics.collection_interval_seconds` | `collection_interval_seconds` | `5.0` | Metrics collection interval | `5.0` |
| `metrics.max_history` | `max_history` | `1000` | Maximum metric samples to keep | `1000` |
| `capacity.thresholds.global` | `thresholds` | `[50%, 75%, 90%, 95%]` | Storage utilization alert thresholds | See below |

### Configuration Examples

#### Example 1: High-Performance Setup

For systems with fast storage and high bandwidth:

```yaml
storage:
  chunk_size_mb: 5  # Larger chunks for better performance

replication:
  default_factor: 4  # More copies for better availability

performance:
  max_concurrent_transfers: 20  # More parallel transfers
  transfer_timeout_seconds: 600  # Longer timeout for large files
```

#### Example 2: Resource-Constrained Setup

For systems with limited resources:

```yaml
storage:
  chunk_size_mb: 0.5  # Smaller chunks use less memory

replication:
  default_factor: 2  # Minimum replication to save space

performance:
  max_concurrent_transfers: 5  # Fewer parallel transfers
```

#### Example 3: Custom Storage Location

```yaml
storage:
  base_directory: "D:/CloudSimStorage"  # Windows
  # base_directory: "/var/cloudsim/storage"  # Linux
  # base_directory: "~/cloudsim/storage"  # Mac (home directory)
```

#### Example 4: Custom Capacity Alerts

```yaml
capacity:
  thresholds:
    global:
      - percent: 60.0
        level: "INFO"
        description: "Storage utilization reached 60%"
      - percent: 80.0
        level: "WARNING"
        description: "Storage utilization reached 80%"
      - percent: 95.0
        level: "CRITICAL"
        description: "Storage utilization reached 95% - Immediate action required"
```

### Email Configuration

Email settings are configured in `AuthService/params.py`:

```python
# Your Gmail address
from_email = "your.email@gmail.com"

# Gmail App Password (16 characters, spaces optional)
app_password = "xxxx xxxx xxxx xxxx"
```

**Setting Up Gmail App Password:**

1. Go to https://myaccount.google.com/apppasswords
2. Sign in with your Google account
3. Enable 2-Step Verification if not already enabled
4. Select "Mail" and "Windows Computer" (or your device)
5. Click "Generate"
6. Copy the 16-character password
7. Paste it into `AuthService/params.py`

**Note:** You cannot use your regular Gmail password. App Passwords are required for security.

### Node State Configuration

Node configurations are automatically saved to `CloudSim/nodes_state.json`. This file is created automatically and should not be edited manually. It contains:

- Node IDs and their configurations
- IP and MAC addresses
- Port assignments
- Resource specifications (CPU, memory, storage, bandwidth)

**Backup Recommendation:** Regularly backup `nodes_state.json` as it contains all your node configurations.

### User Data Storage

User accounts and file metadata are stored in `AuthService/users.json`. This file is created automatically and contains:

- User login credentials (hashed passwords)
- Email addresses
- Storage quotas
- Used storage
- File records (file IDs, names, sizes, node locations)

**Security Note:** This file contains sensitive information. Keep it secure and backed up.

### Environment Variables

Currently, CloudSim does not use environment variables. All configuration is managed through:

- **Main Config**: `CloudSim/config.yaml` (system-wide settings)
- **Email Config**: `AuthService/params.py` (Gmail credentials for OTP)
- **Node State**: `CloudSim/nodes_state.json` (auto-generated, stores node configurations)
- **User Data**: `AuthService/users.json` (auto-generated, stores user accounts)

### Configuration Best Practices

1. **Storage Directory**: Use a dedicated directory with sufficient space
2. **Chunk Size**: Larger chunks (2-5MB) for better performance, smaller chunks (0.5-1MB) for better distribution
3. **Replication**: Use 3 copies (default) for good balance between safety and storage efficiency
4. **Port Range**: Ensure port range doesn't conflict with other applications
5. **Backup Config**: Keep backups of configuration files before making changes

## Architecture

### System Overview

CloudSim uses a **microservices architecture** with three main services communicating via gRPC:

```
┌─────────────────┐
│  Client Portal  │
│  (HTML/JS)      │
└────────┬────────┘
         │ HTTP
         ▼
┌─────────────────┐      ┌──────────────┐
│  REST API        │◄─────►│  CloudRPC    │
│  (FastAPI)       │ gRPC  │  (gRPC)      │
│  Port: 8000      │       │  Port: 50051 │
└────────┬─────────┘       └──────┬───────┘
         │                        │
         │                        ▼
         │              ┌─────────────────┐
         │              │  NetworkService │
         │              │  (Discovery)    │
         │              │  Port: 9999     │
         │              └─────────────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────┐
│  AuthService    │      │  Storage      │
│  (gRPC)         │      │  Nodes        │
│  Port: 51234    │      │  Ports:       │
└─────────────────┘      │  5000-5999    │
                          └──────────────┘
```

### Component Details

#### 1. Client Portal (Frontend)
- **Technology**: Vanilla JavaScript, HTML5, CSS3
- **Purpose**: User interface for end users
- **Features**: File upload/download, account management, storage viewing
- **Location**: `frontend/apps/client/public/`

#### 2. Provider Portal (Frontend)
- **Technology**: Vanilla JavaScript, HTML5, CSS3
- **Purpose**: Administrative interface for system management
- **Features**: Node management, user management, metrics monitoring
- **Location**: `frontend/apps/provider/public/`

#### 3. REST API (Backend Gateway)
- **Technology**: FastAPI (Python)
- **Purpose**: HTTP-to-gRPC bridge, serves frontend, handles file operations
- **Port**: 8000
- **Key Functions**:
  - Receives HTTP requests from web portals
  - Converts requests to gRPC calls
  - Manages file uploads/downloads over TCP/IP
  - Serves static frontend files
- **Location**: `backend/api.py`

#### 4. CloudRPC Server (gRPC Service)
- **Technology**: gRPC, Protocol Buffers
- **Purpose**: Core system operations (node management, network control)
- **Port**: 50051
- **Key Functions**:
  - Node lifecycle management (create, start, stop, delete)
  - Network service control
  - System status queries
  - Node information retrieval
- **Location**: `cloudrpc/server.py`

#### 5. AuthService (gRPC Service)
- **Technology**: gRPC, Protocol Buffers, bcrypt
- **Purpose**: User authentication and file metadata management
- **Port**: 51234
- **Key Functions**:
  - User registration and login
  - OTP email verification
  - Password hashing (bcrypt)
  - File metadata storage
  - User quota management
- **Location**: `AuthService/cloud.py`

#### 6. Network Service
- **Technology**: UDP, TCP/IP
- **Purpose**: Node discovery and coordination
- **Port**: 9999 (UDP)
- **Key Functions**:
  - Node registration and discovery
  - Network health monitoring
  - Inter-node communication facilitation
- **Location**: `CloudSim/network_service.py`

#### 7. Storage Nodes
- **Technology**: Python threading, TCP/IP sockets
- **Purpose**: Actual file storage and retrieval
- **Ports**: 5000-5999 (configurable)
- **Key Functions**:
  - Store file chunks on disk
  - Retrieve chunks on request
  - Network communication via TCP/IP
  - Health monitoring
- **Location**: `CloudSim/storage_virtual_node.py`

### Data Flow Examples

#### Upload Flow
```
User Browser → REST API (HTTP) → CloudRPC (gRPC) → Node Factory
                                                      ↓
User Browser ← REST API ← Network Manager ← Storage Nodes (TCP/IP)
```

#### Download Flow
```
User Browser → REST API (HTTP) → AuthService (gRPC) → File Metadata
                                                      ↓
User Browser ← REST API ← Network Manager ← Storage Nodes (TCP/IP)
```

#### Authentication Flow
```
User Browser → REST API (HTTP) → AuthService (gRPC) → Email Service (SMTP)
                                                      ↓
User Browser ← REST API ← AuthService ← OTP Verification
```

### Storage Architecture

**File Storage Structure:**
```
<base_directory>/
  node1/
    chunks/
      <file_id>_<chunk_id>.bin
      <file_id>_<chunk_id>.bin
      ...
  node2/
    chunks/
      <file_id>_<chunk_id>.bin
      ...
  node3/
    chunks/
      ...
```

**Metadata Storage:**
- User accounts: `AuthService/users.json`
- File records: Stored in AuthService (in-memory, can be persisted)
- Node configurations: `CloudSim/nodes_state.json`

## Troubleshooting

### Common Issues and Solutions

#### Issue: Services Won't Start

**Symptoms:**
- Error messages when running startup scripts
- Port already in use errors
- Import errors

**Solutions:**

1. **Check if ports are already in use:**
   ```bash
   # Windows
   netstat -ano | findstr :8000
   netstat -ano | findstr :50051
   netstat -ano | findstr :51234
   
   # Linux/Mac
   lsof -i :8000
   lsof -i :50051
   lsof -i :51234
   ```

2. **Kill processes using the ports:**
   ```bash
   # Windows (replace <PID> with process ID from netstat)
   taskkill /PID <PID> /F
   
   # Linux/Mac
   kill -9 <PID>
   ```

3. **Check Python dependencies:**
   ```bash
   pip list | grep -E "fastapi|grpcio|protobuf|bcrypt"
   ```

#### Issue: Nodes Won't Start

**Symptoms:**
- Node status shows "Stopped" after starting
- Error messages about ports or permissions

**Solutions:**

1. **Check port availability:**
   ```bash
   python cli.py list  # See which ports nodes are using
   ```

2. **Check storage directory permissions:**
   - Ensure the storage base directory exists
   - Verify write permissions on the directory
   - On Windows, run as Administrator if needed

3. **Check node state file:**
   ```bash
   # Verify nodes_state.json is valid JSON
   python -m json.tool CloudSim/nodes_state.json
   ```

4. **Recreate the node:**
   ```bash
   python cli.py delete <node_id>
   python cli.py create <node_id> --cpu 4 --memory 8 --storage 50 --bandwidth 1000
   ```

#### Issue: File Upload Fails

**Symptoms:**
- Upload progress stops
- Error message about nodes not running
- 400 Bad Request errors

**Solutions:**

1. **Verify nodes are running:**
   ```bash
   python cli.py list  # Check node status
   python cli.py start-all  # Start all nodes if needed
   ```

2. **Check network service:**
   ```bash
   python cli.py network status
   python cli.py network start  # Start if not running
   ```

3. **Check user quota:**
   - Log in to client portal
   - Check your storage usage
   - Contact administrator if quota is full

4. **Check file size:**
   - Ensure file doesn't exceed available quota
   - Large files may take time to upload

#### Issue: File Download Fails or is Incomplete

**Symptoms:**
- Download starts but stops
- Downloaded file is corrupted
- 404 Not Found errors

**Solutions:**

1. **Check if file exists:**
   - Verify file ID is correct
   - Check file list in client portal

2. **Verify nodes are running:**
   ```bash
   python cli.py list  # Ensure nodes containing chunks are running
   ```

3. **Check replication:**
   - If a node is down, the system should use replicated copies
   - Verify at least one copy of each chunk is available

4. **Retry download:**
   - Sometimes network issues cause temporary failures
   - Try downloading again

#### Issue: OTP Emails Not Received

**Symptoms:**
- Login says OTP was sent but email never arrives
- Registration completes but no OTP email

**Solutions:**

1. **Check email configuration:**
   ```bash
   # Verify AuthService/params.py exists and has valid credentials
   cat AuthService/params.py
   ```

2. **Verify Gmail App Password:**
   - Go to https://myaccount.google.com/apppasswords
   - Ensure 2-Step Verification is enabled
   - Create a new App Password if needed
   - Update `AuthService/params.py` with the new password

3. **Check spam folder:**
   - OTP emails might be filtered as spam
   - Check your email's spam/junk folder

4. **Test email sending:**
   ```python
   # Create a test script
   from AuthService.utils import send_otp
   send_otp("test@example.com", "123456")
   ```

#### Issue: Network Service Stops Unexpectedly

**Symptoms:**
- Network status shows "Stopped" after being started
- Nodes can't discover each other

**Solutions:**

1. **Check for port conflicts:**
   ```bash
   # Ensure port 9999 is available
   netstat -ano | findstr :9999  # Windows
   lsof -i :9999  # Linux/Mac
   ```

2. **Restart network service:**
   ```bash
   python cli.py network stop
   python cli.py network start
   ```

3. **Check logs:**
   - Look for error messages in the terminal where network service is running
   - Common issues: socket errors, permission problems

#### Issue: Metrics Not Showing

**Symptoms:**
- Metrics page shows zeros or "No data"
- Transfer history is empty

**Solutions:**

1. **Verify metrics collector is running:**
   - Metrics are collected automatically by the backend API
   - Ensure backend API is running

2. **Perform test operations:**
   - Upload a test file
   - Download a file
   - Metrics are recorded during transfers

3. **Check browser console:**
   - Open browser developer tools (F12)
   - Check for JavaScript errors
   - Verify API responses in Network tab

#### Issue: "Connection Refused" Errors

**Symptoms:**
- gRPC connection errors
- "Failed to connect to all addresses" messages

**Solutions:**

1. **Verify all services are running:**
   - CloudRPC server (port 50051)
   - Backend API (port 8000)
   - AuthService (port 51234)

2. **Check service startup order:**
   - Start CloudRPC first
   - Then start Backend API
   - Finally start AuthService

3. **Verify firewall settings:**
   - Ensure localhost connections are allowed
   - Check if antivirus is blocking connections

### Getting Help

If you encounter issues not covered here:

1. **Check Logs:**
   - Service logs appear in the terminal where services are running
   - Look for error messages and stack traces

2. **Verify Configuration:**
   - Review `CloudSim/config.yaml` for correct settings
   - Check `AuthService/params.py` for email configuration

3. **Test Components Individually:**
   - Test each service independently
   - Use CLI commands to verify node operations

4. **Create an Issue:**
   - Include error messages
   - Describe steps to reproduce
   - Provide system information (OS, Python version)

## FAQ

### General Questions

**Q: What is CloudSim used for?**
A: CloudSim is an educational tool for learning distributed storage systems. It simulates how cloud storage providers (like AWS S3, Google Cloud Storage) work, including file chunking, replication, and network-based operations.

**Q: Is CloudSim suitable for production use?**
A: No. CloudSim is designed for learning and research purposes. It's not intended for storing real production data or sensitive information.

**Q: Can I use CloudSim on multiple machines?**
A: Currently, CloudSim runs on a single machine with multiple virtual nodes. Future versions may support distributed deployment across multiple machines.

**Q: How much storage can CloudSim handle?**
A: Storage capacity depends on:
- Available disk space on your machine
- Number of nodes you create
- Storage capacity assigned to each node
- There's no hard limit, but practical limits depend on your hardware

### Technical Questions

**Q: Why do I need three separate services?**
A: CloudSim uses a microservices architecture:
- **CloudRPC**: Handles core system operations (node management)
- **Backend API**: Provides HTTP interface and file operations
- **AuthService**: Manages users and authentication
This separation allows for better scalability and modularity.

**Q: What happens if a node crashes?**
A: Thanks to replication, your data is safe. Each chunk is stored on multiple nodes (default: 3 copies). If one node fails, the system automatically uses copies from other nodes. You can restart the crashed node or delete it and create a replacement.

**Q: How does file chunking work?**
A: Files are automatically split into smaller pieces (chunks). Default chunk size is 1MB, but it can be configured. Each chunk is stored independently and can be retrieved in parallel, improving performance.

**Q: What is replication factor?**
A: Replication factor determines how many copies of each chunk are stored. Default is 3, meaning each chunk exists on 3 different nodes. This provides fault tolerance: you can lose up to 2 nodes and still access your data.

**Q: Can I change the replication factor?**
A: Yes, you can configure it in `CloudSim/config.yaml`:
```yaml
replication:
  default_factor: 3  # Change this value
  min_factor: 2
  max_factor: 6
```

**Q: How are files stored on disk?**
A: Files are stored as binary chunks in node directories:
```
<base_directory>/node1/chunks/<file_id>_<chunk_id>.bin
<base_directory>/node2/chunks/<file_id>_<chunk_id>.bin
```

**Q: What ports does CloudSim use?**
A:
- **8000**: REST API (Backend)
- **50051**: gRPC (CloudRPC)
- **51234**: gRPC (AuthService)
- **9999**: UDP (Network Discovery)
- **5000-5999**: TCP (Storage Nodes)

**Q: Can I change the ports?**
A: Yes, but it requires configuration changes:
- Node ports: Configured in `config.yaml` (`node_factory.start_port`)
- Service ports: Modify startup scripts or service code
- Network port: Configured in `config.yaml` (`network.discovery.port`)

### User Management Questions

**Q: How do I reset a user's password?**
A: Currently, password reset must be done manually by editing `AuthService/users.json`. Future versions may include a password reset feature.

**Q: Can I increase a user's quota?**
A: Yes, administrators can update user quotas through the Provider Portal:
1. Navigate to "Users"
2. Find the user
3. Click "Update Quota"
4. Enter new quota in GB

**Q: What happens when a user exceeds their quota?**
A: The system prevents new file uploads when a user exceeds their quota. Existing files remain accessible, but new uploads will fail with a quota exceeded error.

**Q: How do I delete a user account?**
A: Currently, user deletion must be done manually by editing `AuthService/users.json`. Be careful: this will also remove all file metadata for that user.

### Performance Questions

**Q: How fast are file uploads/downloads?**
A: Performance depends on:
- Network bandwidth configured for nodes
- Number of nodes (more nodes = better parallelization)
- File size (larger files take longer)
- System resources (CPU, memory, disk I/O)

**Q: Can I improve performance?**
A: Yes:
- Increase node bandwidth in configuration
- Create more nodes for better parallelization
- Use faster storage (SSD vs HDD)
- Increase chunk size for larger files (in config.yaml)

**Q: Why are small files slow to upload?**
A: Small files still go through the full network protocol, which has overhead. The system is optimized for larger files where chunking and parallelization provide benefits.

### Troubleshooting Questions

**Q: My nodes keep stopping. Why?**
A: Common causes:
- Port conflicts (another process using the port)
- Storage directory permissions
- Insufficient system resources
- Check logs for specific error messages

**Q: Files are missing after restart. Where did they go?**
A: Files are stored on disk and persist across restarts. If files are missing:
- Verify nodes are pointing to the correct storage directories
- Check that storage directories weren't deleted
- Ensure nodes are started (files aren't accessible if nodes are stopped)

**Q: Can I backup my data?**
A: Yes:
1. Backup node storage directories (where chunks are stored)
2. Backup `AuthService/users.json` (user accounts and file metadata)
3. Backup `CloudSim/nodes_state.json` (node configurations)
4. Backup `CloudSim/config.yaml` (system configuration)

**Q: How do I completely reset the system?**
A: To start fresh:
1. Stop all services
2. Delete node storage directories
3. Delete `CloudSim/nodes_state.json`
4. Delete `AuthService/users.json`
5. Restart services (they will create new empty files)

## Roadmap

Based on current implementation, potential future enhancements include:

1. **Distributed Node Support**: Extend the system to support nodes running on different machines across a network, enabling true distributed deployment scenarios
2. **Advanced Replication Strategies**: Implement erasure coding, geographic replication, and automatic rebalancing when nodes are added or removed
3. **Performance Optimizations**: Add connection pooling, parallel chunk transfers, compression, and caching layers to improve throughput and reduce latency

## Testing

### Running Tests

CloudSim includes a comprehensive test suite covering integration, storage operations, and threading scenarios.

**Basic Test Execution:**
```bash
cd CloudSim
python -m pytest tests/ -v
```

**With Coverage Report:**
```bash
python -m pytest tests/ --cov=. --cov-report=html
# Open htmlcov/index.html in your browser to view coverage report
```

**Run Specific Test Files:**
```bash
# Integration tests
python -m pytest tests/test_integration.py -v

# Storage operation tests
python -m pytest tests/test_storage_operations.py -v

# Threading tests
python -m pytest tests/test_threading_integration.py -v
```

**Run Specific Test Functions:**
```bash
python -m pytest tests/test_integration.py::test_multi_node_creation -v
```

### Test Coverage

The test suite covers:
- **Node Management**: Creation, starting, stopping, deletion
- **File Operations**: Upload, download, chunking, replication
- **Network Communication**: TCP/IP transfers, node discovery
- **Metrics Collection**: Data aggregation and reporting
- **Thread Safety**: Concurrent operations and race conditions
- **Error Handling**: Failure scenarios and recovery

### Writing New Tests

When adding new features, include corresponding tests:

```python
# Example test structure
def test_new_feature():
    # Setup
    node = create_test_node()
    
    # Execute
    result = node.new_feature()
    
    # Assert
    assert result is not None
    assert result.status == "success"
```

## Getting Started Checklist

Use this checklist to ensure your CloudSim installation is complete and ready to use:

### Pre-Installation
- [ ] Python 3.9+ installed and accessible from command line
- [ ] pip package manager available
- [ ] Sufficient disk space for storage (recommended: 10GB+)
- [ ] Network ports 5000-5999, 8000, 50051, 51234, 9999 available
- [ ] (Optional) Gmail account for OTP functionality

### Installation
- [ ] Repository cloned to local machine
- [ ] Python dependencies installed (`pip install -r requirements.txt`)
- [ ] Backend dependencies installed (FastAPI, gRPC, bcrypt, etc.)
- [ ] Protocol buffer files generated (cloudsim_pb2, cloudsecurity_pb2)
- [ ] Storage directory configured in `config.yaml`
- [ ] (Optional) Email credentials configured in `AuthService/params.py`

### Verification
- [ ] All three services can start without errors:
  - [ ] CloudRPC server starts on port 50051
  - [ ] Backend API starts on port 8000
  - [ ] AuthService starts on port 51234
- [ ] Can create a test node via CLI
- [ ] Can start the test node
- [ ] Can access web portal at `http://127.0.0.1:8000`
- [ ] Can register a test user account
- [ ] (If email configured) Can receive OTP email

### First Use
- [ ] Created at least 3 storage nodes
- [ ] Started all nodes
- [ ] Started network service
- [ ] Registered a user account
- [ ] Successfully uploaded a test file
- [ ] Successfully downloaded the test file
- [ ] Verified file appears in file list
- [ ] Checked metrics page shows data

### System Health
- [ ] All nodes show "Running" status
- [ ] Network service shows "Running"
- [ ] Storage utilization visible in metrics
- [ ] No error messages in service terminals
- [ ] Transfer history records file operations

**If all items are checked, your CloudSim installation is ready for use!**

## Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request


## Acknowledgments

- Built for educational and research purposes
- Demonstrates distributed systems concepts including node management, data replication, and network communication
- Inspired by real-world cloud storage architectures

---

**Note**: This is a simulation system designed for learning and research. It is not intended for production use or storing sensitive data.

