function byId(id) {
  const el = document.getElementById(id);
  if (!el) {
    throw new Error(`Missing element #${id}`);
  }
  return el;
}

export const els = {
  configList: byId("config-list"),
  langBtn: byId("lang-btn"),
  currentConfig: byId("current-config"),
  schedulerIndicator: byId("scheduler-indicator"),
  startBtn: byId("start-btn"),
  stopBtn: byId("stop-btn"),
  refreshBtn: byId("refresh-btn"),
  clearLogBtn: byId("clear-log-btn"),
  autoScrollBtn: byId("autoscroll-btn"),
  runStatusText: byId("run-status-text"),
  logBox: byId("log-box"),

  runningEmpty: byId("running-empty"),
  runningTask: byId("running-task"),
  runningName: byId("running-name"),
  runningTime: byId("running-time"),
  pendingEmpty: byId("pending-empty"),
  pendingList: byId("pending-list"),
  waitingEmpty: byId("waiting-empty"),
  waitingList: byId("waiting-list"),

  taskList: byId("task-list"),
  taskOverlay: byId("task-overlay"),
  overlayTaskTitle: byId("overlay-task-title"),
  overlayBackBtn: byId("overlay-back-btn"),
  overlayReloadBtn: byId("overlay-reload-btn"),
  taskGroups: byId("task-groups"),
};
