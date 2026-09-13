const ROUTE_CLASS = {
  "Fast-Track": "route-fast",
  "Standard Review": "route-standard",
  "Specialist Queue": "route-specialist",
  "Investigation Flag": "route-investigation",
  "Manual Review": "route-manual",
};

const API_BASE = "/api/v1";
const ALLOWED_EXTENSIONS = [".pdf", ".docx", ".jpg", ".jpeg", ".png", ".webp"];
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
let latestResult = null;

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
    return { error: "Unable to reach the FNOL claims processor. Please try again.", code: "NETWORK_ERROR" };
  }
}

function processingSpinner() {
  return `<svg class="processing-spinner" width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-dasharray="28" stroke-dashoffset="8"><animateTransform attributeName="transform" type="rotate" from="0 8 8" to="360 8 8" dur="0.8s" repeatCount="indefinite"/></circle></svg>`;
}

function setBusy(isBusy) {
  const btn = document.getElementById("processBtn");
  btn.disabled = isBusy || !selectedFile;
  btn.setAttribute("aria-busy", String(isBusy));
  btn.innerHTML = isBusy
    ? `${processingSpinner()}<span>Processing claim…</span>`
    : 'Next <span aria-hidden="true">→</span>';
}

function setStep(step) {
  const step1 = document.getElementById("step1");
  const step2 = document.getElementById("step2");
  const line = document.getElementById("stepLine");
  const intake = document.getElementById("intakePage");
  const result = document.getElementById("resultPage");

  if (step === 1) {
    intake.hidden = false;
    result.hidden = true;
    step1.classList.add("active");
    step1.classList.remove("complete");
    step2.classList.remove("active", "complete");
    line.classList.remove("complete");
    window.scrollTo({ top: 0, behavior: "smooth" });
  } else {
    intake.hidden = true;
    result.hidden = false;
    step1.classList.remove("active");
    step1.classList.add("complete");
    step2.classList.add("active");
    line.classList.add("complete");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
}

function getExtension(filename) {
  const name = (filename || "").toLowerCase();
  const dot = name.lastIndexOf(".");
  return dot >= 0 ? name.slice(dot) : "";
}

function validateFile(file) {
  const extension = getExtension(file.name);
  if (!ALLOWED_EXTENSIONS.includes(extension)) {
    return "Please choose a supported claim file.";
  }
  if (file.size > MAX_FILE_SIZE) {
    return "File is too large. The maximum supported size is 10 MB.";
  }
  return null;
}

function selectFile(file) {
  const error = validateFile(file);
  if (error) {
    clearSelectedFile(false);
    document.getElementById("fileHint").textContent = error;
    return false;
  }

  selectedFile = file;
  document.getElementById("selectedFileName").textContent = file.name;
  document.getElementById("fileSize").textContent = `${(file.size / 1024 / 1024).toFixed(2)} MB`;
  document.getElementById("selectedFile").hidden = false;
  document.getElementById("processBtn").disabled = false;
  document.getElementById("fileHint").textContent = "Claim file selected. Select Next to process the claim.";
  return true;
}

function clearSelectedFile(resetResult = true) {
  selectedFile = null;
  document.getElementById("fileInput").value = "";
  document.getElementById("selectedFile").hidden = true;
  document.getElementById("processBtn").disabled = true;
  document.getElementById("processBtn").setAttribute("aria-busy", "false");
  document.getElementById("processBtn").innerHTML = 'Next <span aria-hidden="true">→</span>';
  document.getElementById("fileHint").textContent = "Select a claim file to continue.";
  if (resetResult) setStep(1);
}

function fillList(elementId, items) {
  const el = document.getElementById(elementId);
  el.innerHTML = "";
  const values = Array.isArray(items) ? items : [];
  if (!values.length) {
    const li = document.createElement("li");
    li.className = "flag-list__none";
    li.textContent = "No issues found";
    el.appendChild(li);
    return;
  }
  values.forEach((item) => {
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
  latestResult = result;
  document.getElementById("successBanner").classList.add("error-banner");
  document.getElementById("successBanner").querySelector("strong").textContent = result.code || "PROCESSING ERROR";
  document.getElementById("resultSource").textContent = result.error || "The claim file could not be processed.";
  document.getElementById("stamp").textContent = "Unable to process";
  document.getElementById("stamp").className = "route-name route-manual";
  document.getElementById("recommendationSummary").textContent = "Please return to claim intake and submit a supported claim file.";
  document.getElementById("reasoning").textContent = result.error || "The claim file could not be processed.";
  document.getElementById("completenessMetric").textContent = "—";
  document.getElementById("missingMetric").textContent = "0";
  document.getElementById("inconsistencyMetric").textContent = "0";
  document.getElementById("riskMetric").textContent = "0";
  fillList("missingList", []);
  fillList("inconsistencyList", []);
  document.getElementById("fieldsGrid").innerHTML = "";
  setStep(2);
}

function renderResult(result) {
  if (result.error && !result.recommendedRoute) {
    renderError(result);
    return;
  }

  latestResult = result;
  const banner = document.getElementById("successBanner");
  banner.classList.remove("error-banner");
  banner.querySelector("strong").textContent = "Document processed successfully";
  document.getElementById("resultSource").textContent = result.sourceFile || "Processed FNOL document";

  const route = result.recommendedRoute || "Manual Review";
  const stamp = document.getElementById("stamp");
  stamp.textContent = route;
  stamp.className = "route-name " + (ROUTE_CLASS[route] || "route-manual");

  document.getElementById("recommendationSummary").textContent =
    route === "Fast-Track" ? "This claim meets the rules for a streamlined review workflow." :
    route === "Standard Review" ? "This claim should proceed through the standard claims review workflow." :
    route === "Specialist Queue" ? "This claim requires specialist handling because an injury was identified." :
    route === "Investigation Flag" ? "This claim has indicators that require investigation before normal processing." :
    "This claim requires manual review because mandatory information or data-quality checks need attention.";

  const metrics = result.processingMetrics || {};
  document.getElementById("completenessMetric").textContent =
    Number.isFinite(metrics.mandatoryFieldCompletenessPct) ? `${metrics.mandatoryFieldCompletenessPct}%` : "—";
  document.getElementById("missingMetric").textContent = Array.isArray(result.missingFields) ? result.missingFields.length : 0;
  document.getElementById("inconsistencyMetric").textContent = Array.isArray(result.inconsistencies) ? result.inconsistencies.length : 0;
  document.getElementById("riskMetric").textContent = Array.isArray(result.riskSignals) ? result.riskSignals.length : 0;

  document.getElementById("reasoning").textContent = result.reasoning || "No routing explanation was returned.";
  fillList("missingList", result.missingFields);
  fillList("inconsistencyList", result.inconsistencies);
  setIncidentDescription(result.extractedFields?.incidentInformation?.description);

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
      const row = document.createElement("div");
      row.className = "field-row";
      const label = document.createElement("span");
      label.className = "field-row__label";
      label.textContent = FIELD_LABELS[key] || key;
      const val = document.createElement("span");
      val.className = fields[key] ? "field-row__value" : "field-row__value field-row__value--missing";
      val.textContent = fields[key] || "—";
      row.append(label, val);
      fieldCard.appendChild(row);
    });
    grid.appendChild(fieldCard);
  });

  setStep(2);
}

