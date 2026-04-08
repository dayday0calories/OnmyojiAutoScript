import { els } from "./dom.js?v=20260408c";
import { api } from "./api.js?v=20260408c";
import { i18n } from "./i18n.js?v=20260408c";

const state = {
  ws: null,
  activeConfig: "",
  autoScroll: true,
  currentTaskName: "",
  currentStateValue: 0,
  logsByConfig: {},
  dirtyFields: new Set(),
  pendingTimers: new Map(),
  inFlightSaves: 0,
};

const t = (key) => i18n.t(key);

function setSchedulerIndicator(isRunning) {
  els.schedulerIndicator.classList.remove("bg-gray-400", "bg-emerald-500");
  els.schedulerIndicator.classList.add(isRunning ? "bg-emerald-500" : "bg-gray-400");
}

function appendLog(line) {
  const text = typeof line === "string" ? line : JSON.stringify(line);
  const cfg = state.activeConfig || "__default__";
  if (!state.logsByConfig[cfg]) state.logsByConfig[cfg] = [];
  state.logsByConfig[cfg].push(text);
  if (state.logsByConfig[cfg].length > 2000) {
    state.logsByConfig[cfg] = state.logsByConfig[cfg].slice(-2000);
  }
  els.logBox.textContent = `${state.logsByConfig[cfg].join("\n")}\n`;
  if (state.autoScroll) els.logBox.scrollTop = els.logBox.scrollHeight;
}

function makeFieldKey(taskName, groupName, argName) {
  return `${taskName}.${groupName}.${argName}`;
}

function renderActiveLog() {
  const cfg = state.activeConfig || "__default__";
  const lines = state.logsByConfig[cfg] || [];
  els.logBox.textContent = lines.length ? `${lines.join("\n")}\n` : "";
  if (state.autoScroll) els.logBox.scrollTop = els.logBox.scrollHeight;
}

