
"""
Survivors Network — State Resource Directory
Author: Hope Jones

50-state resource index.

Sources:
- NNEDV state and territorial coalition directory
- U.S. DOJ Office on Violence Against Women
- Legal Services Corporation
- HUD Find Shelter
- 211
- Findhelp

This module deliberately distinguishes statewide coalitions from
local direct-service providers. It does not invent local shelter
addresses or crisis phone numbers.
"""

from urllib.parse import quote_plus
from datetime import date


DIRECTORY_VERSION = "2.0"
LAST_SOURCE_REVIEW = "2026-10-31"

NNEDV_SOURCE = (
    "https://nnedv.org/content/state-u-s-territory-coalitions/"
)

DOJ_STATE_SOURCE = (
    "https://www.justice.gov/ovw/state-and-territory-coalitions"
)

DOJ_SURVIVOR_RESOURCES = (
    "https://www.justice.gov/ovw/resources-victims-and-survivors"
)

LEGAL_AID_LOCATOR = (
    "https://www.lsc.gov/about-lsc/what-legal-aid/i-need-legal-help"
)

LAWHELP = "https://www.lawhelp.org/"

HUD_SHELTER = "https://www.hud.gov/FindShelter"

UNITED_WAY_211 = "https://www.211.org/"

FINDHELP = "https://www.findhelp.org/"

NATIONAL_HOTLINES = {
    "domestic_violence": {
        "name": "National Domestic Violence Hotline",
        "phone": "1-800-799-7233",
        "text": "Text START to 88788",
        "website": "https://www.thehotline.org/",
        "description": (
            "Confidential support, safety planning, and referrals "
            "to local domestic violence programs."
        ),
    },
    "sexual_assault": {
        "name": "RAINN National Sexual Assault Hotline",
        "phone": "1-800-656-4673",
        "text": "Online support is available",
        "website": "https://rainn.org/",
        "description": (
            "Support and referrals for survivors of sexual violence."
        ),
    },
    "victim_connect": {
        "name": "VictimConnect Resource Center",
        "phone": "1-855-484-2846",
        "text": "Online support is available",
        "website": "https://victimconnect.org/",
        "description": (
            "Information, referrals, and support for crime victims."
        ),
    },
    "stronghearts": {
        "name": "StrongHearts Native Helpline",
        "phone": "1-844-762-8483",
        "text": "Text support availability listed on website",
        "website": "https://strongheartshelpline.org/",
        "description": (
            "Culturally specific domestic violence and dating violence "
            "support for Native communities."
        ),
    },
    "childhelp": {
        "name": "Childhelp National Child Abuse Hotline",
        "phone": "1-800-422-4453",
        "text": "Text support availability listed on website",
        "website": "https://www.childhelphotline.org/",
        "description": (
            "Support for child abuse concerns and referrals."
        ),
    },
    "crisis_988": {
        "name": "988 Suicide and Crisis Lifeline",
        "phone": "Call or text 988",
        "text": "988",
        "website": "https://988lifeline.org/",
        "description": (
            "Mental health and emotional crisis support."
        ),
    },
    "human_trafficking": {
        "name": "National Human Trafficking Hotline",
        "phone": "1-888-373-7888",
        "text": "Text HELP or INFO to 233733",
        "website": "https://humantraffickinghotline.org/",
        "description": (
            "Support and referrals for people affected by human trafficking."
        ),
    },
}


# State abbreviation, official coalition name, official website.
# The coalition names and links are based on NNEDV's published directory.

