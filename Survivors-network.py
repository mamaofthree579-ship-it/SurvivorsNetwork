
"""
SURVIVORS NETWORK
Author: Hope Jones

Seven-section Streamlit application:
1. Create Entry
2. Legal Ledger Export
3. Match Mailbox
4. Investigator
5. State Resource Matrix
6. Safety Guide
7. Diagnostics

Run locally:
    streamlit run survivors-network.py

Optional backend:
    Set SURVIVORS_API_URL to the base URL of your authorized API.
    Example: https://your-api.example.com

PRIVACY NOTICE:
The original API design needs additional authentication, authorization,
metadata protection, and secure purge validation before it should be used
for real survivor records. Do not submit identifying or sensitive information
to an unverified backend.
"""

from __future__ import annotations

import os
import io
import json
import csv
import hashlib
import datetime
from typing import Any, Optional
from urllib.parse import quote_plus

import requests
import streamlit as st


# ============================================================
# 1. APPLICATION CONFIGURATION
# ============================================================

APP_NAME = "Survivors Network"
AUTHOR = "Hope Jones"
APP_VERSION = "2.0.0"

REQUEST_TIMEOUT = 12

# Do not assume that a remote Streamlit deployment has a local API.
# Configure this environment variable only when an API is actually deployed.
NODE_URL = os.getenv("SURVIVORS_API_URL", "").strip().rstrip("/")

st.set_page_config(
    page_title=APP_NAME,
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# 2. RESOURCE DIRECTORY DATA — ALL 50 STATES
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
        "description": (
            "Confidential support, safety planning, and referrals."
        ),
    },
    {
        "name": "RAINN National Sexual Assault Hotline",
        "category": "Sexual assault support",
        "phone": "1-800-656-4673",
        "text": "Online chat available",
        "website": "https://rainn.org/",
        "description": (
            "Support and referrals for survivors of sexual violence."
        ),
    },
    {
        "name": "VictimConnect Resource Center",
        "category": "Crime victim support",
        "phone": "1-855-484-2846",
        "text": "Online chat available",
        "website": "https://victimconnect.org/",
        "description": (
            "Information and referrals for victims of crime."
        ),
    },
    {
        "name": "StrongHearts Native Helpline",
        "category": "Native and Indigenous survivor support",
        "phone": "1-844-762-8483",
        "text": "Text support available",
        "website": "https://strongheartshelpline.org/",
        "description": (
            "Culturally specific support for Native American and "
            "Alaska Native survivors."
        ),
    },
    {
        "name": "Childhelp National Child Abuse Hotline",
        "category": "Child abuse support",
        "phone": "1-800-422-4453",
        "text": "Text support available",
        "website": "https://www.childhelphotline.org/",
        "description": (
            "Support and information concerning child abuse."
        ),
    },
    {
        "name": "988 Suicide & Crisis Lifeline",
        "category": "Mental health crisis support",
        "phone": "Call or text 988",
        "text": "988",
        "website": "https://988lifeline.org/",
        "description": (
            "Immediate mental health crisis support."
        ),
    },
    {
        "name": "National Human Trafficking Hotline",
        "category": "Human trafficking support",
        "phone": "1-888-373-7888",
        "text": "Text HELP or INFO to 233733",
        "website": "https://humantraffickinghotline.org/",
        "description": (
            "Support, safety planning, and referrals related to trafficking."
        ),
    },
]

# Official statewide domestic-violence coalition directory.
# The directory links are intended as starting points for local referrals.
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
            "The national coalition directory directs users to "
            "Oklahoma's certified victim-service program listings."
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
# 3. RESOURCE DIRECTORY HELPERS
# ============================================================

def get_state_names() -> list[str]:
    return sorted(STATE_COALITIONS.keys())


def get_state_resource(state: str) -> Optional[dict]:
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


