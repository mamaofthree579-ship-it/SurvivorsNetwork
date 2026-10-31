import os
import json
import datetime
import hashlib
import requests
import numpy as np
from Crypto.Hash import SHA256
from Crypto.Cipher import AES
from argon2 import PasswordHasher
from fastapi import FastAPI, BackgroundTasks

app = FastAPI()
DB_FILE = "mesh_ledger.json"
PEERS_FILE = "peers_registry.json"
CHAT_FILE = "mesh_mailbox.json"

def load_db(file_path):
    if not os.path.exists(file_path): return []
    try:
        with open(file_path, "r") as f: return json.load(f)
    except Exception: return []

def save_db(data, file_path):
    with open(file_path, "w") as f: json.dump(data, f, indent=4)

class CryptographicInvestigatorBot:
    @staticmethod
    def analyze_hidden_patterns(ledger):
        if len(ledger) < 2: return []
        detected_clusters = []
        GEO_THRESHOLD = 0.08 
        TIME_THRESHOLD = 172800 

        for i, block_a in enumerate(ledger):
            token_a = block_a["immutable_proof_visible"]["zkp_proof_signature"]
            coords_a = block_a["immutable_proof_visible"].get("geo_vector_anchor", [0.0, 0.0])
            time_a = block_a["CRDT_CLOCK_SEQUENCE"]
            cid_a = block_a["IPFS_CID"]

            for j, block_b in enumerate(ledger):
                if i >= j: continue
                token_b = block_b["immutable_proof_visible"]["zkp_proof_signature"]
                coords_b = block_b["immutable_proof_visible"].get("geo_vector_anchor", [0.0, 0.0])
                time_b = block_b["CRDT_CLOCK_SEQUENCE"]
                cid_b = block_b["IPFS_CID"]

                direct_match = (token_a == token_b)
                spatial_delta = np.sqrt((coords_a[0] - coords_b[0])**2 + (coords_a[1] - coords_b[1])**2)
                geo_proximity = (spatial_delta <= GEO_THRESHOLD) and (coords_a != [0.0, 0.0])
                temporal_delta = abs(time_a - time_b)
                time_proximity = (temporal_delta <= TIME_THRESHOLD)

                if (direct_match and geo_proximity) or (geo_proximity and time_proximity):
                    cluster_type = "CRITICAL: Shared Target & Proximity" if direct_match else "GEOSPATIAL: Area Pattern Divergence"
                    detected_clusters.append({
                        "Type": cluster_type,
                        "Block_A_CID": cid_a,
                        "Block_B_CID": cid_b,
                        "Spatial_Variance": round(float(spatial_delta), 4),
                        "Temporal_Variance_Hours": round(float(temporal_delta / 3600), 1)
                    })
        return detected_clusters

class DecentralizedLedgerEngine:
    @staticmethod
    def construct_crdt_op_log(proof_pi: str, coordinates: list, secret_key: bytes, user_key_raw: str) -> dict:
        purge_hash = hashlib.sha256(f"{user_key_raw}_PURGE_AUTHORIZATION".encode()).hexdigest()
        block_metadata = {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "zkp_proof_signature": proof_pi,
            "geo_vector_anchor": coordinates,
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
    coords = data.get("coordinates", [0.0, 0.0])
    
    seed = hashlib.sha256(u_key.encode()).digest()
    salt = hashlib.sha256(b"Unified_Field_Dynamic_Salt_1.618").digest()[:16]
    blinded_token = hashlib.sha256(PasswordHasher(time_cost=2, memory_cost=65536).hash(p_id.strip().lower(), salt=salt).encode()).hexdigest()
    
    packet = DecentralizedLedgerEngine.construct_crdt_op_log(blinded_token, coords, seed, u_key)
    
    ledger = load_db(DB_FILE)
    ledger.append(packet)
    ledger.sort(key=lambda x: x["CRDT_CLOCK_SEQUENCE"], reverse=True)
    save_db(ledger, DB_FILE)
    
    return {"status": "success", "packet": packet}

@app.post("/mailbox/send")
def send_mailbox_message(data: dict):
    """Drops an encrypted message block into the anonymous blind match mailbox."""
    match_token = data["match_token"]
    encrypted_msg = data["encrypted_message"]
    sender_nonce = data["nonce"]
    sender_tag = data["tag"]
    
    mailboxes = load_db(CHAT_FILE)
    if not isinstance(mailboxes, dict): mailboxes = {}
    
    if match_token not in mailboxes:
        mailboxes[match_token] = []
        
    mailboxes[match_token].append({
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "nonce": sender_nonce,
        "tag": sender_tag,
        "ciphertext": encrypted_msg
    })
    save_db(mailboxes, CHAT_FILE)
    return {"status": "sent"}

@app.get("/mailbox/{match_token}")
def get_mailbox_messages(match_token: str):
    mailboxes = load_db(CHAT_FILE)
    if not isinstance(mailboxes, dict): return []
    return mailboxes.get(match_token, [])

@app.post("/purge")
def purge_records(data: dict):
    purge_key = data["purge_key"]
    target_hash = hashlib.sha256(f"{purge_key}_PURGE_AUTHORIZATION".encode()).hexdigest()
    ledger = load_db(DB_FILE)
    cleaned = [b for b in ledger if b.get("purge_verification_hash") != target_hash]
    removed = len(ledger) - len(cleaned)
    save_db(cleaned, DB_FILE)
    return {"status": "success", "removed_count": removed}

@app.get("/investigator")
def run_investigator_bot():
    ledger = load_db(DB_FILE)
    return CryptographicInvestigatorBot.analyze_hidden_patterns(ledger)

@app.get("/ledger")
def get_ledger():
    return load_db(DB_FILE)

@app.get("/peers")
def get_peers():
    return load_db(PEERS_FILE)
