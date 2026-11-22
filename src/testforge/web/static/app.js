"use strict";

// Deliberately dependency-free. Every interaction here is one fetch plus an
// innerHTML swap, and the server already returns rendered HTML, so a framework
// would add a vendored file and a version to maintain without removing code.
// It also means the page works on an isolated network, which matters for a tool
// used beside device test benches.

const $ = (sel) => document.querySelector(sel);

const els = {
  source: $("#source"),
  device: $("#device"),
  caseSel: $("#case"),
  stepLevel: $("#step-level"),
  preview: $("#preview"),
  previewStatus: $("#preview-status"),
  editorStatus: $("#editor-status"),
  artifacts: $("#artifacts"),
  generate: $("#generate"),
  advanced: $("#advanced"),
  deviceHint: $("#device-hint"),
  downloadForm: $("#download-form"),
  file: $("#file"),
};

// ---------------------------------------------------------------- form state

function currentForm() {
  const data = new FormData();
  data.set("source", els.source.value);
  data.set("device_id", els.device.value || "");
  if (els.caseSel.value) data.set("case_selector", els.caseSel.value);
  if (els.stepLevel.value) data.set("step_level", els.stepLevel.value);
  return data;
}

function describeDevice() {
  const opt = els.device.selectedOptions[0];
  if (!opt) return;
  els.deviceHint.textContent =
    `步驟標題層級 H${opt.dataset.stepLevel}　規則檔 ${opt.dataset.rules}`;
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
  els.previewStatus.textContent = "解析中…";
  try {
    const res = await fetch("/preview", { method: "POST", body: currentForm() });
    const html = await res.text();
    // A slower earlier request must not overwrite a newer result.
    if (seq !== previewSeq) return;
    els.preview.innerHTML = html;
    els.previewStatus.textContent = "";
    syncCaseOptions();
  } catch (err) {
    if (seq !== previewSeq) return;
    els.previewStatus.textContent = "解析失敗：" + err.message;
  }
}

// Keeps the case selector in step with what the preview actually found, so it
// can never offer a case number that does not exist.
function syncCaseOptions() {
  const cases = [...els.preview.querySelectorAll(".case")];
  const previous = els.caseSel.value;
  els.caseSel.innerHTML = '<option value="">全部</option>';
  cases.forEach((node) => {
    const opt = document.createElement("option");
    opt.value = node.dataset.index;
    const title = node.dataset.title || "";
    opt.textContent = `${node.dataset.index}. ` + (title.length > 26 ? title.slice(0, 25) + "…" : title);
    els.caseSel.appendChild(opt);
  });
  if (previous && Number(previous) <= cases.length) els.caseSel.value = previous;
}

function updateEditorStatus() {
  const text = els.source.value;
  const lines = text ? text.split("\n").length : 0;
  els.editorStatus.textContent = text
    ? `${lines} 行　${text.length} 字元`
    : " ";
}

// ------------------------------------------------------------------ generate

async function runGenerate() {
  if (!els.source.value.trim()) {
    els.artifacts.innerHTML =
      '<p class="banner error">請先貼上或載入一份測試計畫。</p>';
    return;
  }
  els.generate.disabled = true;
  els.generate.textContent = "產生中…";
  try {
    const res = await fetch("/generate", { method: "POST", body: currentForm() });
    els.artifacts.innerHTML = await res.text();
    highlightAll();
    bindArtifacts();
    els.artifacts.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    els.artifacts.innerHTML =
      '<p class="banner error">產生失敗：' + escapeHtml(err.message) + "</p>";
  } finally {
    els.generate.disabled = false;
    els.generate.textContent = "產生程式碼";
  }
}

function bindArtifacts() {
  const tabs = [...els.artifacts.querySelectorAll(".tab")];
  const panes = [...els.artifacts.querySelectorAll(".artifact")];
  const fileButton = els.artifacts.querySelector('[data-download="file"]');

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.toggle("active", t === tab));
      panes.forEach((p) => (p.hidden = p.id !== tab.dataset.target));
      const shown = panes.find((p) => !p.hidden);
      if (fileButton && shown) fileButton.dataset.path = shown.dataset.path;
    });
  });

  els.artifacts.querySelectorAll("[data-download]").forEach((btn) => {
    btn.addEventListener("click", () => submitDownload(btn.dataset.download, btn.dataset.path));
  });
}

// A real form post rather than fetch: the browser then handles the file dialog
// and the Content-Disposition filename itself.
function submitDownload(what, path) {
  const f = els.downloadForm;
  f.source.value = els.source.value;
  f.device_id.value = els.device.value || "";
  f.case_selector.value = els.caseSel.value || "";
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

// One pass, alternation ordered so that comments and strings win over anything
// they contain. Tokenising the raw text and escaping each piece as the output is
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
  els.artifacts.querySelectorAll("pre.code > code").forEach((node) => {
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
  schedulePreview(0);
});
els.stepLevel.addEventListener("change", () => schedulePreview(0));
els.generate.addEventListener("click", runGenerate);

$("#toggle-advanced").addEventListener("click", () => {
  els.advanced.hidden = !els.advanced.hidden;
});

$("#load-example").addEventListener("click", () => {
  els.source.value = $("#example-plan").innerHTML.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");
  updateEditorStatus();
  schedulePreview(0);
});

$("#clear").addEventListener("click", () => {
  els.source.value = "";
  updateEditorStatus();
  els.preview.innerHTML =
    '<p class="empty">貼上計畫後，這裡會顯示偵測到的 test case 與步驟。</p>';
  els.caseSel.innerHTML = '<option value="">全部</option>';
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
updateEditorStatus();
