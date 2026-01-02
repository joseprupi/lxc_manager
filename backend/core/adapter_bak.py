"""
LXC Simple Manager - Container Adapter Layer

Provides a unified interface for LXC container operations, supporting both
native Python bindings (python3-lxc) and shell command fallback.

The adapter automatically selects the best available implementation:
1. Native Python LXC bindings (preferred, faster)
2. Shell command execution (fallback, more compatible)
"""

import datetime
import os
import shutil
import subprocess
import traceback
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

# Attempt to import native LXC bindings
try:
    import lxc as native_lxc
    USE_NATIVE = True
except ImportError:
    native_lxc = None
    USE_NATIVE = False


class LXCAdapterInterface(ABC):
    """Abstract base class defining the LXC adapter interface."""
    
    @abstractmethod
    def list_containers(self) -> List[Dict]:
        """List all containers with their current state and IPs."""
        pass
    
    @abstractmethod
    def get_container(self, name: str) -> Optional[Dict]:
        """Get information about a specific container."""
        pass
    
    @abstractmethod
    def start_container(self, name: str) -> None:
        """Start a stopped container."""
        pass
    
    @abstractmethod
    def stop_container(self, name: str) -> None:
        """Stop a running container."""
        pass
    
    @abstractmethod
    def create_container(self, name: str, distro: str, release: str, arch: str) -> None:
        """Create a new container from a distribution template."""
        pass
    
    @abstractmethod
    def delete_container(self, name: str) -> None:
        """Delete a container (stops it first if running)."""
        pass
    
    @abstractmethod
    def backup_container(self, name: str, backup_dir: str) -> str:
        """Create a tarball backup of a container."""
        pass


