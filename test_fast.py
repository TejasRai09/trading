import sys
import time
from instruments import load_instruments
from scanner import run_full_scan

def test():
    print("🚀 Starting Fast 10-Stock Test Scan...", flush=True)
    inst = load_instruments().head(10)
    
    print(f"DEBUG: Input instruments size: {len(inst)}", flush=True)
    
    # We expect this to be fast
    results = run_full_scan(inst, progress_callback=None)
    
    print(f"\n✅ Fast Test Complete!", flush=True)
    print(f"Total Results Found: {len(results)}", flush=True)

if __name__ == "__main__":
    test()
