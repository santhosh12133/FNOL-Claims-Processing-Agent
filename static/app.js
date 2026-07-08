const ROUTE_CLASS = {
  "Fast-Track": "route-fast",
  "Standard Review": "route-standard",
  "Specialist Queue": "route-specialist",
  "Investigation Flag": "route-investigation",
  "Manual Review": "route-manual",
};

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
  const res = await fetch(url, options);
  return res.json();
}

async function loadSamples() {
  const samples = await fetchJSON("/api/samples");
  const row = document.getElementById("sampleRow");
  row.innerHTML = "";
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

  if (sample.isPdf) {
    textInput.value = "";
    fileHint.textContent = `Loaded: ${sample.filename} (PDF — processed directly, no text preview)`;
  } else {
    const data = await fetchJSON(`/api/sample-text/${sample.filename}`);
    textInput.value = data.text || "";
    fileHint.textContent = `Loaded: ${sample.filename}`;
  }

  const result = await fetchJSON(`/api/process-sample/${sample.filename}`);
  renderResult(result);
}

function fillList(elementId, items) {
  const el = document.getElementById(elementId);
  el.innerHTML = "";
  if (!items || items.length === 0) {
    const li = document.createElement("li");
    li.className = "flag-list__none";
    li.textContent = "None";
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

function renderResult(result) {
  document.getElementById("resultEmpty").hidden = true;
  const card = document.getElementById("resultCard");
  card.hidden = false;

  const stamp = document.getElementById("stamp");

  if (result.error) {
    document.getElementById("sourceFile").textContent = "Error";
    document.getElementById("reasoning").textContent = result.error;
    setIncidentDescription("");
    stamp.textContent = "";
    stamp.className = "stamp";
    fillList("missingList", []);
    fillList("inconsistencyList", []);
    document.getElementById("fieldsGrid").innerHTML = "";
    return;
  }

  document.getElementById("sourceFile").textContent = result.sourceFile;

  stamp.textContent = result.recommendedRoute;
  stamp.className = "stamp " + (ROUTE_CLASS[result.recommendedRoute] || "route-standard");
  // restart the CSS animation on every new result
  stamp.classList.remove("stamp--animate");
  void stamp.offsetWidth;
  stamp.classList.add("stamp--animate");

  document.getElementById("reasoning").textContent = result.reasoning;

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
      if (STACKED_FIELD_KEYS.has(key)) {
        row.classList.add("field-row--stacked");
      }

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
  if (!text) return;
  const result = await fetchJSON("/api/process-text", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  document.getElementById("fileHint").textContent = "Processed pasted text";
  renderResult(result);
});

document.getElementById("fileInput").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  document.getElementById("fileHint").textContent = `Uploaded: ${file.name}`;

  const formData = new FormData();
  formData.append("file", file);
  const result = await fetchJSON("/api/process-upload", { method: "POST", body: formData });
  renderResult(result);
});

loadSamples();
