const ROUTE_CLASS = {
  "Fast-Track": "route-fast",
  "Standard Review": "route-standard",
  "Specialist Queue": "route-specialist",
  "Investigation Flag": "route-investigation",
  "Manual Review": "route-manual",
};

const API_BASE = "/api/v1";
const ALLOWED_EXTENSIONS = [".pdf", ".docx"];
const MAX_FILE_SIZE = 10 * 1024 * 1024;

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

const STACKED_FIELD_KEYS = new Set(["location", "thirdParties", "contactDetails", "attachments"]);

const FIELD_LABELS = {
  policyNumber: "Policy Number",
  policyholderName: "Policyholder Name",
  effectiveDates: "Effective Dates",
  date: "Date",
  time: "Time",
  location: "Location",
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

let selectedFile = null;

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
    return body.success === true && "data" in body ? body.data : body;
  } catch (_error) {
    return {
      error: "Unable to reach the FNOL claims processor. Please try again.",
      code: "NETWORK_ERROR",
    };
  }
}

function setBusy(isBusy) {
  const btn = document.getElementById("processBtn");
  btn.disabled = isBusy || !selectedFile;
  btn.innerHTML = isBusy ? "Processing…" : 'Process claim <span aria-hidden="true">→</span>';
}

function setStatus(text) {
  document.getElementById("resultStatus").textContent = text;
}

function getExtension(filename) {
  const name = (filename || "").toLowerCase();
  const dot = name.lastIndexOf(".");
  return dot >= 0 ? name.slice(dot) : "";
}

function validateFile(file) {
  const extension = getExtension(file.name);
  if (!ALLOWED_EXTENSIONS.includes(extension)) {
    return "Unsupported file type. Please choose a PDF (.pdf) or Word (.docx) document.";
  }
  if (file.size > MAX_FILE_SIZE) {
    return "File is too large. The maximum supported size is 10 MB.";
  }
  return null;
}

function selectFile(file) {
  const error = validateFile(file);
  if (error) {
    selectedFile = null;
    document.getElementById("selectedFile").hidden = true;
    document.getElementById("processBtn").disabled = true;
    document.getElementById("fileHint").textContent = error;
    setStatus("INVALID FILE");
    return false;
  }

  selectedFile = file;
  document.getElementById("selectedFileName").textContent = file.name;
  document.getElementById("selectedFile").hidden = false;
  document.getElementById("processBtn").disabled = false;
  document.getElementById("fileHint").textContent = `${file.name} selected. Ready to process.`;
  return true;
}

function clearSelectedFile() {
  selectedFile = null;
  document.getElementById("fileInput").value = "";
  document.getElementById("selectedFile").hidden = true;
  document.getElementById("processBtn").disabled = true;
  document.getElementById("fileHint").textContent = "Only PDF and Word (.docx) documents can be submitted. Files are processed by the FNOL pipeline.";
  setStatus("AWAITING DOCUMENT");
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
  document.getElementById("reasoning").textContent = result.error || "The document could not be processed.";
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
  document.getElementById("resultCard").hidden = false;
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
    const orderedFields = schemaOrder ? schemaOrder.filter((key) => key in fields) : Object.keys(fields);

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

async function processSelectedFile() {
  if (!selectedFile) return;

  setBusy(true);
  setStatus("PROCESSING");
  document.getElementById("fileHint").textContent = `Processing: ${selectedFile.name}`;

  const formData = new FormData();
  formData.append("file", selectedFile);

  try {
    const result = await fetchJSON(`${API_BASE}/claims/process-upload`, {
      method: "POST",
      body: formData,
    });
    document.getElementById("fileHint").textContent = result.error || `Processed: ${selectedFile.name}`;
    renderResult(result);
  } finally {
    setBusy(false);
  }
}

const fileInput = document.getElementById("fileInput");
const uploadZone = document.getElementById("uploadZone");

fileInput.addEventListener("change", (event) => {
  const file = event.target.files[0];
  if (file) selectFile(file);
});

document.getElementById("processBtn").addEventListener("click", processSelectedFile);
document.getElementById("removeFileBtn").addEventListener("click", clearSelectedFile);

["dragenter", "dragover"].forEach((eventName) => {
  uploadZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    uploadZone.classList.add("upload-zone--active");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  uploadZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    uploadZone.classList.remove("upload-zone--active");
  });
});

uploadZone.addEventListener("drop", (event) => {
  const file = event.dataTransfer.files[0];
  if (file) selectFile(file);
});

uploadZone.addEventListener("click", (event) => {
  if (!event.target.closest("label")) fileInput.click();
});
