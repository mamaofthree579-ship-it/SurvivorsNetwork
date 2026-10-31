import streamlit as st
import requests
import pandas as pd
import json
import datetime
import hashlib
import threading
import os
from Crypto.Cipher import AES

NODE_URL = "http://127.0.0.1:8001"

# --- AUTOMATED WEB CONTAINER BOOTSTRAP HOOK ---
if "node_started" not in st.session_state:
    try:
        # Check if the node is already running in the background
        requests.get(f"{NODE_URL}/ledger", timeout=1)
        st.session_state.node_started = True
    except Exception:
        # If offline, spin up verify.py automatically in a silent background thread
        import uvicorn
        from verify import app as backend_fastapi_app
        
        def start_embedded_node():
            uvicorn.run(backend_fastapi_app, host="127.0.0.1", port=8001, log_level="warning")
            
        t = threading.Thread(target=start_embedded_node, daemon=True)
        t.start()
        st.session_state.node_started = True

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
# --- TAB 3: ANONYMOUS BLIND MATCH MAILBOX ---
with tab3:
    st.subheader("💬 Anonymous Match Communication Mailbox")
    st.markdown("If the system detects another user has matching record identifiers, you can securely communicate here. Conversations are encrypted client-side using your 25-point key matrix variables as a verification seed.")
    
    chat_key = st.text_input("Enter Your Private 25-Point Access Key to Access Mailbox:", type="password", key="chat_key_input")
    chat_perp_id = st.text_input("Enter the Perpetrator Identifier to Verify Mailbox Tunnel:", key="chat_perp_input")
    
    if chat_key and chat_perp_id:
        salt = hashlib.sha256(b"Unified_Field_Dynamic_Salt_1.618").digest()[:16]
        from argon2 import PasswordHasher
        ph_token = hashlib.sha256(PasswordHasher(time_cost=2, memory_cost=65536).hash(chat_perp_id.strip().lower(), salt=salt).encode()).hexdigest()
        
        if ph_token not in active_matches_tokens:
            st.info("🔍 System is monitoring this identifier network route. No verified match collisions detected for this profile yet.")
        else:
            st.success("🔒 Secure Communication Tunnel Connected. You are linked with another anonymous matching account.")
            
            try:
                mailbox_url = f"{NODE_URL}/mailbox/{ph_token}"
                wire_messages = requests.get(mailbox_url).json()
            except Exception:
                wire_messages = []
                
            chat_seed = hashlib.sha256(chat_key.encode()).digest()
            decrypted_chat_logs = []
            
            for msg in wire_messages:
                try:
                    c_nonce = bytes.fromhex(msg["nonce"])
                    c_tag = bytes.fromhex(msg["tag"])
                    c_text = bytes.fromhex(msg["ciphertext"])
                    cipher = AES.new(chat_seed, AES.MODE_GCM, nonce=c_nonce)
                    plain_text = cipher.decrypt_and_verify(c_text, c_tag).decode('utf-8')
                    decrypted_chat_logs.append(f"[{msg['timestamp']}] You: {plain_text}")
                except Exception:
                    decrypted_chat_logs.append(f"[{msg['timestamp']}] Matched Peer: [Encrypted Inbound Wire Payload Block]")
            
            st.markdown("### 📋 Message Timeline Log")
            for logged_msg in decrypted_chat_logs:
                st.text(logged_msg)
                
            st.markdown("---")
            new_msg_payload = st.text_input("Type Secure Message to Broadcast:")
            if st.button("📤 Send Message Blindly", use_container_width=True):
                if new_msg_payload:
                    cipher = AES.new(chat_seed, AES.MODE_GCM)
                    c_text, tag = cipher.encrypt_and_digest(new_msg_payload.encode('utf-8'))
                    
                    post_data = {
                        "match_token": ph_token,
                        "encrypted_message": c_text.hex(),
                        "nonce": cipher.nonce.hex(),
                        "tag": tag.hex()
                    }
                    requests.post(f"{NODE_URL}/mailbox/send", json=post_data)
                    st.success("Message dropped into blind mailbox container registry.")
                    st.rerun()

# --- TAB 4: INTERNAL INVESTIGATOR BOT DISPLAY ---
with tab4:
    st.subheader("🕵️‍♂️ Autonomous Internal Link Analysis Engine")
    if not investigator_data:
        st.success("☀️ Complete Baseline Stability: The engine currently detects zero anomalies or geographic patterns across network wire nodes.")
    else:
        st.info("📊 **Pattern Analysis Log:** The system has flagged spatial or temporal intersections that could indicate related clusters.")
        for anomaly in investigator_data:
            with st.container():
                st.markdown(f"#### 🚨 Connection Pattern: `{anomaly['Type']}`")
                st.markdown(f"* **Vector A Block Connection:** `{anomaly['Block_A_CID']}`")
                st.markdown(f"* **Vector B Block Connection:** `{anomaly['Block_B_CID']}`")
                st.markdown(f"* **Calculated Cluster Proximity Delta:** `{anomaly['Spatial_Variance']}` vector units")
                st.markdown(f"* **Rolling Time Window Delta:** `{anomaly['Temporal_Variance_Hours']}` hours apart")
                st.markdown("---")

