
"""
SURVIVORS NETWORK
Main Streamlit application.

Sections:
1. Create Entry
2. Legal Ledger Export
3. Match Mailbox
4. Investigator
5. State Resource Matrix
6. Safety Guide
7. Diagnostics
8. Automated Resource Crawler

Security boundaries:
- No private survivor records are transmitted to a remote API.
- Public resource crawling is independent of survivor information.
- Directory changes are prepared for network maintenance review.
- The public directory is stored locally and can be exported.
"""

from __future__ import annotations

import html
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import pandas as pd
import streamlit as st


# =========================================================
# STREAMLIT CONFIGURATION — MUST BE FIRST STREAMLIT CALL
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

APP_VERSION = "2.1.0"

PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "resource_crawler_data"

# Shared canonical directory location.
# This matches resource_crawler.py and directory_updates.py.
DIRECTORY_FILE = PROJECT_DIR / "state_resource_directory.json"

AUDIO_DIR = PROJECT_DIR / "assets" / "audio"

DATA_DIR.mkdir(parents=True, exist_ok=True)

QUICK_EXIT_DEFAULT = "https://www.cnn.com/"
QUICK_EXIT_URL = os.getenv(
    "SURVIVORS_QUICK_EXIT_URL",
    QUICK_EXIT_DEFAULT,
).strip()

# The old remote API is intentionally disabled.
# Do not restore remote private-data operations merely by
# configuring SURVIVORS_API_URL.
PRIVATE_REMOTE_OPERATIONS_ENABLED = False


# =========================================================
# QUICK EXIT VALIDATION
# =========================================================

def safe_quick_exit_url(value: str) -> str:
    """
    Only permit an absolute HTTPS destination without credentials.
    The value is escaped before being inserted into HTML.
    """

    try:
        parsed = urlparse(value)

        if (
            parsed.scheme.lower() == "https"
            and parsed.hostname
            and not parsed.username
            and not parsed.password
            and parsed.port in (None, 443)
        ):
            return value

    except (ValueError, TypeError):
        pass

    return QUICK_EXIT_DEFAULT


QUICK_EXIT_URL = safe_quick_exit_url(QUICK_EXIT_URL)

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
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div class="quick-exit-container">
        <a class="quick-exit-button"
           href="{html.escape(QUICK_EXIT_URL, quote=True)}"
           target="_top"
           rel="noopener noreferrer">
           Quick Exit
        </a>
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# OFFICIAL 50-STATE RESOURCE DIRECTORY
# =========================================================

# Compact seed format:
# abbreviation, state, coalition, website, resource type