function wsUrlFor(configName) {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/ws/${encodeURIComponent(configName)}`;
}

function createTaskScheduleItem(item) {
  const wrap = document.createElement("div");
  wrap.className = "rounded-lg border border-gray-200 bg-gray-50 p-2";
  wrap.innerHTML = `
    <div class="text-sm font-semibold">${t(item.name || "-")}</div>
    <div class="mt-1 text-xs text-gray-500">${item.next_run || "-"}</div>
  `;
  return wrap;
}

function renderSchedule(schedule) {
  const running = schedule?.running || {};
  const pending = Array.isArray(schedule?.pending) ? schedule.pending : [];
  const waiting = Array.isArray(schedule?.waiting) ? schedule.waiting : [];

  if (running.name) {
    els.runningEmpty.classList.add("hidden");
    els.runningTask.classList.remove("hidden");
    els.runningName.textContent = t(running.name);
    els.runningTime.textContent = running.next_run || "";
  } else {
    els.runningTask.classList.add("hidden");
    els.runningEmpty.classList.remove("hidden");
  }

  els.pendingList.innerHTML = "";
  els.pendingEmpty.classList.toggle("hidden", pending.length > 0);
  pending.forEach((item) => els.pendingList.appendChild(createTaskScheduleItem(item)));

  els.waitingList.innerHTML = "";
  els.waitingEmpty.classList.toggle("hidden", waiting.length > 0);
  waiting.forEach((item) => els.waitingList.appendChild(createTaskScheduleItem(item)));
}

function updateRunStatusByState(stateValue) {
  state.currentStateValue = stateValue;
  setSchedulerIndicator(stateValue === 1);
  const map = {
    0: { text: t("Idle"), cls: "bg-gray-100 border-gray-300 text-gray-600" },
    1: { text: t("Running"), cls: "bg-emerald-50 border-emerald-200 text-emerald-700" },
    2: { text: t("Warning"), cls: "bg-amber-50 border-amber-200 text-amber-700" },
    3: { text: t("Updating"), cls: "bg-sky-50 border-sky-200 text-sky-700" },
  };
  const c = map[stateValue] || map[0];
  els.runStatusText.textContent = c.text;
  els.runStatusText.className = `rounded-full border px-2 py-0.5 text-xs ${c.cls}`;
}

function applyStaticTranslations() {
  const set = (id, text) => {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  };
  set("configs-title", t("Configs"));
  set("tasks-title", t("Tasks"));
  set("tasks-hint", t("Click one task to edit config"));
  set("scheduler-title", t("Scheduler"));
  set("current-label", t("Current:"));
  set("running-title", t("Running"));
  set("pending-title", t("Pending"));
  set("waiting-title", t("Waiting"));
  set("log-title", t("Log"));
  set("task-config-title", t("Task Config"));

  els.refreshBtn.textContent = t("Refresh");
  els.startBtn.textContent = t("Start");
  els.stopBtn.textContent = t("Stop");
  els.clearLogBtn.textContent = t("Clear");
  els.overlayReloadBtn.textContent = t("Reload");
  els.overlayBackBtn.textContent = t("Return");
  els.autoScrollBtn.textContent = state.autoScroll ? t("Auto Scroll On") : t("Auto Scroll Off");
  els.runningEmpty.textContent = t("No running task");
  els.pendingEmpty.textContent = t("No pending tasks");
  els.waitingEmpty.textContent = t("No waiting tasks");
  els.langBtn.textContent = i18n.currentLang === "zh-CN" ? "EN" : "中文";
}

function markActiveConfigCard() {
  Array.from(els.configList.querySelectorAll("[data-config-card]")).forEach((el) => {
    const selected = el.dataset.configCard === state.activeConfig;
    el.className = selected
      ? "w-full rounded-xl border border-blue-200 bg-blue-50 px-3 py-2 text-left"
      : "w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-left hover:bg-gray-50";
  });
  els.currentConfig.textContent = state.activeConfig || "-";
}

function closeTaskOverlay() {
  els.taskOverlay.classList.add("hidden");
}

async function loadConfigList() {
  const list = await api.getConfigList();
  els.configList.innerHTML = "";

  if (!state.activeConfig && list.length > 0) state.activeConfig = list[0];
  if (state.activeConfig && !list.includes(state.activeConfig) && list.length > 0) state.activeConfig = list[0];

  list.forEach((name) => {
    const btn = document.createElement("button");
    btn.dataset.configCard = name;
    btn.innerHTML = `
      <div class="flex items-center gap-2">
        <span class="inline-flex h-6 w-6 items-center justify-center rounded-md bg-gray-100 text-xs font-bold text-gray-600">O</span>
        <span class="text-sm font-medium">${name}</span>
      </div>
    `;
    btn.addEventListener("click", async () => {
      state.activeConfig = name;
      localStorage.setItem("oas_webui_active_config", state.activeConfig);
      markActiveConfigCard();
      renderActiveLog();
      connectWs();
      closeTaskOverlay();
      await loadTaskNames();
    });
    els.configList.appendChild(btn);
  });
  markActiveConfigCard();
}

async function loadTaskNames() {
  els.taskList.innerHTML = "";
  if (!state.activeConfig) return;
  const menu = await api.getScriptMenu();
  const groups = Object.entries(menu || {});

  groups.forEach(([groupName, tasks]) => {
    const details = document.createElement("details");
    details.className = "rounded-xl border border-gray-200 bg-gray-50";
    details.open = groupName === "Overview" || groupName === "Script";

    const summary = document.createElement("summary");
    summary.className = "cursor-pointer rounded-xl px-3 py-2 text-xs font-semibold text-gray-700";
    summary.textContent = t(groupName);
    details.appendChild(summary);

    const body = document.createElement("div");
    body.className = "space-y-1 px-2 pb-2";

    const seen = new Set();
    (Array.isArray(tasks) ? tasks : []).forEach((taskName) => {
      if (typeof taskName !== "string") return;
      const name = taskName.trim();
      if (!name || seen.has(name)) return;
      seen.add(name);

      const btn = document.createElement("button");
      btn.className = "w-full rounded-lg border border-gray-200 bg-white px-2.5 py-2 text-left text-xs font-medium hover:bg-gray-50";
      btn.textContent = t(name);
      btn.addEventListener("click", () => {
        openTaskOverlay(name).catch((err) => appendLog(`[task] open failed: ${String(err)}`));
      });
      body.appendChild(btn);
    });

    details.appendChild(body);
    els.taskList.appendChild(details);
  });
}

function buildField(taskName, groupName, arg) {
  const wrap = document.createElement("div");
  wrap.className = "rounded-lg border border-gray-200 bg-gray-50 p-3";

  const label = document.createElement("label");
  label.className = "mb-1 block text-sm font-semibold text-gray-700";
  label.textContent = t(arg.name) !== arg.name ? t(arg.name) : t(arg.title || arg.name);
  wrap.appendChild(label);

  const descText = t(arg.description || "");
  if (descText) {
    const d = document.createElement("div");
    d.className = "mb-2 text-xs text-gray-500";
    d.textContent = descText;
    wrap.appendChild(d);
  }

  const rawValue = String(arg.value ?? "");
  const isTime = /^\d{2}:\d{2}:\d{2}$/.test(rawValue);
  const isDateTime = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(rawValue);
  const isTimeDelta = /^\d{1,2} \d{2}:\d{2}:\d{2}$/.test(rawValue);

  const row = document.createElement("div");
  row.className = "flex flex-col gap-2";
  wrap.appendChild(row);

  const hint = document.createElement("div");
  hint.className = "text-xs text-gray-400";
  hint.textContent = "";
  row.appendChild(hint);

  const fieldKey = makeFieldKey(taskName, groupName, arg.name);
  let lastSavedValue = String(arg.value ?? "");

  const markDirty = () => state.dirtyFields.add(fieldKey);
  const clearDirty = () => state.dirtyFields.delete(fieldKey);

  async function saveValue(value) {
    const valueStr = String(value ?? "");
    if (valueStr === lastSavedValue) {
      clearDirty();
      hint.textContent = "";
      return;
    }
    hint.textContent = "Saving...";
    state.inFlightSaves += 1;
    try {
      const resp = await api.setTaskArg(state.activeConfig, taskName, groupName, arg.name, arg.type, value);
      if (!resp.ok) {
        hint.textContent = "Save failed";
        appendLog(`[config] save failed: ${taskName}.${groupName}.${arg.name}`);
        return;
      }
      lastSavedValue = valueStr;
      clearDirty();
      hint.textContent = "Saved";
      setTimeout(() => {
        if (hint.textContent === "Saved") hint.textContent = "";
      }, 900);
    } catch (_e) {
      hint.textContent = "Save failed";
      appendLog(`[config] save failed: ${taskName}.${groupName}.${arg.name}`);
    } finally {
      state.inFlightSaves = Math.max(0, state.inFlightSaves - 1);
    }
  }

  function scheduleDebouncedSave(getValue, delayMs = 500) {
    markDirty();
    hint.textContent = "Unsaved";
    const prev = state.pendingTimers.get(fieldKey);
    if (prev) clearTimeout(prev);
    const timerId = setTimeout(() => {
      state.pendingTimers.delete(fieldKey);
      saveValue(getValue());
    }, delayMs);
    state.pendingTimers.set(fieldKey, timerId);
  }

  function saveNow(getValue) {
    const prev = state.pendingTimers.get(fieldKey);
    if (prev) {
      clearTimeout(prev);
      state.pendingTimers.delete(fieldKey);
    }
    markDirty();
    saveValue(getValue());
  }

  if (arg.type === "boolean") {
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = Boolean(arg.value);
    input.className = "h-4 w-4";
    row.insertBefore(input, hint);
    input.addEventListener("change", () => saveNow(() => input.checked));
    return wrap;
  }

  if (Array.isArray(arg.enumEnum)) {
    const input = document.createElement("select");
    input.className = "w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm";
    arg.enumEnum.forEach((v) => {
      const opt = document.createElement("option");
      opt.value = String(v);
      opt.textContent = t(String(v));
      if (String(arg.value) === String(v)) opt.selected = true;
      input.appendChild(opt);
    });
    row.insertBefore(input, hint);
    input.addEventListener("change", () => saveNow(() => input.value));
    return wrap;
  }

  if (isDateTime) {
    const input = document.createElement("input");
    input.type = "datetime-local";
    input.step = "1";
    input.className = "w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm";
    input.value = rawValue.replace(" ", "T");
    row.insertBefore(input, hint);
    input.addEventListener("change", () => {
      if (!input.value) return;
      saveNow(() => input.value.replace("T", " "));
    });
    return wrap;
  }

  if (isTimeDelta) {
    const parts = rawValue.split(" ");
    const dayRaw = parts[0] || "0";
    const timeRaw = parts[1] || "00:00:00";

    const grid = document.createElement("div");
    grid.className = "grid grid-cols-[88px_auto_minmax(0,1fr)] items-center gap-2";

    const dayInput = document.createElement("input");
    dayInput.type = "number";
    dayInput.min = "0";
    dayInput.max = "99";
    dayInput.className = "rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm";
    dayInput.value = String(parseInt(dayRaw, 10) || 0);

    const timeInput = document.createElement("input");
    timeInput.type = "time";
    timeInput.step = "1";
    timeInput.className = "rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm";
    timeInput.value = timeRaw;

    const dayUnit = document.createElement("span");
    dayUnit.className = "text-xs text-gray-500";
    dayUnit.textContent = t("Days");

    const saveTimeDelta = () => {
      const day = String(Math.max(0, Math.min(99, parseInt(dayInput.value || "0", 10) || 0))).padStart(2, "0");
      const time = timeInput.value || "00:00:00";
      saveNow(() => `${day} ${time}`);
    };

    dayInput.addEventListener("change", saveTimeDelta);
    timeInput.addEventListener("change", saveTimeDelta);
    grid.appendChild(dayInput);
    grid.appendChild(dayUnit);
    grid.appendChild(timeInput);
    row.insertBefore(grid, hint);
    return wrap;
  }

  if (isTime) {
    const input = document.createElement("input");
    input.type = "time";
    input.step = "1";
    input.className = "w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm";
    input.value = rawValue;
    row.insertBefore(input, hint);
    input.addEventListener("change", () => {
      if (!input.value) return;
      saveNow(() => input.value);
    });
    return wrap;
  }

  if (arg.type === "multi_line") {
    const input = document.createElement("textarea");
    input.className = "w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm";
    input.rows = 3;
    input.value = arg.value ?? "";
    row.insertBefore(input, hint);
    input.addEventListener("input", () => scheduleDebouncedSave(() => input.value, 500));
    input.addEventListener("blur", () => saveNow(() => input.value));
    return wrap;
  }

  const input = document.createElement("input");
  input.className = "w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm";
  input.type = arg.type === "integer" || arg.type === "number" ? "number" : "text";
  input.value = arg.value ?? "";
  if (arg.type === "integer") input.step = "1";
  if (arg.type === "number") input.step = "any";
  row.insertBefore(input, hint);
  input.addEventListener("input", () => scheduleDebouncedSave(() => input.value, 500));
  input.addEventListener("blur", () => saveNow(() => input.value));
  return wrap;
}

function renderTaskGroups(taskName, groupsData) {
  els.taskGroups.innerHTML = "";
  const entries = Object.entries(groupsData || {});
  if (entries.length === 0) {
    els.taskGroups.innerHTML = `<div class="text-xs text-gray-400">No task config data for ${t(taskName)}.</div>`;
    return;
  }
  entries.forEach(([groupName, args]) => {
    const details = document.createElement("details");
    details.className = "rounded-xl border border-gray-200";
    details.open = true;

    const summary = document.createElement("summary");
    summary.className = "cursor-pointer rounded-xl bg-gray-50 px-3 py-2 text-sm font-semibold";
    summary.textContent = t(groupName) !== groupName ? t(groupName) : t(groupName.replaceAll("_", " "));
    details.appendChild(summary);

    const body = document.createElement("div");
    body.className = "space-y-2 p-2";
    (args || []).forEach((arg) => body.appendChild(buildField(taskName, groupName, arg)));
    details.appendChild(body);
    els.taskGroups.appendChild(details);
  });
}

async function loadTaskConfig(taskName) {
  if (!state.activeConfig || !taskName) return;
  try {
    const data = await api.getTaskArgs(state.activeConfig, taskName);
    renderTaskGroups(taskName, data);
  } catch (_e) {
    els.taskGroups.innerHTML = `<div class="text-xs text-red-500">Failed to load ${t(taskName)} config.</div>`;
  }
}

async function openTaskOverlay(taskName) {
  state.currentTaskName = taskName;
  els.overlayTaskTitle.textContent = `${state.activeConfig} / ${t(taskName)}`;
  els.taskOverlay.classList.remove("hidden");
  await loadTaskConfig(taskName);
}

function connectWs() {
  if (!state.activeConfig) {
    appendLog("No config selected.");
    return;
  }
  if (state.ws) {
    state.ws.close();
    state.ws = null;
  }
  state.ws = new WebSocket(wsUrlFor(state.activeConfig));

  state.ws.onopen = () => {
    state.ws.send("get_state");
    state.ws.send("get_schedule");
  };
  state.ws.onmessage = (event) => {
    const raw = event.data;
    if (typeof raw !== "string") return;
    try {
      const payload = JSON.parse(raw);
      if (payload.state !== undefined) updateRunStatusByState(payload.state);
      else if (payload.schedule !== undefined) renderSchedule(payload.schedule);
    } catch (_e) {
      appendLog(raw);
    }
  };
  state.ws.onerror = () => appendLog("[ws] error");
  state.ws.onclose = () => {
    setSchedulerIndicator(false);
  };
}

function sendWsCommand(cmd) {
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
    appendLog(`[ws] not connected, cannot send: ${cmd}`);
    return;
  }
  state.ws.send(cmd);
}

function bindEvents() {
  els.startBtn.addEventListener("click", () => sendWsCommand("start"));
  els.stopBtn.addEventListener("click", () => sendWsCommand("stop"));
  els.refreshBtn.addEventListener("click", async () => {
    await loadConfigList();
    await loadTaskNames();
    appendLog("[api] refreshed");
  });
  els.clearLogBtn.addEventListener("click", () => {
    const cfg = state.activeConfig || "__default__";
    state.logsByConfig[cfg] = [];
    renderActiveLog();
  });
  els.autoScrollBtn.addEventListener("click", () => {
    state.autoScroll = !state.autoScroll;
    els.autoScrollBtn.textContent = state.autoScroll ? t("Auto Scroll On") : t("Auto Scroll Off");
  });
  els.overlayBackBtn.addEventListener("click", () => closeTaskOverlay());
  els.overlayReloadBtn.addEventListener("click", () => {
    if (!state.currentTaskName) return;
    loadTaskConfig(state.currentTaskName).catch((err) => appendLog(`[task] reload failed: ${String(err)}`));
  });
  els.langBtn.addEventListener("click", async () => {
    i18n.toggleLang();
    applyStaticTranslations();
    markActiveConfigCard();
    await loadTaskNames();
    if (!els.taskOverlay.classList.contains("hidden") && state.currentTaskName) {
      await loadTaskConfig(state.currentTaskName);
      els.overlayTaskTitle.textContent = `${state.activeConfig} / ${t(state.currentTaskName)}`;
    }
    updateRunStatusByState(state.currentStateValue);
  });

  window.addEventListener("beforeunload", (event) => {
    if (state.dirtyFields.size > 0 || state.pendingTimers.size > 0 || state.inFlightSaves > 0) {
      event.preventDefault();
      event.returnValue = "";
    }
    if (state.ws) state.ws.close();
  });
}

async function bootstrap() {
  state.activeConfig = localStorage.getItem("oas_webui_active_config") || "";
  i18n.setLang("zh-CN");
  await i18n.load(api);
  applyStaticTranslations();
  setSchedulerIndicator(false);
  updateRunStatusByState(0);
  await loadConfigList();
  if (!state.activeConfig) return;
  renderActiveLog();
  await loadTaskNames();
  connectWs();
}

bindEvents();
bootstrap().catch((err) => appendLog(`[boot] failed: ${String(err)}`));
