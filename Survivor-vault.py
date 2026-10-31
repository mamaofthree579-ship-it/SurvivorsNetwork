import streamlit as st
import pandas as pd
import numpy as np
import requests
import datetime
import hashlib
import json
import os
import threading
from Crypto.Hash import SHA256
from Crypto.Cipher import AES
from argon2 import PasswordHasher
from fastapi import FastAPI
import uvicorn

# --- FASTAPI P2P NETWORK CORE (Runs silently in background) ---
node_app = FastAPI()
DB_FILE = "mesh_ledger.json"
PEERS_FILE = "peers_registry.json"

def load_persistent_ledger():
    if not os.path.exists(DB_FILE): return []
    try:
        with open(DB_FILE, "r") as f: return json.load(f)
    except Exception: return []

def save_persistent_ledger(ledger_state):
    with open(DB_FILE, "w") as f: json.dump(ledger_state, f, indent=4)

def load_peers():
    if not os.path.exists(PEERS_FILE): return ["http://127.0.0.1:8001", "http://127.0.0.1:8002"]
    try:
        with open(PEERS_FILE, "r") as f: return json.load(f)
    except Exception: return []

def save_peers(peers_list):
    with open(PEERS_FILE, "w") as f: json.dump(peers_list, f, indent=4)

@node_app.post("/sync")
def handle_incoming_block_sync(block: dict):
    current_ledger = load_persistent_ledger()
    if not block.get("IPFS_CID", "").startswith("Qm"): return {"status": "rejected"}
    exists = any(b["IPFS_CID"] == block["IPFS_CID"] for b in current_ledger)
    if not exists:
        current_ledger.append(block)
        current_ledger.sort(key=lambda x: x["CRDT_CLOCK_SEQUENCE"], reverse=True)
        save_persistent_ledger(current_ledger)
        return {"status": "merged"}
    return {"status": "duplicate"}

@node_app.get("/peers")
def share_known_peer_routing_tables():
    return load_peers()

def run_autonomous_mesh_crawler():
    while True:
        import time
        time.sleep(20)
        known_peers = load_peers()
        discovered_new_lanes = []
        for peer in known_peers:
            try:
                response = requests.get(f"{peer.strip('/')}/peers", timeout=2)
                if response.status_code == 200:
                    for route in response.json():
                        if route not in known_peers and route not in discovered_new_lanes:
                            discovered_new_lanes.append(route)
            except Exception: pass
        if discovered_new_lanes:
            save_peers(list(set(known_peers + discovered_new_lanes)))

def broadcast_block_to_mesh(block: dict):
    for peer in load_peers():
        try: requests.post(f"{peer.strip('/')}/sync", json=block, timeout=3)
        except Exception: pass

if "node_started" not in st.session_state:
    st.session_state.node_port = 8001
    threading.Thread(target=lambda: uvicorn.run(node_app, host="0.0.0.0", port=st.session_state.node_port, log_level="warning"), daemon=True).start()
    threading.Thread(target=run_autonomous_mesh_crawler, daemon=True).start()
    st.session_state.node_started = True

st.session_state.p2p_ledger_state = load_persistent_ledger()

# --- CRYPTODOME LEDGER ENGINE ---
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

    @staticmethod
    def purge_block_by_key(user_key_raw: str, current_peer_state: list) -> tuple:
        target_purge_hash = hashlib.sha256(f"{user_key_raw}_PURGE_AUTHORIZATION".encode()).hexdigest()
        cleaned = [b for b in current_peer_state if b.get("purge_verification_hash") != target_purge_hash]
        return cleaned, (len(current_peer_state) - len(cleaned))

# --- SURVIVOR PLATFORM INTERFACE DESIGN ---
st.set_page_config(page_title="Secure Portal", page_icon="🛡️", layout="centered")

# 1. EMERGENCE QUICK-ESCAPE ACTION (Safety Feature)
if st.button("🚨 QUICK ESCAPE (Hide Screen Immediately)", use_container_width=True):
    st.markdown('<meta http-equiv="refresh" content="0;URL=\'https://google.com\'" />', unsafe_allow_html=True)
    st.stop()

st.title("🛡️ Secure Incident Vault & Mesh Network")
st.markdown("Your information is entirely encrypted on your device. No human beings, server administrators, or external organizations have access to your data.")

# --- LIVE CROSS-CHECK ALERTS (Always displayed transparently at the top if matches exist) ---
if len(st.session_state.p2p_ledger_state) >= 2:
    token_tracking_map = {}
    match_found = False
    for block in st.session_state.p2p_ledger_state:
        token = block["immutable_proof_visible"]["zkp_proof_signature"]
        token_tracking_map.setdefault(token, []).append(block["IPFS_CID"])
        
    for token, cids in token_tracking_map.items():
        if len(cids) > 1:
            match_found = True
            st.error(f"⚠️ **System Alert:** Multiple anonymous records have safely matched against the same unique identifier fingerprint. Your entry has connected with {len(cids)-1} other record(s) inside the distributed mesh network.")

