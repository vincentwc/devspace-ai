const MAX_EXAMPLES = 5;
const MAX_DRAFTS = 3;

function blankToNull(value) {
  const text = (value || "").trim();
  return text === "" ? null : text;
}

function stepRowHtml() {
  return (
    "<tr>" +
    '<td><input data-f="action" type="text" /></td>' +
    '<td><input data-f="expected" type="text" /></td>' +
    '<td><input data-f="test_data" type="text" /></td>' +
    '<td><button type="button" class="small" onclick="removeStep(this)">删除步骤</button></td>' +
    "</tr>"
  );
}

function draftHtml() {
  return (
    '<article class="draft-block">' +
    '<div class="actions"><strong>用例</strong>' +
    '<button type="button" class="small btn-danger" onclick="removeDraft(this)">删除用例</button></div>' +
    "<label>标题</label><input data-f=\"title\" type=\"text\" />" +
    "<label>优先级</label>" +
    '<select data-f="priority">' +
    '<option value="" selected>（空）</option>' +
    '<option value="P0">P0</option><option value="P1">P1</option>' +
    '<option value="P2">P2</option><option value="P3">P3</option>' +
    "</select>" +
    "<label>前置条件（一行一条）</label><textarea data-f=\"preconditions\"></textarea>" +
    "<label>标签（逗号分隔）</label><input data-f=\"tags\" type=\"text\" />" +
    "<label>步骤</label>" +
    '<table class="steps-table"><thead><tr><th>操作</th><th>预期</th><th>测试数据</th><th></th></tr></thead>' +
    "<tbody>" +
    stepRowHtml() +
    "</tbody></table>" +
    '<button type="button" class="small" onclick="addStep(this)">添加步骤</button>' +
    "<details><summary>rationale</summary><textarea data-f=\"rationale\"></textarea></details>" +
    "</article>"
  );
}

function exampleHtml() {
  return (
    '<article class="example-block">' +
    '<div class="actions"><strong>需求</strong>' +
    '<button type="button" class="small btn-danger" onclick="removeExample(this)">删除需求</button></div>' +
    '<label>备注</label><input data-f="label" type="text" maxlength="80" />' +
    '<label>需求文本</label><textarea data-f="requirement_text"></textarea>' +
    '<div class="drafts">' +
    draftHtml() +
    "</div>" +
    '<button type="button" class="small" onclick="addDraft(this)">添加用例</button>' +
    "</article>"
  );
}

function addExample() {
  const root = document.getElementById("examples");
  if (root.querySelectorAll(":scope > .example-block").length >= MAX_EXAMPLES) return;
  root.insertAdjacentHTML("beforeend", exampleHtml());
}

function removeExample(btn) {
  btn.closest(".example-block").remove();
}

function addDraft(btn) {
  const drafts = btn.closest(".example-block").querySelector(".drafts");
  if (drafts.querySelectorAll(":scope > .draft-block").length >= MAX_DRAFTS) return;
  drafts.insertAdjacentHTML("beforeend", draftHtml());
}

function removeDraft(btn) {
  btn.closest(".draft-block").remove();
}

function addStep(btn) {
  const tbody = btn.closest(".draft-block").querySelector(".steps-table tbody");
  tbody.insertAdjacentHTML("beforeend", stepRowHtml());
}

function removeStep(btn) {
  btn.closest("tr").remove();
}

function collectPayload(form) {
  const examples = [...form.querySelectorAll("#examples > .example-block")].map((ex) => ({
    label: blankToNull(ex.querySelector('[data-f="label"]').value),
    requirement_text: ex.querySelector('[data-f="requirement_text"]').value,
    drafts: [...ex.querySelectorAll(":scope > .drafts > .draft-block")].map((draft) => ({
      title: draft.querySelector('[data-f="title"]').value,
      priority: blankToNull(draft.querySelector('[data-f="priority"]').value),
      preconditions: draft
        .querySelector('[data-f="preconditions"]')
        .value.split("\n")
        .map((line) => line.trim())
        .filter(Boolean),
      tags: draft
        .querySelector('[data-f="tags"]')
        .value.split(",")
        .map((tag) => tag.trim())
        .filter(Boolean),
      steps: [...draft.querySelectorAll(".steps-table tbody tr")].map((row) => ({
        action: row.querySelector('[data-f="action"]').value,
        expected: row.querySelector('[data-f="expected"]').value,
        test_data: blankToNull(row.querySelector('[data-f="test_data"]').value),
      })),
      rationale: blankToNull(draft.querySelector('[data-f="rationale"]').value),
    })),
  }));
  const payload = {
    name: form.querySelector("#name").value,
    description: blankToNull(form.querySelector("#description").value),
    examples,
  };
  if (form.dataset.mode === "create") {
    payload.key = form.querySelector("#key").value;
  }
  return payload;
}

function showIssues(issues) {
  const el = document.getElementById("form-issues");
  el.hidden = !issues.length;
  el.innerHTML = issues
    .map((issue) => {
      const field = issue.field ? ` · ${issue.field}` : "";
      return `<div class="issue"><strong>${issue.code || ""}</strong> — ${issue.message || ""}${field}</div>`;
    })
    .join("");
}

async function onSubmit(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const payload = collectPayload(form);
  const creating = form.dataset.mode === "create";
  const url = creating
    ? "/api/v1/style-packs"
    : `/api/v1/style-packs/${form.dataset.packId}`;
  const res = await fetch(url, {
    method: creating ? "POST" : "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  let body = {};
  try {
    body = await res.json();
  } catch (_err) {
    body = {};
  }
  if (res.status === 400 && Array.isArray(body.issues)) {
    showIssues(body.issues);
    return;
  }
  if (!res.ok) {
    const detail = body.detail ? JSON.stringify(body.detail) : `HTTP ${res.status}`;
    showIssues([{ code: "SAVE_FAILED", message: detail, field: null }]);
    return;
  }
  window.location.href = `/debug/style-packs/${body.id}`;
}

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("style-pack-form");
  if (!form) return;
  form.addEventListener("submit", onSubmit);
});
