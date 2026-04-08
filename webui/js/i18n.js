const fallbackZh = {
  "Configs": "配置",
  "Tasks": "任务",
  "Click one task to edit config": "点击任务以编辑配置",
  "Scheduler": "调度器",
  "Current:": "当前:",
  "Connect": "连接",
  "Disconnected": "未连接",
  "Connected": "已连接",
  "Connecting": "连接中",
  "Start": "开始",
  "Stop": "停止",
  "Running": "运行中",
  "Pending": "队列中",
  "Waiting": "等待中",
  "No running task": "无运行中任务",
  "No pending tasks": "无队列任务",
  "No waiting tasks": "无等待任务",
  "Log": "日志",
  "Idle": "闲置",
  "Warning": "警告",
  "Updating": "更新中",
  "Auto Scroll On": "自动滚动开",
  "Auto Scroll Off": "自动滚动关",
  "Clear": "清空",
  "Task Config": "任务配置",
  "Reload": "刷新",
  "Return": "返回",
  "Refresh": "刷新",
  "Save": "保存",
};

function detectInitialLang() {
  const saved = localStorage.getItem("oas_webui_lang");
  if (saved === "zh-CN" || saved === "en-US") return saved;

  return "zh-CN";
}

function splitCamel(text) {
  return String(text ?? "").replace(/([a-z0-9])([A-Z])/g, "$1 $2");
}

function variantsForKey(key) {
  const raw = String(key ?? "").trim();
  if (!raw) return [];

  const camelSplit = splitCamel(raw);
  const snakeToSpace = raw.replaceAll("_", " ");
  const kebabToSpace = raw.replaceAll("-", " ");
  const compact = raw.replace(/[\s_-]+/g, "");
  const lowerCompact = compact.toLowerCase();
  const candidates = [
    raw,
    camelSplit,
    snakeToSpace,
    kebabToSpace,
    splitCamel(snakeToSpace),
    splitCamel(kebabToSpace),
    compact,
    lowerCompact,
    raw.toLowerCase(),
    camelSplit.toLowerCase(),
    snakeToSpace.toLowerCase(),
    kebabToSpace.toLowerCase(),
  ];

  return [...new Set(candidates.filter(Boolean))];
}

function buildAliasDict(dict) {
  const out = {};
  for (const [key, value] of Object.entries(dict || {})) {
    for (const variant of variantsForKey(key)) {
      if (!(variant in out)) out[variant] = value;
    }
  }
  return out;
}

export const i18n = {
  currentLang: detectInitialLang(),
  zhDict: buildAliasDict(fallbackZh),

  async load(api) {
    try {
      const [base, add] = await Promise.all([api.getZhCn(), api.getAdditionalTranslate()]);
      const addZh = add?.["zh-CN"] || {};
      this.zhDict = buildAliasDict({ ...fallbackZh, ...(base || {}), ...(addZh || {}) });
    } catch (_e) {
      this.zhDict = buildAliasDict(fallbackZh);
    }
  },

  setLang(lang) {
    this.currentLang = lang;
    localStorage.setItem("oas_webui_lang", lang);
  },

  toggleLang() {
    this.setLang(this.currentLang === "zh-CN" ? "en-US" : "zh-CN");
  },

  t(key) {
    const text = String(key ?? "");
    if (this.currentLang !== "zh-CN") return text;
    for (const c of variantsForKey(text)) {
      if (this.zhDict[c]) return this.zhDict[c];
    }
    return text;
  },
};
