import subprocess
import shutil
import os
from typing import List, Dict
from backend.database import get_all_rules, add_rule_to_db, delete_rule_from_db, PortMapping

# --- CONFIGURATION ---
DHCP_FILE = "/etc/lxc/dhcp.conf"
CHAIN_NAME = "LXC_MANAGER"

class NetworkManager:
    
    def __init__(self):
        # We don't initialize automatically on import to prevent side effects.
        # initialize_network() must be called explicitly by main.py
        pass

    def _run_cmd(self, cmd: List[str]):
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            print(f"IPTables Error: {e.stderr}")
            raise RuntimeError(f"IPTables failed: {e.stderr}")

    def initialize_network(self):
        """
        Called on App Startup.
        1. Ensures LXC_MANAGER chain exists.
        2. Ensures Jump rule exists.
        3. Flushes old rules and reapplies from DB.
        """
        print("DEBUG: Initializing Network Layer...")
        
        # 1. Create Chain (if missing)
        subprocess.run(["iptables", "-t", "nat", "-N", CHAIN_NAME], capture_output=True)

        # 2. Add Jump Rule (if missing)
        check = subprocess.run(
            ["iptables", "-t", "nat", "-C", "PREROUTING", "-j", CHAIN_NAME], 
            capture_output=True
        )
        if check.returncode != 0:
            print(f"DEBUG: Installing Jump Rule for {CHAIN_NAME}")
            self._run_cmd(["iptables", "-t", "nat", "-I", "PREROUTING", "1", "-j", CHAIN_NAME])

        # 3. SYNC
        self.sync_rules()

    def sync_rules(self):
        """
        The Master Sync: DB -> Kernel
        1. FLUSH the custom chain (wipe RAM).
        2. Iterate DB.
        3. ADD rules to RAM.
        """
        print("DEBUG: Syncing Rules from DB to Kernel...")
        
        # 1. Wipe the slate clean (Only our chain!)
        self._run_cmd(["iptables", "-t", "nat", "-F", CHAIN_NAME])
        
        # 2. Get Rules from DB
        rules = get_all_rules()
        
        # 3. Apply them
        for rule in rules:
            cmd = [
                "iptables", "-t", "nat", "-A", CHAIN_NAME,
                "-p", rule.protocol,
                "--dport", str(rule.external_port),
                "-j", "DNAT",
                "--to-destination", f"{rule.internal_ip}:{rule.internal_port}"
            ]
            # Add interface flag only if specified and not 'all'
            if rule.interface and rule.interface != "all":
                cmd.insert(5, "-i")
                cmd.insert(6, rule.interface)
                
            try:
                self._run_cmd(cmd)
            except Exception as e:
                print(f"ERROR applying rule {rule.external_port}: {e}")

    # --- CRUD ACTIONS ---
    # These just update the DB and trigger a Sync

    def get_port_forwards(self) -> List[PortMapping]:
        return get_all_rules()

    def add_forwarding_rule(self, rule: PortMapping):
        add_rule_to_db(rule)
        self.sync_rules() # Apply immediately

    def remove_forwarding_rule(self, external_port: int):
        delete_rule_from_db(external_port)
        self.sync_rules() # Apply immediately

    # --- DHCP (Remains File-Based as Dnsmasq needs files) ---
    def get_static_ips(self) -> Dict[str, str]:
        leases = {}
        if not os.path.exists(DHCP_FILE): return {}
        with open(DHCP_FILE, 'r') as f:
            for line in f:
                if line.strip().startswith("dhcp-host="):
                    parts = line.replace("dhcp-host=", "").split(",")
                    if len(parts) >= 2:
                        leases[parts[0].strip()] = parts[1].strip()
        return leases

    def set_static_ip(self, name: str, ip: str):
        leases = self.get_static_ips()
        leases[name] = ip
        with open(DHCP_FILE, 'w') as f:
            for n, i in leases.items():
                f.write(f"dhcp-host={n},{i}\n")
        subprocess.run(["systemctl", "reload", "lxc-net"], check=False)

net_manager = NetworkManager()