def get_local_resource_links(
    state: str,
    zip_code: str = "",
) -> list[dict]:
    """
    Returns referral and locator links.

    These are directory links, not a guarantee that a provider is
    currently open, accepting clients, or able to provide a specific service.
    """
    state_record = get_state_resource(state)

    links = [
        {
            "name": "HUD Find Shelter",
            "category": "Shelter and housing",
            "url": "https://www.hud.gov/FindShelter",
            "description": (
                "Search for shelters, food assistance, clinics, "
                "and other local support."
            ),
        },
        {
            "name": "211",
            "category": "Community services",
            "url": "https://www.211.org/",
            "description": (
                "Find local community services and referrals."
            ),
        },
        {
            "name": "Findhelp",
            "category": "Community services",
            "url": "https://www.findhelp.org/",
            "description": (
                "Search for local assistance programs."
            ),
        },
        {
            "name": "Legal Services Corporation",
            "category": "Legal assistance",
            "url": "https://www.lsc.gov/about-lsc/what-legal-aid/"
                   "i-need-legal-help",
            "description": (
                "Find federally funded civil legal-aid organizations."
            ),
        },
        {
            "name": "LawHelp",
            "category": "Legal assistance",
            "url": "https://www.lawhelp.org/",
            "description": (
                "Find legal information and civil legal-aid resources."
            ),
        },
        {
            "name": "DOJ Victim and Survivor Resources",
            "category": "Victim services",
            "url": "https://www.justice.gov/ovw/"
                   "resources-victims-and-survivors",
            "description": (
                "Federal victim and survivor resource directory."
            ),
        },
        {
            "name": "DOJ State and Territory Coalitions",
            "category": "Sexual assault and domestic violence coalitions",
            "url": DOJ_STATE_SOURCE,
            "description": (
                "State and territory coalition directory."
            ),
        },
    ]

    if state_record:
        links.insert(
            0,
            {
                "name": state_record["coalition_name"],
                "category": "Statewide domestic violence coalition",
                "url": state_record["coalition_url"],
                "description": (
                    "Statewide coalition and provider referral starting point."
                ),
            },
        )

    # ZIP codes are not transmitted anywhere by this application.
    # They are only shown as optional search context for the user.
    if zip_code.strip():
        links.append(
            {
                "name": "Local provider search guidance",
                "category": "Local search",
                "url": "https://www.211.org/",
                "description": (
                    f"Use ZIP code {zip_code.strip()} when searching "
                    "the linked directory."
                ),
            }
        )

    return links


def get_all_state_records() -> list[dict]:
    records = []

    for state in get_state_names():
        record = get_state_resource(state)
        if record:
            records.append(record)

    return records


def export_directory() -> dict:
    return {
        "application": APP_NAME,
        "directory_version": DIRECTORY_VERSION,
        "last_source_review": LAST_SOURCE_REVIEW,
        "source": NNEDV_SOURCE,
        "states": get_all_state_records(),
        "national_resources": NATIONAL_RESOURCES,
    }


# ============================================================
# 4. API COMMUNICATION
# ============================================================

def api_is_configured() -> bool:
    return bool(NODE_URL)


