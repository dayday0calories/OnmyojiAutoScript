const baseUrl = "http://127.0.0.1:22267";
const healthUrl = `${baseUrl}/home/test`;
const webuiUrl = `${baseUrl}/webui/`;

const status = document.querySelector("#status");
const retry = document.querySelector("#retry");

async function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForServer() {
  status.textContent = "正在启动本地服务 127.0.0.1:22267…";
  for (let attempt = 1; attempt <= 120; attempt += 1) {
    try {
      const response = await fetch(healthUrl, { cache: "no-store" });
      if (response.ok) {
        status.textContent = "服务已就绪，正在打开 OAS WebUI…";
        window.location.replace(webuiUrl);
        return;
      }
    } catch (_) {
      // keep polling
    }
    status.textContent = `等待本地服务启动… 第 ${attempt}/120 次检查`;
    await sleep(500);
  }

  status.textContent = "本地服务未在预期时间内完成启动。你可以重试，或在浏览器中打开。";
}

retry?.addEventListener("click", () => {
  waitForServer();
});

waitForServer();
