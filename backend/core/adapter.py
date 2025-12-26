import shutil
import sys
import subprocess
import re
from typing import List, Dict, Optional

# --- 1. THE PYTHON BINDING IMPLEMENTATION ---
class PythonLXCAdapter:
    def __init__(self):
        import lxc # specific import here to catch errors early if missing
        print("DEBUG: Using Native Python LXC Bindings")

    def list_containers(self) -> List[Dict]:
        import lxc
        results = []
        try:
            names = lxc.list_containers()
            for name in names:
                c = lxc.Container(name)
                
                # Get IPs (checks all interfaces)
                ipv4 = c.get_ips(family="inet")
                ipv6 = c.get_ips(family="inet6")
                
                results.append({
                    "name": name,
                    "state": c.state, # e.g. "RUNNING" or "STOPPED"
                    "ipv4": ipv4 if ipv4 else [],
                    "ipv6": ipv6 if ipv6 else []
                })
            return results
        except Exception as e:
            print(f"Error listing containers via bindings: {e}")
            return []

    def get_container(self, name: str) -> Optional[Dict]:
        import lxc
        try:
            c = lxc.Container(name)
            if not c.defined:
                return None
            return {
                "name": c.name,
                "state": c.state,
                "ipv4": c.get_ips(family="inet"),
                "ipv6": c.get_ips(family="inet6")
            }
        except:
            return None

    def start_container(self, name: str):
        import lxc
        c = lxc.Container(name)
        if not c.start():
            raise RuntimeError(f"Failed to start container {name}")

    def stop_container(self, name: str):
        import lxc
        c = lxc.Container(name)
        if not c.stop():
            raise RuntimeError(f"Failed to stop container {name}")

    def create_container(self, name: str, distro: str, release: str, arch: str = "amd64"):
        import lxc
        c = lxc.Container(name)
        if c.defined:
            raise ValueError("Container already exists")
        
        # Note: 'download' template uses these keys
        # This blocks execution! In prod, this must be async.
        if not c.create("download", 0, {"dist": distro, "release": release, "arch": arch}):
            raise RuntimeError(f"Failed to create container {name}")

    # def delete_container(self, name: str):
    #     import lxc
    #     c = lxc.Container(name)
    #     if c.running:
    #         c.stop()
    #     if not c.destroy():
    #         raise RuntimeError(f"Failed to destroy container {name}")

    # ... inside PythonLXCAdapter ...

    def backup_container(self, name: str, backup_dir: str) -> str:
        import lxc
        
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir, exist_ok=True)

        c = lxc.Container(name)
        if not c.defined: raise ValueError("Container not found")

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
        filename = f"{name}_{timestamp}.tar.gz"
        filepath = os.path.join(backup_dir, filename)

        was_running = c.running
        if was_running:
            print(f"DEBUG: Stopping {name} for backup...")
            c.stop()
            if not c.wait(lxc.STOPPED, 30):
                raise RuntimeError("Could not stop container")

        try:
            print(f"DEBUG: Compressing to {filepath}...")
            subprocess.run(
                ["tar", "-czf", filepath, "-C", "/var/lib/lxc", name], 
                check=True
            )
        finally:
            if was_running:
                c.start()

        return filename


# --- 2. THE SHELL FALLBACK IMPLEMENTATION (Backup) ---
class ShellLXCAdapter:
    def __init__(self):
        print("DEBUG: Using Shell/Subprocess Fallback")

    def _run_command(self, cmd: List[str]) -> str:
        if cmd[0] == "lxc-ls" and shutil.which("/usr/bin/lxc-ls"):
            cmd[0] = "/usr/bin/lxc-ls"
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr)
        return result.stdout.strip()

    def list_containers(self) -> List[Dict]:
        if not shutil.which("lxc-ls"): return []
        try:
            cmd = ["lxc-ls", "--fancy", "--fancy-format", "NAME,STATE,IPV4,IPV6"]
            output = self._run_command(cmd)
            containers = []
            lines = output.split('\n')
            if len(lines) < 2: return []
            for line in lines[1:]:
                if not line.strip(): continue
                parts = re.split(r'\s{2,}', line.strip())
                name = parts[0] if len(parts) > 0 else "Unknown"
                state = parts[1] if len(parts) > 1 else "UNKNOWN"
                ipv4_str = parts[2] if len(parts) > 2 else "-"
                ipv4 = [] if ipv4_str == "-" else [x.strip() for x in ipv4_str.split(',')]
                containers.append({"name": name, "state": state, "ipv4": ipv4, "ipv6": []})
            return containers
        except Exception as e:
            print(f"Shell parse error: {e}")
            return []

    # (Other shell methods omitted for brevity, they match previous version)
    # ... mapping other methods to _run_command ...
    def start_container(self, name): self._run_command(["lxc-start", "-n", name])
    def stop_container(self, name): self._run_command(["lxc-stop", "-n", name])
    def delete_container(self, name): 
        try: self.stop_container(name) 
        except: pass
        self._run_command(["lxc-destroyyy", "-n", name])
    def create_container(self, name, distro, release, arch):
        self._run_command(["lxc-create", "-n", name, "-t", "download", "--", "--dist", distro, "--release", release, "--arch", arch])
    def get_container(self, name):
        for c in self.list_containers():
            if c["name"] == name: return c
        return None


# --- 3. FACTORY: CHOOSE THE BEST ONE ---
try:
    # Try to initialize the Python bindings
    lxc = PythonLXCAdapter()
except ImportError:
    # Fallback if python3-lxc is missing
    print("WARNING: 'python3-lxc' not found. Falling back to shell commands.")
    lxc = ShellLXCAdapter()
except Exception as e:
    print(f"WARNING: Native adapter failed ({e}). Falling back to shell.")
    lxc = ShellLXCAdapter()