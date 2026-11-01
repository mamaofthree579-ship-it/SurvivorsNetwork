
"use strict";

const DIRECTORY_URL = "./state_resource_directory.json";

const STATE_NAMES = {
    AL: "Alabama", AK: "Alaska", AZ: "Arizona", AR: "Arkansas",
    CA: "California", CO: "Colorado", CT: "Connecticut",
    DE: "Delaware", FL: "Florida", GA: "Georgia", HI: "Hawaii",
    ID: "Idaho", IL: "Illinois", IN: "Indiana", IA: "Iowa",
    KS: "Kansas", KY: "Kentucky", LA: "Louisiana", ME: "Maine",
    MD: "Maryland", MA: "Massachusetts", MI: "Michigan",
    MN: "Minnesota", MS: "Mississippi", MO: "Missouri",
    MT: "Montana", NE: "Nebraska", NV: "Nevada",
    NH: "New Hampshire", NJ: "New Jersey", NM: "New Mexico",
    NY: "New York", NC: "North Carolina", ND: "North Dakota",
    OH: "Ohio", OK: "Oklahoma", OR: "Oregon",
    PA: "Pennsylvania", RI: "Rhode Island",
    SC: "South Carolina", SD: "South Dakota",
    TN: "Tennessee", TX: "Texas", UT: "Utah",
    VT: "Vermont", VA: "Virginia", WA: "Washington",
    WV: "West Virginia", WI: "Wisconsin", WY: "Wyoming",
    DC: "District of Columbia"
};

const STATE_CODES_BY_NAME = Object.fromEntries(
    Object.entries(STATE_NAMES).map(([code, name]) => [
        name.toLowerCase(), code
    ])
);

let allResources = [];
let visibleResources = [];

document.addEventListener("DOMContentLoaded", initialize);

async function initialize() {
    connectNavigation();
    connectFilters();

    try {
        await loadDirectory();
    } catch (error) {
        showDirectoryError(
            "The public directory could not be loaded. " +
            "Please try again later."
        );
        console.error("Directory loading error:", error);
    }
}

function connectNavigation() {
    const buttons = document.querySelectorAll("[data-view]");

    buttons.forEach(button => {
        button.addEventListener("click", () => {
            const target = button.dataset.view;

            document.querySelectorAll(".nav-button").forEach(item => {
                item.classList.remove("active");
                item.removeAttribute("aria-current");
            });

            button.classList.add("active");
            button.setAttribute("aria-current", "page");

            document.querySelectorAll(".view").forEach(view => {
                const isActive = view.id === `${target}-view`;
                view.classList.toggle("active", isActive);
                view.hidden = !isActive;
            });
        });
    });
}

function connectFilters() {
    document.getElementById("resource-search")
        ?.addEventListener("input", applyFilters);

    document.getElementById("state-filter")
        ?.addEventListener("change", applyFilters);

    document.getElementById("category-filter")
        ?.addEventListener("change", applyFilters);

    document.getElementById("clear-filters")
        ?.addEventListener("click", () => {
            document.getElementById("resource-search").value = "";
            document.getElementById("state-filter").value = "";
            document.getElementById("category-filter").value = "";
            applyFilters();
        });
}

async function loadDirectory() {
    const response = await fetch(DIRECTORY_URL, {
        cache: "no-cache"
    });

    if (!response.ok) {
        throw new Error(`Directory request failed: ${response.status}`);
    }

    const data = await response.json();

    allResources = extractResources(data);

    if (!allResources.length) {
        showDirectoryError(
            "The directory file loaded, but no usable public resource " +
            "records were found. Check the directory data structure."
        );
        return;
    }

    populateFilters();
    applyFilters();

    const status = document.getElementById("directory-status");
    status.textContent =
        "Public resource directory loaded successfully.";
    status.classList.remove("error");

    displayUpdatedDate(data);
}

function extractResources(data) {
    const records = [];
    const visited = new WeakSet();

    function walk(value, inheritedState = "") {
        if (!value || typeof value !== "object") return;
        if (visited.has(value)) return;

        visited.add(value);

        if (Array.isArray(value)) {
            value.forEach(item => walk(item, inheritedState));
            return;
        }

        const name = firstValue(value, [
            "name", "organization", "organization_name",
            "org_name", "agency", "title"
        ]);

        const website = firstValue(value, [
            "website", "url", "web_url", "resolved_url"
        ]);

        const stateValue = firstValue(value, [
            "state", "state_name", "state_code", "code", "abbr"
        ]) || inheritedState;

        if (name && (website || hasPublicContact(value))) {
            const normalized = normalizeResource(
                value, name, website, stateValue
            );

            if (normalized) records.push(normalized);
            return;
        }

        for (const [key, child] of Object.entries(value)) {
            const possibleState = normalizeState(key);

            walk(
                child,
                possibleState || inheritedState
            );
        }
    }

    walk(data);

    const seen = new Set();

    return records.filter(record => {
        const identity = [
            record.name.toLowerCase(),
            record.stateCode,
            record.website.toLowerCase()
        ].join("|");

        if (seen.has(identity)) return false;
        seen.add(identity);
        return true;
    });
}

