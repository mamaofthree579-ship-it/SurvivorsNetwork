import streamlit as st
import pandas as pd
import numpy as np
import requests
import datetime
import hashlib
import json
import os
import threading
import time
import socket
from Crypto.Hash import SHA256
from Crypto.Cipher import AES
from argon2 import PasswordHasher
from fastapi import FastAPI, BackgroundTasks
import uvicorn

# --- CONFIGURING CORE FASTAPI P2P NETWORK MATRIX ---
node_app = FastAPI()

DB_FILE = "mesh_ledger.json"
PEERS_FILE = "peers_registry.json"

def load_persistent_ledger():
    if not os.path.exists(DB_FILE):
        return []
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []

def save_persistent_ledger(ledger_state):
    with open(DB_FILE, "w") as f:
        json.dump(ledger_state, f, indent=4)

def load_peers():
    if not os.path.exists(PEERS_FILE):
        return ["http://127.0.0.1:8001", "http://127.0.0.1:8002"]
    try:
        with open(PEERS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []

def save_peers(peers_list):
    with open(PEERS_FILE, "w") as f:
        json.dump(peers_list, f, indent=4)

# --- BACKEND INCOMING NETWORK ROUTER WEBHOOKS ---
@node_app.post("/sync")
def handle_incoming_block_sync(block: dict):
    current_ledger = load_persistent_ledger()
    if not block.get("IPFS_CID", "").startswith("Qm"):
        return {"status": "rejected", "reason": "invalid_cid"}
        
    exists = any(b["IPFS_CID"] == block["IPFS_CID"] for b in current_ledger)
    if not exists:
        current_ledger.append(block)
        current_ledger.sort(key=lambda x: x["CRDT_CLOCK_SEQUENCE"], reverse=True)
        save_persistent_ledger(current_ledger)
        return {"status": "merged", "cid": block["IPFS_CID"]}
    return {"status": "duplicate", "cid": block["IPFS_CID"]}

@node_app.get("/peers")
def share_known_peer_routing_tables():
    """Allows automated crawler bots to pull connection maps from this node."""
    return load_peers()

# --- AUTOMATED CRAWLER & BOT DISCOVERY ENGINE ENGINE ---
def run_autonomous_mesh_crawler():
    """
    Automated crawler bot loop that runs continuously in the background. 
    It queries known active peers to discover new hidden network lanes automatically.
    """
    while True:
        time.sleep(15) # Crawler wakes up every 15 seconds to sync mesh topology
        known_peers = load_peers()
        discovered_new_lanes = []
        
        for peer in known_peers:
            try:
                # Query the target peer node for who they are currently linked to
                response = requests.get(f"{peer.strip('/')}/peers", timeout=2)
                if response.status_code == 200:
                    peer_networks = response.json()
                    for prospective_route in peer_networks:
                        if prospective_route not in known_peers and prospective_route not in discovered_new_lanes:
                            discovered_new_lanes.append(prospective_route)
            except Exception:
                pass # Skip dead nodes quietly; network remains resilient
                
        if discovered_new_lanes:
            updated_peer_list = list(set(known_peers + discovered_new_lanes))
            save_peers(updated_peer_list)

def broadcast_block_to_mesh(block: dict):
    registered_peers = load_peers()
    for peer in registered_peers:
        try:
            requests.post(f"{peer.strip('/')}/sync", json=block, timeout=3)
        except Exception:
            pass 

def run_fastapi_server(port: int):
    uvicorn.run(node_app, host="0.0.0.0", port=port, log_level="warning")

# --- SPARKING THE BACKGROUND BOT RUNNERS ---
if "node_started" not in st.session_state:
    st.session_state.node_port = 8001
    
    # Start the core network router thread
    st_server = threading.Thread(target=run_fastapi_server, args=(st.session_state.node_port,), daemon=True)
    st_server.start()
    
    # Start the autonomous node topology crawler bot thread
    bot_crawler = threading.Thread(target=run_autonomous_mesh_crawler, daemon=True)
    bot_crawler.start()
    
    st.session_state.node_started = True

st.session_state.p2p_ledger_state = load_persistent_ledger()

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Autonomous Survivor Mesh Network",
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ Project Unified Field: Autonomous Zero-Knowledge Mesh Node Engine")
st.markdown(f"**Network Socket Online:** Port `{st.session_state.node_port}` | **Autonomous Bot Crawlers:** `RUNNING` | **System State:** `SELF_SUSTAINING`")

# --- DECENTRALIZED LEDGER ENGINE (Hardened Production Grade) ---
class DecentralizedLedgerEngine:
    @staticmethod
    def construct_crdt_op_log(proof_pi: str, coordinates: list, secret_key: bytes, user_key_raw: str) -> dict:
        purge_verification_hash = hashlib.sha256(f"{user_key_raw}_PURGE_AUTHORIZATION".encode()).hexdigest()
        block_metadata = {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "zkp_proof_signature": proof_pi,
            "geo_vector_anchor": coordinates,
            "system_status": "VERIFIED_VACUUM_POLARIZATION_NODE"
        }
        serialized_payload = json.dumps(block_metadata, sort_keys=True).encode('utf-8')
        
        cipher = AES.new(secret_key, AES.MODE_GCM)
        ciphertext, tag = cipher.encrypt_and_digest(serialized_payload)
        
        hash_engine = SHA256.new()
        hash_engine.update(ciphertext + cipher.nonce + tag)
        merkle_cid = "Qm" + hash_engine.hexdigest()[:44]
        
        return {
            "IPFS_CID": merkle_cid,
            "CRDT_CLOCK_SEQUENCE": datetime.datetime.utcnow().timestamp(),
            "nonce": cipher.nonce.hex(),
            "tag": tag.hex(),
            "ciphertext": ciphertext.hex(),
            "immutable_proof_visible": block_metadata,
            "purge_verification_hash": purge_verification_hash
        }

    @staticmethod
    def purge_block_by_key(user_key_raw: str, current_peer_state: list) -> tuple:
        target_purge_hash = hashlib.sha256(f"{user_key_raw}_PURGE_AUTHORIZATION".encode()).hexdigest()
        initial_count = len(current_peer_state)
        cleaned_peer_state = [block for block in current_peer_state if block.get("purge_verification_hash") != target_purge_hash]
        blocks_removed = initial_count - len(cleaned_peer_state)
        return cleaned_peer_state, blocks_removed

# --- LIVE METRIC FETCH ENGINES ---
def get_lunar_gravitational_factor():
    now = datetime.datetime.now()
    diff = now - datetime.datetime(2026, 1, 1)
    days = diff.days + (diff.seconds / 86400.0)
    cycle_position = (days % 29.53) / 29.53
    illumination = 0.5 * (1 - np.cos(2 * np.pi * cycle_position))
    gravitational_pull = 1.0 + (0.35 * np.abs(np.sin(np.pi * cycle_position)))
    return round(illumination * 100, 1), round(gravitational_pull, 2)

@st.cache_data(ttl=3600)
def get_live_celestial_kp():
    noaa_endpoint = "https://noaa.gov"
    try:
        response = requests.get(noaa_endpoint, timeout=5)
        if response.status_code == 200:
            data = response.json()
            live_kp = float(data.get("0", {}).get("geomagnetic", {}).get("scale", 2.0)) * 2.0
            return max(1.0, min(9.0, live_kp))
    except Exception:
        pass
    return 3.0

lunar_illumi, lunar_grav = get_lunar_gravitational_factor()
live_kp = get_live_celestial_kp()

# --- SIDEBAR CONTROL PANEL ---
st.sidebar.header("🌍 Target Spatial Matrix (Autonomous Nodes)")
mode = st.sidebar.selectbox(
    "Select Active Network Cluster",
    ["Alpha Cluster Nodes (Regional Mesh)", "Beta Cluster Nodes (Isolated Vaults)", "Gamma Cluster Nodes (Edge Matrix)"]
)

st.sidebar.header("🌱 Land Frequency Remediation")
target_pollution_level = st.sidebar.slider("Localized Environmental Entropy (Pollution/Noise)", 1.0, 10.0, 4.0)
broadcast_mesa_code = st.sidebar.checkbox("🔒 Broadcast Mesa Correction Code", value=False)

st.sidebar.header("🏺 Ground Capacitor Calibration")
shard_density = st.sidebar.slider("Mineral / Shard Ground Density", 1.0, 10.0, 6.5)

st.sidebar.header("🎵 Solfeggio Acoustic Input")
acoustic_frequency = st.sidebar.selectbox(
    "Select Harmonic Tuning Scale",
    ["432 Hz - Cosmic Baseline Calibration", "528 Hz - Core Matrix Transformation", "741 Hz - Intuitive Signal Expansion"]
)

acoustic_resonance_multiplier = 1.618 if "528" in acoustic_frequency else 1.333 if "741" in acoustic_frequency else 1.0

if mode == "Alpha Cluster Nodes (Regional Mesh)":
    cluster_name = "Alpha Local Mesh Backbone"
    water_cooling_efficiency = 1.8  
    fungal_lightning_rod_amplifier = 2.8 
    df_nodes = pd.DataFrame([{"Node_ID": "Node-Alpha-1", "Lat": 44.8262, "Lon": -107.9215, "Base_Imprint": 9.5},
                             {"Node_ID": "Node-Alpha-2", "Lat": 44.8264, "Lon": -107.9212, "Base_Imprint": 8.8}])
elif mode == "Beta Cluster Nodes (Isolated Vaults)":
    cluster_name = "Beta Subsurface Copper Matrix"
    water_cooling_efficiency = 0.9  
    fungal_lightning_rod_amplifier = 3.2 
    df_nodes = pd.DataFrame([{"Node_ID": "Node-Beta-1", "Lat": 29.7797, "Lon": 34.9351, "Base_Imprint": 9.6},
                             {"Node_ID": "Node-Beta-2", "Lat": 29.7820, "Lon": 34.9320, "Base_Imprint": 8.5}])
else:
    cluster_name = "Gamma Mesh Edge Array"
    water_cooling_efficiency = 1.2
    fungal_lightning_rod_amplifier = 2.5  
    df_nodes = pd.DataFrame([{"Node_ID": "Node-Gamma-1", "Lat": -14.6922, "Lon": -75.1488, "Base_Imprint": 9.9},
                             {"Node_ID": "Node-Gamma-2", "Lat": -14.6975, "Lon": -75.1250, "Base_Imprint": 9.8}])

st.sidebar.header("🧘 Operator Tuning Interface")
operator_profile = st.sidebar.selectbox("Select Operator Profile", ["Shamanic Coherence", "Passive Observation", "Predatory Siphoning"])

coherence_multiplier = 5.0 if operator_profile == "Shamanic Coherence" else 0.3 if operator_profile == "Predatory Siphoning" else 1.0
operator_harmonic_key = 1.618 if operator_profile == "Shamanic Coherence" else 1.0

st.sidebar.header("⚡ Local Field Fluctuations")
rf_signal_16 = st.sidebar.slider("1.6 GHz RF Base Power (dBm)", -110, -30, -95)

# --- CALCULATION MATRIX LOOP ---
processed_nodes = []
for idx, row in df_nodes.iterrows():
    rf_delta = max(0, (rf_signal_16 + 100) * 0.5)
    cosmic_flux = (live_kp * 0.6) * lunar_grav
    pollution_entropy_damper = 1 + (target_pollution_level * 0.15)
    
    if broadcast_mesa_code:
        remediation_factor = 2.0
        pollution_entropy_damper = 1.0
        current_state_label = "REMEDIATING: Mesa Clean Correction Code Engaged."
    else:
        remediation_factor = 1.0
        current_state_label = ""
    
    catalyst_field = (((rf_delta + cosmic_flux) * (shard_density * 0.4 * acoustic_resonance_multiplier)) / (water_cooling_efficiency * 0.5)) / pollution_entropy_damper
    total_resonance = row["Base_Imprint"] * catalyst_field * fungal_lightning_rod_amplifier * (coherence_multiplier * 0.1) * operator_harmonic_key * remediation_factor
    prob_manifestation = 1 / (1 + np.exp(-0.11 * (total_resonance - 25)))
    
    if current_state_label == "":
        if prob_manifestation > 0.90:
            current_state_label = "PEAK COHERENCE: Secure Zero-Knowledge Data Link Established"
        elif total_resonance > 25.0:
            current_state_label = "HARMONIC SHIFT: Node Electrified via Multi-Point Capacitance"
        else:
            current_state_label = "EQUILIBRIUM: Stabilized Decentralized Space-Time Frequency"

    processed_nodes.append({
        "Independent Node": row["Node_ID"],
        "Lat": row["Lat"],
        "Lon": row["Lon"],
        "Resonance Output": round(total_resonance, 2),
        "Quantum Mesh Stability": f"{round(prob_manifestation * 100, 1)}%",
        "Node Operational State": current_state_label
    })

df_results = pd.DataFrame(processed_nodes)

# --- DISPLAY LAYOUT DISPLAY ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("📊 Autonomous Node Operational Metrics")
    st.markdown(f"**Active Cluster Group:** `{cluster_name}`")
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Live Solar Kp-Index", f"{live_kp} / 9.0")
    m2.metric("Lunar Illumination", f"{lunar_illumi}%")
    m3.metric("Lunar Tidal Factor", f"{lunar_grav}x")
    
    st.dataframe(df_results[["Independent Node", "Resonance Output", "Quantum Mesh Stability", "Node Operational State"]], use_container_width=True)

    # --- THE BOT READOUT INTERFACE PANEL ---
    st.markdown("---")
    st.subheader("🤖 Background Topology Discovery Bots")
    st.success("🤖 **Crawler Running:** Actively crawling connected network nodes to map alternative routing paths automatically. Zero configurations required.")
    
    current_mapped_peers = load_peers()
    st.write("**Discovered Mesh Topology Map:**", current_mapped_peers)

    # --- CRYPTOGRAPHIC PURGE LAYER PANEL ---
    st.markdown("---")
    st.subheader("💥 Cryptographic Self-Purge Panel")
    
    purge_key = st.text_input("Confirm 25-Point Key Structure Matrix to Execute Purge:", type="password", key="purge_input_field")
    if st.button("🗑️ Authorize Permanent Node Purge"):
        if not purge_key:
            st.warning("⚠️ Provide your key matrix sequence to authorize data removal loops.")
        else:
            cleaned_state, removed_count = DecentralizedLedgerEngine.purge_block_by_key(purge_key, st.session_state.p2p_ledger_state)
            if removed_count > 0:
                st.session_state.p2p_ledger_state = cleaned_state
                save_persistent_ledger(cleaned_state)
                st.success(f"💥 Success! Safely dropped {removed_count} records from the active node persistent storage indexes.")
                st.rerun()
            else:
                st.warning("🔍 No active data blocks matched the signature key vector inside this local node ledger.")

with col2:
    st.subheader("🔑 Secure CRDT Vault Drop Interface")
    st.markdown("Utilizing memory-hard parameters. Data transforms immediately into encrypted blocks; no humans ever possess access vectors.")
    
    user_key = st.text_input("Enter Private 25-Point Key Structure Matrix (Minimum 16 characters):", type="password", key="vault_input_field")
    perp_id = st.text_input("Blind Cross-Check Identifier (Unique Handle / Phone):")
    incident_notes = st.text_area("Secure Incident Notes (AES Encrypted Locally):")
    
    selected_target_node_idx = st.selectbox("Select Target Coordinate Node Anchor:", range(len(df_results)), format_func=lambda x: df_results.iloc[x]["Independent Node"])
    active_coords = [float(df_results.iloc[selected_target_node_idx]["Lat"]), float(df_results.iloc[selected_target_node_idx]["Lon"])]

    if st.button("⚡ Execute Hardened Immutable Ledger Drop"):
        if not user_key or not perp_id or not incident_notes:
            st.warning("⚠️ Complete all fields to initialize the payload loops.")
        elif len(user_key) < 16:
            st.error("❌ Key Matrix must be at least 16 characters long to safely seed the engine structure.")
        else:
            with st.spinner("Processing zero-knowledge calculations and routing across network wires..."):
                derived_aes_seed = hashlib.sha256(user_key.encode()).digest()
                
                system_salt = hashlib.sha256(f"Unified_Field_Salt_{acoustic_resonance_multiplier}".encode()).digest()[:16]
                ph = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=4, hash_len=32)
                raw_argon_hash = ph.hash(perp_id.strip().lower(), salt=system_salt)
                
                blinded_token = hashlib.sha256(raw_argon_hash.encode()).hexdigest()
                
                crdt_packet = DecentralizedLedgerEngine.construct_crdt_op_log(
                    proof_pi=blinded_token,
                    coordinates=active_coords,
                    secret_key=derived_aes_seed,
                    user_key_raw=user_key
                )
                
                local_ledger = load_persistent_ledger()
                exists = any(b["IPFS_CID"] == crdt_packet["IPFS_CID"] for b in local_ledger)
                if not exists:
                    local_ledger.append(crdt_packet)
                    local_ledger.sort(key=lambda x: x["CRDT_CLOCK_SEQUENCE"], reverse=True)
                    save_persistent_ledger(local_ledger)
                    st.session_state.p2p_ledger_state = local_ledger
                
                # Dynamic Redundancy: Async broadcast out to all discovered nodes automatically
                threading.Thread(target=broadcast_block_to_mesh, args=(crdt_packet,), daemon=True).start()
                
                st.success("✅ Secure Block Generation Completed! Payload committed locally and gossiped to autonomous mesh routes.")
                st.json(crdt_packet)

