import streamlit as st
import requests
import pandas as pd

NODE_URL = "http://127.0.0.1:8001"

st.set_page_config(page_title="Secure Portal", page_icon="🛡️", layout="centered")

# 1. EMERGENCE QUICK-ESCAPE ACTION
if st.button("🚨 QUICK ESCAPE (Hide Screen Immediately)", use_container_width=True):
    st.markdown('<meta http-equiv="refresh" content="0;URL=\'https://google.com\'" />', unsafe_allow_html=True)
    st.stop()

st.title("🛡️ Secure Incident Vault & Mesh Network")
st.markdown("Your information is entirely encrypted on your device. No human beings have access to your data.")

# Fetch active state from the independent engine safely
try:
    ledger_data = requests.get(f"{NODE_URL}/ledger", timeout=2).json()
except Exception:
    ledger_data = []
    st.warning("⚠️ Background Network Node Engine (`verify.py`) is offline. Please launch it in your terminal.")

# --- LIVE FINGERPRINT CROSS-CHECK ALERTS ---
if len(ledger_data) >= 2:
    token_tracking_map = {}
    for block in ledger_data:
        token = block["immutable_proof_visible"]["zkp_proof_signature"]
        token_tracking_map.setdefault(token, []).append(block["IPFS_CID"])
        
    for token, cids in token_tracking_map.items():
        if len(cids) > 1:
            st.error(f"⚠️ **System Alert:** Multiple anonymous records have safely matched against the same unique identifier fingerprint. Your entry has connected with {len(cids)-1} other record(s) inside the distributed mesh network.")

tab1, tab2, tab3 = st.tabs(["📥 Create Secure Entry", "💥 Manage & Purge Data", "⚙️ Network Health Ledger"])

# --- TAB 1: CREATE VAULT ENTRY ---
with tab1:
    st.subheader("Store an Entry Privately")
    u_key = st.text_input("Create Your Private 25-Point Access Key:", type="password", key="reg_key")
    p_id = st.text_input("Target Cross-Check Identifier (Unique Social Handle or Phone Number):", key="reg_id")
    notes = st.text_area("Secure Incident Record Diary Payload:", key="reg_notes")

    if st.button("🔒 Encrypt and Broadcast onto Mesh", use_container_width=True):
        if not u_key or not p_id or not notes:
            st.warning("Please fill out all fields.")
        elif len(u_key) < 16:
            st.error("Your access key must be at least 16 characters long.")
        else:
            try:
                payload = {"user_key": u_key, "perp_id": p_id, "notes": notes}
                res = requests.post(f"{NODE_URL}/create-entry", json=payload).json()
                if res.get("status") == "success":
                    st.success("🎉 Entry successfully locked and saved to the decentralized network lines!")
                    st.rerun()
            except Exception:
                st.error("Could not communicate with the background data engine.")

# --- TAB 2: CRYPTOGRAPHIC SELF-PURGE ---
with tab2:
    st.subheader("Completely Erase Your Records")
    del_key = st.text_input("Confirm Your Private 25-Point Access Key to Delete Data:", type="password", key="del_key")
    if st.button("🗑️ Permanently Wipe My Data From Node Logs", use_container_width=True):
        if not del_key:
            st.warning("You must enter your security access key.")
        else:
            try:
                res = requests.post(f"{NODE_URL}/purge", json={"purge_key": del_key}).json()
                removed = res.get("removed_count", 0)
                if removed > 0:
                    st.success(f"💥 Permanent deletion success! Dropped {removed} entries completely out of network ledger loops.")
                    st.rerun()
                else:
                    st.warning("No tracking blocks found matching your precise access key credentials.")
            except Exception:
                st.error("Could not communicate with the background data engine.")

# --- TAB 3: MODULAR NETWORK DIAGNOSTICS ---
with tab3:
    st.subheader("Silent Automated Network Operations")
    
    with st.expander("🤖 Discovered Network Map Vectors (Crawler Bot Mappings)"):
        try:
            peers = requests.get(f"{NODE_URL}/peers").json()
            st.write("Discovered Router Peer Lanes:", peers)
        except Exception:
            st.write("Discovered Router Peer Lanes: Node Offline")

    with st.expander("🌐 Raw Cryptographic Ledger Wire Sync Data"):
        if not ledger_data:
            st.caption("No blocks synced on this node line yet.")
        else:
            for b in ledger_data:
                st.json({"Block_CID": b["IPFS_CID"], "Encrypted_Payload": b["ciphertext"], "Public_Metadata": b["immutable_proof_visible"]})