function normalizeResource(source, name, website, stateValue) {
    const state = normalizeState(stateValue);

    const category = firstValue(source, [
        "category", "type", "service_category", "resource_type"
    ]);

    const services = normalizeList(
        source.services ||
        source.service_types ||
        source.programs ||
        source.supports
    );

    const description = firstValue(source, [
        "description", "summary", "excerpt", "new_excerpt",
        "content", "service_description"
    ]);

    const eligibility = firstValue(source, [
        "eligibility", "eligibility_requirements",
        "who_can_apply", "population_served"
    ]);

    const phone = firstValue(source, [
        "phone", "telephone", "phone_number"
    ]);

    const email = firstValue(source, [
        "email", "contact_email"
    ]);

    const address = firstValue(source, [
        "address", "street_address", "location_address"
    ]);

    const city = firstValue(source, ["city", "locality"]);

    const postalCode = firstValue(source, [
        "zip", "zip_code", "postal_code"
    ]);

    const verifiedDate = firstValue(source, [
        "verified_at", "last_verified", "last_checked"
    ]);

    const websiteUrl = safeUrl(website);

    return {
        name: String(name),
        state: state.name,
        stateCode: state.code,
        category: String(category || "Other resources"),
        services,
        description: String(description || ""),
        eligibility: String(eligibility || ""),
        phone: String(phone || ""),
        email: String(email || ""),
        address: String(address || ""),
        city: String(city || ""),
        postalCode: String(postalCode || ""),
        website: websiteUrl,
        verifiedDate: String(verifiedDate || "")
    };
}

function hasPublicContact(value) {
    return Boolean(
        firstValue(value, [
            "phone", "telephone", "phone_number",
            "email", "contact_email"
        ])
    );
}

function firstValue(object, keys) {
    for (const key of keys) {
        const value = object[key];

        if (
            value !== undefined &&
            value !== null &&
            String(value).trim() !== ""
        ) {
            if (Array.isArray(value)) {
                return value.map(String).join(", ");
            }

            if (typeof value === "object") continue;

            return String(value).trim();
        }
    }

    return "";
}

function normalizeList(value) {
    if (Array.isArray(value)) {
        return value
            .map(item => String(item).trim())
            .filter(Boolean);
    }

    if (typeof value === "string" && value.trim()) {
        return value
            .split(/[,;|]/)
            .map(item => item.trim())
            .filter(Boolean);
    }

    return [];
}

function normalizeState(value) {
    const raw = String(value || "").trim();

    if (!raw) return { name: "", code: "" };

    const upper = raw.toUpperCase();

    if (STATE_NAMES[upper]) {
        return {
            name: STATE_NAMES[upper],
            code: upper
        };
    }

    const lower = raw.toLowerCase();
    const code = STATE_CODES_BY_NAME[lower];

    if (code) {
        return {
            name: STATE_NAMES[code],
            code
        };
    }

    return {
        name: raw,
        code: ""
    };
}

function safeUrl(value) {
    if (!value) return "";

    try {
        const url = new URL(String(value));

        if (url.protocol !== "https:" && url.protocol !== "http:") {
            return "";
        }

        return url.href;
    } catch {
        return "";
    }
}

function safePhoneLink(value) {
    const cleaned = String(value || "").replace(/[^\d+]/g, "");

    if (cleaned.length < 7) return "";

    return `tel:${cleaned}`;
}

function populateFilters() {
    const stateSelect = document.getElementById("state-filter");
    const categorySelect = document.getElementById("category-filter");

    const states = [...new Set(
        allResources
            .map(item => item.state)
            .filter(Boolean)
    )].sort();

    const categories = [...new Set(
        allResources
            .map(item => item.category)
            .filter(Boolean)
    )].sort();

    states.forEach(state => {
        const option = document.createElement("option");
        option.value = state;
        option.textContent = state;
        stateSelect.appendChild(option);
    });

    categories.forEach(category => {
        const option = document.createElement("option");
        option.value = category;
        option.textContent = category;
        categorySelect.appendChild(option);
    });
}

