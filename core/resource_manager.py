import psutil
import time
import os
import sys
from typing import Dict, Any

# User-defined caps
RESOURCE_CAP = 0.35  # 35%

class HiveResourceManager:
    def __init__(self):
        self.start_net_io = psutil.net_io_counters()
        self.start_time = time.time()

    def get_cpu_usage(self) -> float:
        return psutil.cpu_percent(interval=None) / 100.0

    def get_ram_usage(self) -> float:
        return psutil.virtual_memory().percent / 100.0

    def get_gpu_usage(self) -> float:
        """Attempt to get GPU usage via nvidia-smi if available."""
        try:
            import subprocess
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=1
            )
            if res.returncode == 0:
                return float(res.stdout.strip()) / 100.0
        except:
            pass
        return 0.0

    def get_network_bandwidth_usage(self) -> float:
        """
        Calculates recent network throughput. 
        Note: Scaling this to '35% of internet traffic' requires an assumed max bandwidth.
        We'll assume a 100Mbps (12.5MB/s) baseline if not calibrated.
        """
        current_io = psutil.net_io_counters()
        elapsed = time.time() - self.start_time
        if elapsed < 0.1: return 0.0
        
        bytes_sent = current_io.bytes_sent - self.start_net_io.bytes_sent
        bytes_recv = current_io.bytes_recv - self.start_net_io.bytes_recv
        total_bytes = bytes_sent + bytes_recv
        
        # bps = (total_bytes * 8) / elapsed
        # For simplicity, we'll return the raw byte rate. 
        # Integration into a % requires a known pipe size.
        return total_bytes / elapsed

    def check_hive_health(self) -> Dict[str, Any]:
        """Returns True if the system is within the 35% 'Hive' safety zone."""
        cpu = self.get_cpu_usage()
        ram = self.get_ram_usage()
        gpu = self.get_gpu_usage()
        
        is_safe = (cpu < RESOURCE_CAP) and (ram < RESOURCE_CAP) and (gpu < RESOURCE_CAP)
        
        return {
            "safe": is_safe,
            "cpu": cpu,
            "ram": ram,
            "gpu": gpu,
            "cap": RESOURCE_CAP
        }

resource_manager = HiveResourceManager()