_STATE_ROWS = [
    ("AL", "Alabama", "Alabama Coalition Against Domestic Violence",
     "https://acadv.org", "Domestic Violence Coalition"),
    ("AK", "Alaska", "Alaska Network on Domestic Violence and Sexual Assault",
     "https://andvsa.org", "Domestic Violence and Sexual Assault Coalition"),
    ("AZ", "Arizona", "Arizona Coalition to End Sexual and Domestic Violence",
     "https://www.acesdv.org", "Domestic Violence and Sexual Assault Coalition"),
    ("AR", "Arkansas", "Arkansas Coalition Against Domestic Violence",
     "https://domesticpeace.com", "Domestic Violence Coalition"),
    ("CA", "California", "California Partnership to End Domestic Violence",
     "https://cpedv.org", "Domestic Violence Coalition"),
    ("CO", "Colorado", "Violence Free Colorado",
     "https://violencefreecolorado.org", "Domestic Violence Coalition"),
    ("CT", "Connecticut", "Connecticut Coalition Against Domestic Violence",
     "https://www.ctcadv.org", "Domestic Violence Coalition"),
    ("DE", "Delaware", "Delaware Coalition Against Domestic Violence",
     "https://dcadv.org", "Domestic Violence Coalition"),
    ("FL", "Florida", "Florida Partnership to End Domestic Violence",
     "https://www.fpedv.org", "Domestic Violence Coalition"),
    ("GA", "Georgia", "Georgia Coalition Against Domestic Violence",
     "https://gcadv.org", "Domestic Violence Coalition"),
    ("HI", "Hawaii", "Hawaii State Coalition Against Domestic Violence",
     "https://hscadv.org", "Domestic Violence Coalition"),
    ("ID", "Idaho", "Idaho Coalition Against Sexual and Domestic Violence",
     "https://idahocoalition.org", "Domestic Violence and Sexual Assault Coalition"),
    ("IL", "Illinois", "Illinois Coalition Against Domestic Violence",
     "https://ilcadv.org", "Domestic Violence Coalition"),
    ("IN", "Indiana", "Indiana Coalition Against Domestic Violence",
     "https://icadvinc.org", "Domestic Violence Coalition"),
    ("IA", "Iowa", "Iowa Coalition Against Domestic Violence",
     "https://icadv.org", "Domestic Violence Coalition"),
    ("KS", "Kansas", "Kansas Coalition Against Sexual and Domestic Violence",
     "https://kcsdv.org", "Domestic Violence and Sexual Assault Coalition"),
    ("KY", "Kentucky", "ZeroV",
     "https://zerov.org", "Domestic Violence Coalition"),
    ("LA", "Louisiana", "Louisiana Coalition Against Domestic Violence",
     "https://lcadv.org", "Domestic Violence Coalition"),
    ("ME", "Maine", "Maine Coalition to End Domestic Violence",
     "https://mcedv.org", "Domestic Violence Coalition"),
    ("MD", "Maryland", "Maryland Network Against Domestic Violence",
     "https://mnadv.org", "Domestic Violence Coalition"),
    ("MA", "Massachusetts", "Jane Doe Inc.",
     "https://janedoe.org", "Domestic Violence and Sexual Assault Coalition"),
    ("MI", "Michigan", "Michigan Coalition to End Domestic and Sexual Violence",
     "https://mcedsv.org", "Domestic Violence and Sexual Assault Coalition"),
    ("MN", "Minnesota", "Violence Free Minnesota",
     "https://vfmn.org", "Domestic Violence Coalition"),
    ("MS", "Mississippi", "Mississippi Coalition Against Domestic Violence",
     "https://mcadv.org", "Domestic Violence Coalition"),
    ("MO", "Missouri", "Missouri Coalition Against Domestic and Sexual Violence",
     "https://mocadsv.org", "Domestic Violence and Sexual Assault Coalition"),
    ("MT", "Montana", "Montana Coalition Against Domestic and Sexual Violence",
     "https://mcadsv.com", "Domestic Violence and Sexual Assault Coalition"),
    ("NE", "Nebraska", "Nebraska Coalition to End Sexual and Domestic Violence",
     "https://nebraskacoalition.org", "Domestic Violence and Sexual Assault Coalition"),
    ("NV", "Nevada", "Nevada Coalition to End Domestic and Sexual Violence",
     "https://ncedsv.org", "Domestic Violence and Sexual Assault Coalition"),
    ("NH", "New Hampshire", "New Hampshire Coalition Against Domestic and Sexual Violence",
     "https://nhcadsv.org", "Domestic Violence and Sexual Assault Coalition"),
    ("NJ", "New Jersey", "New Jersey Coalition to End Domestic Violence",
     "https://njcedv.org", "Domestic Violence Coalition"),
    ("NM", "New Mexico", "New Mexico Coalition Against Domestic Violence",
     "https://nmcadv.org", "Domestic Violence Coalition"),
    ("NY", "New York", "New York State Coalition Against Domestic Violence",
     "https://nyscadv.org", "Domestic Violence Coalition"),
    ("NC", "North Carolina", "North Carolina Coalition Against Domestic Violence",
     "https://nccadv.org", "Domestic Violence Coalition"),
    ("ND", "North Dakota", "North Dakota Domestic and Sexual Violence Coalition",
     "https://nddsvc.org", "Domestic Violence and Sexual Assault Coalition"),
    ("OH", "Ohio", "Ohio Domestic Violence Network",
     "https://odvn.org", "Domestic Violence Coalition"),
    ("OK", "Oklahoma", "Oklahoma Attorney General Certified Victim Services Programs",
     "https://www.oklahoma.gov/oag.html", "State Victim Services Directory"),
    ("OR", "Oregon", "Oregon Coalition Against Domestic and Sexual Violence",
     "https://ocadsv.org", "Domestic Violence and Sexual Assault Coalition"),
    ("PA", "Pennsylvania", "Pennsylvania Coalition Against Domestic Violence",
     "https://pcadv.org", "Domestic Violence Coalition"),
    ("RI", "Rhode Island", "Rhode Island Coalition Against Domestic Violence",
     "https://ricadv.org", "Domestic Violence Coalition"),
    ("SC", "South Carolina", "South Carolina Coalition Against Domestic Violence and Sexual Assault",
     "https://sccadvasa.org", "Domestic Violence and Sexual Assault Coalition"),
    ("SD", "South Dakota", "South Dakota Network Against Family Violence and Sexual Assault",
     "https://sdnafvsa.com", "Domestic Violence and Sexual Assault Coalition"),
    ("TN", "Tennessee", "Tennessee Coalition to End Domestic and Sexual Violence",
     "https://tncoalition.org", "Domestic Violence and Sexual Assault Coalition"),
    ("TX", "Texas", "Texas Council on Family Violence",
     "https://tcfv.org", "Domestic Violence Coalition"),
    ("UT", "Utah", "Utah Domestic Violence Council",
     "https://udvc.org", "Domestic Violence Coalition"),
    ("VT", "Vermont", "Vermont Network Against Domestic and Sexual Violence",
     "https://vtnetwork.org", "Domestic Violence and Sexual Assault Coalition"),
    ("VA", "Virginia", "Virginia Sexual and Domestic Violence Action Alliance",
     "https://vsdvalliance.org", "Domestic Violence and Sexual Assault Coalition"),
    ("WA", "Washington", "Washington State Coalition Against Domestic Violence",
     "https://wscadv.org", "Domestic Violence Coalition"),
    ("WV", "West Virginia", "West Virginia Coalition Against Domestic Violence",
     "https://wvcadv.org", "Domestic Violence Coalition"),
    ("WI", "Wisconsin", "End Domestic Abuse Wisconsin",
     "https://endabusewi.org", "Domestic Violence Coalition"),
    ("WY", "Wyoming", "Wyoming Coalition Against Domestic Violence and Sexual Assault",
     "https://wyomingdvsa.org", "Domestic Violence and Sexual Assault Coalition"),
]


