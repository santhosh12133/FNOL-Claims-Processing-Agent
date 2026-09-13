const ROUTE_CLASS = {
  "Fast-Track": "route-fast",
  "Standard Review": "route-standard",
  "Specialist Queue": "route-specialist",
  "Investigation Flag": "route-investigation",
  "Manual Review": "route-manual",
};

const API_BASE = "/api/v1";

const CATEGORY_LABELS = {
  policyInformation: "Policy Information",
  incidentInformation: "Incident Information",
  involvedParties: "Involved Parties",
  assetDetails: "Asset Details",
  otherMandatoryFields: "Other Mandatory Fields",
};

const CATEGORY_ORDER = [
  "policyInformation",
  "incidentInformation",
  "involvedParties",
  "assetDetails",
  "otherMandatoryFields",
];

const FIELD_ORDER = {
  policyInformation: ["policyNumber", "policyholderName", "effectiveDates"],
  incidentInformation: ["date", "time", "location"],
  involvedParties: ["claimant", "thirdParties", "contactDetails"],
  assetDetails: ["assetType", "assetId", "estimatedDamage"],
  otherMandatoryFields: ["claimType", "attachments", "initialEstimate"],
};

const STACKED_FIELD_KEYS = new Set([
  "location",
  "thirdParties",
  "contactDetails",
  "attachments",
]);

const FIELD_LABELS = {
  policyNumber: "Policy Number",
  policyholderName: "Policyholder Name",
  effectiveDates: "Effective Dates",
  date: "Date",
  time: "Time",
  location: "Location",
  description: "Description",
  claimant: "Claimant",
  thirdParties: "Third Parties",
  contactDetails: "Contact Details",
  assetType: "Asset Type",
  assetId: "Asset ID",
  estimatedDamage: "Estimated Damage",
  claimType: "Claim Type",
  attachments: "Attachments",
  initialEstimate: "Initial Estimate",
};

async function fetchJSON(url, options) {
  try {
    const res = await fetch(url, options);
    const body = await res.json().catch(() => ({}));

    if (!res.ok || body.success === false) {
      const error = body.error || {};
      return {
        error: typeof error === "string" ? error : error.message || `Request failed (${res.status}).`,
        code: typeof error === "object" ? error.code || "REQUEST_ERROR" : "REQUEST_ERROR",
        requestId: typeof error === "object" ? error.requestId : null,
      };
    }

    // v1 endpoints wrap payloads in { success, data }.
    return body.success === true && "data" in body ? body.data : body;
  } catch (_error) {
    return {
      error: "Unable to reach the local claims processor. Check that the Flask app is running.",
      code: "NETWORK_ERROR",
    };
  }
}

function setBusy(isBusy) {
  const btn = document.getElementById("processBtn");
  btn.disabled = isBusy;
  btn.innerHTML = isBusy ? "Processing…" : 'Process claim <span aria-hidden="true">→</span>';
}

function setStatus(text) {
  document.getElementById("resultStatus").textContent = text;
}

async function loadSamples() {
  const samples = await fetchJSON(`${API_BASE}/samples`);
  const row = document.getElementById("sampleRow");
  row.innerHTML = "";
  if (samples.error) {
    document.getElementById("fileHint").textContent = samples.error;
    return;
  }
  samples.forEach((sample) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "sample-pill";
    btn.textContent = sample.label;
    btn.title = sample.filename;
    btn.addEventListener("click", () => onSampleClick(sample));
    row.appendChild(btn);
  });
}

async function onSampleClick(sample) {
  const textInput = document.getElementById("textInput");
  const fileHint = document.getElementById("fileHint");
  setBusy(true);
  setStatus("PROCESSING");

  try {
    if (sample.isPdf) {
      textInput.value = "";
      fileHint.textContent = `Loaded: ${sample.filename} (PDF processed directly)`;
    } else {
      const data = await fetchJSON(`${API_BASE}/samples/${encodeURIComponent(sample.filename)}/text`);
      if (data.error) {
        renderError(data);
        return;
      }
      textInput.value = data.text || "";
      fileHint.textContent = `Loaded: ${sample.filename}`;
    }

    const result = await fetchJSON(`${API_BASE}/claims/process-sample/${encodeURIComponent(sample.filename)}`, { method: "POST" });
    renderResult(result);
  } finally {
    setBusy(false);
  }
}

function fillList(elementId, items) {
  const el = document.getElementById(elementId);
  el.innerHTML = "";
  const count = Array.isArray(items) ? items.length : 0;
  const countId = elementId === "missingList" ? "missingCount" : "inconsistencyCount";
  document.getElementById(countId).textContent = count;

  if (count === 0) {
    const li = document.createElement("li");
    li.className = "flag-list__none";
    li.textContent = "No issues found";
    el.appendChild(li);
    return;
  }
  items.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = FIELD_LABELS[item] || item;
    el.appendChild(li);
  });
}

