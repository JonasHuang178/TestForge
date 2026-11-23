"use strict";

// Dependency-free on purpose. Every interaction is one fetch plus an innerHTML
// swap of server-rendered HTML, so a framework would add a vendored file and a
// version to maintain without removing code. It also means the page works on an
// isolated network, which matters beside a test bench.

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

const els = {
  source: $("#source"),
  device: $("#device"),
  stepLevel: $("#step-level"),
  preview: $("#preview"),
  previewStatus: $("#preview-status"),
  editorStatus: $("#editor-status"),
  artifacts: $("#artifacts"),
  advanced: $("#advanced"),
  deviceHint: $("#device-hint"),
  downloadForm: $("#download-form"),
  file: $("#file"),
  toStep2: $("#to-step-2"),
  step1Note: $("#step1-note"),
  fileList: $("#file-list"),
  downloadSummary: $("#download-summary"),
};

// ------------------------------------------------------------------- steps

let currentStep = 1;

function goToStep(n) {
  currentStep = n;
  $$(".step").forEach((section) => {
    section.hidden = section.id !== `step-${n}`;
  });
  $$("#stepper li").forEach((li) => {
    const step = Number(li.dataset.step);
    li.classList.toggle("current", step === n);
    li.classList.toggle("done", step < n);
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// ---------------------------------------------------------------- form state

function currentForm() {
  const data = new FormData();
  data.set("source", els.source.value);
  data.set("device_id", els.device.value || "");
  if (els.stepLevel.value) data.set("step_level", els.stepLevel.value);
  return data;
}

function describeDevice() {
  const opt = els.device.selectedOptions[0];
  if (!opt) return;
  els.deviceHint.textContent = `${opt.dataset.steps}　規則檔 ${opt.dataset.rules}`;
  // The override only bites when the device reads steps as headings.
  els.stepLevel.disabled = opt.dataset.style !== "heading";
}

// ------------------------------------------------------------- live preview

let previewTimer = null;
let previewSeq = 0;

function schedulePreview(delay = 350) {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(runPreview, delay);
}

async function runPreview() {
  const seq = ++previewSeq;
  if (!els.source.value.trim()) {
    els.preview.innerHTML =
      '<p class="empty">貼上計畫後，這裡會顯示偵測到的 test case 與步驟。</p>';
    els.previewStatus.textContent = "";
    setReady(false, "");
    return;
  }
  els.previewStatus.textContent = "解析中…";
  try {
    const res = await fetch("/preview", { method: "POST", body: currentForm() });
    const html = await res.text();
    // A slower earlier request must not overwrite a newer result.
    if (seq !== previewSeq) return;
    els.preview.innerHTML = html;
    els.previewStatus.textContent = "";

    const cases = els.preview.querySelectorAll(".case").length;
    const steps = els.preview.querySelectorAll(".steps li").length;
    if (res.ok && cases > 0) {
      setReady(true, `偵測到 ${cases} 個 test case、${steps} 個步驟`);
    } else {
      setReady(false, "這份計畫目前無法產生程式碼，請看右側的 diagnostics");
    }
  } catch (err) {
    if (seq !== previewSeq) return;
    els.previewStatus.textContent = "解析失敗：" + err.message;
    setReady(false, "");
  }
}

// The step cannot be left until the plan actually yields something, so the
// user is never carried to an empty result screen.
function setReady(ready, note) {
  els.toStep2.disabled = !ready;
  els.step1Note.textContent = note;
}

function updateEditorStatus() {
  const text = els.source.value;
  const lines = text ? text.split("\n").length : 0;
  els.editorStatus.textContent = text ? `${lines} 行　${text.length} 字元` : " ";
}

// ------------------------------------------------------------------ generate

async function generate() {
  els.toStep2.disabled = true;
  els.toStep2.textContent = "產生中…";
  try {
    const res = await fetch("/generate", { method: "POST", body: currentForm() });
    els.artifacts.innerHTML = await res.text();

    if (els.artifacts.querySelector(".banner.error")) {
      // Generation failed on the plan's content: stay here, where it can be
      // fixed, rather than showing a result screen with an error on it.
      els.preview.innerHTML = els.artifacts.innerHTML;
      els.artifacts.innerHTML = "";
      setReady(false, "產生失敗，請看右側說明");
      return;
    }

    highlightAll();
    bindTabs();
    fillDownloadStep();
    goToStep(2);
  } catch (err) {
    els.step1Note.textContent = "產生失敗：" + err.message;
  } finally {
    els.toStep2.textContent = "產生程式碼 →";
    els.toStep2.disabled = false;
  }
}

function bindTabs() {
  const tabs = $$("#artifacts .tab");
  const panes = $$("#artifacts .artifact");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.toggle("active", t === tab));
      panes.forEach((p) => (p.hidden = p.id !== tab.dataset.target));
    });
  });
}

function fillDownloadStep() {
  const summary = $("#artifacts .summary");
  if (summary) {
    els.downloadSummary.textContent =
      `${summary.dataset.cases} 個 test case、${summary.dataset.steps} 個步驟，` +
      `產生 ${summary.dataset.files} 個檔案。`;
  }

  const panes = $$("#artifacts .artifact");
  // An archive of one file is just a slower way to download that file.
  $(".download-actions").hidden = panes.length < 2;

  els.fileList.innerHTML = "";
  panes.forEach((pane) => {
    const path = pane.dataset.path;
    const li = document.createElement("li");

    const name = document.createElement("code");
    name.textContent = path;

    const button = document.createElement("button");
    button.type = "button";
    // With one file this is the whole point of the step, so it leads; with
    // several, a row of green buttons would just be noise.
    button.className = panes.length === 1 ? "primary" : "ghost";
    button.textContent = "下載";
    button.addEventListener("click", () => submitDownload("file", path));

    li.append(name, button);
    els.fileList.appendChild(li);
  });
}