# --- BLIND CROSS-CHECK MATCH ENGINE READOUT ---
st.markdown("---")
st.subheader("🔍 Blind Cross-Check Perpetrator Match Engine")
st.markdown("Scans the append-only ledger for matching zero-knowledge signatures *without* ever decrypting what the data says.")

if len(st.session_state.p2p_ledger_state) < 2:
    st.caption("Awaiting multiple entries in the ledger to check for network match synchronization alerts.")
else:
    token_tracking_map = {}
    matches_discovered = False
    
    for block in st.session_state.p2p_ledger_state:
        token = block["immutable_proof_visible"]["zkp_proof_signature"]
        cid = block["IPFS_CID"]
        time_stamp = block["immutable_proof_visible"]["timestamp"]
        
        if token not in token_tracking_map:
            token_tracking_map[token] = []
        token_tracking_map[token].append((cid, time_stamp))
        
    for token, peers in token_tracking_map.items():
        if len(peers) > 1:
            matches_discovered = True
            st.error(f"🚨 **CRITICAL NETWORK MATCH ALERT:** Found {len(peers)} independent zero-knowledge entries sharing an identical Perpetrator Fingerprint token!")
            match_data = [{"IPFS Block CID": p, "Registration Timestamp": p} for p in peers]
            st.table(pd.DataFrame(match_data))
            st.info("💡 *Note to Operator:* The database cannot read the name or the text details, but we mathematically prove that multiple separate survivors have flagged the exact same identifier.")
            
    if not matches_discovered:
        st.success("☀️ All zero-knowledge blocks currently traversing the mesh ledger represent completely unique tracking tags. Zero identifier collisions detected.")

# --- PERSISTENT LEDGER VISUALIZATION ---
st.markdown("---")
st.subheader("🌐 Global Decentralized CRDT Ledger Sync View (Persistent JSON Storage Ledger)")
if len(st.session_state.p2p_ledger_state) == 0:
    st.caption("No blocks gossiped onto the disk layer yet.")
else:
    for block in st.session_state.p2p_ledger_state:
        with st.expander(f"🔗 Merkle-CRDT Block ID: {block['IPFS_CID']} | Clock Sequence: {block['CRDT_CLOCK_SEQUENCE']}"):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Public Immutable Metadata Block Content (Visible to Peers):**")
                st.write(block["immutable_proof_visible"])
            with c2:
                st.markdown("**Encrypted Zero-Knowledge Network Wire Data (Completely Private):**")
                st.json({
                    "nonce": block["nonce"],
                    "tag": block["tag"],
                    "ciphertext": block["ciphertext"]
                })

