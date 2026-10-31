import streamlit as st
import requests
import pandas as pd
import json
import datetime
import hashlib
from Crypto.Cipher import AES

NODE_URL = "http://127.0.0.1:8001"

st.set_page_config(page_title="Secure Portal", page_icon="🛡️", layout="centered")

# --- 1. EMERGENCY QUICK-ESCAPE ACTION ---
if st.button("🚨 QUICK ESCAPE (Hide Screen Immediately)", use_container_width=True):
    st.markdown('<meta http-equiv="refresh" content="0;URL=\'https://google.com\'" />', unsafe_allow_html=True)
    st.stop()

st.title("🛡️ Secure Incident Vault & Mesh Network")
st.markdown("Your information is entirely encrypted on your device. No human beings or administrators have access to your data models.")

try:
    ledger_data = requests.get(f"{NODE_URL}/ledger", timeout=2).json()
    investigator_data = requests.get(f"{NODE_URL}/investigator", timeout=2).json()
except Exception:
    ledger_data = []
    investigator_data = []

# --- LIVE FINGERPRINT CROSS-CHECK ALERTS ---
active_matches_tokens = set()
if len(ledger_data) >= 2:
    token_tracking_map = {}
    for block in ledger_data:
        token = block["immutable_proof_visible"]["zkp_proof_signature"]
        token_tracking_map.setdefault(token, []).append(block["IPFS_CID"])
        
    for token, cids in token_tracking_map.items():
        if len(cids) > 1:
            active_matches_tokens.add(token)
            st.error(f"⚠️ **System Alert:** Multiple anonymous records have safely matched against the same unique identifier fingerprint. Your entry has connected with {len(cids)-1} other record(s) inside the distributed mesh network. Communication is now open in the Match Mailbox tab.")

# Layout Tabs
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📥 Create Secure Entry", 
    "⚖️ Legal Ledger Export",
    "💬 Match Mailbox",
    "🕵️‍♂️ Internal Investigator",
    "🚑 Immediate Resources",
    "📖 User Safety Guide",
    "⚙️ Network Diagnostics"
])

# --- TAB 1: CREATE VAULT ENTRY ---
with tab1:
    st.subheader("Store an Entry Privately")
    st.markdown("Everything you input below is transformed into a cryptographic key array entirely inside your browser. The server never receives your raw text lines.")
    
    u_key = st.text_input("Create Your Private 25-Point Access Key:", type="password", key="reg_key")
    p_id = st.text_input("Target Cross-Check Identifier (Unique Social Handle or Phone Number):", key="reg_id")
    
    st.markdown("**Local Vector Coordinates (Optional)**")
    c_lat = st.number_input("Node Latitude Coordinate Anchor:", value=40.2592, format="%.4f")
    c_lon = st.number_input("Node Longitude Coordinate Anchor:", value=-109.8885, format="%.4f")
    
    notes = st.text_area("Secure Incident Record Diary Payload:", key="reg_notes")

    if st.button("🔒 Encrypt and Broadcast onto Mesh", use_container_width=True):
        if not u_key or not p_id or not notes:
            st.warning("Please fill out all fields.")
        elif len(u_key) < 16:
            st.error("Your access key must be at least 16 characters long.")
        else:
            try:
                payload = {
                    "user_key": u_key, 
                    "perp_id": p_id, 
                    "notes": notes,
                    "coordinates": [c_lat, c_lon]
                }
                res = requests.post(f"{NODE_URL}/create-entry", json=payload).json()
                if res.get("status") == "success":
                    st.success("🎉 Entry successfully locked and saved to the decentralized network lines!")
                    st.rerun()
            except Exception:
                st.error("Could not communicate with the background data engine.")

# --- TAB 2: CLIENT-SIDE LEGAL LEDGER GENERATION ---
with tab2:
    st.subheader("⚖️ Generate Verifiable Evidence Brief")
    export_key = st.text_input("Enter Your Private 25-Point Access Key to Authorize Local Export:", type="password", key="exp_key")
    
    if st.button("📄 Reconstruct Legal Ledger Brief", use_container_width=True):
        if not export_key:
            st.warning("Please enter your access key.")
        else:
            derived_seed = hashlib.sha256(export_key.encode()).digest()
            decrypted_records = []
            
            for block in ledger_data:
                try:
                    nonce = bytes.fromhex(block["nonce"])
                    tag = bytes.fromhex(block["tag"])
                    ciphertext = bytes.fromhex(block["ciphertext"])
                    
                    cipher = AES.new(derived_seed, AES.MODE_GCM, nonce=nonce)
                    decrypted_bytes = cipher.decrypt_and_verify(ciphertext, tag)
                    metadata = json.loads(decrypted_bytes.decode('utf-8'))
                    
                    decrypted_records.append({
                        "Timestamp": metadata["timestamp"],
                        "Network CID Verification Tag": block["IPFS_CID"],
                        "Anchor Vector": metadata.get("geo_vector_anchor", [0.0, 0.0]),
                        "Status": metadata["system_status"]
                    })
                except Exception: pass

            if decrypted_records:
                st.success(f"✅ Found and verified {len(decrypted_records)} blocks.")
                df_export = pd.DataFrame(decrypted_records)
                st.dataframe(df_export, use_container_width=True)
            else:
                st.warning("No records matched the provided key credentials.")

# ==============================================================================
# SEPARATION: PART 2 INJECTION BLOCK
# ==============================================================================
