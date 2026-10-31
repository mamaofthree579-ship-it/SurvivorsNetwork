import os
from pathlib import Path

import streamlit as st

from security import VaultSecurity
from storage import LocalVault


APP_HOME = Path(
    os.environ.get(
        "SURVIVORS_NETWORK_HOME",
        str(Path.home() / ".survivors_network")
    )
)

DATABASE = APP_HOME / "survivors_vault.sqlite3"
SALT_FILE = APP_HOME / "vault.salt"


st.set_page_config(
    page_title="Survivors Network",
    page_icon="🕊️",
    layout="wide"
)


st.markdown("""
<style>

.stApp {
    background-color: #F5F7F6;
}

.block-container {
    max-width: 1150px;
    padding-top: 2rem;
}

h1, h2, h3 {
    color: #29423E;
}

p, label {
    color: #405451;
}

section[data-testid="stSidebar"] {
    background-color: #EAF1ED;
}

div.stButton > button {
    border-radius: 10px;
    min-height: 42px;
}

div[data-testid="stMetric"] {
    background: white;
    border: 1px solid #E1E9E5;
    padding: 14px;
    border-radius: 12px;
}

</style>
""", unsafe_allow_html=True)


def lock_vault():

    st.session_state.vault = None
    st.session_state.vault_key = None

    st.rerun()


def create_or_unlock():

    st.title("🕊️ Survivors Network")

    st.write(
        "A private space for organizing information "
        "and finding useful resources."
    )

    APP_HOME.mkdir(
        parents=True,
        exist_ok=True
    )

    database_exists = DATABASE.exists()

    with st.form("vault_access"):

        password = st.text_input(
            "Passphrase",
            type="password"
        )

        confirmation = None

        if not database_exists:

            confirmation = st.text_input(
                "Confirm your passphrase",
                type="password"
            )

        submitted = st.form_submit_button(
            "Unlock local space" if database_exists
            else "Create local space",
            type="primary"
        )

    if not submitted:
        return

    if len(password) < 12:

        st.error(
            "Use a passphrase of at least 12 characters."
        )

        return

    if not database_exists and password != confirmation:

        st.error("The passphrases do not match.")

        return

    try:

        salt = VaultSecurity.get_salt(SALT_FILE)

        key = VaultSecurity.derive_key(
            password,
            salt
        )

        vault = LocalVault(
            DATABASE,
            key
        )

        if database_exists:

            if not vault.verify_key():

                st.error(
                    "Unable to unlock the vault. "
                    "Check your passphrase and backup files."
                )

                return

        else:

            vault.initialize_vault()

        st.session_state.vault = vault
        st.session_state.vault_key = key

        st.rerun()

    except Exception as exc:

        st.error(
            f"Vault initialization failed: {exc}"
        )


if "vault" not in st.session_state:
    st.session_state.vault = None

if "vault_key" not in st.session_state:
    st.session_state.vault_key = None


if st.session_state.vault is None:

    create_or_unlock()

    st.stop()


vault = st.session_state.vault


with st.sidebar:

    st.title("Survivors Network")

    st.caption("Your information. Your control.")

    section = st.radio(
        "Navigation",
        [
            "Home",
            "Private Records",
            "Resource Directory",
            "Network Status",
            "Research Investigator",
            "Safety Information",
            "Diagnostics"
        ]
    )

    st.divider()

    st.caption(
        "Local installation · Private vault"
    )

    if st.button(
        "Lock my private space",
        use_container_width=True
    ):

        lock_vault()


# --------------------------------------------------
# HOME
# --------------------------------------------------

if section == "Home":

    st.title("Welcome")

    st.write(
        "You can move through this application at your "
        "own pace. Start with whichever section is useful."
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Private records",
        vault.record_count()
    )

    col2.metric(
        "Storage",
        "Local"
    )

    col3.metric(
        "Network sharing",
        "Disabled"
    )

    st.divider()

    st.subheader("Your private space")

    st.write(
        "Create and organize encrypted personal records."
    )

    st.subheader("Resource directory")

    st.write(
        "Find starting points for community, housing, "
        "crisis, and support resources."
    )

    st.subheader("Privacy")

    st.info(
        "Your private records are encrypted before "
        "they are written to the local database."
    )


# --------------------------------------------------
# PRIVATE RECORDS
# --------------------------------------------------