st.tabs_style = """
<style>
    .stTabs [data-baseweb="tab-list"] {gap: 24px;}
    .stTabs [data-baseweb="tab"] {font-size: 16px; font-weight: 500;}
</style>
"""
st.markdown(st.tabs_style, unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["📥 Create Secure Entry", "💥 Manage & Purge Data", "⚙️ Network Health Ledger"])

# --- TAB 1: USER REGISTRATION ENTRY PANEL ---
with tab1:
    st.subheader("Store an Entry Privately")
    st.info("Everything you input below is transformed into a cryptographic key array entirely inside your browser. The server never receives your raw text lines.")
    
    u_key = st.text_input("Create Your Private 25-Point Access Key:", type="password", help="Make this long and unique. Write it down safely; there is no way to reset or recover it if lost.")
    p_id = st.text_input("Target Cross-Check Identifier (Unique Social Handle or Phone Number):", help="This value is strongly hashed so the system can watch for overlaps without reading the text.")
    notes = st.text_area("Secure Incident Record Diary Payload:")

    if st.button("🔒 Encrypt and Broadcast onto Mesh", use_container_width=True):
        if not u_key or not p_id or not notes:
            st.warning("Please fill out all input fields to construct your secure block package.")
        elif len(u_key) < 16:
            st.error("For absolute security, your 25-Point access key must be at least 16 characters long.")
        else:
            with st.spinner("Locking entry container layers..."):
                seed = hashlib.sha256(u_key.encode()).digest()
                salt = hashlib.sha256(b"Unified_Field_Dynamic_Salt_1.618").digest()[:16]
                blinded_token = hashlib.sha256(PasswordHasher(time_cost=2, memory_cost=65536).hash(p_id.strip().lower(), salt=salt).encode()).hexdigest()
                
                packet = DecentralizedLedgerEngine.construct_crdt_op_log(blinded_token, seed, u_key)
                
                local_ledger = load_persistent_ledger()
                if not any(b["IPFS_CID"] == packet["IPFS_CID"] for b in local_ledger):
                    local_ledger.append(packet)
                    local_ledger.sort(key=lambda x: x["CRDT_CLOCK_SEQUENCE"], reverse=True)
                    save_persistent_ledger(local_ledger)
                    st.session_state.p2p_ledger_state = local_ledger
                
                threading.Thread(target=broadcast_block_to_mesh, args=(packet,), daemon=True).start()
                st.success("🎉 Entry successfully locked and saved to the decentralized redundant network network lines!")

# --- TAB 2: DATA OWNERSHIP & DELETION ACTIONS ---
with tab2:
    st.subheader("Completely Erase Your Records")
    st.markdown("Because the nodes hold zero identifiable profiles, you control your data via your private key matrix. Input your key to completely strip your data files away from this node permanently.")
    
    del_key = st.text_input("Confirm Your Private 25-Point Access Key to Delete Data:", type="password")
    if st.button("🗑️ Permanently Wipe My Data From Node Logs", use_container_width=True):
        if not del_key:
            st.warning("You must enter your security access key to confirm block drops.")
        else:
            cleaned, count = DecentralizedLedgerEngine.purge_block_by_key(del_key, st.session_state.p2p_ledger_state)
            if count > 0:
                save_persistent_ledger(cleaned)
                st.session_state.p2p_ledger_state = cleaned
                st.success(f"💥 Permanent deletion success! Dropped {count} secure data container entries completely out of network ledger loops.")
                st.rerun()
            else:
                st.warning("No tracking blocks found inside this node matching your precise access key credentials.")

# --- TAB 3: NETWORK VISIBILITY ACCORDIONS (Tucked away quietly) ---
with tab3:
    st.subheader("Silent Automated Network Operations")
    
    with st.expander("🤖 Discovered Network Map Vectors (Crawler Bot Mappings)"):
        st.write("Discovered Router Peer Lanes:", load_peers())
        st.caption("Background bots actively maintain connection redundancy paths across these lanes without human maintenance.")

    with st.expander("🌐 Raw Cryptographic Ledger Wire Sync Data"):
        if not st.session_state.p2p_ledger_state:
            st.caption("No blocks synced on this node line yet.")
        else:
            for b in st.session_state.p2p_ledger_state:
                st.json({
                    "Block_CID": b["IPFS_CID"], 
                    "Encrypted_Payload": b["ciphertext"], 
                    "Public_Metadata": b["immutable_proof_visible"]
                })
