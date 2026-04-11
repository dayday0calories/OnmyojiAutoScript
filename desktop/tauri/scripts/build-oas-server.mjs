import { spawn } from "node:child_process";
import { cp, mkdir, rm } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const tauriRoot = path.resolve(__dirname, "..");
const repoRoot = path.resolve(tauriRoot, "..", "..");
const resourcesDir = path.resolve(tauriRoot, "src-tauri", "resources");
const bundleDir = path.resolve(resourcesDir, "oas_server");
const distRoot = path.resolve(repoRoot, "build", "tauri-pyinstaller-dist");
const distDir = path.resolve(distRoot, "OAS");
const workDir = path.resolve(repoRoot, "build", "pyinstaller-tauri");
const specDir = path.resolve(repoRoot, "build", "pyinstaller-tauri-spec");
const pyinstallerConfigDir = path.resolve(repoRoot, "build", "pyinstaller-config");
const pyinstallerFromVenv = path.resolve(repoRoot, ".venv", "bin", "pyinstaller");
const pyinstaller = pyinstallerFromVenv;

const dataDirs = ["assets", "bin", "config", "deploy", "module", "tasks", "webui"];

async function main() {
  await mkdir(resourcesDir, { recursive: true });
  await rm(bundleDir, { force: true, recursive: true });
  await rm(distDir, { force: true, recursive: true });
  await mkdir(distRoot, { recursive: true });
  await mkdir(workDir, { recursive: true });
  await mkdir(specDir, { recursive: true });
  await mkdir(pyinstallerConfigDir, { recursive: true });

  const args = [
    "--noconfirm",
    "--clean",
    "--onedir",
    "--name",
    "OAS",
    "--distpath",
    distRoot,
    "--workpath",
    workDir,
    "--specpath",
    specDir,
    ...dataDirs.flatMap((dir) => ["--add-data", `${path.resolve(repoRoot, dir)}:${dir}`]),
    path.resolve(repoRoot, "server.py"),
  ];

  await run(pyinstaller, args, repoRoot);
  await cp(distDir, bundleDir, { recursive: true });
}

function run(command, args, cwd) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd,
      stdio: "inherit",
      env: {
        ...process.env,
        PYTHONUNBUFFERED: "1",
        PYINSTALLER_CONFIG_DIR: pyinstallerConfigDir,
      },
    });

    child.on("error", (error) => {
      reject(
        new Error(
          `Failed to start PyInstaller at ${command}. ` +
            `Make sure the repo virtualenv exists and PyInstaller is installed.\n${error.message}`
        )
      );
    });

    child.on("exit", (code) => {
      if (code === 0) {
        resolve();
        return;
      }
      reject(new Error(`PyInstaller build failed with exit code ${code ?? "unknown"}`));
    });
  });
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