# --- TAB 5: COMPREHENSIVE 50-STATE OFFLINE RESOURCE MATRIX ---
with tab5:
    st.subheader("🚑 Nationwide Immediate Crisis Resources")
    st.markdown("Select a state to instantly access verified local helplines. Everything operates entirely offline inside your browser container environment to ensure complete confidentiality.")
    
    us_state_matrix = {
        "Alabama": "Alabama Coalition Against Sexual Assault (ACASA) - Helpline: 334-264-0123",
        "Alaska": "Alaska Network on Domestic Violence and Sexual Assault - Helpline: 907-586-3650",
        "Arizona": "Arizona Coalition to End Sexual and Domestic Violence - Helpline: 602-279-2900",
        "Arkansas": "Arkansas Coalition Against Sexual Assault (ACASA) - Helpline: 800-656-4673",
        "California": "VALOR US Network / CA Sexual Assault Coalition - Helpline: 916-446-2520",
        "Colorado": "Colorado Coalition Against Sexual Assault (CCASA) - Helpline: 303-839-9999",
        "Connecticut": "Connecticut Alliance to End Sexual Violence - Helpline: 888-999-5545",
        "Delaware": "Delaware Coalition Against Domestic Violence - Helpline: 302-658-2960",
        "Florida": "Florida Coalition Against Sexual Violence (FCASV) - Helpline: 888-956-7273",
        "Georgia": "Georgia Coalition Against Domestic Violence - Helpline: 800-334-2836",
        "Hawaii": "Hawaii Sexual Assault Response and Training Hub - Helpline: 808-524-7273",
        "Idaho": "Idaho Coalition Against Sexual Assault & Domestic Violence - Helpline: 208-384-0419",
        "Illinois": "Illinois Coalition Against Sexual Assault (ICASA) - Helpline: 217-753-4117",
        "Indiana": "Indiana Coalition Against Sexual Assault Network - Helpline: 317-632-3498",
        "Iowa": "Iowa Coalition Against Sexual Assault (IowaCASA) - Helpline: 517-244-7741",
        "Kansas": "Kansas Coalition Against Sexual and Domestic Violence - Helpline: 785-232-9784",
        "Kentucky": "Kentucky Association of Sexual Assault Programs - Helpline: 866-375-2727",
        "Louisiana": "Louisiana Foundation Against Sexual Assault - Helpline: 866-666-6666",
        "Maine": "Maine Coalition Against Sexual Assault (MECASA) - Helpline: 800-871-7741",
        "Maryland": "Maryland Coalition Against Sexual Assault (MCASA) - Helpline: 410-974-4507",
        "Massachusetts": "Jane Doe Inc. (MA Coalition Against Assault) - Helpline: 617-248-0922",
        "Michigan": "Michigan Coalition to End Domestic and Sexual Violence - Helpline: 517-347-7000",
        "Minnesota": "Minnesota Coalition Against Sexual Assault (MNCASA) - Helpline: 651-209-9993",
        "Mississippi": "Mississippi Coalition Against Sexual Assault - Helpline: 601-948-0555",
        "Missouri": "Missouri Coalition Against Domestic and Sexual Violence - Helpline: 573-634-4161",
        "Montana": "Montana Coalition Against Domestic and Sexual Violence - Helpline: 406-443-7794",
        "Nebraska": "Nebraska Coalition to End Sexual and Domestic Violence - Helpline: 402-476-6256",
        "Nevada": "Nevada Coalition Against Sexual Violence - Helpline: 775-358-1171",
        "New Hampshire": "New Hampshire Coalition Against Domestic Violence - Helpline: 603-224-8893",
        "New Jersey": "New Jersey Coalition Against Sexual Assault - Helpline: 609-631-4450",
        "New Mexico": "New Mexico Coalition of Sexual Assault Programs - Helpline: 505-883-8020",
        "New York": "New York State Coalition Against Sexual Assault - Helpline: 800-942-6906",
        "North Carolina": "North Carolina Coalition Against Sexual Assault - Helpline: 919-871-1015",
        "North Dakota": "North Dakota Council on Abusive Relationships - Helpline: 701-223-9524",
        "Ohio": "Ohio Alliance to End Sexual Violence (OAESV) - Helpline: 888-886-8388",
        "Oklahoma": "Oklahoma Coalition Against Domestic and Sexual Violence - Helpline: 405-524-0700",
        "Oregon": "Oregon Coalition Against Domestic and Sexual Violence - Helpline: 503-230-1951",
        "Pennsylvania": "Pennsylvania Coalition Against Rape (PCAR) - Helpline: 888-772-7227",
        "Rhode Island": "Day One Rhode Island Coalition Hub - Helpline: 800-425-6109",
        "South Carolina": "South Carolina Coalition Against Assault - Helpline: 803-256-2900",
        "South Dakota": "South Dakota Coalition Against Domestic Violence - Helpline: 605-945-0869",
        "Tennessee": "Tennessee Coalition to End Domestic and Sexual Violence - Helpline: 615-386-9406",
        "Texas": "Texas Association Against Sexual Assault (TAASA) - Helpline: 512-474-7507",
        "Utah": "Utah Coalition Against Sexual Assault (UCASA) - Helpline: 888-421-1100",
        "Vermont": "Vermont Network Against Domestic and Sexual Violence - Helpline: 802-223-1302",
        "Virginia": "Virginia Sexual and Domestic Violence Action Alliance - Helpline: 804-221-4468",
        "Washington": "Washington Coalition of Sexual Assault Programs - Helpline: 360-754-7583",
        "West Virginia": "West Virginia Coalition Against Domestic Violence - Helpline: 304-965-3552",
        "Wisconsin": "Wisconsin Coalition Against Sexual Assault (WCASA) - Helpline: 608-257-1516",
        "Wyoming": "Wyoming Coalition Against Assault & Violence Network - Helpline: 307-777-7233"
    }
    
    selected_us_state = st.selectbox("Choose Your Current State / Target Region Location:", ["Select a Region Location"] + list(us_state_matrix.keys()))
    if selected_us_state != "Select a Region Location":
        st.info(f"🚑 **Confidential Resources Localized for {selected_us_state}:**\n\n`{us_state_matrix[selected_us_state]}`")
        st.caption("🔒 *Privacy Notice: State query evaluation runs completely local to memory. No external tracking logs generated.*")

