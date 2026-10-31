import os
import json
import datetime
import hashlib
import requests
from Crypto.Hash import SHA256
from Crypto.Cipher import AES
from argon2 import PasswordHasher
from fastapi import FastAPI, BackgroundTasks

app = FastAPI()
DB_FILE = "mesh_ledger.json"
PEERS_FILE = "peers_registry.json"

def load_db(file_path):
    if not os.path.exists(file_path): return []
    try:
        with open(file_path, "r") as f: return json.load(f)
    except Exception: return []

def save_db(data, file_path):
    with open(file_path, "w") as f: json.dump(data, f, indent=4)

class DecentralizedLedgerEngine:
    @staticmethod
    def construct_crdt_op_log(proof_pi: str, secret_key: bytes, user_key_raw: str) -> dict:
        purge_hash = hashlib.sha256(f"{user_key_raw}_PURGE_AUTHORIZATION".encode()).hexdigest()
        block_metadata = {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "zkp_proof_signature": proof_pi,
            "system_status": "VERIFIED_SECURE_NODE"
        }
        serialized = json.dumps(block_metadata, sort_keys=True).encode('utf-8')
        cipher = AES.new(secret_key, AES.MODE_GCM)
        ciphertext, tag = cipher.encrypt_and_digest(serialized)
        merkle_cid = "Qm" + SHA256.new(ciphertext + cipher.nonce + tag).hexdigest()[:44]
        return {
            "IPFS_CID": merkle_cid,
            "CRDT_CLOCK_SEQUENCE": datetime.datetime.utcnow().timestamp(),
            "nonce": cipher.nonce.hex(),
            "tag": tag.hex(),
            "ciphertext": ciphertext.hex(),
            "immutable_proof_visible": block_metadata,
            "purge_verification_hash": purge_hash
        }

def gossip_worker(packet: dict):
    peers = load_db(PEERS_FILE)
    if not peers: peers = ["http://127.0.0.1:8002"] # Autocomplete fallback
    for peer in peers:
        try: requests.post(f"{peer.strip('/')}/sync", json=packet, timeout=2)
        except Exception: pass

@app.post("/sync")
def sync_incoming_block(block: dict):
    ledger = load_db(DB_FILE)
    if not block.get("IPFS_CID", "").startswith("Qm"): return {"status": "invalid"}
    if any(b["IPFS_CID"] == block["IPFS_CID"] for b in ledger): return {"status": "duplicate"}
    ledger.append(block)
    ledger.sort(key=lambda x: x["CRDT_CLOCK_SEQUENCE"], reverse=True)
    save_db(ledger, DB_FILE)
    return {"status": "merged"}

@app.post("/create-entry")
def create_entry(data: dict, background_tasks: BackgroundTasks):
    u_key = data["user_key"]
    p_id = data["perp_id"]
    notes = data["notes"]
    
    seed = hashlib.sha256(u_key.encode()).digest()
    salt = hashlib.sha256(b"Unified_Field_Dynamic_Salt_1.618").digest()[:16]
    blinded_token = hashlib.sha256(PasswordHasher(time_cost=2, memory_cost=65536).hash(p_id.strip().lower(), salt=salt).encode()).hexdigest()
    
    packet = DecentralizedLedgerEngine.construct_crdt_op_log(blinded_token, seed, u_key)
    
    ledger = load_db(DB_FILE)
    ledger.append(packet)
    ledger.sort(key=lambda x: x["CRDT_CLOCK_SEQUENCE"], reverse=True)
    save_db(ledger, DB_FILE)
    
    background_tasks.add_task(gossip_worker, packet)
    return {"status": "success", "packet": packet}

@app.post("/purge")
def purge_records(data: dict):
    purge_key = data["purge_key"]
    target_hash = hashlib.sha256(f"{purge_key}_PURGE_AUTHORIZATION".encode()).hexdigest()
    ledger = load_db(DB_FILE)
    cleaned = [b for b in ledger if b.get("purge_verification_hash") != target_hash]
    removed = len(ledger) - len(cleaned)
    save_db(cleaned, DB_FILE)
    return {"status": "success", "removed_count": removed}

@app.get("/ledger")
def get_ledger():
    return load_db(DB_FILE)

@app.get("/peers")
def get_peers():
    return load_db(PEERS_FILE)
