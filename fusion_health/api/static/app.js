/* Fusion-Health Console — thin vanilla-JS client over the existing /api/v1 routes. */

const keyInput = document.getElementById("api-key");
keyInput.value = localStorage.getItem("fh_api_key") || "";

function headers() {
    const h = { "Content-Type": "application/json" };
    const key = localStorage.getItem("fh_api_key");
    if (key) h["X-API-Key"] = key;
    return h;
}

function saveKey() {
    localStorage.setItem("fh_api_key", keyInput.value.trim());
    loadHealth();
}

async function api(path, options = {}) {
    const resp = await fetch(path, { ...options, headers: { ...headers(), ...(options.headers || {}) } });
    const body = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(body.error || body.detail || `HTTP ${resp.status}`);
    return body;
}

function show(id, data) {
    const el = document.getElementById(id);
    el.textContent = typeof data === "string" ? data : JSON.stringify(data, null, 2);
}

/* ---- tabs ---- */

document.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", () => activateTab(btn.dataset.tab));
});

function activateTab(name) {
    document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("tab-active", b.dataset.tab === name));
    document.querySelectorAll(".panel").forEach((p) => {
        const on = p.id === `tab-${name}`;
        p.classList.toggle("hidden", !on);
        p.classList.toggle("flex", on);
    });
    if (name === "overview") loadOverview();
    if (name === "audit") runAuditVerify();
    if (name === "chat") initChat();
}
activateTab("overview");

/* ---- overview ---- */

async function loadHealth() {
    const line = document.getElementById("health-line");
    try {
        const h = await api("/api/v1/health");
        line.textContent = `${h.status} · v${h.version} · model ${h.model} · backend ${h.backend && h.backend.ok ? "ok" : "down"}`;
        return h;
    } catch (e) {
        line.textContent = `unreachable: ${e.message}`;
        return null;
    }
}

async function loadOverview() {
    const h = await loadHealth();
    const cards = document.getElementById("overview-cards");
    const status = h ? h.status : "unknown";
    const color = status === "ok" ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400";
    cards.innerHTML = `
        <div class="rounded-xl border border-zinc-200/80 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <p class="text-xs text-zinc-500 dark:text-zinc-400">Service</p>
            <p class="mt-1 text-xl font-semibold ${color}">${status}</p></div>
        <div class="rounded-xl border border-zinc-200/80 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <p class="text-xs text-zinc-500 dark:text-zinc-400">Sessions</p>
            <p class="mt-1 text-xl font-semibold">${h ? h.sessions : "–"}</p></div>
        <div class="rounded-xl border border-zinc-200/80 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <p class="text-xs text-zinc-500 dark:text-zinc-400">Backend</p>
            <p class="mt-1 text-xl font-semibold">${h && h.backend && h.backend.ok ? "ok" : (h ? "down" : "–")}</p></div>`;
    try {
        const m = await api("/api/v1/metrics");
        show("metrics-out", m);
    } catch (e) {
        show("metrics-out", `metrics unavailable: ${e.message}`);
    }
    lucide.createIcons();
}

/* ---- clinical ---- */

async function runClinical(path, payload) {
    show("clinical-out", "running…");
    try {
        const r = await api(path, { method: "POST", body: JSON.stringify(payload) });
        show("clinical-out", r);
    } catch (e) {
        show("clinical-out", `error: ${e.message}`);
    }
}

function notes() {
    const text = document.getElementById("clinical-notes").value.trim();
    if (!text) { show("clinical-out", "enter clinical notes first"); throw new Error("empty"); }
    return text;
}

function runEhrSummary() { runClinical("/api/v1/ehr/summary", { clinical_notes: notes() }); }
function runIcd10() { runClinical("/api/v1/insurance/icd10", { diagnosis_text: notes() }); }
function runDrg() { runClinical("/api/v1/insurance/drg", { diagnosis_or_procedure: notes() }); }

/* ---- audit ---- */

async function runAuditVerify() {
    const el = document.getElementById("audit-status");
    try {
        const r = await api("/api/v1/audit/verify");
        el.innerHTML = r.intact
            ? `<span class="font-medium text-emerald-600 dark:text-emerald-400">Chain intact</span> — ${r.verified} verified, 0 tampered (${r.log_path})`
            : `<span class="font-medium text-red-600 dark:text-red-400">Chain broken</span> — ${r.verified} verified, ${r.tampered} tampered (${r.log_path})`;
    } catch (e) {
        el.textContent = `verify failed: ${e.message}`;
    }
}

async function loadAuditRecent() {
    const rows = document.getElementById("audit-rows");
    try {
        const r = await api("/api/v1/audit/recent?limit=50");
        rows.innerHTML = r.events.map((ev) => `
            <tr class="border-b border-zinc-100 last:border-0 dark:border-zinc-800/60">
                <td class="p-3">${ev.seq ?? ""}</td>
                <td class="p-3">${ev.ts ?? ""}</td>
                <td class="p-3">${ev.owner_id ?? ""}</td>
                <td class="p-3">${ev.action ?? ""}</td>
                <td class="p-3">${ev.path ?? ""}</td>
                <td class="p-3">${ev.status ?? ""}</td>
            </tr>`).join("") || `<tr><td class="p-3 text-zinc-500" colspan="6">no events</td></tr>`;
    } catch (e) {
        rows.innerHTML = `<tr><td class="p-3" colspan="6">load failed: ${e.message}</td></tr>`;
    }
}

/* ---- chat ---- */

let chatSid = null;

function chatAppend(role, text) {
    const log = document.getElementById("chat-log");
    const bubble = document.createElement("div");
    bubble.className = role === "user"
        ? "self-end max-w-[80%] rounded-2xl rounded-br-sm bg-indigo-600 px-3 py-2 text-white"
        : "self-start max-w-[80%] rounded-2xl rounded-bl-sm bg-zinc-100 px-3 py-2 dark:bg-zinc-800";
    bubble.textContent = text;
    log.appendChild(bubble);
    log.scrollTop = log.scrollHeight;
}

async function initChat() {
    if (chatSid) return;
    try {
        const r = await api("/api/v1/chat/start", { method: "POST", body: "{}" });
        chatSid = r.session_id;
        chatAppend("assistant", "New session started.");
    } catch (e) {
        chatAppend("assistant", `session start failed: ${e.message}`);
    }
}

async function newChatSession() {
    chatSid = null;
    document.getElementById("chat-log").innerHTML = "";
    await initChat();
}

async function sendChat() {
    const input = document.getElementById("chat-input");
    const message = input.value.trim();
    if (!message || !chatSid) return;
    input.value = "";
    chatAppend("user", message);
    chatAppend("assistant", "…");
    try {
        const r = await api("/api/v1/chat/message", {
            method: "POST",
            body: JSON.stringify({ session_id: chatSid, message }),
        });
        document.getElementById("chat-log").lastChild.textContent = r.response || r.error || "(empty)";
    } catch (e) {
        document.getElementById("chat-log").lastChild.textContent = `error: ${e.message}`;
    }
}

document.getElementById("chat-input").addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") sendChat();
});

loadHealth();