def api_get(endpoint: str, params: Optional[dict] = None) -> Any:
    if not api_is_configured():
        raise RuntimeError(
            "No API is configured. Set SURVIVORS_API_URL to use "
            "the network backend."
        )

    url = f"{NODE_URL}{endpoint}"

    response = requests.get(
        url,
        params=params,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    if response.content:
        return response.json()

    return {}


def api_post(endpoint: str, payload: dict) -> Any:
    if not api_is_configured():
        raise RuntimeError(
            "No API is configured. Set SURVIVORS_API_URL to use "
            "the network backend."
        )

    url = f"{NODE_URL}{endpoint}"

    response = requests.post(
        url,
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    if response.content:
        return response.json()

    return {}


def show_api_error(error: Exception) -> None:
    st.error(f"Network request could not be completed: {error}")


def api_status_message() -> None:
    if api_is_configured():
        st.success(f"Network API configured: {NODE_URL}")
    else:
        st.info(
            "Local interface mode: no network API is configured. "
            "Resource browsing and directory exports are available, "
            "but network operations require a deployed API."
        )


# ============================================================
# 5. GENERAL DISPLAY HELPERS
# ============================================================

def section_header(title: str, description: str = "") -> None:
    st.subheader(title)

    if description:
        st.caption(description)


def safe_download_json(data: Any, filename: str) -> None:
    payload = json.dumps(
        data,
        indent=2,
        ensure_ascii=False,
        default=str,
    )

    st.download_button(
        label="Download JSON",
        data=payload.encode("utf-8"),
        file_name=filename,
        mime="application/json",
        use_container_width=True,
    )


def make_csv_download(rows: list[dict], filename: str) -> None:
    if not rows:
        st.warning("There are no records to export.")
        return

    output = io.StringIO()

    fieldnames = sorted(
        {
            key
            for row in rows
            for key in row.keys()
        }
    )

    writer = csv.DictWriter(
        output,
        fieldnames=fieldnames,
        extrasaction="ignore",
    )

    writer.writeheader()
    writer.writerows(rows)

    st.download_button(
        "Download CSV",
        data=output.getvalue().encode("utf-8"),
        file_name=filename,
        mime="text/csv",
        use_container_width=True,
    )


def display_records(data: Any) -> None:
    if isinstance(data, list):
        if data:
            st.dataframe(data, use_container_width=True)
        else:
            st.info("No records were returned.")
    elif isinstance(data, dict):
        st.json(data)
    else:
        st.write(data)


# ============================================================
# 6. SIDEBAR AND APPLICATION INTRODUCTION
# ============================================================

st.sidebar.title("🛡️ Survivors Network")
st.sidebar.caption(f"Version {APP_VERSION}")
st.sidebar.caption(f"Author: {AUTHOR}")

st.sidebar.markdown("---")

st.sidebar.markdown(
    """
    **Purpose**

    A survivor-centered resource and record interface designed around
    privacy, user control, and independently operated network components.
    """
)

st.sidebar.markdown("---")

st.sidebar.markdown(
    """
    **Privacy reminder**

    Do not enter identifying information into a network endpoint until
    its authentication, encryption, access controls, and data-retention
    behavior have been independently reviewed.
    """
)

st.title("🛡️ Survivors Network")
st.caption(
    "A survivor-centered resource directory, record interface, "
    "and distributed-network project."
)

api_status_message()

st.markdown("---")


# ============================================================
# 7. ORIGINAL SEVEN-SECTION NAVIGATION
# ============================================================

tabs = st.tabs(
    [
        "Create Entry",
        "Legal Ledger Export",
        "Match Mailbox",
        "Investigator",
        "State Resource Matrix",
        "Safety Guide",
        "Diagnostics",
    ]
)


# ============================================================
# TAB 1 — CREATE ENTRY
# ============================================================

with tabs[0]:
    section_header(
        "Create Entry",
        (
            "Create a record through the configured network API. "
            "Use a non-identifying test record until the backend "
            "security review is complete."
        ),
    )

    st.warning(
        "The original API implementation does not provide adequate "
        "authentication and authorization. Do not submit real names, "
        "addresses, contact details, identifying case information, "
        "or sensitive narrative notes to that backend."
    )

    with st.form("create_entry_form"):
        st.markdown("#### Record information")

        user_key = st.text_input(
            "User key",
            type="password",
            help=(
                "Do not reuse a personal account password. "
                "The original API's key-handling design requires revision."
            ),
        )

        participant_id = st.text_input(
            "Non-identifying participant reference",
            help="Use a random reference, not a real name.",
        )

        notes = st.text_area(
            "Test notes",
            placeholder=(
                "Use non-sensitive test information only until "
                "the backend has been secured."
            ),
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

        confirm_test_data = st.checkbox(
            "I confirm this is test data and contains no identifying "
            "survivor information."
        )

        submitted = st.form_submit_button(
            "Submit Test Entry",
            use_container_width=True,
        )

    if submitted:
        if not api_is_configured():
            st.error(
                "No backend is configured. The entry was not sent."
            )
        elif not user_key.strip() or not participant_id.strip():
            st.error("A user key and participant reference are required.")
        elif not confirm_test_data:
            st.error(
                "Please confirm that you are using non-sensitive test data."
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
                st.success("The API returned a response.")
                display_records(result)
            except Exception as exc:
                show_api_error(exc)


# ============================================================
# TAB 2 — LEGAL LEDGER EXPORT
# ============================================================

with tabs[1]:
    section_header(
        "Legal Ledger Export",
        (
            "Retrieve available ledger records and export them for "
            "independent review."
        ),
    )

    st.info(
        "An exported ledger is a record of what the configured API returns. "
        "It is not, by itself, proof of authenticity, chain of custody, "
        "immutability, or legal admissibility."
    )

    if st.button(
        "Retrieve Ledger",
        key="retrieve_ledger",
        use_container_width=True,
    ):
        try:
            ledger_result = api_get("/ledger")
            st.session_state["ledger_result"] = ledger_result
            st.success("Ledger response received.")
        except Exception as exc:
            show_api_error(exc)

    ledger_result = st.session_state.get("ledger_result")

    if ledger_result is not None:
        display_records(ledger_result)

        if isinstance(ledger_result, list):
            make_csv_download(
                ledger_result,
                "survivors_network_ledger.csv",
            )

        safe_download_json(
            ledger_result,
            "survivors_network_ledger.json",
        )

    st.markdown("#### Export notes")

    st.markdown(
        """
        - Preserve the original downloaded file.
        - Record when and from which endpoint the export was obtained.
        - Keep a separate copy of supporting evidence.
        - Do not assume that a server timestamp proves when an event occurred.
        - Do not treat a hash alone as proof that a record is accurate.
        """
    )


# ============================================================
# TAB 3 — MATCH MAILBOX
# ============================================================

with tabs[2]:
    section_header(
        "Match Mailbox",
        (
            "Send or retrieve a mailbox message using the configured API."
        ),
    )

    st.error(
        "The original mailbox retrieval endpoint is not adequately "
        "protected. Anyone who knows a match token may be able to retrieve "
        "the associated message. Do not use it for real survivor messages "
        "until authentication and authorization are implemented."
    )

    send_tab, receive_tab = st.tabs(
        ["Send Message", "Retrieve Message"]
    )

    with send_tab:
        with st.form("mailbox_send_form"):
            st.markdown("#### Send a test message")

            send_match_token = st.text_input(
                "Match token",
                key="send_match_token",
            )

            recipient_reference = st.text_input(
                "Recipient reference",
                key="recipient_reference",
            )

            message_text = st.text_area(
                "Test message",
                height=130,
                key="message_text",
            )

            confirm_mail_test = st.checkbox(
                "This is a non-sensitive test message."
            )

            send_submitted = st.form_submit_button(
                "Send Test Message",
                use_container_width=True,
            )

        if send_submitted:
            if not api_is_configured():
                st.error("No backend is configured.")
            elif not send_match_token.strip():
                st.error("A match token is required.")
            elif not confirm_mail_test:
                st.error(
                    "Please confirm that this is a non-sensitive test."
                )
            else:
                payload = {
                    "match_token": send_match_token.strip(),
                    "recipient": recipient_reference.strip(),
                    "message": message_text,
                }

                try:
                    result = api_post(
                        "/mailbox/send",
                        payload,
                    )
                    st.success("The API returned a response.")
                    display_records(result)
                except Exception as exc:
                    show_api_error(exc)

    with receive_tab:
        with st.form("mailbox_receive_form"):
            st.markdown("#### Retrieve a test message")

            receive_match_token = st.text_input(
                "Match token",
                key="receive_match_token",
            )

            receive_submitted = st.form_submit_button(
                "Retrieve Test Message",
                use_container_width=True,
            )

        if receive_submitted:
            if not api_is_configured():
                st.error("No backend is configured.")
            elif not receive_match_token.strip():
                st.error("Enter a match token.")
            else:
                try:
                    token = quote_plus(receive_match_token.strip())
                    result = api_get(
                        f"/mailbox/{token}"
                    )
                    display_records(result)
                except Exception as exc:
                    show_api_error(exc)


# ============================================================
# TAB 4 — INVESTIGATOR
# ============================================================

with tabs[3]:
    section_header(
        "Research Investigator",
        (
            "View the investigator output returned by the configured "
            "network service."
        ),
    )

    st.markdown(
        """
        The investigator section is intended to identify possible
        relationships among submitted records. A detected relationship
        should be treated as a research lead, not a verified finding.
        """
    )

    if st.button(
        "Run Investigator",
        key="run_investigator",
        use_container_width=True,
    ):
        try:
            result = api_get("/investigator")
            st.session_state["investigator_result"] = result
            st.success("Investigator response received.")
        except Exception as exc:
            show_api_error(exc)

    investigator_result = st.session_state.get(
        "investigator_result"
    )

    if investigator_result is not None:
        display_records(investigator_result)

        safe_download_json(
            investigator_result,
            "survivors_network_investigator.json",
        )

    st.markdown("#### Interpretation safeguards")

    st.markdown(
        """
        - A pattern match is not proof of identity.
        - A shared location does not establish a relationship.
        - Similar timestamps do not establish coordination.
        - An investigator result should retain its source records.
        - Human review is required before any conclusion or action.
        """ 
    )


# ============================================================
# TAB 5 — STATE RESOURCE MATRIX
# ============================================================

with tabs[4]:
    section_header(
        "State Resource Matrix",
        (
            "Statewide coalition contacts and national directories "
            "for locating local services."
        ),
    )

    st.caption(
        f"Directory version {DIRECTORY_VERSION} | "
        f"Source review date: {LAST_SOURCE_REVIEW}"
    )

    st.markdown(
        """
        The statewide coalition is a starting point for finding local
        organizations. It is not a substitute for checking a provider's
        current service area, availability, eligibility, and contact details.
        """
    )

    state_names = get_state_names()

    selected_state = st.selectbox(
        "Select a state",
        state_names,
        index=state_names.index("West Virginia"),
    )

    zip_code = st.text_input(
        "ZIP code (optional)",
        max_chars=10,
        help=(
            "This is not submitted to the network API. "
            "Use it when searching an external directory."
        ),
    )

    state_record = get_state_resource(selected_state)

    if state_record:
        st.markdown("---")
        st.markdown(f"### {selected_state}")

        st.markdown(
            f"**Statewide coalition:** "
            f"{state_record['coalition_name']}"
        )

        st.markdown(
            f"[Open official coalition website]"
            f"({state_record['coalition_url']})"
        )

        if state_record.get("note"):
            st.info(state_record["note"])

    st.markdown("---")
    st.markdown("### Local and statewide service directories")

    local_links = get_local_resource_links(
        selected_state,
        zip_code,
    )

    for item in local_links:
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
    st.markdown("### Directory sources")

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
    st.markdown("### Export resource directory")

    directory_data = export_directory()

    safe_download_json(
        directory_data,
        "survivors_network_50_state_resource_directory.json",
    )

    st.caption(
        "This export contains statewide coalition records and national "
        "directory links. It does not claim to contain every local shelter, "
        "provider, or county-level service."
    )


# ============================================================
# TAB 6 — SAFETY GUIDE
# ============================================================

with tabs[5]:
    section_header(
        "Safety Guide",
        (
            "Practical privacy and safety reminders for using digital "
            "resources and maintaining records."
        ),
    )

    st.warning(
        "If someone may be monitoring your device, browser, email, "
        "or accounts, consider whether opening or saving resources "
        "could be visible to that person."
    )

    st.markdown("### Digital safety")

    st.markdown(
        """
        - Use a device and account that the other person cannot access,
          when possible.
        - Review shared-device access, browser history, saved passwords,
          location sharing, and account recovery settings.
        - Be aware that private browsing does not make activity invisible
          to network administrators, device monitoring software, or
          account owners.
        - Avoid storing sensitive records in shared cloud folders.
        - Use a strong, unique password for each important account.
        - Enable multifactor authentication when it is safe to do so.
        - Consider whether notifications could reveal sensitive activity.
        """
    )

    st.markdown("### Evidence preservation")

    st.markdown(
        """
        - Preserve original files when possible.
        - Keep a separate working copy for annotations.
        - Record the date and time an item was collected.
        - Preserve source URLs and relevant context.
        - Avoid editing the original image, message, or document.
        - Keep a log of who collected, transferred, or reviewed each item.
        - Do not assume that a screenshot alone establishes authenticity.
        """
    )

    st.markdown("### Record privacy")

    st.markdown(
        """
        - Avoid putting real names in participant-reference fields.
        - Do not place passwords, account recovery answers, or government
          identification numbers in notes.
        - Do not send sensitive records to an unverified endpoint.
        - Confirm who controls the server before uploading information.
        - Understand the retention and deletion behavior of any service.
        """
    )

    st.markdown("### Immediate support")

    st.markdown(
        """
        If you are in immediate danger, contact emergency services
        when it is safe to do so.

        For confidential support and referrals, the State Resource Matrix
        contains national and state-level starting points.
        """
    )

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
        (
            "Inspect the local interface configuration and test the "
            "configured API connection."
        ),
    )

    st.markdown("### Application")

    st.write(f"Application: {APP_NAME}")
    st.write(f"Author: {AUTHOR}")
    st.write(f"Version: {APP_VERSION}")
    st.write(f"Directory version: {DIRECTORY_VERSION}")
    st.write(f"States in directory: {len(STATE_COALITIONS)}")

    expected_states = 50
    actual_states = len(STATE_COALITIONS)

    if actual_states == expected_states:
        st.success("All 50 states are represented in the directory.")
    else:
        st.error(
            f"Directory count mismatch: {actual_states} of "
            f"{expected_states} states."
        )

    st.markdown("### Backend configuration")

    if api_is_configured():
        st.success("API base URL is configured.")
        st.code(NODE_URL, language="text")
    else:
        st.info(
            "No API base URL is configured. Network features are inactive."
        )

    if st.button(
        "Test API Connection",
        key="test_api_connection",
        use_container_width=True,
    ):
        if not api_is_configured():
            st.error(
                "Set SURVIVORS_API_URL before testing the API."
            )
        else:
            try:
                result = api_get("/")
                st.success("The API responded.")
                display_records(result)
            except Exception as exc:
                show_api_error(exc)

    st.markdown("---")
    st.markdown("### Resource directory integrity")

    state_records = get_all_state_records()

    duplicate_abbreviations = []
    seen_abbreviations = set()

    for record in state_records:
        abbreviation = record["abbr"]

        if abbreviation in seen_abbreviations:
            duplicate_abbreviations.append(abbreviation)

        seen_abbreviations.add(abbreviation)

    if duplicate_abbreviations:
        st.error(
            "Duplicate state abbreviations: "
            + ", ".join(duplicate_abbreviations)
        )
    else:
        st.success("No duplicate state abbreviations detected.")

    missing_urls = [
        record["state"]
        for record in state_records
        if not record["coalition_url"].startswith("https://")
    ]

    if missing_urls:
        st.warning(
            "Records with missing or non-HTTPS URLs: "
            + ", ".join(missing_urls)
        )
    else:
        st.success("All state coalition records have HTTPS links.")

    st.markdown("---")
    st.markdown("### Source review")

    st.write(f"Last source review recorded: {LAST_SOURCE_REVIEW}")

    st.markdown(
        """
        The date above identifies the directory's recorded review date.
        It does not mean that every individual provider's phone number,
        service availability, or website was independently tested on that
        date. Check the provider's official source before relying on it.
        """
    )

    st.markdown("---")
    st.markdown("### Current application limitations")

    limitations = [
        "The Streamlit interface does not itself create a decentralized network.",
        "A configured API must provide its own authentication and access controls.",
        "The original API's mailbox endpoint needs authorization before real use.",
        "The original API's purge mechanism needs cryptographic authorization.",
        "A hash or generated CID does not independently prove record authenticity.",
        "The state directory is a referral index, not a complete local-provider database.",
        "A GitHub Pages website cannot run this Python application or host its private database.",
    ]

    for limitation in limitations:
        st.markdown(f"- {limitation}")


# ============================================================
# 8. FOOTER
# ============================================================

st.markdown("---")

st.caption(
    f"{APP_NAME} | Version {APP_VERSION} | "
    f"Project author: {AUTHOR}"
)

st.caption(
    "Resource links are provided as starting points. "
    "Verify current contact information, availability, and eligibility "
    "directly with each provider."
)
