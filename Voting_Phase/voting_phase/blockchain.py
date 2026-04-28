import hashlib
import json
import time
import os
import base64
import logging
import secrets  # <--- [NEW] Required for Entropy-Seeded Shuffling
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import ec

# Configure internal logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BlockchainCore")

class Blockchain:
    def __init__(self):
        self.chain = []
        self.pending_votes = []
        self.authority_id = "ELECTION_COMMISSION_NODE_01"
        
        # Robust Path Handling
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.chain_file = os.path.join(base_dir, 'local_ledger.json')
        self.key_dir = base_dir # Assuming keys are in the same folder
        
        # Load Authority Private Key (For Signing)
        # This allows THIS node to create valid blocks.
        self.private_key = None
        try:
            with open(os.path.join(self.key_dir, "poa_private.pem"), "rb") as f:
                self.private_key = serialization.load_pem_private_key(f.read(), password=None)
        except FileNotFoundError:
            logger.warning("⚠ POA Private Key not found! This node cannot seal blocks (Read-Only Mode).")

        # Initialize Chain
        if os.path.exists(self.chain_file):
            self.load_chain()
        else:
            self.create_genesis_block()

    # --- [SECURITY CHECK] ---
    def voter_already_voted(self, target_alias):
        """
        Scans the entire Blockchain AND Mempool to ensure this alias 
        has not been used before.
        Returns: True (Already Voted), False (Safe to Vote)
        """
        # 1. Check Mempool (Pending Votes)
        for vote in self.pending_votes:
            if vote['voter_alias'] == target_alias:
                logger.warning(f"SECURITY ALERT: Duplicate vote detected in MEMPOOL for {target_alias[:10]}...")
                return True

        # 2. Check Committed Chain
        for block in self.chain:
            # Skip Genesis block as it has no votes
            if block['index'] == 1: continue 
            
            for vote in block.get('votes', []):
                if vote['voter_alias'] == target_alias:
                    logger.warning(f"SECURITY ALERT: Duplicate vote detected in BLOCK #{block['index']} for {target_alias[:10]}...")
                    return True
        
        return False

    def create_genesis_block(self):
        """Creates the very first block in the chain."""
        self.create_block(validator_id="SYSTEM_GENESIS", previous_hash='0')

    def create_block(self, validator_id, previous_hash=None):
        """
        Seals pending votes into a new block, SHUFFLES them to break 
        temporal correlation, and SIGNS the block.
        """
        # --- [NEW] FISHER-YATES SHUFFLE ---
        # 1. Create a local copy to avoid modifying the mempool during processing
        aggregated_votes = self.pending_votes[:]
        
        # 2. Apply Fisher-Yates Shuffle seeded by system entropy (secrets)
        # This breaks the FIFO order: Traffic Analysis cannot correlate 
        # the 1st packet received to the 1st vote in the block.
        for i in range(len(aggregated_votes) - 1, 0, -1):
            j = secrets.randbelow(i + 1) # Cryptographically secure random index
            aggregated_votes[i], aggregated_votes[j] = aggregated_votes[j], aggregated_votes[i]

        block = {
            'index': len(self.chain) + 1,
            'timestamp': time.time(),
            'votes': aggregated_votes, # Use the shuffled list
            'validator': validator_id,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
            'signature': "" # Placeholder
        }
        
        # 3. Calculate Hash of the Content
        block_hash = self.hash(block)
        
        # 4. Cryptographic Signing (Proof of Authority)
        if self.private_key:
            signature = self.private_key.sign(
                block_hash.encode(),
                ec.ECDSA(hashes.SHA256())
            )
            block['signature'] = base64.b64encode(signature).decode('utf-8')
        else:
            logger.error("Cannot sign block: Private Key missing!")
        
        # Reset Mempool
        self.pending_votes = []
        
        self.chain.append(block)
        self.save_chain()
        return block

    def add_vote(self, voter_alias, encrypted_vote, constituency):
        """Adds a vote to the Mempool."""
        
        # [SECURITY] Final Barrier check before adding to mempool
        if self.voter_already_voted(voter_alias):
            logger.error(f"BLOCKED: Attempt to add duplicate vote for {voter_alias[:10]}...")
            return -1 # Error Code for Duplicate
            
        vote = {
            'voter_alias': voter_alias,
            'vote_data': encrypted_vote,
            'constituency': constituency,
            'timestamp': time.time()
        }
        self.pending_votes.append(vote)
        return len(self.chain) + 1

    @staticmethod
    def hash(block):
        """
        Generates a SHA-256 hash of a block.
        Excludes the 'signature' field to avoid circular dependency during verification.
        """
        block_copy = block.copy()
        block_copy['signature'] = "" # Ensure we hash the data, not the signature itself
        block_string = json.dumps(block_copy, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def is_chain_valid(self):
        """
        Performs a full cryptographic audit using the Public Key.
        """
        if not self.chain: return False, "Chain is empty"

        # Load Public Key for Verification
        try:
            with open(os.path.join(self.key_dir, "poa_public.pem"), "rb") as f:
                public_key = serialization.load_pem_public_key(f.read())
        except FileNotFoundError:
            return False, "❌ POA Public Key missing. Cannot verify signatures."

        previous_block = self.chain[0]
        block_index = 1

        while block_index < len(self.chain):
            block = self.chain[block_index]
            
            # 1. Check Linkage
            if block['previous_hash'] != self.hash(previous_block):
                return False, f"Broken Chain Link at Block #{block['index']}"

            # 2. Check Signature (Skip Genesis)
            if block['index'] > 1:
                sig_b64 = block.get('signature')
                if not sig_b64:
                    return False, f"Unsigned Block found at #{block['index']}"

                # Recreate the hash that was signed
                content_hash = self.hash(block) 
                
                try:
                    public_key.verify(
                        base64.b64decode(sig_b64),
                        content_hash.encode(),
                        ec.ECDSA(hashes.SHA256())
                    )
                except Exception as e:
                    return False, f"⛔ FATAL: Invalid Signature at Block #{block['index']}! (Forged Block)"

            previous_block = block
            block_index += 1

        return True, "✅ Blockchain Integrity Verified. All signatures valid."

    def save_chain(self):
        try:
            with open(self.chain_file, 'w') as f:
                json.dump(self.chain, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save ledger: {e}")

    def load_chain(self):
        try:
            with open(self.chain_file, 'r') as f:
                content = f.read()
                if not content: raise ValueError("Empty File")
                self.chain = json.loads(content)
        except (FileNotFoundError, ValueError, json.JSONDecodeError):
            logger.warning("Ledger file missing or corrupted. Creating new Genesis Block.")
            self.chain = []
            self.create_genesis_block()