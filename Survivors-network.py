import os

import json

import csv

import io

from datetime import datetime, timezone

import requests

import streamlit as st

# ---------------------------------------------------------

# APPLICATION CONFIGURATION

# ---------------------------------------------------------

st.set_page_config(

    page_title="Survivors Network",

    page_icon="🛡️",

    layout="wide",

    initial_sidebar_state="expanded"

)

APP_NAME = "Survivors Network"

AUTHOR = "Hope Jones"

NODE_URL = os.getenv(

    "SURVIVORS_NETWORK_API",

    "http://127.0.0.1:8001"

).rstrip("/")

REQUEST_TIMEOUT = 12

# ---------------------------------------------------------

# VISUAL DESIGN

# ---------------------------------------------------------

st.markdown("""

<style>

    .stApp {

        background-color: #f5f7f8;

        color: #24343b;

    }

    section[data-testid="stSidebar"] {

        background-color: #e8eef0;

    }

    h1, h2, h3 {

        color: #294b55;

    }

    .resource-card {

        background: #ffffff;

        border: 1px solid #d9e3e5;

        border-radius: 12px;

        padding: 16px;

        margin-bottom: 12px;

    }

    .resource-card a {

        color: #245f70;

        font-weight: 600;

    }

    .small-note {

        color: #64777d;

        font-size: 0.88rem;

    }

    div[data-testid="stMetric"] {

        background: #ffffff;

        border: 1px solid #d9e3e5;

        padding: 12px;

        border-radius: 10px;

    }

</style>

""", unsafe_allow_html=True)

# ---------------------------------------------------------

# 50-STATE RESOURCE MATRIX

# Official state coalition websites from NNEDV.

# Oklahoma uses the federal DOJ resource directory.

# ---------------------------------------------------------