async function processSelectedFile() {
  if (!selectedFile) return;
  setBusy(true);
  document.getElementById("fileHint").textContent = `Processing ${selectedFile.name}… Extracting and validating claim data.`;

  const formData = new FormData();
  formData.append("file", selectedFile);
  try {
    const result = await fetchJSON(`${API_BASE}/claims/process-upload`, { method: "POST", body: formData });
    if (result.error) renderError(result);
    else renderResult(result);
  } finally {
    setBusy(false);
  }
}

function downloadResult() {
  if (!latestResult) return;
  const blob = new Blob([JSON.stringify(latestResult, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${(latestResult.sourceFile || "fnol-result").replace(/\.[^.]+$/, "")}-result.json`;
  anchor.click();
  URL.revokeObjectURL(url);
}

const fileInput = document.getElementById("fileInput");
const uploadZone = document.getElementById("uploadZone");

fileInput.addEventListener("change", (event) => {
  const file = event.target.files[0];
  if (file) selectFile(file);
});

document.getElementById("processBtn").addEventListener("click", processSelectedFile);
document.getElementById("removeFileBtn").addEventListener("click", () => clearSelectedFile());
document.getElementById("newDocumentBtn").addEventListener("click", () => clearSelectedFile());
document.getElementById("backBtn").addEventListener("click", () => setStep(1));
document.getElementById("downloadBtn").addEventListener("click", downloadResult);

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

uploadZone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    fileInput.click();
  }
});

uploadZone.addEventListener("click", (event) => {
  if (!event.target.closest("label")) fileInput.click();
});