// A real form post rather than fetch: the browser then handles the save dialog
// and the Content-Disposition filename itself.
function submitDownload(what, path) {
  const f = els.downloadForm;
  f.source.value = els.source.value;
  f.device_id.value = els.device.value || "";
  f.case_selector.value = "";
  f.step_level.value = els.stepLevel.value || "";
  f.what.value = what;
  f.path.value = path || "";
  f.submit();
}

// --------------------------------------------------------- C++ highlighting

const CPP_KEYWORDS = [
  "alignas", "auto", "bool", "break", "case", "catch", "char", "class", "const",
  "constexpr", "continue", "default", "delete", "do", "double", "else", "enum",
  "explicit", "extern", "false", "float", "for", "friend", "goto", "if",
  "inline", "int", "long", "mutable", "namespace", "new", "noexcept",
  "nullptr", "operator", "private", "protected", "public", "return", "short",
  "signed", "sizeof", "static", "struct", "switch", "template", "this",
  "throw", "true", "try", "typedef", "typename", "union", "unsigned", "using",
  "virtual", "void", "volatile", "while",
];

// One pass, alternation ordered so comments and strings win over anything they
// contain. Tokenising the raw text and escaping each piece as the output is
// built avoids the usual bug of running the pattern over pre-escaped HTML,
// where an escaped quote no longer looks like a string delimiter.
const CPP_PATTERN = new RegExp(
  [
    /\/\/[^\n]*/.source,
    /\/\*[\s\S]*?\*\//.source,
    /"(?:\\.|[^"\\\n])*"/.source,
    /'(?:\\.|[^'\\\n])*'/.source,
    /^[ \t]*#[A-Za-z]+/.source,
    /\b[A-Z][A-Z0-9_]{2,}\b/.source,
    "\\b(?:" + CPP_KEYWORDS.join("|") + ")\\b",
    /\b\d[A-Za-z0-9_.']*\b/.source,
  ]
    .map((s) => "(" + s + ")")
    .join("|"),
  "gm"
);

const TOKEN_CLASS = [
  "t-comment", "t-comment", "t-string", "t-string",
  "t-preproc", "t-macro", "t-keyword", "t-number",
];

function escapeHtml(text) {
  return text.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

function highlightCpp(code) {
  let out = "";
  let last = 0;
  for (const m of code.matchAll(CPP_PATTERN)) {
    out += escapeHtml(code.slice(last, m.index));
    const group = m.slice(1).findIndex((g) => g !== undefined);
    out += `<span class="${TOKEN_CLASS[group]}">${escapeHtml(m[0])}</span>`;
    last = m.index + m[0].length;
  }
  return out + escapeHtml(code.slice(last));
}

function highlightAll() {
  $$("#artifacts pre.code > code").forEach((node) => {
    node.innerHTML = highlightCpp(node.textContent);
  });
}

// ----------------------------------------------------------------- wiring up

els.source.addEventListener("input", () => {
  updateEditorStatus();
  schedulePreview();
});
els.device.addEventListener("change", () => {
  describeDevice();
  syncExampleButton();
  schedulePreview(0);
});
els.stepLevel.addEventListener("change", () => schedulePreview(0));

els.toStep2.addEventListener("click", generate);
$("#to-step-3").addEventListener("click", () => goToStep(3));
$("#back-to-1").addEventListener("click", () => goToStep(1));
$("#back-to-2").addEventListener("click", () => goToStep(2));
$("#restart").addEventListener("click", () => goToStep(1));
$$("[data-download='zip']").forEach((b) =>
  b.addEventListener("click", () => submitDownload("zip"))
);

$("#toggle-advanced").addEventListener("click", () => {
  els.advanced.hidden = !els.advanced.hidden;
});

// Each device ships its own sample: a plan written for one device's heading
// conventions parses to nothing under another's.
function examplePlanFor(deviceId) {
  const node = document.querySelector(`.example-plan[data-device="${deviceId}"]`);
  // textContent, not innerHTML: the browser has already decoded the entities.
  return node ? node.content.textContent : "";
}

$("#load-example").addEventListener("click", () => {
  const plan = examplePlanFor(els.device.value);
  if (!plan.trim()) {
    els.editorStatus.textContent = "這個 device 沒有附範例計畫";
    return;
  }
  els.source.value = plan;
  updateEditorStatus();
  schedulePreview(0);
});

function syncExampleButton() {
  const has = Boolean(examplePlanFor(els.device.value).trim());
  $("#load-example").disabled = !has;
  $("#load-example").title = has ? "" : "這個 device 沒有附範例計畫";
}

$("#clear").addEventListener("click", () => {
  els.source.value = "";
  updateEditorStatus();
  schedulePreview(0);
});

// Read the file in the browser: no upload endpoint, no multipart handling.
els.file.addEventListener("change", (ev) => {
  const file = ev.target.files && ev.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    els.source.value = String(reader.result);
    updateEditorStatus();
    schedulePreview(0);
  };
  reader.readAsText(file);
  ev.target.value = "";
});

describeDevice();
syncExampleButton();
updateEditorStatus();
goToStep(1);