function applyFilters() {
    const query = document.getElementById("resource-search")
        .value.trim().toLowerCase();

    const selectedState = document.getElementById("state-filter").value;
    const selectedCategory =
        document.getElementById("category-filter").value;

    visibleResources = allResources.filter(resource => {
        const searchable = [
            resource.name,
            resource.state,
            resource.category,
            resource.services.join(" "),
            resource.description,
            resource.eligibility,
            resource.city
        ].join(" ").toLowerCase();

        const matchesQuery = !query || searchable.includes(query);
        const matchesState =
            !selectedState || resource.state === selectedState;
        const matchesCategory =
            !selectedCategory ||
            resource.category === selectedCategory;

        return matchesQuery && matchesState && matchesCategory;
    });

    renderResources();
    updateResultCount();
}

function renderResources() {
    const container = document.getElementById("resource-results");
    container.replaceChildren();

    if (!visibleResources.length) {
        const empty = document.createElement("div");
        empty.className = "status-message";
        empty.textContent =
            "No resources match those filters. Try another search " +
            "or clear the filters.";
        container.appendChild(empty);
        return;
    }

    visibleResources.forEach(resource => {
        container.appendChild(createResourceCard(resource));
    });
}

function createResourceCard(resource) {
    const card = document.createElement("article");
    card.className = "resource-card";

    const title = document.createElement("h2");
    title.textContent = resource.name;
    card.appendChild(title);

    const locationParts = [
        resource.city,
        resource.state
    ].filter(Boolean);

    if (resource.address) locationParts.unshift(resource.address);
    if (resource.postalCode) locationParts.push(resource.postalCode);

    if (locationParts.length) {
        const location = document.createElement("p");
        location.className = "resource-location";
        location.textContent = locationParts.join(", ");
        card.appendChild(location);
    }

    const category = document.createElement("span");
    category.className = "resource-category";
    category.textContent = resource.category;
    card.appendChild(category);

    if (resource.services.length) {
        const services = document.createElement("p");
        services.className = "resource-description";
        services.textContent =
            "Services: " + resource.services.join(", ");
        card.appendChild(services);
    }

    if (resource.description) {
        const description = document.createElement("p");
        description.className = "resource-description";
        description.textContent = resource.description;
        card.appendChild(description);
    }

    if (resource.eligibility) {
        const eligibility = document.createElement("p");
        eligibility.className = "resource-meta";
        eligibility.textContent =
            "Eligibility: " + resource.eligibility;
        card.appendChild(eligibility);
    }

    const contact = document.createElement("div");
    contact.className = "resource-contact";

    if (resource.website) {
        const website = document.createElement("a");
        website.href = resource.website;
        website.target = "_blank";
        website.rel = "noopener noreferrer";
        website.textContent = "Website";
        contact.appendChild(website);
    }

    if (resource.phone) {
        const phoneLink = safePhoneLink(resource.phone);

        if (phoneLink) {
            const phone = document.createElement("a");
            phone.href = phoneLink;
            phone.textContent = "Call: " + resource.phone;
            contact.appendChild(phone);
        } else {
            const phone = document.createElement("span");
            phone.textContent = "Phone: " + resource.phone;
            contact.appendChild(phone);
        }
    }

    if (resource.email) {
        const email = document.createElement("a");
        email.href = `mailto:${resource.email}`;
        email.textContent = "Email";
        contact.appendChild(email);
    }

    if (contact.childNodes.length) {
        card.appendChild(contact);
    }

    if (resource.verifiedDate) {
        const verified = document.createElement("p");
        verified.className = "resource-meta";
        verified.textContent =
            "Last verification recorded: " + resource.verifiedDate;
        card.appendChild(verified);
    }

    return card;
}

function updateResultCount() {
    const count = document.getElementById("result-count");
    const total = visibleResources.length;

    count.textContent =
        `${total} ${total === 1 ? "resource" : "resources"} found`;
}

function displayUpdatedDate(data) {
    const target = document.getElementById("directory-updated");

    if (!target || !data || typeof data !== "object") return;

    const dateValue = firstValue(data, [
        "updated_at", "last_updated", "generated_at",
        "exported_at", "timestamp"
    ]);

    if (!dateValue) return;

    target.textContent = "Directory file timestamp: " + dateValue;
}

function showDirectoryError(message) {
    const status = document.getElementById("directory-status");

    status.textContent = message;
    status.classList.add("error");

    document.getElementById("resource-results").replaceChildren();

    document.getElementById("result-count").textContent =
        "Directory unavailable";
}
