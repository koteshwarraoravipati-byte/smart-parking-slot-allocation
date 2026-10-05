"""Educational ONLY: process-local primitives, never database correctness."""
import threading, time
from concurrent.futures import ThreadPoolExecutor

def run_demo(workers: int = 8, capacity: int = 3):
    semaphore = threading.Semaphore(capacity)
    mutex = threading.Lock()
    active = peak = counter = 0
    events = []
    def work(i):
        nonlocal active, peak, counter
        with semaphore:
            with mutex:
                active += 1
                peak = max(peak, active)
                events.append({"worker": i, "event": "enter", "active": active})
            time.sleep(0.02)
            with mutex:
                counter += 1
                active -= 1
                events.append({"worker": i, "event": "exit", "active": active})
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(work, range(workers)))
    return {"workers": workers, "capacity": capacity, "peak_active": peak, "mutex_counter": counter, "events": events,
            "scope": "Process-local teaching demo. PostgreSQL transactions and constraints protect real bookings."}
