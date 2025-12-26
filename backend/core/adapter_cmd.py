import subprocess
import shutil
import re
from typing import List, Dict, Optional

class LXCAdapter:
    @staticmethod
    def _run_command(cmd: List[str]) -> str:
        try:
            # Force full path to avoid alias issues
            if cmd[0] == "lxc-ls" and shutil.which("/usr/bin/lxc-ls"):
                cmd[0] = "/usr/bin/lxc-ls"
            
            # Run command
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"Command failed: {result.stderr}")
                raise RuntimeError(f"LXC Command Failed: {result.stderr}")
            
            return result.stdout.strip()
        except FileNotFoundError:
            raise RuntimeError(f"Command not found: {cmd[0]}")

    def list_containers(self) -> List[Dict]:
        """
        Parses 'lxc-ls --fancy' output because this version of LXC lacks JSON support.
        """
        if not shutil.which("lxc-ls") and not shutil.which("/usr/bin/lxc-ls"):
            return []
            
        try:
            # We explicitly ask for specific columns to make parsing easier
            # Columns: NAME, STATE, IPV4, IPV6
            cmd = ["lxc-ls", "--fancy", "--fancy-format", "NAME,STATE,IPV4,IPV6"]
            output = self._run_command(cmd)
            
            containers = []
            lines = output.split('\n')
            
            # unexpected output check
            if len(lines) < 2: 
                return []

            # Skip header (NAME STATE IPV4 IPV6)
            for line in lines[1:]:
                if not line.strip(): continue
                
                # Split by multiple spaces
                parts = re.split(r'\s{2,}', line.strip())
                
                # Safety check on columns
                name = parts[0] if len(parts) > 0 else "Unknown"
                state = parts[1] if len(parts) > 1 else "UNKNOWN"
                ipv4_str = parts[2] if len(parts) > 2 else "-"
                ipv6_str = parts[3] if len(parts) > 3 else "-"
                
                # Clean up IPs (handle "-" or empty)
                ipv4 = [] if ipv4_str == "-" else [x.strip() for x in ipv4_str.split(',')]
                ipv6 = [] if ipv6_str == "-" else [x.strip() for x in ipv6_str.split(',')]

                containers.append({
                    "name": name,
                    "state": state,
                    "ipv4": ipv4,
                    "ipv6": ipv6
                })
            
            return containers

        except Exception as e:
            print(f"Error parsing lxc-ls output: {e}")
            return []

    def get_container(self, name: str) -> Optional[Dict]:
        all_c = self.list_containers()
        for c in all_c:
            if c["name"] == name:
                return c
        return None

    def start_container(self, name: str):
        return self._run_command(["lxc-start", "-n", name])

    def stop_container(self, name: str):
        return self._run_command(["lxc-stop", "-n", name])

    def create_container(self, name: str, distro: str, release: str, arch: str = "amd64"):
        # This can take a long time
        cmd = ["lxc-create", "-n", name, "-t", "download", "--", "--dist", distro, "--release", release, "--arch", arch]
        return self._run_command(cmd)

    def delete_container(self, name: str):
        try:
            self.stop_container(name)
        except:
            pass
        return self._run_command(["lxc-destroy-", "-n", name])

lxc = LXCAdapter()