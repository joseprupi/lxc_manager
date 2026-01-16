"""
LXC Simple Manager - Network Configuration Manager

Manages iptables NAT rules and DHCP static IP assignments for LXC containers.

Architecture:
    - Uses a dedicated iptables chain (LXC_MANAGER) to avoid conflicts
    - Rules are persisted in the database and synced to the kernel
    - DHCP leases are managed via dnsmasq configuration file
"""

import os
import subprocess
from typing import Dict, List

from backend.database import (
    PortMapping,
    add_rule_to_db,
    delete_rule_from_db,
    get_all_rules,
)


# =============================================================================
# Configuration
# =============================================================================

DHCP_CONFIG_FILE = "/etc/lxc/dhcp.conf"
IPTABLES_CHAIN_NAME = "LXC_MANAGER"


class NetworkManager:
    """
    Manages network configuration for LXC containers.
    
    Handles:
        - IPTables DNAT rules for port forwarding
        - DHCP static IP assignments via dnsmasq
    """
    
    def __init__(self):
        """
        Initialize the network manager.
        
        Note: Network initialization is deferred to initialize_network()
        to prevent side effects during import.
        """
        pass
    
    def _run_iptables(self, cmd: List[str]) -> None:
        """
        Execute an iptables command.
        
        Args:
            cmd: Command arguments (without 'iptables' prefix)
            
        Raises:
            RuntimeError: If the command fails
        """
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            print(f"ERROR: iptables command failed: {error_msg}")
            raise RuntimeError(f"iptables failed: {error_msg}")
    
    # =========================================================================
    # Initialization
    # =========================================================================
    
    def initialize_network(self) -> None:
        """
        Initialize the network layer on application startup.
        
        Steps:
            1. Create the LXC_MANAGER chain if it doesn't exist
            2. Add jump rule from PREROUTING to our chain
            3. Sync rules from database to kernel
        """
        print("INFO: Initializing network layer...")
        
        # Create chain (ignore error if already exists)
        subprocess.run(
            ["iptables", "-t", "nat", "-N", IPTABLES_CHAIN_NAME],
            capture_output=True
        )
        
        # Check if jump rule exists
        check_result = subprocess.run(
            ["iptables", "-t", "nat", "-C", "PREROUTING", "-j", IPTABLES_CHAIN_NAME],
            capture_output=True
        )
        
        # Add jump rule if missing
        if check_result.returncode != 0:
            print(f"INFO: Installing jump rule for {IPTABLES_CHAIN_NAME}")
            self._run_iptables([
                "iptables", "-t", "nat", "-I", "PREROUTING", "1",
                "-j", IPTABLES_CHAIN_NAME
            ])
        
        # Sync rules from database
        self.sync_rules()
    
    def sync_rules(self) -> None:
        """
        Synchronize rules from database to kernel.
        
        This is the master sync operation that:
            1. Flushes all rules from our chain
            2. Reads rules from database
            3. Applies each rule to iptables
        """
        print("INFO: Syncing rules from database to kernel...")
        
        # Flush our chain
        self._run_iptables(["iptables", "-t", "nat", "-F", IPTABLES_CHAIN_NAME])
        
        # Get rules from database
        rules = get_all_rules()
        
        # Apply each rule
        for rule in rules:
            cmd = [
                "iptables", "-t", "nat", "-A", IPTABLES_CHAIN_NAME,
                "-p", rule.protocol,
                "--dport", str(rule.external_port),
                "-j", "DNAT",
                "--to-destination", f"{rule.internal_ip}:{rule.internal_port}"
            ]
            
            # Add interface filter if specified
            if rule.interface and rule.interface.lower() != "all":
                cmd.insert(5, "-i")
                cmd.insert(6, rule.interface)
            
            try:
                self._run_iptables(cmd)
            except Exception as e:
                print(f"ERROR: Failed to apply rule for port {rule.external_port}: {e}")
    
    # =========================================================================
    # Port Forwarding (DNAT) Operations
    # =========================================================================
    
    def get_port_forwards(self) -> List[PortMapping]:
        """
        Get all port forwarding rules.
        
        Returns:
            List of PortMapping objects from the database
        """
        return get_all_rules()
    
    def add_forwarding_rule(self, rule: PortMapping) -> None:
        """
        Add a new port forwarding rule.
        
        The rule is persisted to database and immediately applied to iptables.
        
        Args:
            rule: Port mapping configuration
            
        Raises:
            ValueError: If the external port is already in use
        """
        add_rule_to_db(rule)
        self.sync_rules()
    
    def remove_forwarding_rule(self, external_port: int) -> None:
        """
        Remove a port forwarding rule.
        
        The rule is deleted from database and iptables is updated.
        
        Args:
            external_port: The external port to remove
        """
        delete_rule_from_db(external_port)
        self.sync_rules()
    
    def apply_iptables(self) -> None:
        """
        Force re-application of all iptables rules.
        
        This is called when the user clicks "Apply to System" in the UI.
        """
        self.sync_rules()
    
    # =========================================================================
    # DHCP / Static IP Operations
    # =========================================================================
    
    def get_static_ips(self) -> Dict[str, str]:
        """
        Get all static IP assignments.
        
        Reads the dnsmasq DHCP configuration file.
        
        Returns:
            Dict mapping container names to IP addresses
        """
        leases = {}
        
        if not os.path.exists(DHCP_CONFIG_FILE):
            return leases
        
        with open(DHCP_CONFIG_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith("dhcp-host="):
                    parts = line.replace("dhcp-host=", "").split(",")
                    if len(parts) >= 2:
                        name = parts[0].strip()
                        ip = parts[1].strip()
                        leases[name] = ip
        
        return leases
    
    def set_static_ip(self, name: str, ip: str) -> None:
        """
        Set or update a static IP assignment for a container.
        
        Updates the dnsmasq configuration file and reloads lxc-net.
        
        Args:
            name: Container name (used as hostname identifier)
            ip: IP address to assign
        """
        leases = self.get_static_ips()
        leases[name] = ip
        
        # Write updated configuration
        with open(DHCP_CONFIG_FILE, 'w') as f:
            for container_name, container_ip in leases.items():
                f.write(f"dhcp-host={container_name},{container_ip}\n")
        
        # Reload dnsmasq to pick up changes
        subprocess.run(["systemctl", "reload", "lxc-net"], check=False)
    
    def remove_static_ip(self, name: str) -> bool:
        """
        Remove a static IP assignment.
        
        Args:
            name: Container name to remove
            
        Returns:
            True if the entry was removed, False if not found
        """
        leases = self.get_static_ips()
        
        if name not in leases:
            return False
        
        del leases[name]
        
        with open(DHCP_CONFIG_FILE, 'w') as f:
            for container_name, container_ip in leases.items():
                f.write(f"dhcp-host={container_name},{container_ip}\n")
        
        subprocess.run(["systemctl", "reload", "lxc-net"], check=False)
        return True


# Global instance
net_manager = NetworkManager()
