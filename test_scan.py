import sys
import time
from instruments import load_instruments
from scanner import run_full_scan

def test():
    print("🚀 Starting Test Scan...", flush=True)
    inst = load_instruments()
    
    # Run a full scan
    print(f"DEBUG: Input instruments size: {len(inst)}", flush=True)
    
    results = run_full_scan(inst, progress_callback=None)
    
    print(f"\n✅ Test Scan Complete!", flush=True)
    print(f"Total Results Found: {len(results)}", flush=True)

if __name__ == "__main__":
    test()