STATE_DIRECTORY_SEED = {}

for abbr, name, coalition, url, resource_type in _STATE_ROWS:
    STATE_DIRECTORY_SEED[abbr] = {
        "abbr": abbr,
        "name": name,
        "coalition": coalition,
        "url": url,
        "resource_type": resource_type,
    }

STATE_DIRECTORY_SEED["OK"]["special_directory"] = True
STATE_DIRECTORY_SEED["OK"]["directory_note"] = (
    "Use the Oklahoma Attorney General's certified victim "
    "services program list. NNEDV directs Oklahoma users "
    "to this resource."
)


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
# SAFE LOCAL DIRECTORY STORAGE
# =========================================================

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = path.with_suffix(path.suffix + ".tmp")

    with temporary.open("w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )
        file.flush()
        os.fsync(file.fileno())

    temporary.replace(path)


def normalize_directory(data: Any) -> dict:
    """
    Accept either a direct state mapping or a wrapper containing
    a 'states' mapping. Preserve existing fields and state records.
    """

    if not isinstance(data, dict):
        raise ValueError("Directory data must be a JSON object.")

    states = data.get("states", data)

    if not isinstance(states, dict):
        raise ValueError("Directory states must be a JSON object.")

    normalized = {}

    for key, value in states.items():
        if not isinstance(value, dict):
            continue

        abbr = str(
            value.get("abbr")
            or value.get("code")
            or key
        ).strip().upper()

        if len(abbr) != 2:
            continue

        record = dict(value)
        record["abbr"] = abbr

        # Preserve compatibility with both companion modules.
        if not record.get("url") and record.get("website"):
            record["url"] = record["website"]

        if not record.get("website") and record.get("url"):
            record["website"] = record["url"]

        if not record.get("code"):
            record["code"] = abbr

        normalized[abbr] = record

    return normalized


def initialize_directory() -> dict:
    """
    Load the existing directory without overwriting it.

    Missing state records are added from the seed.
    Existing records and additional fields are preserved.

    Invalid JSON is backed up before a fresh seed is written.
    """

    if DIRECTORY_FILE.exists():
        try:
            with DIRECTORY_FILE.open("r", encoding="utf-8") as file:
                saved = json.load(file)

            directory = normalize_directory(saved)

            if directory:
                for abbr, seed_record in STATE_DIRECTORY_SEED.items():
                    if abbr not in directory:
                        directory[abbr] = dict(seed_record)

                atomic_write_json(DIRECTORY_FILE, directory)
                return directory

        except (OSError, json.JSONDecodeError, ValueError) as error:
            backup = DIRECTORY_FILE.with_name(
                f"{DIRECTORY_FILE.name}.corrupt-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            )

            try:
                shutil.copy2(DIRECTORY_FILE, backup)
            except OSError:
                st.error(
                    "The existing directory could not be backed up. "
                    "It has not been replaced."
                )
                raise RuntimeError(
                    "Directory initialization stopped to protect existing data."
                ) from error

    seeded = {
        key: dict(value)
        for key, value in STATE_DIRECTORY_SEED.items()
    }

    atomic_write_json(DIRECTORY_FILE, seeded)
    return seeded


STATE_COALITIONS = initialize_directory()


# =========================================================
# DIRECTORY HELPERS
# =========================================================

def get_state_names() -> list[str]:
    return sorted(
        record.get("name", key)
        for key, record in STATE_COALITIONS.items()
    )


def get_state_by_name(name: str) -> Optional[dict]:
    for record in STATE_COALITIONS.values():
        if record.get("name") == name:
            return record
    return None


def get_state_resource(abbreviation: str) -> Optional[dict]:
    return STATE_COALITIONS.get(abbreviation.upper())


def get_all_state_records() -> list[dict]:
    return [
        STATE_COALITIONS[key]
        for key in sorted(STATE_COALITIONS)
    ]


def export_directory() -> dict:
    return {
        "exported_at": utc_now(),
        "state_count": len(STATE_COALITIONS),
        "states": STATE_COALITIONS,
        "national_resources": NATIONAL_RESOURCES,
    }


def safe_download_json(
    data: Any,
    filename: str,
    label: str,
) -> None:
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


def directory_for_bot() -> dict:
    """
    The directory bot expects code/website fields.
    Provide an adapted copy without changing the public app schema.
    """

    adapted = {}

    for abbr, record in STATE_COALITIONS.items():
        item = dict(record)
        item["code"] = abbr
        item["website"] = (
            item.get("website")
            or item.get("url")
            or ""
        )
        adapted[abbr] = item

    return adapted


def normalize_bot_directory(data: Any) -> dict:
    """
    Convert bot output back to the app's abbr/url format.
    """

    result = normalize_directory(data)

    for abbr, record in result.items():
        if record.get("website"):
            record["url"] = record["website"]

        record["abbr"] = abbr

    return result


# =========================================================
# PRIVATE API — DISABLED
# =========================================================

def private_api_disabled_message() -> str:
    return (
        "Remote private-data operations are disabled. "
        "The previous API backend has not been verified to provide "
        "the authentication, authorization, encryption, and access "
        "controls required for survivor information. "
        "No information was transmitted."
    )


# =========================================================
# RESOURCE CRAWLER INTEGRATION
# =========================================================

CRAWLER_AVAILABLE = False
CRAWLER_IMPORT_ERROR = ""

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

except Exception as error:
    CRAWLER_IMPORT_ERROR = str(error)


# =========================================================
# DIRECTORY BOT INTEGRATION
# =========================================================

DIRECTORY_BOTS_AVAILABLE = False
DIRECTORY_BOT_IMPORT_ERROR = ""

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

except Exception as error:
    DIRECTORY_BOT_IMPORT_ERROR = str(error)


# =========================================================
# SENSORY SUPPORT CENTER
# =========================================================

SOUND_LIBRARY = {
    "Gentle rain": "gentle_rain.mp3",
    "Forest birds": "forest_birds.mp3",
    "Ocean waves": "ocean_waves.mp3",
    "Flowing stream": "flowing_stream.mp3",
    "Wind through trees": "wind_trees.mp3",
    "Fireplace": "fireplace.mp3",
    "Night nature": "night_nature.mp3",
    "Soft instrumental": "soft_instrumental.mp3",
}

EXTERNAL_SOUND_RESOURCES = {
    "Pixabay sound library": "https://pixabay.com/sound-effects/",
    "Freesound audio library": "https://freesound.org/",
    "Wikimedia Commons audio": "https://commons.wikimedia.org/wiki/Category:Audio_files",
}


def render_sensory_support_center():
    st.markdown("## Your Space")

    st.caption(
        "A place to pause, explore, and find something that feels "
        "comfortable. You choose what works for you."
    )

    with st.expander("🎵 Sound & Nature", expanded=True):
        st.write(
            "Choose an environment or sound that you find comfortable."
        )

        sound_choice = st.selectbox(
            "Choose a sound",
            ["Choose a sound"] + list(SOUND_LIBRARY.keys()),
            key="sensory_sound_choice",
        )

        if sound_choice != "Choose a sound":
            sound_file = AUDIO_DIR / SOUND_LIBRARY[sound_choice]

            if sound_file.is_file():
                st.audio(str(sound_file), format="audio/mpeg")
                st.caption(
                    "Use the audio player's controls to pause or stop playback."
                )
            else:
                st.info(
                    "This sound is available when its licensed audio file "
                    "is added to assets/audio."
                )
                st.caption(f"Selected experience: {sound_choice}")

        st.caption(
            "No sound plays automatically. Device volume controls remain available."
        )

        st.markdown("**Explore additional sound libraries**")

        for name, url in EXTERNAL_SOUND_RESOURCES.items():
            st.markdown(f"- [{name}]({url})")

        st.caption(
            "Check licensing and usage terms before incorporating recordings."
        )

    with st.expander("🌿 Visual Calm"):
        choice = st.selectbox(
            "Choose a visual grounding activity",
            [
                "Notice the natural light",
                "Observe a peaceful object",
                "Look at the colors around you",
                "Imagine a familiar peaceful place",
            ],
            key="visual_calm_choice",
        )

        guidance = {
            "Notice the natural light":
                "Notice the light around you. It may be sunlight, "
                "a lamp, or the gentle change of light in the room.",
            "Observe a peaceful object":
                "Choose an object that feels familiar or neutral. "
                "Notice its shape, texture, and details.",
            "Look at the colors around you":
                "Notice three colors in your surroundings. "
                "There is no need to search for anything difficult.",
            "Imagine a familiar peaceful place":
                "If comfortable, picture a place where you feel "
                "safe, comfortable, or at ease.",
        }

        st.write(guidance[choice])
        st.caption("You can keep your eyes open, change activities, or stop.")

    with st.expander("🤲 Sensory Grounding"):
        choice = st.radio(
            "Select an activity",
            [
                "Notice the feeling of your feet on the floor",
                "Touch a familiar object",
                "Hold a comfortable object",
                "Notice the temperature of the room",
                "Simply observe your surroundings",
            ],
            key="sensory_grounding_choice",
        )

        st.write(choice)
        st.caption(
            "There is no required sequence. You can stop at any time."
        )

    with st.expander("🧘 Movement & Release"):
        choice = st.selectbox(
            "Choose a gentle movement",
            [
                "Relax your hands",
                "Gently move your shoulders",
                "Stretch your fingers",
                "Move your feet",
                "Take a comfortable walk",
                "Remain still and rest",
            ],
            key="movement_choice",
        )

        guidance = {
            "Relax your hands":
                "If comfortable, allow your hands to rest without gripping.",
            "Gently move your shoulders":
                "If comfortable, gently move your shoulders and return "
                "to a position that feels natural.",
            "Stretch your fingers":
                "Gently move or stretch your fingers without forcing them.",
            "Move your feet":
                "Try gently moving your toes or changing your foot position.",
            "Take a comfortable walk":
                "If it is safe and accessible, take a short, comfortable walk.",
            "Remain still and rest":
                "Resting without doing anything is also an option.",
        }

        st.write(guidance[choice])

    with st.expander("🌬️ Breathing & Relaxation"):
        st.write(
            "If focusing on breathing feels comfortable, allow your "
            "breathing to follow its natural rhythm."
        )

        st.write(
            "You may allow the exhale to become gently slower, "
            "without forcing a deep breath or holding your breath."
        )

        st.info(
            "If breathing exercises cause discomfort, dizziness, "
            "or increased distress, stop and choose another activity."
        )

    with st.expander("💚 Connection & Support"):
        st.write(
            "Sometimes a sense of connection can help us feel less alone."
        )

        st.markdown(
            """
            - Contact someone you trust, if it feels safe.
            - Spend time with a comforting pet.
            - Sit somewhere familiar.
            - Listen to a familiar voice or favorite song.
            - Choose a quiet activity that brings comfort.
            - Take a break from communication if you need one.
            """
        )

    with st.expander("☁️ A Moment for Yourself"):
        st.markdown(
            """
            You do not have to:

            - Finish an exercise.
            - Explain what happened.
            - Submit information.
            - Continue using this application.
            - Make a decision right now.

            You can pause, leave, or return whenever you choose.
            """
        )

    st.divider()

    st.caption(
        "Your choices remain yours. These activities are optional "
        "self-guided support, not medical treatment."
    )


# =========================================================
# APP HEADER AND SIDEBAR
# =========================================================

st.title("🛡️ Survivors Network")

st.markdown(
    """
    A survivor-centered resource, documentation, and support network.

    Public resource discovery is separate from private survivor information.
    Resource maintenance is designed to reduce administrative work for survivors.
    """
)

with st.sidebar:
    render_sensory_support_center()

    st.divider()

    st.caption(
        "Survivors Network · Your information. Your choices."
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
        "Private evidence submission is disabled in this version. "
        "The previous backend does not provide verified protections "
        "for real survivor records. Nothing entered here will be sent "
        "to a remote service."
    )

    st.markdown(
        """
        The original entry workflow included:

        - User key
        - Participant reference
        - Evidence notes
        - Coordinates

        Those fields are not collected here because the current app
        does not have a verified secure storage and access-control layer.
        """
    )

    st.info(
        "The original form's undefined variables and unsafe remote "
        "submission path have been removed. This section will remain "
        "available for integration when a secure local or properly "
        "authenticated storage layer is implemented."
    )

    st.caption(
        "Do not place real names, locations, identifying details, "
        "or evidence in public GitHub files or Streamlit source code."
    )


# =========================================================
# TAB 2 — LEGAL LEDGER EXPORT
# =========================================================

with tabs[1]:
    st.header("Legal Ledger Export")

    st.warning(
        "Private ledger retrieval is disabled. This app does not "
        "connect to the previous remote ledger endpoint."
    )

    st.info(
        "You can still export the public resource directory. "
        "This export contains no survivor evidence or private records."
    )

    safe_download_json(
        export_directory(),
        "survivors_network_resource_directory.json",
        "Download Resource Directory JSON",
    )

    st.divider()

    st.subheader("Private Ledger Status")

    st.write(
        "Remote private ledger retrieval:",
        "Disabled",
    )

    st.write(
        "Private record transmission:",
        "Disabled",
    )


# =========================================================
# TAB 3 — MATCH MAILBOX
# =========================================================

with tabs[2]:
    st.header("Match Mailbox")

    st.warning(
        "Remote mailbox operations are disabled because the previous "
        "backend has not been verified for authentication, authorization, "
        "message confidentiality, and safe key management."
    )

    st.info(
        "No mailbox token or message is collected or transmitted by this app."
    )

    st.markdown(
        """
        A secure mailbox implementation should provide:

        - End-to-end encryption with independently managed keys.
        - Authentication and authorization for every mailbox operation.
        - Least-privilege access.
        - No plaintext message logging.
        - Rate limits and abuse protection.
        - Safe key rotation and revocation.
        - Clear separation between public resource data and private messages.
        """
    )


# =========================================================
# TAB 4 — INVESTIGATOR
# =========================================================

with tabs[3]:
    st.header("Investigator")

    st.warning(
        "Remote investigator and peer-registry endpoints are disabled. "
        "This application does not transmit survivor records for analysis."
    )

    st.markdown(
        """
        Incident-pattern analysis should operate within a separately
        protected data boundary.

        It should not be combined with the public resource crawler.
        Public websites are crawler inputs; private survivor records
        are not.
        """
    )

    st.markdown(
        """
        **Required safeguards before activation:**

        - Local or independently verified secure processing.
        - Explicit authorization for each investigator function.
        - Minimum necessary data access.
        - Auditable access records.
        - No automatic disclosure of private records.
        - No public exposure of survivor identities or locations.
        """
    )


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

    selected_state = get_state_by_name(selected_state_name)

    if selected_state:
        st.subheader(selected_state["name"])

        st.markdown(
            f"**State abbreviation:** {selected_state.get('abbr', '')}"
        )

        st.markdown(
            f"**Coalition:** {selected_state.get('coalition', '')}"
        )

        st.markdown(
            f"**Resource type:** {selected_state.get('resource_type', '')}"
        )

        resource_url = (
            selected_state.get("url")
            or selected_state.get("website")
            or ""
        )

        if resource_url:
            st.markdown(
                f"**Official resource:** [{resource_url}]({resource_url})"
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
            "State": record.get("name"),
            "Abbreviation": record.get("abbr"),
            "Coalition": record.get("coalition"),
            "Website": record.get("url") or record.get("website"),
            "Resource Type": record.get("resource_type"),
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
    st.write("Project directory:", str(PROJECT_DIR))
    st.write("Resource data directory:", str(DATA_DIR))
    st.write("Canonical directory file:", str(DIRECTORY_FILE))
    st.write("State records:", len(STATE_COALITIONS))

    st.write(
        "Private remote operations:",
        "Disabled",
    )

    st.divider()

    st.subheader("State Directory Validation")

    state_checks = {
        "Exactly 50 state records": len(STATE_COALITIONS) == 50,
        "All state abbreviations unique": (
            len(set(STATE_COALITIONS.keys())) == 50
        ),
        "All state records have names": all(
            bool(item.get("name"))
            for item in STATE_COALITIONS.values()
        ),
        "All state records have URLs": all(
            bool(item.get("url") or item.get("website"))
            for item in STATE_COALITIONS.values()
        ),
        "All state URLs use HTTPS": all(
            str(item.get("url") or item.get("website") or "")
            .lower()
            .startswith("https://")
            for item in STATE_COALITIONS.values()
        ),
    }

    for check, passed in state_checks.items():
        if passed:
            st.success(check)
        else:
            st.error(check)

    st.divider()

    st.subheader("Private Data Boundary")

    st.success("Remote private API calls are disabled.")
    st.success("The public crawler does not receive survivor records.")
    st.success("The resource directory is stored separately.")

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
                st.json(crawler_self_test())

        except Exception as error:
            st.error(f"Crawler diagnostics failed: {error}")

    else:
        st.error("resource_crawler.py could not be imported.")
        st.code(CRAWLER_IMPORT_ERROR or "Unknown import error.")

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
                st.json(directory_bot_self_test())

        except Exception as error:
            st.error(f"Directory bot diagnostics failed: {error}")

    else:
        st.error("directory_updates.py could not be imported.")
        st.code(
            DIRECTORY_BOT_IMPORT_ERROR or "Unknown import error."
        )

    st.divider()

    st.subheader("Storage Diagnostics")

    storage_files = [
        DIRECTORY_FILE,
        DATA_DIR / "snapshots.json",
        DATA_DIR / "pending_reviews.json",
        DATA_DIR / "activity_log.json",
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
        The resource-maintenance system monitors registered public
        state coalition and national resource websites.

        It operates independently of survivor records and private messages.
        """
    )

    st.info(
        "The crawler operates on public resource websites. "
        "It does not crawl survivor accounts, private messages, "
        "or survivor evidence."
    )

    if not CRAWLER_AVAILABLE:
        st.error(
            "The resource crawler module is unavailable. "
            "Place resource_crawler.py beside this application."
        )

    else:
        st.subheader("Source Registry")

        source_registry = build_source_registry(
            state_coalitions=STATE_COALITIONS,
            include_national=True,
        )

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Registered public sources",
            len(source_registry),
        )

        col2.metric(
            "State coalition sources",
            sum(
                item.get("category") == "State Coalition"
                for item in source_registry
            ),
        )

        col3.metric(
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
                    report = run_crawl(
                        state_coalitions=STATE_COALITIONS,
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

                if report.get("reviews_saved") is False:
                    st.error(
                        "The crawler could not save its review queue. "
                        "Check storage before relying on this run."
                    )

                elif report.get("snapshots_saved") is False:
                    st.warning(
                        "The review queue was saved, but snapshots "
                        "could not be saved. Review records remain available."
                    )

                else:
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
        # DIRECTORY INTELLIGENCE
        # -------------------------------------------------

        st.subheader("Independent Directory Validation Bots")

        if not DIRECTORY_BOTS_AVAILABLE:
            st.error(
                "directory_updates.py is unavailable. "
                "Place it beside survivors_network.py."
            )

        else:
            st.markdown(
                """
                The directory bots process saved public-source information.
                They identify candidate updates, validate fields, and isolate
                unresolved conflicts.

                They do not silently publish directory changes. Review and
                approval are network-maintenance responsibilities, not
                survivor tasks.
                """
            )

            try:
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

            except Exception as error:
                st.error(
                    f"Could not load directory bot status: {error}"
                )

            if st.button(
                "Run Automated Directory Intelligence",
                key="run_directory_intelligence",
            ):
                with st.spinner(
                    "Running independent validation and consistency bots..."
                ):
                    try:
                        result = run_automated_updates(
                            current_directory=directory_for_bot(),
                            auto_apply=False,
                        )

                        st.session_state[
                            "last_directory_bot_result"
                        ] = result

                        if result.get("success"):
                            st.success(
                                result.get(
                                    "message",
                                    "Directory intelligence completed.",
                                )
                            )
                        else:
                            st.error(
                                result.get(
                                    "message",
                                    "Directory intelligence did not complete.",
                                )
                            )

                    except Exception as error:
                        st.error(
                            f"Directory intelligence failed: {error}"
                        )

            latest_bot_result = st.session_state.get(
                "last_directory_bot_result"
            )

            if latest_bot_result:
                st.markdown("**Latest Bot Run**")
                st.json(latest_bot_result)

            st.divider()

            # ---------------------------------------------
            # CURRENT DIRECTORY
            # ---------------------------------------------

            st.subheader("Maintained Resource Directory")

            safe_download_json(
                export_directory(),
                "survivors_network_maintained_directory.json",
                "Download Current Resource Directory",
            )

            st.caption(
                "This is the current application directory. "
                "Bot candidates are not automatically published."
            )

            st.divider()

            # ---------------------------------------------
            # EXCEPTION QUEUE
            # ---------------------------------------------

            st.subheader("Network Maintenance Exceptions")

            try:
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

            except Exception as error:
                st.error(
                    f"Could not load directory exceptions: {error}"
                )

            st.divider()

            # ---------------------------------------------
            # VERSION HISTORY
            # ---------------------------------------------

            st.subheader("Directory Version History")

            try:
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

                    st.warning(
                        "Restoring a directory version changes the "
                        "public resource directory. This should be "
                        "performed by an authorized network maintainer."
                    )

                    confirm_restore = st.checkbox(
                        "I am authorized to restore this directory version.",
                        key="confirm_directory_restore",
                    )

                    if st.button(
                        "Restore Selected Directory Version",
                        key="restore_directory_version",
                        disabled=not confirm_restore,
                    ):
                        restored = rollback_directory(
                            version=version_options[selected_version],
                        )

                        if restored.get("success"):
                            st.success(restored["message"])

                            restored_directory = normalize_bot_directory(
                                restored.get("directory", {})
                            )

                            STATE_COALITIONS.clear()
                            STATE_COALITIONS.update(
                                restored_directory
                            )

                            atomic_write_json(
                                DIRECTORY_FILE,
                                STATE_COALITIONS,
                            )

                            st.rerun()

                        else:
                            st.error(
                                restored.get(
                                    "message",
                                    "Directory restoration failed.",
                                )
                            )

                else:
                    st.info(
                        "No automated directory versions have been saved."
                    )

            except Exception as error:
                st.error(
                    f"Could not load directory history: {error}"
                )

        st.divider()

        # -------------------------------------------------
        # CRAWLER CHANGE RECORDS
        # -------------------------------------------------

        st.subheader("Crawler Change Records")

        st.caption(
            "These records support public-source monitoring and "
            "network maintenance. They are not survivor tasks."
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