elif section == "Private Records":

    st.title("Private Records")

    with st.form("record_form"):

        title = st.text_input(
            "Record title"
        )

        category = st.selectbox(
            "Category",
            [
                "Personal Notes",
                "Incident Documentation",
                "Resource Information",
                "Appointments",
                "Other"
            ]
        )

        content = st.text_area(
            "Information",
            height=200
        )

        save = st.form_submit_button(
            "Save encrypted record",
            type="primary"
        )

    if save:

        if not title.strip() or not content.strip():

            st.warning(
                "Please enter a title and information."
            )

        else:

            vault.add_record(
                title.strip(),
                category,
                content
            )

            st.success(
                "Record encrypted and saved locally."
            )

            st.rerun()

    st.divider()

    st.subheader("Saved records")

    records = vault.list_records()

    if not records:

        st.caption(
            "No records have been saved."
        )

    for record in records:

        with st.expander(
            f"{record['title']} — {record['category']}"
        ):

            details = vault.read_record(
                record["id"]
            )

            st.caption(
                details["created_at"]
            )

            st.text_area(
                "Record contents",
                details["content"],
                height=160,
                key=f"view_{record['id']}"
            )

            if st.button(
                "Delete record",
                key=f"delete_{record['id']}"
            ):

                vault.delete_record(
                    record["id"]
                )

                st.success("Record deleted.")

                st.rerun()


# --------------------------------------------------
# RESOURCE DIRECTORY
# --------------------------------------------------

elif section == "Resource Directory":

    st.title("Resource Directory")

    st.write(
        "These organizations provide general starting points. "
        "Availability and eligibility vary."
    )

    resources = [

        {
            "name": "National Domestic Violence Hotline",
            "url": "https://www.thehotline.org/",
            "description": "Domestic violence information and support."
        },

        {
            "name": "RAINN",
            "url": "https://rainn.org/",
            "description": "Sexual violence support and information."
        },

        {
            "name": "211",
            "url": "https://www.211.org/",
            "description": "Community resources and assistance."
        },

        {
            "name": "Findhelp",
            "url": "https://www.findhelp.org/",
            "description": "Search for local assistance programs."
        },

        {
            "name": "988 Lifeline",
            "url": "https://988lifeline.org/",
            "description": "Mental health and crisis support."
        }

    ]

    for resource in resources:

        with st.container(border=True):

            st.subheader(resource["name"])

            st.write(resource["description"])

            st.link_button(
                "Visit resource",
                resource["url"]
            )

    st.caption(
        "This directory is US-oriented and is not an "
        "emergency response service."
    )


# --------------------------------------------------
# NETWORK STATUS
# --------------------------------------------------

elif section == "Network Status":

    st.title("Network Status")

    st.info(
        "This installation is operating in local-only mode."
    )

    st.write("Local storage: Available")

    st.write("Encrypted record storage: Enabled")

    st.write("Peer discovery: Not yet activated")

    st.write("Crawler synchronization: Not yet activated")

    st.write("Remote mailbox: Not yet activated")

    st.write(
        "These network capabilities will be enabled "
        "through separately authenticated modules."
    )


# --------------------------------------------------
# RESEARCH INVESTIGATOR
# --------------------------------------------------

elif section == "Research Investigator":

    st.title("Research Investigator")

    st.write(
        "This section is reserved for the independent "
        "research and verification components."
    )

    st.info(
        "The investigator interface is not connected "
        "to private survivor records in this release."
    )

    st.write(
        "Future modules can provide independent resource "
        "verification, duplicate detection, and source "
        "reliability assessment."
    )


# --------------------------------------------------
# SAFETY INFORMATION
# --------------------------------------------------

elif section == "Safety Information":

    st.title("Safety and Privacy")

    st.subheader("Local data control")

    st.write(
        "Private record contents are encrypted before "
        "being stored in the local database."
    )

    st.subheader("Device safety")

    st.warning(
        "Local encryption does not protect against "
        "malware, keyloggers, screen capture, or someone "
        "accessing your computer while the vault is unlocked."
    )

    st.subheader("Backups")

    st.write(
        "Keep the database and its matching salt file "
        "together in a secure location you control."
    )

    st.subheader("Deletion")

    st.write(
        "Deleting a database record does not guarantee "
        "forensic erasure from storage media or backups."
    )

    st.subheader("Network sharing")

    st.write(
        "No peer synchronization is active in this release. "
        "Future sharing will require explicit consent."
    )


# --------------------------------------------------
# DIAGNOSTICS
# --------------------------------------------------

elif section == "Diagnostics":

    st.title("Diagnostics")

    st.write(
        "Local application information."
    )

    st.write(
        f"Database available: {DATABASE.exists()}"
    )

    st.write(
        f"Stored records: {vault.record_count()}"
    )

    st.write(
        f"Storage directory: {APP_HOME}"
    )

    st.caption(
        "Avoid sharing diagnostic screenshots that expose "
        "sensitive filesystem information."
    )
