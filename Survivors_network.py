

"""

SURVIVORS NETWORK

=================

Main Streamlit application.

Application sections:

1. Create Entry

2. Legal Ledger Export

3. Match Mailbox

4. Investigator

5. State Resource Matrix

6. Safety Guide

7. Diagnostics

8. Automated Resource Crawler

Companion modules:

- verify.py

- resource_crawler.py

- directory_updates.py

The resource crawler and directory intelligence system are

independent of survivor records.

The resource directory is maintained locally and can be exported.

Private survivor records must not be sent to an untrusted remote API.

"""

from __future__ import annotations

import csv

import io

import json

import os

import re

import time

from datetime import datetime, timezone

from pathlib import Path

from typing import Any, Optional

import pandas as pd

import requests

import streamlit as st

import os
import streamlit as st

QUICK_EXIT_URL = os.getenv(
    "SURVIVORS_QUICK_EXIT_URL",
    "https://www.cnn.com/"
)

st.markdown(
    """
    <style>
    .quick-exit-container {
        display: flex;
        justify-content: flex-end;
        margin-bottom: 12px;
    }
    .quick-exit-button {
        display: inline-block;
        background: #8f2f38;
        color: white !important;
        padding: 12px 22px;
        border-radius: 9px;
        font-weight: 700;
        text-decoration: none !important;
        border: 1px solid #76252d;
    }
    .quick-exit-button:hover {
        background: #76252d;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown(
    f"""
    <div class="quick-exit-container">
        <a class="quick-exit-button"
           href="{QUICK_EXIT_URL}"
           target="_top"
           rel="noopener noreferrer">
           Quick Exit
        </a>
    </div>
    """,
    unsafe_allow_html=True
)
# =========================================================

# STREAMLIT CONFIGURATION

# =========================================================

st.set_page_config(

    page_title="Survivors Network",

    page_icon="🛡️",

    layout="wide",

    initial_sidebar_state="expanded",

)

# =========================================================

# APPLICATION CONFIGURATION

# =========================================================

APP_VERSION = "2.0.0"

DATA_DIR = Path("resource_crawler_data")

DATA_DIR.mkdir(

    parents=True,

    exist_ok=True,

)

DIRECTORY_FILE = DATA_DIR / "state_resource_directory.json"

API_URL = os.getenv(

    "SURVIVORS_API_URL",

    "",

).strip().rstrip("/")

REQUEST_TIMEOUT = 15

# =========================================================

# OFFICIAL 50-STATE RESOURCE DIRECTORY

# =========================================================

STATE_DIRECTORY_SEED = {

    "AL": {

        "abbr": "AL",

        "name": "Alabama",

        "coalition": "Alabama Coalition Against Domestic Violence",

        "url": "https://acadv.org",

        "resource_type": "Domestic Violence Coalition",

    },

    "AK": {

        "abbr": "AK",

        "name": "Alaska",

        "coalition": "Alaska Network on Domestic Violence and Sexual Assault",

        "url": "https://andvsa.org",

        "resource_type": "Domestic Violence and Sexual Assault Coalition",

    },

    "AZ": {

        "abbr": "AZ",

        "name": "Arizona",

        "coalition": "Arizona Coalition to End Sexual and Domestic Violence",

        "url": "https://www.acesdv.org",

        "resource_type": "Domestic Violence and Sexual Assault Coalition",

    },

    "AR": {

        "abbr": "AR",

        "name": "Arkansas",

        "coalition": "Arkansas Coalition Against Domestic Violence",

        "url": "https://domesticpeace.com",

        "resource_type": "Domestic Violence Coalition",

    },

    "CA": {

        "abbr": "CA",

        "name": "California",

        "coalition": "California Partnership to End Domestic Violence",

        "url": "https://cpedv.org",

        "resource_type": "Domestic Violence Coalition",

    },

    "CO": {

        "abbr": "CO",

        "name": "Colorado",

        "coalition": "Violence Free Colorado",

        "url": "https://violencefreecolorado.org",

        "resource_type": "Domestic Violence Coalition",

    },

    "CT": {

        "abbr": "CT",

        "name": "Connecticut",

        "coalition": "Connecticut Coalition Against Domestic Violence",

        "url": "https://www.ctcadv.org",

        "resource_type": "Domestic Violence Coalition",

    },

    "DE": {

        "abbr": "DE",

        "name": "Delaware",

        "coalition": "Delaware Coalition Against Domestic Violence",

        "url": "https://dcadv.org",

        "resource_type": "Domestic Violence Coalition",

    },

    "FL": {

        "abbr": "FL",

        "name": "Florida",

        "coalition": "Florida Partnership to End Domestic Violence",

        "url": "https://www.fpedv.org",

        "resource_type": "Domestic Violence Coalition",

    },

    "GA": {

        "abbr": "GA",

        "name": "Georgia",

        "coalition": "Georgia Coalition Against Domestic Violence",

        "url": "https://gcadv.org",

        "resource_type": "Domestic Violence Coalition",

    },

    "HI": {

        "abbr": "HI",

        "name": "Hawaii",

        "coalition": "Hawaii State Coalition Against Domestic Violence",

        "url": "https://hscadv.org",

        "resource_type": "Domestic Violence Coalition",

    },

    "ID": {

        "abbr": "ID",

        "name": "Idaho",

        "coalition": "Idaho Coalition Against Sexual and Domestic Violence",

        "url": "https://idahocoalition.org",

        "resource_type": "Domestic Violence and Sexual Assault Coalition",

    },

    "IL": {

        "abbr": "IL",

        "name": "Illinois",

        "coalition": "Illinois Coalition Against Domestic Violence",

        "url": "https://ilcadv.org",

        "resource_type": "Domestic Violence Coalition",

    },

    "IN": {

        "abbr": "IN",

        "name": "Indiana",

        "coalition": "Indiana Coalition Against Domestic Violence",

        "url": "https://icadvinc.org",

        "resource_type": "Domestic Violence Coalition",

    },

    "IA": {

        "abbr": "IA",

        "name": "Iowa",

        "coalition": "Iowa Coalition Against Domestic Violence",

        "url": "https://icadv.org",

        "resource_type": "Domestic Violence Coalition",

    },

    "KS": {

        "abbr": "KS",

        "name": "Kansas",

        "coalition": "Kansas Coalition Against Sexual and Domestic Violence",

        "url": "https://kcsdv.org",

        "resource_type": "Domestic Violence and Sexual Assault Coalition",

    },

    "KY": {

        "abbr": "KY",

        "name": "Kentucky",

        "coalition": "ZeroV",

        "url": "https://zerov.org",

        "resource_type": "Domestic Violence Coalition",

    },

    "LA": {

        "abbr": "LA",

        "name": "Louisiana",

        "coalition": "Louisiana Coalition Against Domestic Violence",

        "url": "https://lcadv.org",

        "resource_type": "Domestic Violence Coalition",

    },

    "ME": {

        "abbr": "ME",

        "name": "Maine",

        "coalition": "Maine Coalition to End Domestic Violence",

        "url": "https://mcedv.org",

        "resource_type": "Domestic Violence Coalition",

    },

    "MD": {

        "abbr": "MD",

        "name": "Maryland",

        "coalition": "Maryland Network Against Domestic Violence",

        "url": "https://mnadv.org",

        "resource_type": "Domestic Violence Coalition",

    },

    "MA": {

        "abbr": "MA",

        "name": "Massachusetts",

        "coalition": "Jane Doe Inc.",

        "url": "https://janedoe.org",

        "resource_type": "Domestic Violence and Sexual Assault Coalition",

    },

    "MI": {

        "abbr": "MI",

        "name": "Michigan",

        "coalition": "Michigan Coalition to End Domestic and Sexual Violence",

        "url": "https://mcedsv.org",

        "resource_type": "Domestic Violence and Sexual Assault Coalition",

    },

    "MN": {

        "abbr": "MN",

        "name": "Minnesota",

        "coalition": "Violence Free Minnesota",

        "url": "https://vfmn.org",

        "resource_type": "Domestic Violence Coalition",

    },

    "MS": {

        "abbr": "MS",

        "name": "Mississippi",

        "coalition": "Mississippi Coalition Against Domestic Violence",

        "url": "https://mcadv.org",

        "resource_type": "Domestic Violence Coalition",

    },

    "MO": {

        "abbr": "MO",

        "name": "Missouri",

        "coalition": "Missouri Coalition Against Domestic and Sexual Violence",

        "url": "https://mocadsv.org",

        "resource_type": "Domestic Violence and Sexual Assault Coalition",

    },

    "MT": {

        "abbr": "MT",

        "name": "Montana",

        "coalition": "Montana Coalition Against Domestic and Sexual Violence",

        "url": "https://mcadsv.com",

        "resource_type": "Domestic Violence and Sexual Assault Coalition",

    },

    "NE": {

        "abbr": "NE",

        "name": "Nebraska",

        "coalition": "Nebraska Coalition to End Sexual and Domestic Violence",

        "url": "https://nebraskacoalition.org",

        "resource_type": "Domestic Violence and Sexual Assault Coalition",

    },

    "NV": {

        "abbr": "NV",

        "name": "Nevada",

        "coalition": "Nevada Coalition to End Domestic and Sexual Violence",

        "url": "https://ncedsv.org",

        "resource_type": "Domestic Violence and Sexual Assault Coalition",

    },

    "NH": {

        "abbr": "NH",

        "name": "New Hampshire",

        "coalition": "New Hampshire Coalition Against Domestic and Sexual Violence",

        "url": "https://nhcadsv.org",

        "resource_type": "Domestic Violence and Sexual Assault Coalition",

    },

    "NJ": {

        "abbr": "NJ",

        "name": "New Jersey",

        "coalition": "New Jersey Coalition to End Domestic Violence",

        "url": "https://njcedv.org",

        "resource_type": "Domestic Violence Coalition",

    },

    "NM": {

        "abbr": "NM",

        "name": "New Mexico",

        "coalition": "New Mexico Coalition Against Domestic Violence",

        "url": "https://nmcadv.org",

        "resource_type": "Domestic Violence Coalition",

    },

    "NY": {

        "abbr": "NY",

        "name": "New York",

        "coalition": "New York State Coalition Against Domestic Violence",

        "url": "https://nyscadv.org",

        "resource_type": "Domestic Violence Coalition",

    },

    "NC": {

        "abbr": "NC",

        "name": "North Carolina",

        "coalition": "North Carolina Coalition Against Domestic Violence",

        "url": "https://nccadv.org",

        "resource_type": "Domestic Violence Coalition",

    },

    "ND": {

        "abbr": "ND",

        "name": "North Dakota",

        "coalition": "North Dakota Domestic and Sexual Violence Coalition",

        "url": "https://nddsvc.org",

        "resource_type": "Domestic Violence and Sexual Assault Coalition",

    },

    "OH": {

        "abbr": "OH",

        "name": "Ohio",

        "coalition": "Ohio Domestic Violence Network",

        "url": "https://odvn.org",

        "resource_type": "Domestic Violence Coalition",

    },

    "OK": {

        "abbr": "OK",

        "name": "Oklahoma",

        "coalition": "Oklahoma Attorney General Certified Victim Services Programs",

        "url": "https://www.oklahoma.gov/oag.html",

        "resource_type": "State Victim Services Directory",

        "special_directory": True,

        "directory_note": (

            "Use the Oklahoma Attorney General's certified victim "

            "services program list. NNEDV directs Oklahoma users "

            "to this resource."

        ),

    },

    "OR": {

        "abbr": "OR",

        "name": "Oregon",

        "coalition": "Oregon Coalition Against Domestic and Sexual Violence",

        "url": "https://ocadsv.org",

        "resource_type": "Domestic Violence and Sexual Assault Coalition",

    },

    "PA": {

        "abbr": "PA",

        "name": "Pennsylvania",

        "coalition": "Pennsylvania Coalition Against Domestic Violence",

        "url": "https://pcadv.org",

        "resource_type": "Domestic Violence Coalition",

    },

    "RI": {

        "abbr": "RI",

        "name": "Rhode Island",

        "coalition": "Rhode Island Coalition Against Domestic Violence",

        "url": "https://ricadv.org",

        "resource_type": "Domestic Violence Coalition",

    },

    "SC": {

        "abbr": "SC",

        "name": "South Carolina",

        "coalition": "South Carolina Coalition Against Domestic Violence and Sexual Assault",

        "url": "https://sccadvasa.org",

        "resource_type": "Domestic Violence and Sexual Assault Coalition",

    },

    "SD": {

        "abbr": "SD",

        "name": "South Dakota",

        "coalition": "South Dakota Network Against Family Violence and Sexual Assault",

        "url": "https://sdnafVsa.com",

        "resource_type": "Domestic Violence and Sexual Assault Coalition",

    },

    "TN": {

        "abbr": "TN",

        "name": "Tennessee",

        "coalition": "Tennessee Coalition to End Domestic and Sexual Violence",

        "url": "https://tncoalition.org",

        "resource_type": "Domestic Violence and Sexual Assault Coalition",

    },

    "TX": {

        "abbr": "TX",

        "name": "Texas",

        "coalition": "Texas Council on Family Violence",

        "url": "https://tcfv.org",

        "resource_type": "Domestic Violence Coalition",

    },

    "UT": {

        "abbr": "UT",

        "name": "Utah",

        "coalition": "Utah Domestic Violence Council",

        "url": "https://udvc.org",

        "resource_type": "Domestic Violence Coalition",

    },

    "VT": {

        "abbr": "VT",

        "name": "Vermont",

        "coalition": "Vermont Network Against Domestic and Sexual Violence",

        "url": "https://vtnetwork.org",

        "resource_type": "Domestic Violence and Sexual Assault Coalition",

    },

    "VA": {

        "abbr": "VA",

        "name": "Virginia",

        "coalition": "Virginia Sexual and Domestic Violence Action Alliance",

        "url": "https://vsdvalliance.org",

        "resource_type": "Domestic Violence and Sexual Assault Coalition",

    },

    "WA": {

        "abbr": "WA",

        "name": "Washington",

        "coalition": "Washington State Coalition Against Domestic Violence",

        "url": "https://wscadv.org",

        "resource_type": "Domestic Violence Coalition",

    },

    "WV": {

        "abbr": "WV",

        "name": "West Virginia",

        "coalition": "West Virginia Coalition Against Domestic Violence",

        "url": "https://wvcadv.org",

        "resource_type": "Domestic Violence Coalition",

    },

    "WI": {

        "abbr": "WI",

        "name": "Wisconsin",

        "coalition": "End Domestic Abuse Wisconsin",

        "url": "https://endabusewi.org",

        "resource_type": "Domestic Violence Coalition",

    },

    "WY": {

        "abbr": "WY",

        "name": "Wyoming",

        "coalition": "Wyoming Coalition Against Domestic Violence and Sexual Assault",

        "url": "https://wyomingdvsa.org",

        "resource_type": "Domestic Violence and Sexual Assault Coalition",

    },

}

# =========================================================

# NATIONAL RESOURCES

# =========================================================

NATIONAL_RESOURCES = [

    {

        "name": "National Domestic Violence Hotline",

        "category": "Immediate Support",

        "phone": "1-800-799-7233",

        "text": "Text START to 88788",

        "url": "https://www.thehotline.org/",

        "description": "Domestic violence support, safety planning, and referrals.",

    },

    {

        "name": "RAINN National Sexual Assault Hotline",

        "category": "Sexual Assault Support",

        "phone": "1-800-656-4673",

        "url": "https://rainn.org/",

        "description": "Sexual assault support and referrals.",

    },

    {

        "name": "StrongHearts Native Helpline",

        "category": "Culturally Specific Support",

        "phone": "1-844-762-8483",

        "url": "https://strongheartshelpline.org/",

        "description": "Support for Native American and Alaska Native survivors.",

    },

    {

        "name": "National Human Trafficking Hotline",

        "category": "Trafficking Support",

        "phone": "1-888-373-7888",

        "text": "Text 233733",

        "url": "https://humantraffickinghotline.org/",

        "description": "Support and referrals related to human trafficking.",

    },

    {

        "name": "Childhelp National Child Abuse Hotline",

        "category": "Child Safety",

        "phone": "1-800-422-4453",

        "url": "https://www.childhelphotline.org/",

        "description": "Support and reporting guidance concerning child abuse.",

    },

    {

        "name": "988 Suicide and Crisis Lifeline",

        "category": "Crisis Support",

        "phone": "988",

        "url": "https://988lifeline.org/",

        "description": "Call or text 988 for crisis support.",

    },

    {

        "name": "Legal Services Corporation",

        "category": "Legal Assistance",

        "url": "https://www.lsc.gov/about-lsc/what-legal-aid/i-need-legal-help",

        "description": "Find civil legal aid organizations.",

    },

    {

        "name": "HUD Find Shelter",

        "category": "Housing",

        "url": "https://www.hud.gov/FindShelter",

        "description": "Find housing and shelter resources.",

    },

    {

        "name": "211",

        "category": "Community Resources",

        "phone": "211",

        "url": "https://www.211.org/",

        "description": "Community assistance and local resource referrals.",

    },

    {

        "name": "Findhelp",

        "category": "Community Resources",

        "url": "https://www.findhelp.org/",

        "description": "Search for local social services and assistance.",

    },

    {

        "name": "WomensLaw",

        "category": "Legal Information",

        "url": "https://www.womenslaw.org/",

        "description": "Legal information for survivors of abuse.",

    },

    {

        "name": "NNEDV Safety Net Project",

        "category": "Technology Safety",

        "url": "https://www.techsafety.org/",

        "description": "Technology safety and privacy information.",

    },

]

# =========================================================

# DIRECTORY INITIALIZATION

# =========================================================

def initialize_directory() -> dict:

    """

    Seed the 50-state directory once.

    If an automatically maintained directory already exists,

    load it instead of overwriting it with the original seed.

    """

    if DIRECTORY_FILE.exists():

        try:

            with DIRECTORY_FILE.open("r", encoding="utf-8") as file:

                saved = json.load(file)

            if (

                isinstance(saved, dict)

                and set(STATE_DIRECTORY_SEED).issubset(saved.keys())

            ):

                return saved

        except (OSError, json.JSONDecodeError):

            pass

    seeded = {

        key: dict(value)

        for key, value in STATE_DIRECTORY_SEED.items()

    }

    temporary = DIRECTORY_FILE.with_suffix(".tmp")

    with temporary.open("w", encoding="utf-8") as file:

        json.dump(

            seeded,

            file,

            indent=2,

            ensure_ascii=False,

        )

    temporary.replace(DIRECTORY_FILE)

    return seeded

STATE_COALITIONS = initialize_directory()

# =========================================================

# GENERAL HELPERS

# =========================================================

def utc_now() -> str:

    return datetime.now(timezone.utc).isoformat()

def get_state_names() -> list[str]:

    return sorted(

        record["name"]

        for record in STATE_COALITIONS.values()

    )

def get_state_by_name(name: str) -> Optional[dict]:

    for record in STATE_COALITIONS.values():

        if record["name"] == name:

            return record

    return None

def get_state_resource(abbreviation: str) -> Optional[dict]:

    return STATE_COALITIONS.get(

        abbreviation.upper()

    )

def get_all_state_records() -> list[dict]:

    return [

        STATE_COALITIONS[key]

        for key in sorted(STATE_COALITIONS)

    ]

def get_local_resource_links() -> list[dict]:

    return [

        {

            "name": "211 Community Resources",

            "url": "https://www.211.org/",

        },

        {

            "name": "Findhelp",

            "url": "https://www.findhelp.org/",

        },

        {

            "name": "HUD Find Shelter",

            "url": "https://www.hud.gov/FindShelter",

        },

        {

            "name": "Legal Services Corporation",

            "url": "https://www.lsc.gov/about-lsc/what-legal-aid/i-need-legal-help",

        },

        {

            "name": "National Domestic Violence Hotline",

            "url": "https://www.thehotline.org/",

        },

    ]

def export_directory() -> dict:

    return {

        "exported_at": utc_now(),

        "state_count": len(STATE_COALITIONS),

        "states": STATE_COALITIONS,

        "national_resources": NATIONAL_RESOURCES,

    }

def dataframe_from_records(records: list[dict]) -> pd.DataFrame:

    if not records:

        return pd.DataFrame()

    return pd.DataFrame(records)

def safe_download_json(

    data: Any,

    filename: str,

    label: str,

):

    st.download_button(

        label=label,

        data=json.dumps(

            data,

            indent=2,

            ensure_ascii=False,

        ),

        file_name=filename,

        mime="application/json",

    )

# =========================================================

# API CONNECTION HELPERS

# =========================================================

def api_configured() -> bool:

    return bool(API_URL)

def api_get(endpoint: str) -> dict:

    if not api_configured():

        return {

            "success": False,

            "error": "SURVIVORS_API_URL is not configured.",

        }

    try:

        response = requests.get(

            f"{API_URL}{endpoint}",

            timeout=REQUEST_TIMEOUT,

        )

        response.raise_for_status()

        return {

            "success": True,

            "data": response.json(),

            "status_code": response.status_code,

        }

    except requests.RequestException as error:

        return {

            "success": False,

            "error": str(error),

        }

    except ValueError:

        return {

            "success": False,

            "error": "API returned invalid JSON.",

        }

def api_post(endpoint: str, payload: dict) -> dict:

    if not api_configured():

        return {

            "success": False,

            "error": "SURVIVORS_API_URL is not configured.",

        }

    try:

        response = requests.post(

            f"{API_URL}{endpoint}",

            json=payload,

            timeout=REQUEST_TIMEOUT,

        )

        response.raise_for_status()

        try:

            data = response.json()

        except ValueError:

            data = {"message": response.text}

        return {

            "success": True,

            "data": data,

            "status_code": response.status_code,

        }

    except requests.RequestException as error:

        return {

            "success": False,

            "error": str(error),

        }

def api_delete(endpoint: str) -> dict:

    if not api_configured():

        return {

            "success": False,

            "error": "SURVIVORS_API_URL is not configured.",

        }

    try:

        response = requests.delete(

            f"{API_URL}{endpoint}",

            timeout=REQUEST_TIMEOUT,

        )

        response.raise_for_status()

        return {

            "success": True,

            "status_code": response.status_code,

        }

    except requests.RequestException as error:

        return {

            "success": False,

            "error": str(error),

        }

# =========================================================

# RESOURCE CRAWLER INTEGRATION

# =========================================================

CRAWLER_AVAILABLE = False

try:

    from resource_crawler import (

        run_crawl,

        get_crawler_status,

        get_pending_reviews,

        get_all_reviews,

        review_change,

        export_review_queue,

        build_source_registry,

        self_test as crawler_self_test,

    )

    CRAWLER_AVAILABLE = True

except ImportError as error:

    CRAWLER_IMPORT_ERROR = str(error)

# =========================================================

# AUTOMATED DIRECTORY BOT INTEGRATION

# =========================================================

DIRECTORY_BOTS_AVAILABLE = False

try:

    from directory_updates import (

        run_automated_updates,

        get_directory_update_status,

        get_directory_exceptions,

        get_directory_history,

        export_current_directory,

        rollback_directory,

        self_test as directory_bot_self_test,

    )

    DIRECTORY_BOTS_AVAILABLE = True

except ImportError as error:

    DIRECTORY_BOT_IMPORT_ERROR = str(error)

# =========================================================

# APP HEADER

# =========================================================

st.title("🛡️ Survivors Network")

st.markdown(

    """

    A survivor-centered resource, documentation, and support network.

    The application separates public resource discovery from private

    survivor information. Resource maintenance is designed to run

    automatically, reducing administrative work for survivors.

    """

)

with st.sidebar:
    st.markdown("## Your Space")

    st.caption("Take a moment. You are in control of what happens next.")

    st.divider()

    st.markdown("### 🌿 Nervous System Reset")

    reset_tool = st.selectbox(
        "What would help right now?",
        [
            "Choose a reset",
            "Orient to the present",
            "Ground through your senses",
            "Gentle breathing",
            "Release physical tension",
            "Pause and regain control"
        ],
        label_visibility="collapsed",
        key="nervous_system_reset"
    )

    if reset_tool == "Orient to the present":
        st.markdown("**Look around at your surroundings.**")
        st.write(
            "Without forcing yourself to do anything, notice "
            "three things that tell you where you are right now."
        )
        st.write(
            "Notice the room, the lighting, the objects around you, "
            "or something familiar."
        )
        st.caption("You can keep your eyes open and stop whenever you wish.")

    elif reset_tool == "Ground through your senses":
        st.markdown("**Reconnect with your surroundings.**")
        st.write(
            "Notice something you can see, something you can hear, "
            "and something you can physically feel."
        )
        st.write(
            "If comfortable, touch a nearby surface and notice its texture."
        )
        st.caption("You do not have to complete every step.")

    elif reset_tool == "Gentle breathing":
        st.markdown("**Let your breathing find a comfortable rhythm.**")
        st.write(
            "If it feels comfortable, allow your exhale to be a little "
            "slower than your inhale."
        )
        st.write(
            "There is no required count. Do not hold your breath or "
            "force a deeper breath."
        )
        st.caption(
            "If focusing on breathing feels uncomfortable, choose "
            "the orienting exercise instead."
        )

    elif reset_tool == "Release physical tension":
        st.markdown("**Give your body permission to soften.**")
        st.write(
            "If comfortable, lower your shoulders, unclench your hands, "
            "or gently move your fingers and feet."
        )
        st.write(
            "You can change position, stretch, or simply remain still."
        )

    elif reset_tool == "Pause and regain control":
        st.markdown("**You can decide what happens next.**")
        st.write(
            "You do not have to finish a task, submit information, "
            "read another page, or explain anything."
        )
        st.write(
            "You can pause, leave this application, or return when "
            "you feel ready."
        )

    st.divider()

    st.markdown("### A reminder")
    st.caption(
        "You can move at your own pace. You can stop any exercise. "
        "You do not owe this application any information."
    )

    st.divider()

    st.caption("Your information. Your choices.")

# =========================================================

# MAIN TABS

# =========================================================

tabs = st.tabs([

    "Create Entry",

    "Legal Ledger Export",

    "Match Mailbox",

    "Investigator",

    "State Resource Matrix",

    "Safety Guide",

    "Diagnostics",

    "Automated Resource Crawler",

])

# =========================================================

# TAB 1 — CREATE ENTRY

# =========================================================

with tabs[0]:

    st.header("Create Evidence Entry")

    st.warning(

        "The original API backend is not yet suitable for real "

        "survivor records. It lacks adequate authentication and "

        "access controls. Do not submit real names, locations, "

        "notes, or identifying information to it."

    )

    st.markdown(

        """

        This section preserves the original evidence-entry workflow.

        The original backend accepts:

        - User key

        - Participant reference

        - Notes

        - Coordinates

        Its current implementation does not securely protect all

        of those fields. The form below is restricted to test data.

        """

    )

    with st.form("create_entry_form"):

        st.subheader("Test Evidence Entry")

        user_key = st.text_input(

            "Test user key",

            type="password",

        )

        participant_reference = st.text_input(

            "Test participant reference",

        )

        evidence_notes = st.text_area(

            "Test evidence notes",

            height=120,

        )

        col1, col2 = st.columns(2)

        with col1:

            latitude = st.text_input(

                "Test latitude",

                value="",

            )

        with col2:

            longitude = st.text_input(

                "Test longitude",

                value="",

            )

        test_confirmation = st.checkbox(

            "I confirm that this is fictional test data "

            "and contains no survivor-identifying information."

        )

        submitted = st.form_submit_button(

            "Submit Test Entry",

            disabled=not test_confirmation,

        )

        if submitted:

            if not API_URL:

                st.error("Configure SURVIVORS_API_URL first.")

            elif not user_key or not participant_reference:

                st.error("Enter the required test fields.")

            else:

                try:

                    coordinates = {

                        "lat": float(latitude or 0),

                        "lon": float(longitude or 0),

                    }

                    payload = {
    "perp_id": participant_reference.strip(),
    "notes": notes.strip(),
    "coordinates": [
        float(latitude),
        float(longitude)
    ] if include_location else [0.0, 0.0]
}
                    result = api_post(

                        "/create-entry",

                        payload,

                    )

                    if result["success"]:

                        st.success("Test entry submitted.")

                        st.json(result["data"])

                    else:

                        st.error(result["error"])

                except ValueError:

                    st.error("Coordinates must be numeric.")

# =========================================================

# TAB 2 — LEGAL LEDGER EXPORT

# =========================================================

with tabs[1]:

    st.header("Legal Ledger Export")

    st.markdown(

        """

        Retrieve available ledger entries and create exportable

        JSON and CSV records.

        """

    )

    if st.button(

        "Retrieve Ledger",

        key="retrieve_ledger",

    ):

        result = api_get("/ledger")

        if result["success"]:

            st.session_state["ledger_data"] = result["data"]

            st.success("Ledger retrieved.")

        else:

            st.error(result["error"])

    ledger_data = st.session_state.get(

        "ledger_data",

        None,

    )

    if ledger_data is not None:

        st.subheader("Ledger Data")

        st.json(ledger_data)

        safe_download_json(

            ledger_data,

            "survivors_network_ledger.json",

            "Download Ledger JSON",

        )

        if isinstance(ledger_data, list):

            ledger_df = pd.DataFrame(ledger_data)

        elif isinstance(ledger_data, dict):

            records = (

                ledger_data.get("ledger")

                or ledger_data.get("entries")

                or ledger_data.get("records")

            )

            if isinstance(records, list):

                ledger_df = pd.DataFrame(records)

            else:

                ledger_df = pd.DataFrame([ledger_data])

        else:

            ledger_df = pd.DataFrame()

        if not ledger_df.empty:

            csv_data = ledger_df.to_csv(index=False)

            st.download_button(

                "Download Ledger CSV",

                data=csv_data,

                file_name="survivors_network_ledger.csv",

                mime="text/csv",

            )

    st.divider()

    st.subheader("Resource Directory Legal Reference Export")

    st.caption(

        "This export contains public resource directory information, "

        "not private survivor records."

    )

    safe_download_json(

        export_directory(),

        "survivors_network_resource_directory.json",

        "Download Resource Directory",

    )

# =========================================================

# TAB 3 — MATCH MAILBOX

# =========================================================

with tabs[2]:

    st.header("Match Mailbox")

    st.warning(

        "The current backend mailbox does not provide sufficient "

        "authentication or access control for real survivor messages. "

        "Use fictional test data only."

    )

    st.subheader("Send Test Message")

    with st.form("mailbox_send_form"):

        match_token = st.text_input(

            "Test match token",

        )

        encrypted_message = st.text_area(

            "Test encrypted message payload",

        )

        send_confirmation = st.checkbox(

            "This is fictional test data."

        )

        send_message = st.form_submit_button(

            "Send Test Message",

            disabled=not send_confirmation,

        )

        if send_message:

            if not match_token or not encrypted_message:

                st.error("Enter the test token and message.")

            else:

                payload = {

                    "match_token": match_token,

                    "encrypted_message": encrypted_message,

                }

                result = api_post(

                    "/mailbox/send",

                    payload,

                )

                if result["success"]:

                    st.success("Test message submitted.")

                    st.json(result["data"])

                else:

                    st.error(result["error"])

    st.divider()

    st.subheader("Retrieve Test Mailbox")

    with st.form("mailbox_read_form"):

        read_token = st.text_input(

            "Mailbox match token",

            key="mailbox_read_token",

        )

        retrieve_message = st.form_submit_button(

            "Retrieve Test Messages"

        )

        if retrieve_message:

            if not read_token:

                st.error("Enter a test token.")

            else:

                result = api_get(

                    f"/mailbox/{read_token}"

                )

                if result["success"]:

                    st.json(result["data"])

                else:

                    st.error(result["error"])

# =========================================================

# TAB 4 — INVESTIGATOR

# =========================================================

with tabs[3]:

    st.header("Investigator")

    st.markdown(

        """

        Retrieve available ledger analysis and pattern information

        from the existing investigator endpoint.

        """

    )

    if st.button(

        "Run Investigator",

        key="run_investigator",

    ):

        result = api_get("/investigator")

        if result["success"]:

            st.session_state["investigator_data"] = result["data"]

            st.success("Investigator results retrieved.")

        else:

            st.error(result["error"])

    investigator_data = st.session_state.get(

        "investigator_data",

        None,

    )

    if investigator_data is not None:

        st.subheader("Analysis Results")

        st.json(investigator_data)

        safe_download_json(

            investigator_data,

            "survivors_network_investigator.json",

            "Download Investigator Results",

        )

    st.divider()

    st.subheader("Peer Registry")

    if st.button(

        "Retrieve Peer Registry",

        key="retrieve_peers",

    ):

        result = api_get("/peers")

        if result["success"]:

            st.session_state["peer_data"] = result["data"]

        else:

            st.error(result["error"])

    peer_data = st.session_state.get("peer_data")

    if peer_data is not None:

        st.json(peer_data)

# =========================================================

# TAB 5 — STATE RESOURCE MATRIX

# =========================================================

with tabs[4]:

    st.header("United States Resource Matrix")

    st.markdown(

        """

        State-level domestic violence and sexual assault coalition

        directory, connected to national assistance resources.

        """

    )

    state_names = get_state_names()

    selected_state_name = st.selectbox(

        "Select your state",

        state_names,

        key="state_resource_selector",

    )

    selected_state = get_state_by_name(

        selected_state_name

    )

    if selected_state:

        st.subheader(selected_state["name"])

        st.markdown(

            f"**State abbreviation:** {selected_state['abbr']}"

        )

        st.markdown(

            f"**Coalition:** {selected_state['coalition']}"

        )

        st.markdown(

            f"**Resource type:** {selected_state['resource_type']}"

        )

        st.markdown(

            f"**Official resource:** [{selected_state['url']}]"

            f"({selected_state['url']})"

        )

        if selected_state.get("directory_note"):

            st.info(selected_state["directory_note"])

        if selected_state.get("phone"):

            st.markdown(

                f"**Telephone:** {selected_state['phone']}"

            )

        if selected_state.get("services"):

            st.markdown("**Services:**")

            for service in selected_state["services"]:

                st.write(f"- {service}")

        if selected_state.get("eligibility"):

            st.markdown("**Eligibility:**")

            st.write(selected_state["eligibility"])

        if selected_state.get("hours"):

            st.markdown("**Hours:**")

            st.write(selected_state["hours"])

        if selected_state.get("last_verified"):

            st.caption(

                f"Last verified: {selected_state['last_verified']}"

            )

    st.divider()

    st.subheader("National Resources")

    for resource in NATIONAL_RESOURCES:

        with st.expander(

            f"{resource['name']} — {resource['category']}"

        ):

            st.write(resource["description"])

            if resource.get("phone"):

                st.write("Telephone:", resource["phone"])

            if resource.get("text"):

                st.write("Text:", resource["text"])

            st.markdown(

                f"[Visit resource website]({resource['url']})"

            )

    st.divider()

    st.subheader("All 50 States")

    state_table = []

    for record in get_all_state_records():

        state_table.append({

            "State": record["name"],

            "Abbreviation": record["abbr"],

            "Coalition": record["coalition"],

            "Website": record["url"],

            "Resource Type": record["resource_type"],

            "Last Verified": record.get(

                "last_verified",

                "Not yet verified",

            ),

        })

    st.dataframe(

        pd.DataFrame(state_table),

        use_container_width=True,

        hide_index=True,

    )

    safe_download_json(

        export_directory(),

        "survivors_network_all_state_resources.json",

        "Download All State Resources",

    )

# =========================================================

# TAB 6 — SAFETY GUIDE

# =========================================================

with tabs[5]:

    st.header("Survivor Safety Guide")

    st.markdown(

        """

        This section provides general safety information. Individual

        safety decisions should remain under the survivor's control.

        """

    )

    with st.expander("Technology and Device Safety", expanded=True):

        st.markdown(

            """

            - Use a device that another person cannot access when possible.

            - Review account sessions and connected devices.

            - Check location-sharing settings.

            - Review shared cloud accounts and family plans.

            - Be aware that browsing history and notifications may be visible.

            - Consider whether changing passwords could trigger alerts.

            - Use a safer device when researching support options.

            - Review the NNEDV Safety Net technology resources.

            """

        )

        st.markdown(

            "[Technology Safety Project](https://www.techsafety.org/)"

        )

    with st.expander("Documentation and Evidence"):

        st.markdown(

            """

            - Preserve original files when possible.

            - Record dates and times.

            - Keep copies in a location the other person cannot access.

            - Preserve relevant messages and communication records.

            - Avoid altering original evidence files.

            - Keep a separate record of where evidence originated.

            """

        )

    with st.expander("Digital Privacy"):

        st.markdown(

            """

            - Avoid placing personal identifying information in public repositories.

            - Do not upload private evidence to public GitHub repositories.

            - Review device permissions and location access.

            - Be cautious about shared devices and cloud storage.

            - Use separate accounts where appropriate.

            - Consider the safety implications of notifications and email previews.

            """

        )

    with st.expander("Emergency Resources"):

        st.markdown(

            """

            If there is immediate danger, contact emergency services

            when it is safe to do so.

            National Domestic Violence Hotline:

            **1-800-799-7233**

            Text **START** to **88788**.

            [TheHotline.org](https://www.thehotline.org/)

            """

        )

    with st.expander("Legal and Housing Assistance"):

        st.markdown(

            """

            - [Legal Services Corporation](https://www.lsc.gov/)

            - [HUD Find Shelter](https://www.hud.gov/FindShelter)

            - [WomensLaw](https://www.womenslaw.org/)

            - [211](https://www.211.org/)

            - [Findhelp](https://www.findhelp.org/)

            """

        )

# =========================================================

# TAB 7 — DIAGNOSTICS

# =========================================================

with tabs[6]:

    st.header("System Diagnostics")

    st.subheader("Application")

    st.write("Application version:", APP_VERSION)

    st.write("Python directory:", str(Path.cwd()))

    st.write("Resource data directory:", str(DATA_DIR))

    st.write("State records:", len(STATE_COALITIONS))

    st.write(

        "Unique state abbreviations:",

        len(set(STATE_COALITIONS.keys())),

    )

    st.write(

        "Directory file exists:",

        DIRECTORY_FILE.exists(),

    )

    st.divider()

    st.subheader("State Directory Validation")

    state_checks = {

        "Exactly 50 state records": (

            len(STATE_COALITIONS) == 50

        ),

        "All state abbreviations unique": (

            len(set(STATE_COALITIONS.keys())) == 50

        ),

        "All state records have names": all(

            bool(item.get("name"))

            for item in STATE_COALITIONS.values()

        ),

        "All state records have URLs": all(

            bool(item.get("url"))

            for item in STATE_COALITIONS.values()

        ),

        "All state URLs use HTTPS": all(

            item.get("url", "").startswith("https://")

            for item in STATE_COALITIONS.values()

        ),

    }

    for check, passed in state_checks.items():

        if passed:

            st.success(check)

        else:

            st.error(check)

    st.divider()

    st.subheader("API Diagnostics")

    if API_URL:

        st.write("Configured API:", API_URL)

        ledger_check = api_get("/ledger")

        if ledger_check["success"]:

            st.success("Ledger endpoint reachable.")

        else:

            st.warning(

                f"Ledger endpoint unavailable: "

                f"{ledger_check['error']}"

            )

    else:

        st.info(

            "No remote API configured. The resource directory "

            "and crawler can operate independently."

        )

    st.divider()

    st.subheader("Crawler Diagnostics")

    if CRAWLER_AVAILABLE:

        try:

            crawler_status = get_crawler_status()

            st.json(crawler_status)

            if st.button(

                "Run Crawler Offline Self-Test",

                key="crawler_self_test",

            ):

                test_result = crawler_self_test()

                st.json(test_result)

        except Exception as error:

            st.error(f"Crawler diagnostics failed: {error}")

    else:

        st.error(

            "resource_crawler.py could not be imported."

        )

        st.code(

            globals().get(

                "CRAWLER_IMPORT_ERROR",

                "Unknown import error.",

            )

        )

    st.divider()

    st.subheader("Directory Bot Diagnostics")

    if DIRECTORY_BOTS_AVAILABLE:

        try:

            bot_status = get_directory_update_status()

            st.json(bot_status)

            if st.button(

                "Run Directory Bot Offline Self-Test",

                key="directory_bot_self_test",

            ):

                bot_test = directory_bot_self_test()

                st.json(bot_test)

        except Exception as error:

            st.error(

                f"Directory bot diagnostics failed: {error}"

            )

    else:

        st.error(

            "directory_updates.py could not be imported."

        )

        st.code(

            globals().get(

                "DIRECTORY_BOT_IMPORT_ERROR",

                "Unknown import error.",

            )

        )

    st.divider()

    st.subheader("Storage Diagnostics")

    storage_files = [

        DATA_DIR / "snapshots.json",

        DATA_DIR / "pending_reviews.json",

        DATA_DIR / "activity_log.json",

        DATA_DIR / "state_resource_directory.json",

        DATA_DIR / "directory_history.json",

        DATA_DIR / "directory_exceptions.json",

        DATA_DIR / "directory_bot_report.json",

    ]

    for path in storage_files:

        st.write(

            f"{path.name}:",

            "Present" if path.exists() else "Not created yet",

        )

# =========================================================

# TAB 8 — AUTOMATED RESOURCE CRAWLER

# =========================================================

with tabs[7]:

    st.header("Automated Resource Intelligence")

    st.markdown(

        """

        The resource-maintenance system independently monitors

        public state coalition and national resource websites.

        Its purpose is to maintain current resource information

        without requiring survivors to manage directory updates.

        """

    )

    st.info(

        "This crawler operates on public resource websites. "

        "It does not crawl survivor accounts, private messages, "

        "or survivor evidence."

    )

    if not CRAWLER_AVAILABLE:

        st.error(

            "The resource crawler module is unavailable. "

            "Place resource_crawler.py in the application directory."

        )

    else:

        # -------------------------------------------------

        # SOURCE REGISTRY

        # -------------------------------------------------

        st.subheader("Source Registry")

        source_registry = build_source_registry(

            state_coalitions=STATE_COALITIONS,

            include_national=True,

        )

        st.metric(

            "Registered public sources",

            len(source_registry),

        )

        st.metric(

            "State coalition sources",

            sum(

                item.get("category") == "State Coalition"

                for item in source_registry

            ),

        )

        st.metric(

            "National sources",

            sum(

                item.get("category") != "State Coalition"

                for item in source_registry

            ),

        )

        with st.expander("View Registered Sources"):

            st.dataframe(

                pd.DataFrame([

                    {

                        "Name": item.get("name"),

                        "Category": item.get("category"),

                        "State": item.get("state"),

                        "URL": item.get("url"),

                    }

                    for item in source_registry

                ]),

                use_container_width=True,

                hide_index=True,

            )

        st.divider()

        # -------------------------------------------------

        # CRAWL EXECUTION

        # -------------------------------------------------

        st.subheader("Public Resource Discovery")

        crawl_limit = st.selectbox(

            "Crawl scope",

            [

                "All registered sources",

                "State sources only",

                "National sources only",

                "First 5 sources (test)",

            ],

            key="crawl_scope",

        )

        if st.button(

            "Run Public Resource Crawler",

            key="run_public_crawler",

        ):

            try:

                if crawl_limit == "State sources only":

                    state_only = {

                        key: value

                        for key, value in STATE_COALITIONS.items()

                    }

                    report = run_crawl(

                        state_coalitions=state_only,

                        include_national=False,

                    )

                elif crawl_limit == "National sources only":

                    report = run_crawl(

                        state_coalitions={},

                        include_national=True,

                    )

                elif crawl_limit == "First 5 sources (test)":

                    report = run_crawl(

                        state_coalitions=STATE_COALITIONS,

                        include_national=True,

                        max_sources=5,

                    )

                else:

                    report = run_crawl(

                        state_coalitions=STATE_COALITIONS,

                        include_national=True,

                    )

                st.session_state["last_crawl_report"] = report

                st.success("Crawler run completed.")

            except Exception as error:

                st.error(f"Crawler execution failed: {error}")

        last_crawl_report = st.session_state.get(

            "last_crawl_report"

        )

        if last_crawl_report:

            st.subheader("Latest Crawl Report")

            st.json(last_crawl_report)

            safe_download_json(

                last_crawl_report,

                "survivors_network_crawl_report.json",

                "Download Crawl Report",

            )

        st.divider()

        # -------------------------------------------------

        # CRAWLER STATUS

        # -------------------------------------------------

        st.subheader("Crawler Status")

        try:

            crawler_status = get_crawler_status()

            status_columns = st.columns(4)

            status_columns[0].metric(

                "Snapshots",

                crawler_status.get("snapshot_count", 0),

            )

            status_columns[1].metric(

                "Review records",

                crawler_status.get("review_count", 0),

            )

            status_columns[2].metric(

                "Pending reviews",

                crawler_status.get("pending_reviews", 0),

            )

            status_columns[3].metric(

                "Activity entries",

                crawler_status.get("activity_entries", 0),

            )

        except Exception as error:

            st.error(f"Could not load crawler status: {error}")

        st.divider()

        # -------------------------------------------------

        # AUTOMATED DIRECTORY BOTS

        # -------------------------------------------------

        st.subheader("Independent Directory Validation Bots")

        if not DIRECTORY_BOTS_AVAILABLE:

            st.error(

                "directory_updates.py is unavailable. "

                "Place the module beside survivors-network.py."

            )

        else:

            st.markdown(

                """

                The directory bots process the crawler's saved public

                source data. High-confidence changes can be applied

                automatically, while unresolved conflicts are isolated

                in the network maintenance exception queue.

                """

            )

            bot_status = get_directory_update_status()

            bot_columns = st.columns(4)

            bot_columns[0].metric(

                "Sources loaded",

                bot_status.get("sources_loaded", 0),

            )

            bot_columns[1].metric(

                "Candidates found",

                bot_status.get("candidates_found", 0),

            )

            bot_columns[2].metric(

                "Updates applied",

                bot_status.get("updates_applied", 0),

            )

            bot_columns[3].metric(

                "Exceptions",

                bot_status.get("exception_count", 0),

            )

            if st.button(

                "Run Automated Directory Intelligence",

                key="run_directory_intelligence",

            ):

                with st.spinner(

                    "Running independent validation and consistency bots..."

                ):

                    result = run_automated_updates(

                        current_directory=STATE_COALITIONS,

                        auto_apply=True,

                    )

                if result.get("success"):

                    st.success(result["message"])

                    st.session_state[

                        "last_directory_bot_report"

                    ] = result["report"]

                    # Load the persisted directory version so that

                    # the current application immediately reflects

                    # automated updates.

                    persisted_directory = export_current_directory()

                    if persisted_directory:

                        STATE_COALITIONS.clear()

                        STATE_COALITIONS.update(

                            persisted_directory

                        )

                    st.rerun()

                else:

                    st.error(

                        result.get(

                            "message",

                            "Automated directory maintenance failed.",

                        )

                    )

                    if result.get("report"):

                        st.json(result["report"])

            latest_bot_report = st.session_state.get(

                "last_directory_bot_report"

            )

            if latest_bot_report:

                st.markdown("**Latest Bot Run**")

                st.json(latest_bot_report)

            st.divider()

            # ---------------------------------------------

            # AUTOMATIC DIRECTORY EXPORT

            # ---------------------------------------------

            st.subheader("Maintained Resource Directory")

            maintained_directory = export_current_directory()

            if maintained_directory:

                st.metric(

                    "Maintained state records",

                    len(maintained_directory),

                )

                safe_download_json(

                    maintained_directory,

                    "survivors_network_maintained_directory.json",

                    "Download Maintained Directory",

                )

            else:

                st.info(

                    "The automated directory has not produced "

                    "a saved version yet. The original 50-state "

                    "directory remains available."

                )

            st.divider()

            # ---------------------------------------------

            # EXCEPTION QUEUE

            # ---------------------------------------------

            st.subheader("Network Maintenance Exceptions")

            exceptions = get_directory_exceptions()

            if exceptions:

                st.write(

                    f"{len(exceptions)} unresolved candidate records."

                )

                exception_rows = []

                for item in exceptions:

                    exception_rows.append({

                        "State": item.get("state"),

                        "Field": item.get("field"),

                        "Candidate": item.get("display"),

                        "Confidence": item.get("confidence"),

                        "Reason": item.get("exception_reason"),

                    })

                st.dataframe(

                    pd.DataFrame(exception_rows),

                    use_container_width=True,

                    hide_index=True,

                )

                safe_download_json(

                    exceptions,

                    "survivors_network_directory_exceptions.json",

                    "Export Exception Records",

                )

            else:

                st.success(

                    "No unresolved directory exceptions."

                )

            st.divider()

            # ---------------------------------------------

            # VERSION HISTORY

            # ---------------------------------------------

            st.subheader("Directory Version History")

            history = get_directory_history()

            if history:

                history_rows = []

                for item in history:

                    history_rows.append({

                        "Version": item.get("version"),

                        "Created": item.get("created_at"),

                        "Changes": len(

                            item.get("changes", [])

                        ),

                        "Previous Hash": item.get("previous_hash"),

                        "New Hash": item.get("new_hash"),

                    })

                st.dataframe(

                    pd.DataFrame(history_rows),

                    use_container_width=True,

                    hide_index=True,

                )

                version_options = {

                    (

                        f"Version {item['version']} — "

                        f"{item['created_at']}"

                    ): item["version"]

                    for item in history

                }

                selected_version = st.selectbox(

                    "Select directory version",

                    list(version_options.keys()),

                    key="directory_restore_version",

                )

                if st.button(

                    "Restore Selected Directory Version",

                    key="restore_directory_version",

                ):

                    restored = rollback_directory(

                        version=version_options[selected_version],

                    )

                    if restored.get("success"):

                        st.success(restored["message"])

                        STATE_COALITIONS.clear()

                        STATE_COALITIONS.update(

                            restored["directory"]

                        )

                        st.rerun()

                    else:

                        st.error(restored["message"])

            else:

                st.info(

                    "No automated directory versions have been saved."

                )

        st.divider()

        # -------------------------------------------------

        # HUMAN REVIEW RECORDS — NETWORK MAINTENANCE

        # -------------------------------------------------

        st.subheader("Crawler Change Records")

        st.caption(

            "These records support source monitoring and network "

            "maintenance. They are not survivor tasks."

        )

        try:

            all_reviews = get_all_reviews()

            if all_reviews:

                review_rows = []

                for item in all_reviews:

                    review_rows.append({

                        "Source": item.get("source_name"),

                        "State": item.get("state"),

                        "Change": item.get("change_type"),

                        "Status": item.get("status"),

                        "Detected": item.get("detected_at"),

                    })

                st.dataframe(

                    pd.DataFrame(review_rows),

                    use_container_width=True,

                    hide_index=True,

                )

                safe_download_json(

                    export_review_queue(),

                    "survivors_network_crawler_review_records.json",

                    "Export Crawler Change Records",

                )

            else:

                st.info(

                    "No crawler change records have been generated."

                )

        except Exception as error:

            st.error(

                f"Could not load crawler review records: {error}"

            )

# =========================================================

# FOOTER

# =========================================================

st.divider()

st.caption(

    f"Survivors Network v{APP_VERSION} | "

    "Public resource maintenance is separate from private survivor data."

)