STATE_RESOURCES = {

    "Alabama": {

        "code": "AL",

        "coalition": "Alabama Coalition Against Domestic Violence",

        "url": "https://acadv.org"

    },

    "Alaska": {

        "code": "AK",

        "coalition": "Alaska Network on Domestic Violence and Sexual Assault",

        "url": "https://andvsa.org"

    },

    "Arizona": {

        "code": "AZ",

        "coalition": "Arizona Coalition to End Sexual and Domestic Violence",

        "url": "https://acesdv.org"

    },

    "Arkansas": {

        "code": "AR",

        "coalition": "Arkansas Coalition Against Domestic Violence",

        "url": "https://domesticpeace.com"

    },

    "California": {

        "code": "CA",

        "coalition": "California Partnership to End Domestic Violence",

        "url": "https://cpedv.org"

    },

    "Colorado": {

        "code": "CO",

        "coalition": "Violence Free Colorado",

        "url": "https://violencefreecolorado.org"

    },

    "Connecticut": {

        "code": "CT",

        "coalition": "Connecticut Coalition Against Domestic Violence",

        "url": "https://ctcadv.org"

    },

    "Delaware": {

        "code": "DE",

        "coalition": "Delaware Coalition Against Domestic Violence",

        "url": "https://dcadv.org"

    },

    "Florida": {

        "code": "FL",

        "coalition": "Florida Partnership to End Domestic Violence",

        "url": "https://fpedv.org"

    },

    "Georgia": {

        "code": "GA",

        "coalition": "Georgia Coalition Against Domestic Violence",

        "url": "https://gcadv.org"

    },

    "Hawaii": {

        "code": "HI",

        "coalition": "Hawaii State Coalition Against Domestic Violence",

        "url": "https://hscadv.org"

    },

    "Idaho": {

        "code": "ID",

        "coalition": "Idaho Coalition Against Sexual and Domestic Violence",

        "url": "https://idahocoalition.org"

    },

    "Illinois": {

        "code": "IL",

        "coalition": "Illinois Coalition Against Domestic Violence",

        "url": "https://ilcadv.org"

    },

    "Indiana": {

        "code": "IN",

        "coalition": "Indiana Coalition Against Domestic Violence",

        "url": "https://icadvinc.org"

    },

    "Iowa": {

        "code": "IA",

        "coalition": "Iowa Coalition Against Domestic Violence",

        "url": "https://icadv.org"

    },

    "Kansas": {

        "code": "KS",

        "coalition": "Kansas Coalition Against Sexual and Domestic Violence",

        "url": "https://kcsdv.org"

    },

    "Kentucky": {

        "code": "KY",

        "coalition": "ZeroV",

        "url": "https://zerov.org"

    },

    "Louisiana": {

        "code": "LA",

        "coalition": "Louisiana Coalition Against Domestic Violence",

        "url": "https://lcadv.org"

    },

    "Maine": {

        "code": "ME",

        "coalition": "Maine Coalition to End Domestic Violence",

        "url": "https://mcedv.org"

    },

    "Maryland": {

        "code": "MD",

        "coalition": "Maryland Network Against Domestic Violence",

        "url": "https://mnadv.org"

    },

    "Massachusetts": {

        "code": "MA",

        "coalition": "Jane Doe Inc.",

        "url": "https://janedoe.org"

    },

    "Michigan": {

        "code": "MI",

        "coalition": "Michigan Coalition to End Domestic and Sexual Violence",

        "url": "https://mcedsv.org"

    },

    "Minnesota": {

        "code": "MN",

        "coalition": "Violence Free Minnesota",

        "url": "https://vfmn.org"

    },

    "Mississippi": {

        "code": "MS",

        "coalition": "Mississippi Coalition Against Domestic Violence",

        "url": "https://mcadv.org"

    },

    "Missouri": {

        "code": "MO",

        "coalition": "Missouri Coalition Against Domestic and Sexual Violence",

        "url": "https://mocadsv.org"

    },

    "Montana": {

        "code": "MT",

        "coalition": "Montana Coalition Against Domestic and Sexual Violence",

        "url": "https://mcadsv.com"

    },

    "Nebraska": {

        "code": "NE",

        "coalition": "Nebraska Coalition to End Sexual and Domestic Violence",

        "url": "https://nebraskacoalition.org"

    },

    "Nevada": {

        "code": "NV",

        "coalition": "Nevada Coalition to End Domestic and Sexual Violence",

        "url": "https://ncedsv.org"

    },

    "New Hampshire": {

        "code": "NH",

        "coalition": "New Hampshire Coalition Against Domestic and Sexual Violence",

        "url": "https://nhcadsv.org"

    },

    "New Jersey": {

        "code": "NJ",

        "coalition": "New Jersey Coalition to End Domestic Violence",

        "url": "https://njcedv.org"

    },

    "New Mexico": {

        "code": "NM",

        "coalition": "New Mexico Coalition Against Domestic Violence",

        "url": "https://nmcadv.org"

    },

    "New York": {

        "code": "NY",

        "coalition": "New York State Coalition Against Domestic Violence",

        "url": "https://nyscadv.org"

    },

    "North Carolina": {

        "code": "NC",

        "coalition": "North Carolina Coalition Against Domestic Violence",

        "url": "https://nccadv.org"

    },

    "North Dakota": {

        "code": "ND",

        "coalition": "North Dakota Domestic and Sexual Violence Coalition",

        "url": "https://nddsvc.org"

    },

    "Ohio": {

        "code": "OH",

        "coalition": "Ohio Domestic Violence Network",

        "url": "https://odvn.org"

    },

    "Oklahoma": {

        "code": "OK",

        "coalition": "Oklahoma victim services directory",

        "url": "https://www.justice.gov/ovw/resources-victims-and-survivors"

    },

    "Oregon": {

        "code": "OR",

        "coalition": "Oregon Coalition Against Domestic and Sexual Violence",

        "url": "https://ocadsv.org"

    },

    "Pennsylvania": {

        "code": "PA",

        "coalition": "Pennsylvania Coalition Against Domestic Violence",

        "url": "https://pcadv.org"

    },

    "Rhode Island": {

        "code": "RI",

        "coalition": "Rhode Island Coalition Against Domestic Violence",

        "url": "https://ricadv.org"

    },

    "South Carolina": {

        "code": "SC",

        "coalition": "South Carolina Coalition Against Domestic Violence and Sexual Assault",

        "url": "https://sccadvasa.org"

    },

    "South Dakota": {

        "code": "SD",

        "coalition": "South Dakota Network Against Family Violence and Sexual Assault",

        "url": "https://sdnafvsa.com"

    },

    "Tennessee": {

        "code": "TN",

        "coalition": "Tennessee Coalition to End Domestic and Sexual Violence",

        "url": "https://tncoalition.org"

    },

    "Texas": {

        "code": "TX",

        "coalition": "Texas Council on Family Violence",

        "url": "https://tcfv.org"

    },

    "Utah": {

        "code": "UT",

        "coalition": "Utah Domestic Violence Council",

        "url": "https://udvc.org"

    },

    "Vermont": {

        "code": "VT",

        "coalition": "Vermont Network Against Domestic and Sexual Violence",

        "url": "https://vtnetwork.org"

    },

    "Virginia": {

        "code": "VA",

        "coalition": "Virginia Sexual and Domestic Violence Action Alliance",

        "url": "https://vsdvalliance.org"

    },

    "Washington": {

        "code": "WA",

        "coalition": "Washington State Coalition Against Domestic Violence",

        "url": "https://wscadv.org"

    },

    "West Virginia": {

        "code": "WV",

        "coalition": "West Virginia Coalition Against Domestic Violence",

        "url": "https://wvcadv.org"

    },

    "Wisconsin": {

        "code": "WI",

        "coalition": "End Domestic Abuse Wisconsin",

        "url": "https://endabusewi.org"

    },

    "Wyoming": {

        "code": "WY",

        "coalition": "Wyoming Coalition Against Domestic Violence and Sexual Assault",

        "url": "https://wyomingdvsa.org"

    }

}

