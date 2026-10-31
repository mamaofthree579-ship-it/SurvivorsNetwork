
"""
SURVIVORS NETWORK
Streamlit application

Sections:
1. Create Entry
2. Legal Ledger Export
3. Match Mailbox
4. Investigator
5. State Resource Matrix
6. Safety Guide
7. Diagnostics
8. Resource Crawler

Companion module:
    resource_crawler.py

Run:
    streamlit run survivors-network.py
"""

from __future__ import annotations

import os
import io
import csv
import json
from urllib.parse import quote_plus

import requests
import streamlit as st


# ============================================================
# APPLICATION CONFIGURATION
# ============================================================

APP_VERSION = "2.1.0"
APP_NAME = "Survivors Network"

NODE_URL = os.getenv(
    "SURVIVORS_API_URL",
    ""
).strip().rstrip("/")

REQUEST_TIMEOUT = 12

st.set_page_config(
    page_title=APP_NAME,
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# STATE RESOURCE DIRECTORY
# ============================================================

DIRECTORY_VERSION = "2.0"
LAST_SOURCE_REVIEW = "2026-10-31"

NNEDV_SOURCE = (
    "https://nnedv.org/content/state-u-s-territory-coalitions/"
)

DOJ_STATE_SOURCE = (
    "https://www.justice.gov/ovw/state-and-territory-coalitions"
)

NATIONAL_RESOURCES = [
    {
        "name": "National Domestic Violence Hotline",
        "category": "Domestic violence support",
        "phone": "1-800-799-7233",
        "text": "Text START to 88788",
        "website": "https://www.thehotline.org/",
        "description": "Confidential support, safety planning, and referrals.",
    },
    {
        "name": "RAINN National Sexual Assault Hotline",
        "category": "Sexual assault support",
        "phone": "1-800-656-4673",
        "text": "Online chat available",
        "website": "https://rainn.org/",
        "description": "Support and referrals for survivors of sexual violence.",
    },
    {
        "name": "VictimConnect Resource Center",
        "category": "Crime victim support",
        "phone": "1-855-484-2846",
        "text": "Online chat available",
        "website": "https://victimconnect.org/",
        "description": "Information and referrals for victims of crime.",
    },
    {
        "name": "StrongHearts Native Helpline",
        "category": "Native and Indigenous survivor support",
        "phone": "1-844-762-8483",
        "text": "Text support available",
        "website": "https://strongheartshelpline.org/",
        "description": "Culturally specific survivor support.",
    },
    {
        "name": "Childhelp National Child Abuse Hotline",
        "category": "Child abuse support",
        "phone": "1-800-422-4453",
        "text": "Text support available",
        "website": "https://www.childhelphotline.org/",
        "description": "Support and information concerning child abuse.",
    },
    {
        "name": "988 Suicide & Crisis Lifeline",
        "category": "Mental health crisis support",
        "phone": "Call or text 988",
        "text": "988",
        "website": "https://988lifeline.org/",
        "description": "Immediate mental health crisis support.",
    },
    {
        "name": "National Human Trafficking Hotline",
        "category": "Human trafficking support",
        "phone": "1-888-373-7888",
        "text": "Text HELP or INFO to 233733",
        "website": "https://humantraffickinghotline.org/",
        "description": "Support and referrals related to trafficking.",
    },
]

STATE_COALITIONS = {
    "Alabama": {
        "abbr": "AL",
        "name": "Alabama Coalition Against Domestic Violence",
        "url": "https://www.acadv.org/",
    },
    "Alaska": {
        "abbr": "AK",
        "name": "Alaska Network on Domestic Violence and Sexual Assault",
        "url": "https://andvsa.org/",
    },
    "Arizona": {
        "abbr": "AZ",
        "name": "Arizona Coalition to End Sexual and Domestic Violence",
        "url": "https://www.acesdv.org/",
    },
    "Arkansas": {
        "abbr": "AR",
        "name": "Arkansas Coalition Against Domestic Violence",
        "url": "https://domesticpeace.com/",
    },
    "California": {
        "abbr": "CA",
        "name": "California Partnership to End Domestic Violence",
        "url": "https://www.cpedv.org/",
    },
    "Colorado": {
        "abbr": "CO",
        "name": "Violence Free Colorado",
        "url": "https://violencefreecolorado.org/",
    },
    "Connecticut": {
        "abbr": "CT",
        "name": "Connecticut Coalition Against Domestic Violence",
        "url": "https://www.ctcadv.org/",
    },
    "Delaware": {
        "abbr": "DE",
        "name": "Delaware Coalition Against Domestic Violence",
        "url": "https://dcadv.org/",
    },
    "Florida": {
        "abbr": "FL",
        "name": "Florida Partnership to End Domestic Violence",
        "url": "https://www.fpedv.org/",
    },
    "Georgia": {
        "abbr": "GA",
        "name": "Georgia Coalition Against Domestic Violence",
        "url": "https://gcadv.org/",
    },
    "Hawaii": {
        "abbr": "HI",
        "name": "Hawaii State Coalition Against Domestic Violence",
        "url": "https://hscadv.org/",
    },
    "Idaho": {
        "abbr": "ID",
        "name": "Idaho Coalition Against Sexual and Domestic Violence",
        "url": "https://idvsa.org/",
    },
    "Illinois": {
        "abbr": "IL",
        "name": "Illinois Coalition Against Domestic Violence",
        "url": "https://ilcadv.org/",
    },
    "Indiana": {
        "abbr": "IN",
        "name": "Indiana Coalition Against Domestic Violence",
        "url": "https://icadvinc.org/",
    },
    "Iowa": {
        "abbr": "IA",
        "name": "Iowa Coalition Against Domestic Violence",
        "url": "https://www.icadv.org/",
    },
    "Kansas": {
        "abbr": "KS",
        "name": "Kansas Coalition Against Sexual and Domestic Violence",
        "url": "https://kcsdv.org/",
    },
    "Kentucky": {
        "abbr": "KY",
        "name": "ZeroV",
        "url": "https://zerov.org/",
    },
    "Louisiana": {
        "abbr": "LA",
        "name": "Louisiana Coalition Against Domestic Violence",
        "url": "https://lcadv.org/",
    },
    "Maine": {
        "abbr": "ME",
        "name": "Maine Coalition to End Domestic Violence",
        "url": "https://www.mcedv.org/",
    },
    "Maryland": {
        "abbr": "MD",
        "name": "Maryland Network Against Domestic Violence",
        "url": "https://mnadv.org/",
    },
    "Massachusetts": {
        "abbr": "MA",
        "name": "Jane Doe Inc.",
        "url": "https://www.janedoe.org/",
    },
    "Michigan": {
        "abbr": "MI",
        "name": "Michigan Coalition to End Domestic and Sexual Violence",
        "url": "https://mcedsv.org/",
    },
    "Minnesota": {
        "abbr": "MN",
        "name": "Violence Free Minnesota",
        "url": "https://www.vfmn.org/",
    },
    "Mississippi": {
        "abbr": "MS",
        "name": "Mississippi Coalition Against Domestic Violence",
        "url": "https://mcadv.org/",
    },
    "Missouri": {
        "abbr": "MO",
        "name": "Missouri Coalition Against Domestic and Sexual Violence",
        "url": "https://mocadsv.org/",
    },
    "Montana": {
        "abbr": "MT",
        "name": "Montana Coalition Against Domestic and Sexual Violence",
        "url": "https://mcadsv.com/",
    },
    "Nebraska": {
        "abbr": "NE",
        "name": "Nebraska Coalition to End Sexual and Domestic Violence",
        "url": "https://nebraskacoalition.org/",
    },
    "Nevada": {
        "abbr": "NV",
        "name": "Nevada Coalition to End Domestic and Sexual Violence",
        "url": "https://ncedsv.org/",
    },
    "New Hampshire": {
        "abbr": "NH",
        "name": "New Hampshire Coalition Against Domestic and Sexual Violence",
        "url": "https://www.nhcadsv.org/",
    },
    "New Jersey": {
        "abbr": "NJ",
        "name": "New Jersey Coalition to End Domestic Violence",
        "url": "https://njcedv.org/",
    },
    "New Mexico": {
        "abbr": "NM",
        "name": "New Mexico Coalition Against Domestic Violence",
        "url": "https://nmcadv.org/",
    },
    "New York": {
        "abbr": "NY",
        "name": "New York State Coalition Against Domestic Violence",
        "url": "https://www.nyscadv.org/",
    },
    "North Carolina": {
        "abbr": "NC",
        "name": "North Carolina Coalition Against Domestic Violence",
        "url": "https://nccadv.org/",
    },
    "North Dakota": {
        "abbr": "ND",
        "name": "North Dakota Domestic and Sexual Violence Coalition",
        "url": "https://nddsvc.org/",
    },
    "Ohio": {
        "abbr": "OH",
        "name": "Ohio Domestic Violence Network",
        "url": "https://odvn.org/",
    },
    "Oklahoma": {
        "abbr": "OK",
        "name": "Oklahoma Attorney General Victim Services Directory",
        "url": "https://www.oag.ok.gov/",
        "note": (
            "Use the state's certified victim-service program listings "
            "to locate local services."
        ),
    },
    "Oregon": {
        "abbr": "OR",
        "name": "Oregon Coalition Against Domestic and Sexual Violence",
        "url": "https://www.ocadsv.org/",
    },
    "Pennsylvania": {
        "abbr": "PA",
        "name": "Pennsylvania Coalition Against Domestic Violence",
        "url": "https://www.pcadv.org/",
    },
    "Rhode Island": {
        "abbr": "RI",
        "name": "Rhode Island Coalition Against Domestic Violence",
        "url": "https://ricadv.org/",
    },
    "South Carolina": {
        "abbr": "SC",
        "name": "South Carolina Coalition Against Domestic Violence and Sexual Assault",
        "url": "https://sccadvasa.org/",
    },
    "South Dakota": {
        "abbr": "SD",
        "name": "South Dakota Network Against Family Violence and Sexual Assault",
        "url": "https://sdnafvsa.com/",
    },
    "Tennessee": {
        "abbr": "TN",
        "name": "Tennessee Coalition to End Domestic and Sexual Violence",
        "url": "https://tncoalition.org/",
    },
    "Texas": {
        "abbr": "TX",
        "name": "Texas Council on Family Violence",
        "url": "https://tcfv.org/",
    },
    "Utah": {
        "abbr": "UT",
        "name": "Utah Domestic Violence Coalition",
        "url": "https://udvc.org/",
    },
    "Vermont": {
        "abbr": "VT",
        "name": "Vermont Network Against Domestic and Sexual Violence",
        "url": "https://vtnetwork.org/",
    },
    "Virginia": {
        "abbr": "VA",
        "name": "Virginia Sexual and Domestic Violence Action Alliance",
        "url": "https://vsdvalliance.org/",
    },
    "Washington": {
        "abbr": "WA",
        "name": "Washington State Coalition Against Domestic Violence",
        "url": "https://wscadv.org/",
    },
    "West Virginia": {
        "abbr": "WV",
        "name": "West Virginia Coalition Against Domestic Violence",
        "url": "https://wvcadv.org/",
    },
    "Wisconsin": {
        "abbr": "WI",
        "name": "End Domestic Abuse Wisconsin",
        "url": "https://www.endabusewi.org/",
    },
    "Wyoming": {
        "abbr": "WY",
        "name": "Wyoming Coalition Against Domestic Violence and Sexual Assault",
        "url": "https://wyomingdvsa.org/",
    },
}


# ============================================================
# DIRECTORY FUNCTIONS
# ============================================================

def get_state_names():
    return sorted(STATE_COALITIONS.keys())


def get_state_resource(state):
    record = STATE_COALITIONS.get(state)

    if not record:
        return None

    return {
        "state": state,
        "abbr": record["abbr"],
        "coalition_name": record["name"],
        "coalition_url": record["url"],
        "note": record.get("note", ""),
    }


def get_local_resource_links(state, zip_code=""):
    record = get_state_resource(state)

    links = [
        {
            "name": "HUD Find Shelter",
            "category": "Shelter and housing",
            "url": "https://www.hud.gov/FindShelter",
            "description": "Search for shelters, food assistance, clinics, and other local support.",
        },
        {
            "name": "211",
            "category": "Community services",
            "url": "https://www.211.org/",
            "description": "Find local community services and referrals.",
        },
        {
            "name": "Findhelp",
            "category": "Community services",
            "url": "https://www.findhelp.org/",
            "description": "Search for local assistance programs.",
        },
        {
            "name": "Legal Services Corporation",
            "category": "Legal assistance",
            "url": "https://www.lsc.gov/about-lsc/what-legal-aid/i-need-legal-help",
            "description": "Find federally funded civil legal-aid organizations.",
        },
        {
            "name": "LawHelp",
            "category": "Legal assistance",
            "url": "https://www.lawhelp.org/",
            "description": "Find legal information and civil legal-aid resources.",
        },
        {
            "name": "DOJ Victim and Survivor Resources",
            "category": "Victim services",
            "url": "https://www.justice.gov/ovw/resources-victims-and-survivors",
            "description": "Federal victim and survivor resource directory.",
        },
        {
            "name": "DOJ State and Territory Coalitions",
            "category": "State and territory coalitions",
            "url": DOJ_STATE_SOURCE,
            "description": "State and territory coalition directory.",
        },
    ]

    if record:
        links.insert(
            0,
            {
                "name": record["coalition_name"],
                "category": "Statewide coalition",
                "url": record["coalition_url"],
                "description": "Statewide coalition and local-provider referral starting point.",
            },
        )

    if zip_code.strip():
        links.append(
            {
                "name": "ZIP code search guidance",
                "category": "Local search",
                "url": "https://www.211.org/",
                "description": (
                    f"Use ZIP code {zip_code.strip()} in the external "
                    "directory search."
                ),
            }
        )

    return links


def get_all_state_records():
    return [
        get_state_resource(state)
        for state in get_state_names()
    ]


def export_directory():
    return {
        "application": APP_NAME,
        "directory_version": DIRECTORY_VERSION,
        "last_source_review": LAST_SOURCE_REVIEW,
        "source": NNEDV_SOURCE,
        "states": get_all_state_records(),
        "national_resources": NATIONAL_RESOURCES,
    }


# ============================================================
# API COMMUNICATION
# ============================================================

def api_is_configured():
    return bool(NODE_URL)


def api_get(endpoint, params=None):
    if not api_is_configured():
        raise RuntimeError("No API is configured.")

    response = requests.get(
        f"{NODE_URL}{endpoint}",
        params=params,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    if response.content:
        return response.json()

    return {}


def api_post(endpoint, payload):
    if not api_is_configured():
        raise RuntimeError("No API is configured.")

    response = requests.post(
        f"{NODE_URL}{endpoint}",
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    if response.content:
        return response.json()

    return {}


def api_status_message():
    if api_is_configured():
        st.success("Network API configured.")
    else:
        st.info(
            "Local interface mode. Resource browsing and exports are "
            "available; network functions require an API endpoint."
        )


# ============================================================
# GENERAL HELPERS
# ============================================================

def section_header(title, description=""):
    st.subheader(title)

    if description:
        st.caption(description)


def safe_download_json(data, filename):
    payload = json.dumps(
        data,
        indent=2,
        ensure_ascii=False,
        default=str,
    )

    st.download_button(
        "Download JSON",
        data=payload.encode("utf-8"),
        file_name=filename,
        mime="application/json",
        use_container_width=True,
    )


def make_csv_download(rows, filename):
    if not rows:
        st.info("No records available to export.")
        return

    output = io.StringIO()

    fields = sorted({
        key
        for row in rows
        for key in row.keys()
    })

    writer = csv.DictWriter(
        output,
        fieldnames=fields,
        extrasaction="ignore",
    )

    writer.writeheader()
    writer.writerows(rows)

    st.download_button(
        "Download CSV",
        output.getvalue().encode("utf-8"),
        file_name=filename,
        mime="text/csv",
        use_container_width=True,
    )


def display_records(data):
    if isinstance(data, list):
        if data:
            st.dataframe(data, use_container_width=True)
        else:
            st.info("No records returned.")
    elif isinstance(data, dict):
        st.json(data)
    else:
        st.write(data)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("🛡️ Survivors Network")
st.sidebar.caption(f"Version {APP_VERSION}")

st.sidebar.markdown("---")

st.sidebar.markdown(
    """
    **Project components**

    - Survivor-controlled records
    - Distributed network architecture
    - Independent resource crawlers
    - Resource verification
    - Legal record export
    - State and national support directory
    """
)

st.sidebar.markdown("---")

st.title("🛡️ Survivors Network")

st.caption(
    "Survivor-centered resources, records, and network tools."
)

api_status_message()

st.markdown("---")


# ============================================================
# NAVIGATION — EIGHT SECTIONS
# ============================================================

tabs = st.tabs([
    "Create Entry",
    "Legal Ledger Export",
    "Match Mailbox",
    "Investigator",
    "State Resource Matrix",
    "Safety Guide",
    "Diagnostics",
    "Resource Crawler",
])


# ============================================================
# TAB 1 — CREATE ENTRY
# ============================================================

with tabs[0]:
    section_header(
        "Create Entry",
        "Create a record through the configured network API.",
    )

    with st.form("create_entry_form"):
        st.markdown("#### Record information")

        user_key = st.text_input(
            "User key",
            type="password",
        )

        participant_id = st.text_input(
            "Participant reference",
            help="Use a non-identifying reference.",
        )

        notes = st.text_area(
            "Record notes",
            height=120,
        )

        col1, col2 = st.columns(2)

        with col1:
            latitude = st.number_input(
                "Latitude",
                min_value=-90.0,
                max_value=90.0,
                value=0.0,
                step=0.0001,
                format="%.4f",
            )

        with col2:
            longitude = st.number_input(
                "Longitude",
                min_value=-180.0,
                max_value=180.0,
                value=0.0,
                step=0.0001,
                format="%.4f",
            )

        test_confirmation = st.checkbox(
            "I confirm this is non-sensitive test data."
        )

        submitted = st.form_submit_button(
            "Submit Entry",
            use_container_width=True,
        )

    if submitted:
        if not api_is_configured():
            st.error("No API is configured.")
        elif not user_key.strip() or not participant_id.strip():
            st.error("User key and participant reference are required.")
        elif not test_confirmation:
            st.error(
                "Confirm that the submitted information is non-sensitive "
                "test data before using this original API."
            )
        else:
            payload = {
                "u_key": user_key,
                "perp_id": participant_id,
                "notes": notes,
                "coordinates": [
                    float(latitude),
                    float(longitude),
                ],
            }

            try:
                result = api_post("/create-entry", payload)
                st.success("Entry submitted.")
                display_records(result)
            except Exception as exc:
                st.error(f"Request failed: {exc}")


# ============================================================
# TAB 2 — LEGAL LEDGER EXPORT
# ============================================================

with tabs[1]:
    section_header(
        "Legal Ledger Export",
        "Retrieve and export records returned by the network API.",
    )

    if st.button(
        "Retrieve Ledger",
        use_container_width=True,
    ):
        try:
            result = api_get("/ledger")
            st.session_state["ledger_result"] = result
            st.success("Ledger retrieved.")
        except Exception as exc:
            st.error(f"Ledger retrieval failed: {exc}")

    ledger = st.session_state.get("ledger_result")

    if ledger is not None:
        display_records(ledger)

        if isinstance(ledger, list):
            make_csv_download(
                ledger,
                "survivors_network_ledger.csv",
            )

        safe_download_json(
            ledger,
            "survivors_network_ledger.json",
        )

    st.markdown("#### Record preservation")

    st.markdown(
        """
        - Preserve original downloaded records.
        - Keep supporting evidence separately.
        - Record collection dates and source information.
        - Maintain a record of transfers and access.
        - Do not treat a hash alone as proof of authenticity.
        """
    )


# ============================================================
# TAB 3 — MATCH MAILBOX
# ============================================================

with tabs[2]:
    section_header(
        "Match Mailbox",
        "Send and retrieve messages through the configured API.",
    )

    send_tab, receive_tab = st.tabs([
        "Send Message",
        "Retrieve Message",
    ])

    with send_tab:
        with st.form("mailbox_send_form"):
            match_token = st.text_input(
                "Match token",
            )

            recipient_reference = st.text_input(
                "Recipient reference",
            )

            message_text = st.text_area(
                "Message",
                height=130,
            )

            confirm_test = st.checkbox(
                "This is a non-sensitive test message."
            )

            send_submitted = st.form_submit_button(
                "Send Message",
                use_container_width=True,
            )

        if send_submitted:
            if not api_is_configured():
                st.error("No API is configured.")
            elif not match_token.strip():
                st.error("A match token is required.")
            elif not confirm_test:
                st.error("Use non-sensitive test messages only.")
            else:
                payload = {
                    "match_token": match_token.strip(),
                    "recipient": recipient_reference.strip(),
                    "message": message_text,
                }

                try:
                    result = api_post(
                        "/mailbox/send",
                        payload,
                    )
                    display_records(result)
                except Exception as exc:
                    st.error(f"Message submission failed: {exc}")

    with receive_tab:
        with st.form("mailbox_receive_form"):
            retrieve_token = st.text_input(
                "Match token",
            )

            retrieve_submitted = st.form_submit_button(
                "Retrieve Message",
                use_container_width=True,
            )

        if retrieve_submitted:
            if not api_is_configured():
                st.error("No API is configured.")
            elif not retrieve_token.strip():
                st.error("Enter a match token.")
            else:
                try:
                    encoded_token = quote_plus(
                        retrieve_token.strip()
                    )

                    result = api_get(
                        f"/mailbox/{encoded_token}"
                    )

                    display_records(result)

                except Exception as exc:
                    st.error(f"Message retrieval failed: {exc}")


# ============================================================
# TAB 4 — INVESTIGATOR
# ============================================================

with tabs[3]:
    section_header(
        "Investigator",
        "Review possible patterns identified by the network investigator.",
    )

    st.markdown(
        """
        Investigator output is a research lead. A detected match or
        relationship is not automatically proof of identity, coordination,
        or causation.
        """
    )

    if st.button(
        "Run Investigator",
        use_container_width=True,
    ):
        try:
            result = api_get("/investigator")
            st.session_state["investigator_result"] = result
            st.success("Investigator response received.")
        except Exception as exc:
            st.error(f"Investigator request failed: {exc}")

    investigator = st.session_state.get(
        "investigator_result"
    )

    if investigator is not None:
        display_records(investigator)

        safe_download_json(
            investigator,
            "survivors_network_investigator.json",
        )

    st.markdown("#### Review standards")

    st.markdown(
        """
        - Preserve the source records supporting each detected pattern.
        - Distinguish correlation from verified relationships.
        - Record uncertainty and alternative explanations.
        - Require human review before taking action.
        """ 
    )


# ============================================================
# TAB 5 — STATE RESOURCE MATRIX
# ============================================================

with tabs[4]:
    section_header(
        "State Resource Matrix",
        "Statewide coalition links and national service directories.",
    )

    st.caption(
        f"Directory version {DIRECTORY_VERSION} | "
        f"Recorded source review: {LAST_SOURCE_REVIEW}"
    )

    selected_state = st.selectbox(
        "Select state",
        get_state_names(),
        index=get_state_names().index("West Virginia"),
    )

    zip_code = st.text_input(
        "ZIP code (optional)",
        max_chars=10,
    )

    state_record = get_state_resource(selected_state)

    if state_record:
        st.markdown(f"### {selected_state}")

        st.markdown(
            f"**{state_record['coalition_name']}**"
        )

        st.markdown(
            f"[Open official coalition website]"
            f"({state_record['coalition_url']})"
        )

        if state_record["note"]:
            st.info(state_record["note"])

    st.markdown("---")
    st.markdown("### Local and statewide resources")

    for item in get_local_resource_links(
        selected_state,
        zip_code,
    ):
        with st.container(border=True):
            st.markdown(f"**{item['name']}**")
            st.caption(item["category"])
            st.write(item["description"])
            st.markdown(f"[Open resource]({item['url']})")

    st.markdown("---")
    st.markdown("### National support contacts")

    for resource in NATIONAL_RESOURCES:
        with st.container(border=True):
            st.markdown(f"**{resource['name']}**")
            st.caption(resource["category"])

            if resource.get("phone"):
                st.write(f"Phone: {resource['phone']}")

            if resource.get("text"):
                st.write(f"Text: {resource['text']}")

            st.write(resource["description"])

            st.markdown(
                f"[Open official resource]({resource['website']})"
            )

    st.markdown("---")
    st.markdown("### Directory source references")

    st.markdown(
        f"- [NNEDV State and U.S. Territory Coalitions]({NNEDV_SOURCE})"
    )

    st.markdown(
        f"- [DOJ State and Territory Coalitions]({DOJ_STATE_SOURCE})"
    )

    st.markdown(
        "- [Legal Services Corporation locator]"
        "(https://www.lsc.gov/about-lsc/what-legal-aid/i-need-legal-help)"
    )

    st.markdown(
        "- [HUD Find Shelter](https://www.hud.gov/FindShelter)"
    )

    st.markdown(
        "- [211](https://www.211.org/)"
    )

    st.markdown(
        "- [Findhelp](https://www.findhelp.org/)"
    )

    st.markdown("---")
    st.markdown("### Export directory")

    safe_download_json(
        export_directory(),
        "survivors_network_50_state_resource_directory.json",
    )


# ============================================================
# TAB 6 — SAFETY GUIDE
# ============================================================

with tabs[5]:
    section_header(
        "Safety Guide",
        "Digital privacy, evidence preservation, and resource access.",
    )

    st.markdown("### Digital safety")

    st.markdown(
        """
        - Consider whether your device or accounts are monitored.
        - Review shared-device access and account recovery settings.
        - Review location-sharing permissions.
        - Be aware that private browsing does not hide activity from
          device monitoring software or network administrators.
        - Avoid shared cloud folders for sensitive records.
        - Use unique passwords and multifactor authentication when safe.
        - Consider whether notifications could reveal sensitive activity.
        """
    )

    st.markdown("### Evidence preservation")

    st.markdown(
        """
        - Preserve original files whenever possible.
        - Keep separate working copies for annotations.
        - Record collection dates and source URLs.
        - Preserve surrounding context.
        - Maintain a transfer and access log.
        - Do not assume screenshots alone establish authenticity.
        """
    )

    st.markdown("### Data protection")

    st.markdown(
        """
        - Avoid real names in participant-reference fields.
        - Do not enter passwords or account recovery answers into notes.
        - Confirm who controls a server before uploading records.
        - Understand data retention and deletion procedures.
        - Do not send sensitive information to unverified endpoints.
        """
    )

    st.markdown("### Support")

    st.markdown(
        "[National Domestic Violence Hotline](https://www.thehotline.org/)"
    )

    st.markdown(
        "[RAINN](https://rainn.org/)"
    )

    st.markdown(
        "[VictimConnect](https://victimconnect.org/)"
    )


# ============================================================
# TAB 7 — DIAGNOSTICS
# ============================================================

with tabs[6]:
    section_header(
        "Diagnostics",
        "Application, directory, and API configuration checks.",
    )

    st.markdown("### Application")

    st.write("Application:", APP_NAME)
    st.write("Version:", APP_VERSION)
    st.write("Directory version:", DIRECTORY_VERSION)
    st.write("State count:", len(STATE_COALITIONS))

    if len(STATE_COALITIONS) == 50:
        st.success("All 50 states are represented.")
    else:
        st.error(
            f"Expected 50 states; found {len(STATE_COALITIONS)}."
        )

    abbreviations = [
        record["abbr"]
        for record in STATE_COALITIONS.values()
    ]

    if len(abbreviations) == len(set(abbreviations)):
        st.success("No duplicate state abbreviations.")
    else:
        st.error("Duplicate state abbreviations detected.")

    missing_urls = [
        state
        for state, record in STATE_COALITIONS.items()
        if not record["url"].startswith("https://")
    ]

    if missing_urls:
        st.warning(
            "Non-HTTPS resource links: "
            + ", ".join(missing_urls)
        )
    else:
        st.success("All state coalition links use HTTPS.")

    st.markdown("---")
    st.markdown("### API")

    if api_is_configured():
        st.success("API base URL is configured.")
    else:
        st.info("No API base URL is configured.")

    if st.button(
        "Test API Connection",
        use_container_width=True,
    ):
        if not api_is_configured():
            st.error("Configure SURVIVORS_API_URL first.")
        else:
            try:
                result = api_get("/")
                st.success("API responded.")
                display_records(result)
            except Exception as exc:
                st.error(f"Connection failed: {exc}")

    st.markdown("---")
    st.markdown("### Crawler module")

    try:
        import resource_crawler

        st.success(
            f"Resource crawler loaded: "
            f"{resource_crawler.CRAWLER_VERSION}"
        )

    except ImportError:
        st.error(
            "resource_crawler.py is not available in the project directory."
        )

    st.markdown("---")
    st.markdown("### Project components")

    components = [
        "Create Entry",
        "Legal Ledger Export",
        "Match Mailbox",
        "Investigator",
        "50-State Resource Matrix",
        "Safety Guide",
        "Diagnostics",
        "Independent Resource Crawler",
        "Human Review Queue",
    ]

    for component in components:
        st.write(f"✓ {component}")


# ============================================================
# TAB 8 — INDEPENDENT RESOURCE CRAWLER
# ============================================================

with tabs[7]:
    section_header(
        "Independent Resource Crawler",
        "Monitor public resource sources and review detected changes.",
    )

    try:
        from resource_crawler import (
            run_crawl,
            get_crawler_status,
            get_pending_reviews,
            get_all_reviews,
            review_change,
            export_review_queue,
            build_source_registry,
        )

        crawler_available = True

    except ImportError as exc:
        crawler_available = False
        st.error(
            "The crawler module could not be loaded. "
            "Add resource_crawler.py to the repository."
        )
        st.code(str(exc))

    if crawler_available:
        st.markdown("### Crawler status")

        status = get_crawler_status()

        col1, col2, col3, col4 = st.columns(4)

        col1.metric(
            "Sources recorded",
            status["sources_with_snapshots"],
        )

        col2.metric(
            "Pending review",
            status["pending_reviews"],
        )

        col3.metric(
            "Approved",
            status["approved_reviews"],
        )

        col4.metric(
            "Rejected",
            status["rejected_reviews"],
        )

        st.markdown("---")
        st.markdown("### Run resource check")

        state_sources = {
            state: {
                "abbr": record["abbr"],
                "name": record["name"],
                "url": record["url"],
            }
            for state, record in STATE_COALITIONS.items()
        }

        crawl_scope = st.radio(
            "Crawl scope",
            [
                "All state and national sources",
                "State coalition sources only",
                "National sources only",
            ],
        )

        if st.button(
            "Start Resource Crawl",
            use_container_width=True,
            key="start_resource_crawl",
        ):
            all_sources = build_source_registry(
                state_sources
            )

            if crawl_scope == "State coalition sources only":
                selected_ids = [
                    source["source_id"]
                    for source in all_sources
                    if source["source_id"].startswith("state_")
                ]

            elif crawl_scope == "National sources only":
                selected_ids = [
                    source["source_id"]
                    for source in all_sources
                    if source["source_id"].startswith("national_")
                ]

            else:
                selected_ids = None

            with st.spinner(
                "Checking registered public resource websites..."
            ):
                try:
                    result = run_crawl(
                        state_coalitions=state_sources,
                        selected_source_ids=selected_ids,
                    )

                    st.session_state["last_crawl_result"] = result

                    st.success("Resource crawl completed.")

                except Exception as exc:
                    st.error(f"Crawl failed: {exc}")

        last_crawl = st.session_state.get(
            "last_crawl_result"
        )

        if last_crawl:
            st.markdown("### Latest crawl results")

            col1, col2, col3 = st.columns(3)

            col1.metric(
                "Checked",
                last_crawl["sources_attempted"],
            )

            col2.metric(
                "Changed",
                last_crawl["changed"],
            )

            col3.metric(
                "Errors",
                last_crawl["errors"],
            )

            st.dataframe(
                last_crawl["results"],
                use_container_width=True,
            )

            safe_download_json(
                last_crawl,
                "resource_crawl_results.json",
            )

        st.markdown("---")
        st.markdown("### Pending human review")

        pending = get_pending_reviews()

        if not pending:
            st.success(
                "There are no pending resource changes."
            )

        for item in pending:
            with st.expander(
                f"{item['source_name']} — {item['change_type']}"
            ):
                st.write("Source:", item["source_url"])

                st.write(
                    "Location:",
                    item.get("state") or "National",
                )

                st.write(
                    "Detected:",
                    item["detected_at"],
                )

                st.markdown("**Previous content**")

                st.text(
                    item.get("previous_excerpt")
                    or "No previous snapshot."
                )

                st.markdown("**Current content**")

                st.text(
                    item.get("current_excerpt", "")
                )

                st.caption(
                    "A page change is not necessarily a change in "
                    "provider contact information. Verify the specific "
                    "resource before approving an update."
                )

                reviewer_note = st.text_area(
                    "Review note",
                    key=f"review_note_{item['change_id']}",
                )

                col1, col2 = st.columns(2)

                with col1:
                    if st.button(
                        "Approve for manual update",
                        key=f"approve_{item['change_id']}",
                    ):
                        try:
                            review_change(
                                storage_dir="resource_crawler_data",
                                change_id=item["change_id"],
                                decision="approved",
                                reviewer_note=reviewer_note,
                            )

                            st.success(
                                "Review approved. "
                                "The directory itself was not changed."
                            )

                            st.rerun()

                        except Exception as exc:
                            st.error(str(exc))

                with col2:
                    if st.button(
                        "Reject",
                        key=f"reject_{item['change_id']}",
                    ):
                        try:
                            review_change(
                                storage_dir="resource_crawler_data",
                                change_id=item["change_id"],
                                decision="rejected",
                                reviewer_note=reviewer_note,
                            )

                            st.success("Review rejected.")
                            st.rerun()

                        except Exception as exc:
                            st.error(str(exc))

        st.markdown("---")
        st.markdown("### Review history")

        all_reviews = get_all_reviews()

        if all_reviews:
            st.dataframe(
                all_reviews,
                use_container_width=True,
            )

        safe_download_json(
            export_review_queue(),
            "resource_review_queue.json",
        )


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.caption(
    f"{APP_NAME} | Version {APP_VERSION}"
)
