
"use strict";

const DIRECTORY_URL = "./state_resource_directory.json";

let allResources = [];
let visibleResources = [];

document.addEventListener("DOMContentLoaded", initialize);

async function initialize() {
    connectNavigation();
    connectFilters();

    // Categories are not present in the current source data.
    // Hide that filter rather than displaying a misleading option.
    const categoryFilter = document.getElementById("category-filter");
    if (categoryFilter) {
        const categoryContainer = categoryFilter.closest("div");
        if (categoryContainer) categoryContainer.hidden = true;
    }

    try {
        await loadDirectory();
    } catch (error) {
        console.error("Directory loading error:", error);
        showDirectoryError(
            "The public directory could not be loaded. " +
            "Please try again later."
        );
    }
}

function connectNavigation() {
    document.querySelectorAll("[data-view]").forEach(button => {
        button.addEventListener("click", () => {
            const target = button.dataset.view;

            document.querySelectorAll(".nav-button").forEach(item => {
                item.classList.remove("active");
                item.removeAttribute("aria-current");
            });

            button.classList.add("active");
            button.setAttribute("aria-current", "page");

            document.querySelectorAll(".view").forEach(view => {
                const active = view.id === `${target}-view`;
                view.classList.toggle("active", active);
                view.hidden = !active;
            });
        });
    });
}

function connectFilters() {
    document.getElementById("resource-search")
        ?.addEventListener("input", applyFilters);

    document.getElementById("state-filter")
        ?.addEventListener("change", applyFilters);

    document.getElementById("clear-filters")
        ?.addEventListener("click", () => {
            document.getElementById("resource-search").value = "";
            document.getElementById("state-filter").value = "";

            applyFilters();
        });
}

async function loadDirectory() {
    const response = await fetch(DIRECTORY_URL, {
        cache: "no-cache"
    });

    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();

    if (
        !data ||
        typeof data !== "object" ||
        Array.isArray(data)
    ) {
        throw new Error("Unexpected directory format.");
    }

    allResources = normalizeDirectory(data);

    if (!allResources.length) {
        showDirectoryError(
            "The directory file loaded, but no usable state " +
            "resource records were found."
        );
        return;
    }

    populateStateFilter();
    applyFilters();

    const status = document.getElementById("directory-status");
    status.textContent =
        `Public directory loaded: ${allResources.length} state listings.`;
    status.classList.remove("error");
}

function normalizeDirectory(data) {
    const resources = [];

    for (const [stateName, entry] of Object.entries(data)) {
        if (
            !entry ||
            typeof entry !== "object" ||
            Array.isArray(entry)
        ) {
            continue;
        }

        const name = cleanText(entry.name);
        const code = cleanText(entry.code).toUpperCase();
        const website = validateWebsite(entry.website);
        const note = cleanText(entry.note);

        // A name and a valid website are required for a public listing.
        // Missing phone or email is not a reason to reject a listing.
        if (!name || !website) {
            console.warn(
                `Skipping incomplete public listing for ${stateName}.`
            );
            continue;
        }

        resources.push({
            state: cleanText(stateName),
            code,
            name,
            website,
            note
        });
    }

    return resources.sort((a, b) =>
        a.state.localeCompare(b.state)
    );
}

function cleanText(value) {
    if (
        value === undefined ||
        value === null ||
        typeof value === "object"
    ) {
        return "";
    }

    return String(value).trim();
}

function validateWebsite(value) {
    const raw = cleanText(value);

    if (!raw) return "";

    try {
        const url = new URL(raw);

        if (
            url.protocol !== "https:" &&
            url.protocol !== "http:"
        ) {
            return "";
        }

        return url.href;
    } catch {
        return "";
    }
}

function populateStateFilter() {
    const select = document.getElementById("state-filter");

    if (!select) return;

    // Keep the original "All states" option.
    select.replaceChildren();

    const allOption = document.createElement("option");
    allOption.value = "";
    allOption.textContent = "All states";
    select.appendChild(allOption);

    allResources.forEach(resource => {
        const option = document.createElement("option");
        option.value = resource.state;
        option.textContent =
            `${resource.state} (${resource.code})`;

        select.appendChild(option);
    });
}

function applyFilters() {
    const search = (
        document.getElementById("resource-search")?.value || ""
    ).trim().toLowerCase();

    const selectedState =
        document.getElementById("state-filter")?.value || "";

    visibleResources = allResources.filter(resource => {
        const searchable = [
            resource.state,
            resource.code,
            resource.name,
            resource.note
        ].join(" ").toLowerCase();

        const matchesSearch =
            !search || searchable.includes(search);

        const matchesState =
            !selectedState || resource.state === selectedState;

        return matchesSearch && matchesState;
    });

    renderResources();
    updateResultCount();
}

function renderResources() {
    const container = document.getElementById("resource-results");

    if (!container) return;

    container.replaceChildren();

    if (!visibleResources.length) {
        const empty = document.createElement("div");
        empty.className = "status-message";
        empty.textContent =
            "No state listings match your search. " +
            "Try another search or clear the filters.";

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

    const code = document.createElement("span");
    code.className = "resource-category";
    code.textContent = resource.code;
    card.appendChild(code);

    const title = document.createElement("h2");
    title.textContent = resource.state;
    card.appendChild(title);

    const organization = document.createElement("p");
    organization.className = "resource-description";
    organization.textContent = resource.name;
    card.appendChild(organization);

    if (resource.note) {
        const note = document.createElement("p");
        note.className = "resource-meta";
        note.textContent = resource.note;
        card.appendChild(note);
    }

    const contact = document.createElement("div");
    contact.className = "resource-contact";

    const website = document.createElement("a");
    website.href = resource.website;
    website.target = "_blank";
    website.rel = "noopener noreferrer";
    website.textContent = "Visit organization website";

    contact.appendChild(website);
    card.appendChild(contact);

    return card;
}

function updateResultCount() {
    const count = document.getElementById("result-count");

    if (!count) return;

    const total = visibleResources.length;

    count.textContent =
        `${total} of ${allResources.length} state listings`;
}

function showDirectoryError(message) {
    const status = document.getElementById("directory-status");

    if (status) {
        status.textContent = message;
        status.classList.add("error");
    }

    const results = document.getElementById("resource-results");
    if (results) results.replaceChildren();

    const count = document.getElementById("result-count");
    if (count) count.textContent = "Directory unavailable";
}
