"""
LXC Simple Manager - Container Adapter Layer

Provides a unified interface for LXC container operations using a hybrid approach:
- Native Python bindings (python3-lxc) for READ operations (list, get, status)
- Shell commands for STATE-CHANGING operations (start, stop, create, delete)

This hybrid approach is necessary because the native LXC Python bindings
have compatibility issues with Python async event loops (like uvicorn uses).
The native bindings' start()/stop() methods fail silently when called from
within an async context.
"""

import datetime
import os
import re
import shutil
import subprocess
from typing import Dict, List, Optional

# Attempt to import native LXC bindings (used for read operations)
try:
    import lxc as native_lxc
    USE_NATIVE = True
except ImportError:
    native_lxc = None
    USE_NATIVE = False


class HybridLXCAdapter:
    """
    LXC adapter using a hybrid approach for maximum compatibility.
    
    Uses native Python bindings for fast read operations (listing, status checks)
    and shell commands for reliable state changes (start, stop, create, delete).
    
    This works around a known issue where native LXC bindings fail when
    called from within async event loops (FastAPI/uvicorn).
    """
    
    def __init__(self):
        if USE_NATIVE:
            print("INFO: Using hybrid LXC adapter (native reads, shell commands for state changes)")
        else:
            print("INFO: Using shell-only LXC adapter (python3-lxc not available)")
    
    def _run_command(self, cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """
        Execute a shell command.
        
        Args:
            cmd: Command and arguments
            check: If True, raise exception on non-zero exit
            
        Returns:
            CompletedProcess instance
            
        Raises:
            RuntimeError: If command fails and check=True
        """
        result = subprocess.run(cmd, capture_output=True, text=True)
        if check and result.returncode != 0:
            error_msg = result.stderr.strip() or f"Command failed: {' '.join(cmd)}"
            raise RuntimeError(error_msg)
        return result
    
    # =========================================================================
    # Read Operations (use native bindings if available for speed)
    # =========================================================================
    
    def list_containers(self) -> List[Dict]:
        """
        List all defined containers with their state and IP addresses.
        
        Uses native bindings if available, falls back to shell parsing.
        """
        if USE_NATIVE:
            return self._list_containers_native()
        return self._list_containers_shell()
    
    def _list_containers_native(self) -> List[Dict]:
        """List containers using native Python bindings."""
        results = []
        try:
            names = native_lxc.list_containers()
            for name in names:
                container = native_lxc.Container(name)
                results.append({
                    "name": name,
                    "state": container.state,
                    "ipv4": container.get_ips(family="inet") or [],
                    "ipv6": container.get_ips(family="inet6") or [],
                })
        except Exception as e:
            print(f"ERROR: Failed to list containers: {e}")
        return results
    
    def _list_containers_shell(self) -> List[Dict]:
        """List containers using lxc-ls command."""
        if not shutil.which("lxc-ls"):
            return []
        
        try:
            result = self._run_command(
                ["lxc-ls", "--fancy", "--fancy-format", "NAME,STATE,IPV4,IPV6"],
                check=False
            )
            if result.returncode != 0:
                return []
            
            containers = []
            lines = result.stdout.strip().split('\n')
            
            # Skip header line
            for line in lines[1:]:
                if not line.strip():
                    continue
                
                parts = re.split(r'\s{2,}', line.strip())
                
                name = parts[0] if len(parts) > 0 else "Unknown"
                state = parts[1] if len(parts) > 1 else "UNKNOWN"
                ipv4_str = parts[2] if len(parts) > 2 else "-"
                ipv6_str = parts[3] if len(parts) > 3 else "-"
                
                ipv4 = [] if ipv4_str == "-" else [x.strip() for x in ipv4_str.split(',')]
                ipv6 = [] if ipv6_str == "-" else [x.strip() for x in ipv6_str.split(',')]
                
                containers.append({
                    "name": name,
                    "state": state,
                    "ipv4": ipv4,
                    "ipv6": ipv6,
                })
            
            return containers
        except Exception as e:
            print(f"ERROR: Shell parse error: {e}")
            return []
    
    def get_container(self, name: str) -> Optional[Dict]:
        """
        Get information about a specific container.
        
        Args:
            name: Container name
            
        Returns:
            Container info dict or None if not found
        """
        if USE_NATIVE:
            try:
                container = native_lxc.Container(name)
                if not container.defined:
                    return None
                return {
                    "name": container.name,
                    "state": container.state,
                    "ipv4": container.get_ips(family="inet") or [],
                    "ipv6": container.get_ips(family="inet6") or [],
                }
            except Exception:
                return None
        else:
            for container in self.list_containers():
                if container["name"] == name:
                    return container
            return None
    
    # =========================================================================
    # State-Changing Operations (use shell commands for async compatibility)
    # =========================================================================
    
    def start_container(self, name: str) -> None:
        """
        Start a stopped container.
        
        Uses lxc-start command for compatibility with async event loops.
        
        Args:
            name: Container name
            
        Raises:
            ValueError: If container doesn't exist
            RuntimeError: If start fails
        """
        # Check if container exists and current state
        container = self.get_container(name)
        if not container:
            raise ValueError(f"Container '{name}' does not exist")
        
        if container["state"] == "RUNNING":
            return  # Already running
        
        self._run_command(["lxc-start", "-n", name])
    
    def stop_container(self, name: str) -> None:
        """
        Stop a running container.
        
        Uses lxc-stop command for compatibility with async event loops.
        
        Args:
            name: Container name
            
        Raises:
            ValueError: If container doesn't exist
            RuntimeError: If stop fails
        """
        container = self.get_container(name)
        if not container:
            raise ValueError(f"Container '{name}' does not exist")
        
        if container["state"] != "RUNNING":
            return  # Already stopped
        
        self._run_command(["lxc-stop", "-n", name])
    
    def create_container(self, name: str, distro: str, release: str, arch: str = "amd64") -> None:
        """
        Create a new container using the download template.
        
        Args:
            name: Container name
            distro: Distribution name (e.g., "debian")
            release: Distribution release (e.g., "bookworm")
            arch: Target architecture (default: "amd64")
            
        Raises:
            ValueError: If container already exists
            RuntimeError: If creation fails
        """
        if self.get_container(name):
            raise ValueError(f"Container '{name}' already exists")
        
        self._run_command([
            "lxc-create", "-n", name, "-t", "download",
            "--", "--dist", distro, "--release", release, "--arch", arch
        ])
        
        # Start the container after creation
        self.start_container(name)
    
    def delete_container(self, name: str) -> None:
        """
        Delete a container, stopping it first if running.
        
        Args:
            name: Container name
            
        Raises:
            RuntimeError: If deletion fails
        """
        container = self.get_container(name)
        if not container:
            raise ValueError(f"Container '{name}' does not exist")
        
        # Stop if running
        if container["state"] == "RUNNING":
            try:
                self.stop_container(name)
            except Exception:
                pass  # Continue with destroy anyway
        
        self._run_command(["lxc-destroy", "-n", name])
    
    def backup_container(self, name: str, backup_dir: str) -> str:
        """
        Create a compressed tarball backup of a container.
        
        The container is stopped during backup to ensure consistency,
        then restarted if it was running.
        
        Args:
            name: Container name
            backup_dir: Directory to store the backup
            
        Returns:
            Filename of the created backup
            
        Raises:
            ValueError: If container doesn't exist
            RuntimeError: If backup fails
        """
        container = self.get_container(name)
        if not container:
            raise ValueError(f"Container '{name}' not found")
        
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
        filename = f"{name}_{timestamp}.tar.gz"
        filepath = os.path.join(backup_dir, filename)
        
        was_running = container["state"] == "RUNNING"
        
        try:
            if was_running:
                print(f"INFO: Stopping '{name}' for backup...")
                self.stop_container(name)
            
            print(f"INFO: Creating backup at {filepath}...")
            subprocess.run(
                ["tar", "-czf", filepath, "-C", "/var/lib/lxc", name],
                check=True
            )
            return filename
            
        finally:
            if was_running:
                print(f"INFO: Restarting '{name}'...")
                self.start_container(name)


    def get_container_logs(self, name: str, lines: int = 100) -> str:
        """
        Get recent logs from a container.
        
        Reads from the container's console log file if available.
        
        Args:
            name: Container name
            lines: Number of lines to return (default 100)
            
        Returns:
            Log content as string
            
        Raises:
            ValueError: If container doesn't exist
        """
        container = self.get_container(name)
        if not container:
            raise ValueError(f"Container '{name}' does not exist")
        
        # Try to read console log file
        console_log = f"/var/lib/lxc/{name}/console.log"
        
        if os.path.exists(console_log):
            try:
                result = subprocess.run(
                    ["tail", "-n", str(lines), console_log],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    return result.stdout
            except Exception:
                pass
        
        # If no console log, try to get recent output via lxc-attach
        # This only works for running containers
        if container["state"] == "RUNNING":
            try:
                result = subprocess.run(
                    ["lxc-attach", "-n", name, "--", "dmesg", "-T"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0 and result.stdout:
                    # Return last N lines
                    log_lines = result.stdout.strip().split('\n')
                    return '\n'.join(log_lines[-lines:])
            except subprocess.TimeoutExpired:
                pass
            except Exception:
                pass
        
        return f"No logs available for container '{name}'"
    
    def get_container_stats(self, name: str) -> Dict:
        """
        Get resource usage statistics for a container.
        
        Args:
            name: Container name
            
        Returns:
            Dict with cpu, memory, and disk stats
            
        Raises:
            ValueError: If container doesn't exist
        """
        container = self.get_container(name)
        if not container:
            raise ValueError(f"Container '{name}' does not exist")
        
        stats = {
            "name": name,
            "state": container["state"],
            "cpu_usage": None,
            "memory_usage": None,
            "memory_limit": None,
            "disk_usage": None,
        }
        
        if container["state"] != "RUNNING":
            return stats
        
        # Get cgroup path for the container
        cgroup_base = f"/sys/fs/cgroup/lxc.payload.{name}"
        
        # Try cgroup v2 paths first, then v1
        try:
            # CPU usage (cgroup v2)
            cpu_stat_file = f"{cgroup_base}/cpu.stat"
            if os.path.exists(cpu_stat_file):
                with open(cpu_stat_file, 'r') as f:
                    for line in f:
                        if line.startswith('usage_usec'):
                            stats["cpu_usage"] = int(line.split()[1])
                            break
            
            # Memory usage (cgroup v2)
            mem_current_file = f"{cgroup_base}/memory.current"
            mem_max_file = f"{cgroup_base}/memory.max"
            
            if os.path.exists(mem_current_file):
                with open(mem_current_file, 'r') as f:
                    stats["memory_usage"] = int(f.read().strip())
            
            if os.path.exists(mem_max_file):
                with open(mem_max_file, 'r') as f:
                    val = f.read().strip()
                    if val != "max":
                        stats["memory_limit"] = int(val)
        except Exception as e:
            print(f"DEBUG: Error reading cgroup stats: {e}")
        
        # Disk usage - check rootfs size
        rootfs_path = f"/var/lib/lxc/{name}/rootfs"
        if os.path.exists(rootfs_path):
            try:
                result = subprocess.run(
                    ["du", "-sb", rootfs_path],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    stats["disk_usage"] = int(result.stdout.split()[0])
            except Exception:
                pass
        
        return stats


# Global adapter instance - imported by other modules
lxc = HybridLXCAdapter()