# ---------------------------------------------------------

# NATIONAL RESOURCE DIRECTORY

# ---------------------------------------------------------

NATIONAL_RESOURCES = [

    {

        "name": "National Domestic Violence Hotline",

        "description": "Domestic violence support, safety planning, and referrals.",

        "phone": "1-800-799-7233",

        "text": "Text START to 88788",

        "url": "https://www.thehotline.org/"

    },

    {

        "name": "RAINN National Sexual Assault Hotline",

        "description": "Sexual assault support and referrals.",

        "phone": "1-800-656-4673",

        "text": "Online support available",

        "url": "https://rainn.org/"

    },

    {

        "name": "211",

        "description": "Local housing, food, healthcare, and social-service referrals.",

        "phone": "Dial 211 where available",

        "text": "Online resource directory",

        "url": "https://www.211.org/"

    },

    {

        "name": "Findhelp",

        "description": "Search for local assistance by ZIP code.",

        "phone": "Online directory",

        "text": "Search by location",

        "url": "https://www.findhelp.org/"

    },

    {

        "name": "988 Suicide and Crisis Lifeline",

        "description": "Mental health and emotional crisis support.",

        "phone": "Call or text 988",

        "text": "Online support available",

        "url": "https://988lifeline.org/"

    }

]

# ---------------------------------------------------------

# API HELPERS

# ---------------------------------------------------------

def api_get(endpoint):

    try:

        response = requests.get(

            f"{NODE_URL}{endpoint}",

            timeout=REQUEST_TIMEOUT

        )

        response.raise_for_status()

        return response.json(), None

    except requests.RequestException as exc:

        return None, str(exc)

    except ValueError:

        return None, "The API returned invalid JSON."

def api_post(endpoint, payload):

    try:

        response = requests.post(

            f"{NODE_URL}{endpoint}",

            json=payload,

            timeout=REQUEST_TIMEOUT

        )

        response.raise_for_status()

        try:

            return response.json(), None

        except ValueError:

            return {"response": response.text}, None

    except requests.RequestException as exc:

        return None, str(exc)

def show_api_error(error):

    st.warning(

        "The network service is not currently reachable. "

        "The resource directory and safety information remain available."

    )

    with st.expander("Technical details"):

        st.code(str(error))

# ---------------------------------------------------------

# HEADER

# ---------------------------------------------------------

st.title("🛡️ Survivors Network")

st.caption(

    "A survivor-centered resource, documentation, and independent "

    "network project."

)

st.markdown(

    f"<p class='small-note'>Project author: {AUTHOR}</p>",

    unsafe_allow_html=True

)

st.divider()

# ---------------------------------------------------------

# ORIGINAL SEVEN-SECTION NAVIGATION

# ---------------------------------------------------------

tabs = st.tabs([

    "Create Entry",

    "Legal Ledger Export",

    "Match Mailbox",

    "Investigator",

    "State Resource Matrix",

    "Safety Guide",

    "Diagnostics"

])

# =========================================================

# 1. CREATE ENTRY

# =========================================================

with tabs[0]:

    st.header("Create Survivor Entry")

    st.write(

        "Create a documented entry associated with your survivor record."

    )

    st.warning(

        "Security notice: the original backend you supplied sends entry "

        "metadata to its API. Its current implementation does not securely "

        "store the notes field and has authentication issues. Do not submit "

        "sensitive personal information until that backend is corrected."

    )

    with st.form("create_entry_form"):

        user_key = st.text_input(

            "Your private user key",

            type="password"

        )

        identity = st.text_input(

            "Private reference identifier",

            help="Avoid entering a legal name or identifying information."

        )

        notes = st.text_area(

            "Entry notes",

            height=150

        )

        col1, col2 = st.columns(2)

        with col1:

            latitude = st.number_input(

                "Latitude",

                value=0.0,

                format="%.6f"

            )

        with col2:

            longitude = st.number_input(

                "Longitude",

                value=0.0,

                format="%.6f"

            )

        submitted = st.form_submit_button(

            "Submit Entry",

            use_container_width=True

        )

    if submitted:

        if not user_key or not identity:

            st.error("A user key and reference identifier are required.")

        else:

            payload = {

                "u_key": user_key,

                "perp_id": identity,

                "notes": notes,

                "coordinates": {

                    "latitude": latitude,

                    "longitude": longitude

                }

            }

            result, error = api_post("/create-entry", payload)

            if error:

                show_api_error(error)

            else:

                st.success("The API accepted the entry request.")

                st.json(result)