STATE_COALITIONS = {
    "Alabama": {
        "code": "AL",
        "name": "Alabama Coalition Against Domestic Violence",
        "website": "https://www.acadv.org/",
    },
    "Alaska": {
        "code": "AK",
        "name": "Alaska Network on Domestic Violence and Sexual Assault",
        "website": "https://andvsa.org/",
    },
    "Arizona": {
        "code": "AZ",
        "name": "Arizona Coalition to End Sexual and Domestic Violence",
        "website": "https://www.acesdv.org/",
    },
    "Arkansas": {
        "code": "AR",
        "name": "Arkansas Coalition Against Domestic Violence",
        "website": "https://www.domesticpeace.com/",
    },
    "California": {
        "code": "CA",
        "name": "California Partnership to End Domestic Violence",
        "website": "https://www.cpedv.org/",
    },
    "Colorado": {
        "code": "CO",
        "name": "Violence Free Colorado",
        "website": "https://violencefreecolorado.org/",
    },
    "Connecticut": {
        "code": "CT",
        "name": "Connecticut Coalition Against Domestic Violence",
        "website": "https://www.ctcadv.org/",
    },
    "Delaware": {
        "code": "DE",
        "name": "Delaware Coalition Against Domestic Violence",
        "website": "https://dcadv.org/",
    },
    "Florida": {
        "code": "FL",
        "name": "Florida Partnership to End Domestic Violence",
        "website": "https://www.fpedv.org/",
    },
    "Georgia": {
        "code": "GA",
        "name": "Georgia Coalition Against Domestic Violence",
        "website": "https://gcadv.org/",
    },
    "Hawaii": {
        "code": "HI",
        "name": "Hawaii State Coalition Against Domestic Violence",
        "website": "https://www.hscadv.org/",
    },
    "Idaho": {
        "code": "ID",
        "name": "Idaho Coalition Against Sexual and Domestic Violence",
        "website": "https://idahocoalition.org/",
    },
    "Illinois": {
        "code": "IL",
        "name": "Illinois Coalition Against Domestic Violence",
        "website": "https://www.ilcadv.org/",
    },
    "Indiana": {
        "code": "IN",
        "name": "Indiana Coalition Against Domestic Violence",
        "website": "https://www.icadvinc.org/",
    },
    "Iowa": {
        "code": "IA",
        "name": "Iowa Coalition Against Domestic Violence",
        "website": "https://www.icadv.org/",
    },
    "Kansas": {
        "code": "KS",
        "name": "Kansas Coalition Against Sexual and Domestic Violence",
        "website": "https://www.kcsdv.org/",
    },
    "Kentucky": {
        "code": "KY",
        "name": "ZeroV",
        "website": "https://zerov.org/",
    },
    "Louisiana": {
        "code": "LA",
        "name": "Louisiana Coalition Against Domestic Violence",
        "website": "https://lcadv.org/",
    },
    "Maine": {
        "code": "ME",
        "name": "Maine Coalition to End Domestic Violence",
        "website": "https://www.mcedv.org/",
    },
    "Maryland": {
        "code": "MD",
        "name": "Maryland Network Against Domestic Violence",
        "website": "https://mnadv.org/",
    },
    "Massachusetts": {
        "code": "MA",
        "name": "Jane Doe Inc.",
        "website": "https://www.janedoe.org/",
    },
    "Michigan": {
        "code": "MI",
        "name": "Michigan Coalition to End Domestic and Sexual Violence",
        "website": "https://www.mcedsv.org/",
    },
    "Minnesota": {
        "code": "MN",
        "name": "Violence Free Minnesota",
        "website": "https://www.vfmn.org/",
    },
    "Mississippi": {
        "code": "MS",
        "name": "Mississippi Coalition Against Domestic Violence",
        "website": "https://mcadv.org/",
    },
    "Missouri": {
        "code": "MO",
        "name": "Missouri Coalition Against Domestic and Sexual Violence",
        "website": "https://www.mocadsv.org/",
    },
    "Montana": {
        "code": "MT",
        "name": "Montana Coalition Against Domestic and Sexual Violence",
        "website": "https://mcadsv.com/",
    },
    "Nebraska": {
        "code": "NE",
        "name": "Nebraska Coalition to End Sexual and Domestic Violence",
        "website": "https://www.nebraskacoalition.org/",
    },
    "Nevada": {
        "code": "NV",
        "name": "Nevada Coalition to End Domestic and Sexual Violence",
        "website": "https://www.ncedsv.org/",
    },
    "New Hampshire": {
        "code": "NH",
        "name": "New Hampshire Coalition Against Domestic and Sexual Violence",
        "website": "https://www.nhcadsv.org/",
    },
    "New Jersey": {
        "code": "NJ",
        "name": "New Jersey Coalition to End Domestic Violence",
        "website": "https://www.njcedv.org/",
    },
    "New Mexico": {
        "code": "NM",
        "name": "New Mexico Coalition Against Domestic Violence",
        "website": "https://www.nmcadv.org/",
    },
    "New York": {
        "code": "NY",
        "name": "New York State Coalition Against Domestic Violence",
        "website": "https://www.nyscadv.org/",
    },
    "North Carolina": {
        "code": "NC",
        "name": "North Carolina Coalition Against Domestic Violence",
        "website": "https://nccadv.org/",
    },
    "North Dakota": {
        "code": "ND",
        "name": "North Dakota Domestic and Sexual Violence Coalition",
        "website": "https://nddsvc.org/",
    },
    "Ohio": {
        "code": "OH",
        "name": "Ohio Domestic Violence Network",
        "website": "https://www.odvn.org/",
    },
    "Oklahoma": {
        "code": "OK",
        "name": "Oklahoma Attorney General Certified Victim Services Programs",
        "website": "https://www.oag.ok.gov/",
        "note": (
            "NNEDV directs visitors to Oklahoma's Attorney General "
            "certified victim-services program list."
        ),
    },
    "Oregon": {
        "code": "OR",
        "name": "Oregon Coalition Against Domestic and Sexual Violence",
        "website": "https://www.ocadsv.org/",
    },
    "Pennsylvania": {
        "code": "PA",
        "name": "Pennsylvania Coalition Against Domestic Violence",
        "website": "https://www.pcadv.org/",
    },
    "Rhode Island": {
        "code": "RI",
        "name": "Rhode Island Coalition Against Domestic Violence",
        "website": "https://www.ricadv.org/",
    },
    "South Carolina": {
        "code": "SC",
        "name": "South Carolina Coalition Against Domestic Violence and Sexual Assault",
        "website": "https://www.sccadvasa.org/",
    },
    "South Dakota": {
        "code": "SD",
        "name": "South Dakota Network Against Family Violence and Sexual Assault",
        "website": "https://sdnafvsa.com/",
    },
    "Tennessee": {
        "code": "TN",
        "name": "Tennessee Coalition to End Domestic and Sexual Violence",
        "website": "https://www.tncoalition.org/",
    },
    "Texas": {
        "code": "TX",
        "name": "Texas Council on Family Violence",
        "website": "https://tcfv.org/",
    },
    "Utah": {
        "code": "UT",
        "name": "Utah Domestic Violence Coalition",
        "website": "https://udvc.org/",
    },
    "Vermont": {
        "code": "VT",
        "name": "Vermont Network Against Domestic and Sexual Violence",
        "website": "https://vtnetwork.org/",
    },
    "Virginia": {
        "code": "VA",
        "name": "Virginia Sexual and Domestic Violence Action Alliance",
        "website": "https://vsdvalliance.org/",
    },
    "Washington": {
        "code": "WA",
        "name": "Washington State Coalition Against Domestic Violence",
        "website": "https://wscadv.org/",
    },
    "West Virginia": {
        "code": "WV",
        "name": "West Virginia Coalition Against Domestic Violence",
        "website": "https://wvcadv.org/",
    },
    "Wisconsin": {
        "code": "WI",
        "name": "End Domestic Abuse Wisconsin",
        "website": "https://www.endabusewi.org/",
    },
    "Wyoming": {
        "code": "WY",
        "name": "Wyoming Coalition Against Domestic Violence and Sexual Assault",
        "website": "https://www.wyomingdvsa.org/",
    },
}