function setIncidentDescription(text) {
  const container = document.getElementById("incidentDescription");
  const body = document.getElementById("incidentDescriptionText");
  const value = (text || "").trim();
  body.textContent = value;
  container.hidden = !value;
}

function renderError(result) {
  document.getElementById("resultEmpty").hidden = true;
  document.getElementById("resultCard").hidden = false;
  document.getElementById("sourceFile").textContent = result.code || "PROCESSING ERROR";
  document.getElementById("reasoning").textContent = result.error || "The claim could not be processed.";
  document.getElementById("stamp").textContent = "Unable to process";
  document.getElementById("stamp").className = "stamp route-manual";
  setIncidentDescription("");
  fillList("missingList", []);
  fillList("inconsistencyList", []);
  document.getElementById("fieldsGrid").innerHTML = "";
  setStatus("ERROR");
}

function renderResult(result) {
  if (result.error && !result.recommendedRoute) {
    renderError(result);
    return;
  }

  document.getElementById("resultEmpty").hidden = true;
  const card = document.getElementById("resultCard");
  card.hidden = false;
  setStatus("DECISION READY");

  const stamp = document.getElementById("stamp");
  document.getElementById("sourceFile").textContent = result.sourceFile || "Processed claim";
  stamp.textContent = result.recommendedRoute || "Review Required";
  stamp.className = "stamp " + (ROUTE_CLASS[result.recommendedRoute] || "route-manual");
  stamp.classList.remove("stamp--animate");
  void stamp.offsetWidth;
  stamp.classList.add("stamp--animate");

  document.getElementById("reasoning").textContent = result.reasoning || "No routing explanation was returned.";
  setIncidentDescription(result.extractedFields?.incidentInformation?.description);
  fillList("missingList", result.missingFields);
  fillList("inconsistencyList", result.inconsistencies);

  const grid = document.getElementById("fieldsGrid");
  grid.innerHTML = "";
  const extractedFields = result.extractedFields || {};
  const orderedCategories = [
    ...CATEGORY_ORDER.filter((category) => category in extractedFields),
    ...Object.keys(extractedFields).filter((category) => !CATEGORY_ORDER.includes(category)),
  ];

  orderedCategories.forEach((category) => {
    const fields = extractedFields[category] || {};
    const fieldCard = document.createElement("div");
    fieldCard.className = "field-card";

    const title = document.createElement("div");
    title.className = "field-card__title";
    title.textContent = CATEGORY_LABELS[category] || category;
    fieldCard.appendChild(title);

    const schemaOrder = FIELD_ORDER[category];
    const orderedFields = schemaOrder
      ? schemaOrder.filter((key) => key in fields)
      : Object.keys(fields);

    orderedFields.forEach((key) => {
      const value = fields[key];
      const row = document.createElement("div");
      row.className = "field-row";
      if (STACKED_FIELD_KEYS.has(key)) row.classList.add("field-row--stacked");

      const label = document.createElement("span");
      label.className = "field-row__label";
      label.textContent = FIELD_LABELS[key] || key;

      const val = document.createElement("span");
      val.className = value ? "field-row__value" : "field-row__value field-row__value--missing";
      val.textContent = value || "—";

      row.appendChild(label);
      row.appendChild(val);
      fieldCard.appendChild(row);
    });

    grid.appendChild(fieldCard);
  });
}

document.getElementById("processBtn").addEventListener("click", async () => {
  const text = document.getElementById("textInput").value.trim();
  if (!text) {
    renderError({ error: "Paste an FNOL document or select a sample before processing.", code: "EMPTY_INPUT" });
    return;
  }

  setBusy(true);
  setStatus("PROCESSING");
  try {
    const result = await fetchJSON(`${API_BASE}/claims/process-text`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    document.getElementById("fileHint").textContent = result.error ? result.error : "Processed pasted text";
    renderResult(result);
  } finally {
    setBusy(false);
  }
});

document.getElementById("fileInput").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;

  setBusy(true);
  setStatus("PROCESSING");
  document.getElementById("fileHint").textContent = `Uploading: ${file.name}`;

  const formData = new FormData();
  formData.append("file", file);
  try {
    const result = await fetchJSON(`${API_BASE}/claims/process-upload`, { method: "POST", body: formData });
    document.getElementById("fileHint").textContent = result.error ? result.error : `Processed: ${file.name}`;
    renderResult(result);
  } finally {
    setBusy(false);
    event.target.value = "";
  }
});

loadSamples();