# =========================================================

# 2. LEGAL LEDGER EXPORT

# =========================================================

with tabs[1]:

    st.header("Legal Ledger Export")

    st.write(

        "Review and export the ledger records returned by your network."

    )

    if st.button("Load Ledger", key="load_ledger"):

        ledger, error = api_get("/ledger")

        if error:

            show_api_error(error)

        else:

            st.session_state["loaded_ledger"] = ledger

    ledger = st.session_state.get("loaded_ledger")

    if ledger is not None:

        st.subheader("Ledger Records")

        st.json(ledger)

        ledger_bytes = json.dumps(

            ledger,

            indent=2,

            ensure_ascii=False

        ).encode("utf-8")

        st.download_button(

            "Download Ledger JSON",

            data=ledger_bytes,

            file_name="survivors_network_ledger.json",

            mime="application/json",

            use_container_width=True

        )

        if isinstance(ledger, list) and ledger:

            csv_buffer = io.StringIO()

            writer = csv.DictWriter(

                csv_buffer,

                fieldnames=list(ledger[0].keys())

            )

            writer.writeheader()

            writer.writerows(ledger)

            st.download_button(

                "Download Ledger CSV",

                data=csv_buffer.getvalue(),

                file_name="survivors_network_ledger.csv",

                mime="text/csv",

                use_container_width=True

            )

# =========================================================

# 3. MATCH MAILBOX

# =========================================================

with tabs[2]:

    st.header("Match Mailbox")

    st.write(

        "Send or retrieve a message using the match-token mailbox."

    )

    send_tab, receive_tab = st.tabs([

        "Send Message",

        "Retrieve Message"

    ])

    with send_tab:

        with st.form("mailbox_send_form"):

            match_token = st.text_input("Match token")

            message = st.text_area(

                "Message",

                height=150

            )

            send_button = st.form_submit_button(

                "Send Message",

                use_container_width=True

            )

        if send_button:

            if not match_token or not message:

                st.error("A match token and message are required.")

            else:

                result, error = api_post(

                    "/mailbox/send",

                    {

                        "match_token": match_token,

                        "message": message

                    }

                )

                if error:

                    show_api_error(error)

                else:

                    st.success("Mailbox request accepted.")

                    st.json(result)

    with receive_tab:

        retrieve_token = st.text_input(

            "Enter match token",

            key="retrieve_token"

        )

        if st.button("Retrieve Message"):

            if not retrieve_token:

                st.error("Enter a match token.")

            else:

                result, error = api_get(

                    f"/mailbox/{retrieve_token}"

                )

                if error:

                    show_api_error(error)

                else:

                    st.subheader("Mailbox Result")

                    st.json(result)

# =========================================================

# 4. INVESTIGATOR

# =========================================================

with tabs[3]:

    st.header("Research Investigator")

    st.write(

        "Review pattern-analysis results returned by the investigator "

        "component."

    )

    st.info(

        "The investigator should analyze only records that the owner "

        "has authorized it to access."

    )

    if st.button("Run Investigator", key="run_investigator"):

        result, error = api_get("/investigator")

        if error:

            show_api_error(error)

        else:

            st.session_state["investigator_results"] = result

    investigator_results = st.session_state.get(

        "investigator_results"

    )

    if investigator_results is not None:

        st.subheader("Investigator Results")

        st.json(investigator_results)

# =========================================================

# 5. STATE RESOURCE MATRIX — ALL 50 STATES

# =========================================================

