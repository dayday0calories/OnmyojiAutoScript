async function fetchJson(url, init) {
  const resp = await fetch(url, init);
  if (!resp.ok) {
    throw new Error(`${resp.status} ${resp.statusText} @ ${url}`);
  }
  return resp.json();
}

export const api = {
  getConfigList: () => fetchJson("/config_list"),
  getScriptMenu: () => fetchJson("/script_menu"),
  getTaskArgs: (config, task) => fetchJson(`/${encodeURIComponent(config)}/${encodeURIComponent(task)}/args`),
  setTaskArg: (config, task, group, arg, type, value) => {
    const params = new URLSearchParams({ types: String(type), value: String(value) });
    const url = `/${encodeURIComponent(config)}/${encodeURIComponent(task)}/${encodeURIComponent(group)}/${encodeURIComponent(arg)}/value?${params.toString()}`;
    return fetch(url, { method: "PUT" });
  },
  getZhCn: () => fetchJson("/home/chinese_translate"),
  getAdditionalTranslate: () => fetchJson("/home/additional_translate"),
};