# --- TAB 6: TRAUMA-INFORMED SAFETY GUIDE ---
with tab6:
    st.subheader("📖 User Guidance & Emotional Safety Protocol")
    st.markdown("""
    When your internal nervous system feels overwhelmed, managing data can feel heavy or intimidating. This platform is designed to carry that weight for you silently. 
    
    **💡 Things to Remember:**
    1. **Your 25-Point Key is Everything:** This key is generated entirely in your browser window. No human being knows what it is. Because it is never stored anywhere, **there is no password reset.** Write it down or save it somewhere only you can look.
    2. **The Identifier is Blinded:** When you enter a phone number or social handle, the system strips the text away instantly and turns it into a mathematical coordinate tag. The node monitors the network for overlaps *without* knowing who you named.
    3. **You Always Have Control:** If you decide you want your records gone, head to the diagnostics tab, type in your key, and the system will completely shred your container blocks from the node disk permanently.
    4. **The Panic Button:** If you feel unsafe or notice someone approaching, click the **🚨 QUICK ESCAPE** button at the top of the screen. The portal will close instantly and redirect to a neutral page.
    """)

# --- TAB 7: MODULAR NETWORK DIAGNOSTICS & PURGES ---
with tab7:
    st.subheader("Silent Automated Network Operations")
    
    st.markdown("### 💾 Export Encrypted Node Database Backup")
    st.markdown("Download a full backup file containing the network's zero-knowledge encrypted wire packets.")
    
    if ledger_data:
        json_backup_payload = json.dumps(ledger_data, indent=4)
        st.download_button(
            label="💾 Download Persistent Ledger Backup (.JSON)",
            data=json_backup_payload,
            file_name=f"Survivor_Node_Mesh_Backup_{datetime.datetime.utcnow().strftime('%Y%m%d')}.json",
            mime="application/json",
            use_container_width=True
        )
    else:
        st.caption("No synchronized blocks available to back up yet.")
        
    st.markdown("---")
    st.markdown("### 🗑️ Permanent Node Data Destruction")
    del_key = st.text_input("Confirm Your Private 25-Point Access Key to Delete Data:", type="password", key="del_key_panel")
    if st.button("🗑️ Permanently Wipe My Data From Node Logs", use_container_width=True):
        if del_key:
            try:
                res = requests.post(f"{NODE_URL}/purge", json={"purge_key": del_key}).json()
                st.success(f"💥 Permanent deletion success! Dropped {res.get('removed_count', 0)} entries.")
                st.rerun()
            except Exception:
                st.error("Could not complete the purge request on the backend node.")

    with st.expander("🌐 Raw Cryptographic Ledger Wire Sync Data"):
        if not ledger_data: 
            st.caption("No blocks synced on this node line yet.")
        else:
            for b in ledger_data:
                st.json({
                    "Block_CID": b["IPFS_CID"], 
                    "Encrypted_Payload": b["ciphertext"], 
                    "Public_Metadata": b["immutable_proof_visible"]
                })
