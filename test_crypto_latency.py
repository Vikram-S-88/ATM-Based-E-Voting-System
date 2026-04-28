import hashlib
import time
import statistics

# Simulated Inputs
cif_number = "CIF987654321"
bank_salt = "BANK_PRIVATE_SALT_XYZ"
govt_salt = "EC_GOVT_SALT_ABC"

def generate_double_blind_hash(cif, b_salt, g_salt):
    # Phase 1: Bank Side
    bank_input = f"{cif}{b_salt}".encode()
    bank_hash = hashlib.sha256(bank_input).hexdigest()
    
    # Phase 2: EC Side
    ec_input = f"{bank_hash}{g_salt}".encode()
    final_hash = hashlib.sha256(ec_input).hexdigest()
    
    return final_hash

def run_benchmark(iterations=100000):
    times_ns = []
    
    print(f"Starting benchmark for {iterations} iterations...")
    for _ in range(iterations):
        start_time = time.perf_counter_ns()
        generate_double_blind_hash(cif_number, bank_salt, govt_salt)
        end_time = time.perf_counter_ns()
        
        times_ns.append(end_time - start_time)
    
    # Convert nanoseconds to microseconds
    avg_time_us = statistics.mean(times_ns) / 1000.0
    median_time_us = statistics.median(times_ns) / 1000.0
    max_time_us = max(times_ns) / 1000.0
    min_time_us = min(times_ns) / 1000.0
    
    print("\n--- Benchmark Results ---")
    print(f"Average Time: {avg_time_us:.2f} µs")
    print(f"Median Time:  {median_time_us:.2f} µs")
    print(f"Min Time:     {min_time_us:.2f} µs")
    print(f"Max Time:     {max_time_us:.2f} µs")

if __name__ == "__main__":
    run_benchmark(100000)