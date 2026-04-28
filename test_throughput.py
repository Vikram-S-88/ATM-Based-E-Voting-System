import time
import secrets
import hashlib

def simulate_poa_consensus(num_votes):
    # 1. Simulate mempool aggregation (encrypted votes arriving from ATMs)
    aggregated_votes = [f"ENCRYPTED_VOTE_PAYLOAD_DATA_{i}" for i in range(num_votes)]
    
    print(f"Sealing block with {num_votes} votes...")
    
    # Start timer for consensus processing
    start_time = time.perf_counter()
    
    # 2. Apply Fisher-Yates Shuffle (Breaking FIFO timing attacks)
    for i in range(len(aggregated_votes) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        aggregated_votes[i], aggregated_votes[j] = aggregated_votes[j], aggregated_votes[i]
        
    # 3. Block Sealing (Simulating Validator Signature/Hashing)
    block_string = "".join(aggregated_votes).encode()
    block_hash = hashlib.sha256(block_string).hexdigest()
    
    end_time = time.perf_counter()
    
    time_taken = end_time - start_time
    tps = num_votes / time_taken if time_taken > 0 else 0
    
    return time_taken, tps

if __name__ == "__main__":
    # Test with a block of 10,000 simultaneous votes
    votes_in_block = 10000
    time_taken, tps = simulate_poa_consensus(votes_in_block)
    
    print("\n--- Consensus Throughput Results ---")
    print(f"Block Size:    {votes_in_block} votes")
    print(f"Time to Seal:  {time_taken:.4f} seconds")
    print(f"Throughput:    {tps:,.2f} TPS (Transactions Per Second)")