class PythonLXCAdapter(LXCAdapterInterface):
    """
    LXC adapter using native Python bindings (python3-lxc).
    
    This is the preferred implementation as it provides direct access
    to liblxc without spawning subprocesses.
    """
    
    def __init__(self):
        if not USE_NATIVE:
            raise ImportError("Python LXC bindings (python3-lxc) not available")
        print("INFO: Using native Python LXC bindings")
    
    def list_containers(self) -> List[Dict]:
        """
        List all defined containers with their state and IP addresses.
        
        Returns:
            List of container info dictionaries
        """
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
            traceback.print_exc()
        return results
    
    def get_container(self, name: str) -> Optional[Dict]:
        """
        Get information about a specific container.
        
        Args:
            name: Container name
            
        Returns:
            Container info dict or None if not found
        """
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
    
    def start_container(self, name: str) -> None:
        """
        Start a container.
        
        Args:
            name: Container name
            
        Raises:
            RuntimeError: If the container fails to start
        """
        container = native_lxc.Container(name)
        if not container.start():
            raise RuntimeError(f"Failed to start container '{name}'")
    
    def stop_container(self, name: str) -> None:
        """
        Stop a container.
        
        Args:
            name: Container name
            
        Raises:
            RuntimeError: If the container fails to stop
        """
        container = native_lxc.Container(name)
        if not container.stop():
            raise RuntimeError(f"Failed to stop container '{name}'")
    
    def create_container(self, name: str, distro: str, release: str, arch: str = "amd64") -> None:
        """
        Create a new container using the download template.
        
        Args:
            name: Container name
            distro: Distribution name (e.g., "debian")
            release: Distribution release (e.g., "bookworm")
            arch: Target architecture (default: "amd64")
            
        Raises:
            ValueError: If a container with the name already exists
            RuntimeError: If container creation fails
        """
        container = native_lxc.Container(name)
        if container.defined:
            raise ValueError(f"Container '{name}' already exists")
        
        template_args = {"dist": distro, "release": release, "arch": arch}
        if not container.create("download", 0, template_args):
            raise RuntimeError(f"Failed to create container '{name}'")
        
        container.start()
    
    def delete_container(self, name: str) -> None:
        """
        Delete a container, stopping it first if running.
        
        Args:
            name: Container name
            
        Raises:
            RuntimeError: If the container cannot be destroyed
        """
        container = native_lxc.Container(name)
        if container.running:
            container.stop()
        if not container.destroy():
            raise RuntimeError(f"Failed to destroy container '{name}'")
    
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
            ValueError: If the container doesn't exist
            RuntimeError: If backup fails
        """
        os.makedirs(backup_dir, exist_ok=True)
        
        container = native_lxc.Container(name)
        if not container.defined:
            raise ValueError(f"Container '{name}' not found")
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
        filename = f"{name}_{timestamp}.tar.gz"
        filepath = os.path.join(backup_dir, filename)
        
        was_running = container.running
        
        try:
            if was_running:
                print(f"INFO: Stopping '{name}' for backup...")
                container.stop()
                if not container.wait("STOPPED", 30):
                    raise RuntimeError("Container did not stop within timeout")
            
            print(f"INFO: Creating backup at {filepath}...")
            subprocess.run(
                ["tar", "-czf", filepath, "-C", "/var/lib/lxc", name],
                check=True
            )
            return filename
            
        finally:
            if was_running:
                print(f"INFO: Restarting '{name}'...")
                container.start()


class ShellLXCAdapter(LXCAdapterInterface):
    """
    LXC adapter using shell commands as fallback.
    
    This implementation spawns lxc-* commands via subprocess when
    native Python bindings are unavailable.
    """
    
    def __init__(self):
        print("INFO: Using shell command fallback for LXC operations")
    
    def _run_command(self, cmd: List[str]) -> str:
        """
        Execute a shell command and return its output.
        
        Args:
            cmd: Command and arguments as list
            
        Returns:
            Command stdout stripped of whitespace
            
        Raises:
            RuntimeError: If the command fails
        """
        # Use absolute path for lxc-ls if available
        if cmd[0] == "lxc-ls" and shutil.which("/usr/bin/lxc-ls"):
            cmd[0] = "/usr/bin/lxc-ls"
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or f"Command failed: {' '.join(cmd)}")
        return result.stdout.strip()
    
    def list_containers(self) -> List[Dict]:
        """List all containers using lxc-ls."""
        if not shutil.which("lxc-ls"):
            return []
        
        try:
            cmd = ["lxc-ls", "--fancy", "--fancy-format", "NAME,STATE,IPV4,IPV6"]
            output = self._run_command(cmd)
            
            containers = []
            lines = output.split('\n')
            
            if len(lines) < 2:
                return []
            
            # Skip header line
            for line in lines[1:]:
                if not line.strip():
                    continue
                
                # Split on multiple spaces
                import re
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
        """Get container info by name."""
        for container in self.list_containers():
            if container["name"] == name:
                return container
        return None
    
    def start_container(self, name: str) -> None:
        """Start a container using lxc-start."""
        self._run_command(["lxc-start", "-n", name])
    
    def stop_container(self, name: str) -> None:
        """Stop a container using lxc-stop."""
        self._run_command(["lxc-stop", "-n", name])
    
    def create_container(self, name: str, distro: str, release: str, arch: str = "amd64") -> None:
        """Create a container using lxc-create with download template."""
        self._run_command([
            "lxc-create", "-n", name, "-t", "download",
            "--", "--dist", distro, "--release", release, "--arch", arch
        ])
    
    def delete_container(self, name: str) -> None:
        """Delete a container using lxc-destroy."""
        try:
            self.stop_container(name)
        except Exception:
            pass  # Container may already be stopped
        self._run_command(["lxc-destroy", "-n", name])
    
    def backup_container(self, name: str, backup_dir: str) -> str:
        """Create a backup tarball using tar."""
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
        filename = f"{name}_{timestamp}.tar.gz"
        filepath = os.path.join(backup_dir, filename)
        
        was_running = False
        container = self.get_container(name)
        if container and container.get("state") == "RUNNING":
            was_running = True
            self.stop_container(name)
        
        try:
            subprocess.run(
                ["tar", "-czf", filepath, "-C", "/var/lib/lxc", name],
                check=True
            )
            return filename
        finally:
            if was_running:
                self.start_container(name)


# =============================================================================
# Adapter Instance (Auto-selected)
# =============================================================================

def _create_adapter() -> LXCAdapterInterface:
    """
    Factory function to create the appropriate LXC adapter.
    
    Attempts to use native Python bindings first, falls back to shell commands.
    """
    if USE_NATIVE:
        try:
            return PythonLXCAdapter()
        except Exception as e:
            print(f"WARNING: Native adapter failed ({e}), using shell fallback")
    else:
        print("WARNING: python3-lxc not found, using shell commands")
    
    return ShellLXCAdapter()


# Global adapter instance - imported by other modules
lxc = _create_adapter()