def get_state_names():
    """Return all 50 states in alphabetical order."""
    return sorted(STATE_COALITIONS.keys())


def get_state_resource(state):
    """Return one state's resource record."""
    if state not in STATE_COALITIONS:
        raise KeyError(f"Unknown state: {state}")

    record = dict(STATE_COALITIONS[state])

    record["state"] = state
    record["resource_categories"] = [
        "Domestic violence advocacy",
        "Sexual assault services",
        "Shelter and housing",
        "Legal assistance",
        "Victim services",
        "Community assistance",
    ]

    return record


def get_local_resource_links(state, zip_code=""):
    """
    Return national/local resource locators.

    These links are search portals, not claims that a particular
    local provider has been verified.
    """

    state_record = get_state_resource(state)

    location = zip_code.strip() or state

    encoded_location = quote_plus(location)

    return {
        "state": state,
        "location_search": location,

        "domestic_violence": {
            "label": "State domestic violence coalition",
            "url": state_record["website"],
            "source": NNEDV_SOURCE,
        },

        "sexual_assault": {
            "label": "State and territory sexual assault coalition directory",
            "url": DOJ_STATE_SOURCE,
            "source": DOJ_STATE_SOURCE,
        },

        "shelter_and_housing": {
            "label": "HUD Find Shelter",
            "url": HUD_SHELTER,
            "source": HUD_SHELTER,
        },

        "legal_aid": {
            "label": "Legal Services Corporation legal aid locator",
            "url": LEGAL_AID_LOCATOR,
            "source": LEGAL_AID_LOCATOR,
        },

        "free_legal_information": {
            "label": "LawHelp",
            "url": LAWHELP,
            "source": LAWHELP,
        },

        "victim_services": {
            "label": "U.S. Department of Justice survivor resources",
            "url": DOJ_SURVIVOR_RESOURCES,
            "source": DOJ_SURVIVOR_RESOURCES,
        },

        "community_assistance": {
            "label": "211 community assistance",
            "url": UNITED_WAY_211,
            "source": UNITED_WAY_211,
        },

        "local_services": {
            "label": "Findhelp local services",
            "url": FINDHELP,
            "source": FINDHELP,
        },

        "search_queries": {
            "shelters": (
                f"https://www.google.com/search?q="
                f"{quote_plus('domestic violence shelters ' + location)}"
            ),
            "sexual_assault": (
                f"https://www.google.com/search?q="
                f"{quote_plus('sexual assault service providers ' + location)}"
            ),
            "legal": (
                f"https://www.google.com/search?q="
                f"{quote_plus('free legal aid domestic violence ' + location)}"
            ),
            "advocacy": (
                f"https://www.google.com/search?q="
                f"{quote_plus('victim advocacy services ' + location)}"
            ),
        },
    }


def get_all_state_records():
    """Return all 50 states as serializable records."""
    records = []

    for state in get_state_names():
        record = get_state_resource(state)
        record["local_resource_finders"] = get_local_resource_links(state)
        records.append(record)

    return records


def export_directory():
    """Return a JSON-compatible directory export."""
    return {
        "application": "Survivors Network",
        "author": "Hope Jones",
        "directory_version": DIRECTORY_VERSION,
        "source_review_date": LAST_SOURCE_REVIEW,
        "source": NNEDV_SOURCE,
        "state_count": len(STATE_COALITIONS),
        "states": get_all_state_records(),
        "national_hotlines": NATIONAL_HOTLINES,
    }