with tabs[4]:

    st.header("State Resource Matrix")

    st.write(

        "Find state-level domestic violence coalition information "

        "and national survivor support services."

    )

    st.success(

        f"{len(STATE_RESOURCES)} states included in the directory."

    )

    selected_state = st.selectbox(

        "Choose your state",

        sorted(STATE_RESOURCES.keys())

    )

    state_data = STATE_RESOURCES[selected_state]

    st.subheader(

        f"{selected_state} ({state_data['code']})"

    )

    st.markdown(

        f"""

        <div class="resource-card">

            <h4>{state_data['coalition']}</h4>

            <p>

                <a href="{state_data['url']}" target="_blank">

                    Open state resource website

                </a>

            </p>

        </div>

        """,

        unsafe_allow_html=True

    )

    st.caption(

        "State coalition websites connect survivors with local programs, "

        "shelters, advocacy organizations, and additional referrals. "

        "Availability and services vary by location."

    )

    st.markdown("### Additional local resource searches")

    st.markdown(

        "- [211 — local community services](https://www.211.org/)"

    )

    st.markdown(

        "- [Findhelp — search by ZIP code](https://www.findhelp.org/)"

    )

    st.markdown(

        "- [U.S. Department of Justice — state and territory resources]"

        "(https://www.justice.gov/ovw/resources-victims-and-survivors)"

    )

    st.divider()

    st.subheader("Browse all 50 states")

    search_state = st.text_input(

        "Filter state directory",

        placeholder="Enter a state name..."

    )

    for state_name, resource in sorted(STATE_RESOURCES.items()):

        if search_state.lower() in state_name.lower():

            with st.expander(

                f"{state_name} — {resource['coalition']}"

            ):

                st.write(

                    f"State abbreviation: {resource['code']}"

                )

                st.markdown(

                    f"[Open state coalition website]({resource['url']})"

                )

# =========================================================

# 6. SAFETY GUIDE

# =========================================================

with tabs[5]:

    st.header("Safety Information")

    st.write(

        "A quick-access directory of national support resources."

    )

    st.warning(

        "If you are in immediate danger, contact emergency services "

        "when it is safe and appropriate to do so."

    )

    for resource in NATIONAL_RESOURCES:

        with st.container():

            st.markdown(

                f"""

                <div class="resource-card">

                    <h4>{resource['name']}</h4>

                    <p>{resource['description']}</p>

                    <p><b>Phone:</b> {resource['phone']}</p>

                    <p><b>Text:</b> {resource['text']}</p>

                    <a href="{resource['url']}" target="_blank">

                        Open resource

                    </a>

                </div>

                """,

                unsafe_allow_html=True

            )

    st.divider()

    st.subheader("Digital Safety")

    st.markdown("""

    - Consider whether your device or browser activity is monitored.

    - Use a safer device when researching support options if possible.

    - Be aware that private browsing does not make activity invisible

      to network administrators or monitoring software.

    - Avoid storing sensitive documents on shared devices.

    - Consider the safety of notification previews and email accounts.

    - Do not share passwords or private access keys with other users.

    """)

    st.subheader("Documentation Safety")

    st.markdown("""

    - Keep original evidence files when possible.

    - Record dates and times consistently.

    - Separate direct observations from interpretations.

    - Keep copies of important records in a secure location.

    - Do not assume a downloaded ledger is independently authenticated

      merely because it contains timestamps or hashes.

    """)

# =========================================================

# 7. DIAGNOSTICS

# =========================================================

with tabs[6]:

    st.header("Network Diagnostics")

    st.write(

        "Check connectivity to the configured API and inspect the "

        "network components."

    )

    st.code(f"API endpoint: {NODE_URL}")

    if st.button("Run Connectivity Test"):

        health, error = api_get("/")

        if error:

            st.error("API root endpoint did not respond.")

            with st.expander("Connection details"):

                st.write(error)

        else:

            st.success("API root endpoint responded.")

            st.json(health)

    st.divider()

    st.subheader("Peer Registry")

    if st.button("Load Peer Registry"):

        peers, error = api_get("/peers")

        if error:

            show_api_error(error)

        else:

            st.json(peers)

    st.divider()

    st.subheader("Ledger Status")

    if st.button("Check Ledger Status"):

        ledger, error = api_get("/ledger")

        if error:

            show_api_error(error)

        else:

            if isinstance(ledger, list):

                st.metric("Ledger entries", len(ledger))

            else:

                st.json(ledger)

    st.divider()

    st.subheader("Application Configuration")

    st.write({

        "application": APP_NAME,

        "author": AUTHOR,

        "state_directory_entries": len(STATE_RESOURCES),

        "national_resources": len(NATIONAL_RESOURCES),

        "api_endpoint": NODE_URL,

        "dashboard_mode": "Streamlit",

        "private_record_storage": "Not verified by this dashboard",

        "peer_authentication": "Requires backend implementation",

        "independent_crawlers": "Requires crawler modules"

    })

    st.caption(

        "A successful connectivity test does not establish that the "

        "backend is secure, authenticated, or distributed."

    )

# ---------------------------------------------------------

# FOOTER

# ---------------------------------------------------------

st.divider()

st.caption(

    "Survivors Network | Hope Jones | Survivor-centered resource access"

)
