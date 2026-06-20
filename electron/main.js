const { app, BrowserWindow, dialog } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
const net = require("net");
const path = require("path");

const APP_PORT = process.env.LIUYAO_PORT || "8765";
let backendProcess = null;

function backendPath() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, "backend", "liuyao-backend.exe");
  }
  return path.join(__dirname, "..", "app.py");
}

function startBackend() {
  const target = backendPath();
  const env = {
    ...process.env,
    HOST: "127.0.0.1",
    PORT: APP_PORT,
  };

  if (app.isPackaged) {
    if (!fs.existsSync(target)) {
      throw new Error(`未找到后端程序：${target}`);
    }
    backendProcess = spawn(target, [], {
      env,
      windowsHide: true,
    });
    return;
  }

  backendProcess = spawn("python", [target], {
    env,
    cwd: path.join(__dirname, ".."),
    windowsHide: true,
  });
}

function waitForBackend(timeoutMs = 12000) {
  const startedAt = Date.now();

  return new Promise((resolve, reject) => {
    const tryConnect = () => {
      const socket = net.createConnection(Number(APP_PORT), "127.0.0.1");

      socket.on("connect", () => {
        socket.end();
        resolve();
      });

      socket.on("error", () => {
        socket.destroy();
        if (Date.now() - startedAt > timeoutMs) {
          reject(new Error("排盘服务启动超时"));
          return;
        }
        setTimeout(tryConnect, 250);
      });
    };

    tryConnect();
  });
}

async function createWindow() {
  const win = new BrowserWindow({
    width: 1220,
    height: 820,
    minWidth: 980,
    minHeight: 680,
    backgroundColor: "#f3eee5",
    title: "京房六爻排盘",
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  await win.loadURL(`http://127.0.0.1:${APP_PORT}/`);
}

app.whenReady().then(async () => {
  try {
    startBackend();
    await waitForBackend();
    await createWindow();
  } catch (error) {
    dialog.showErrorBox("启动失败", error.message || String(error));
    app.quit();
  }
});

app.on("window-all-closed", () => {
  app.quit();
});

app.on("before-quit", () => {
  if (backendProcess) {
    backendProcess.kill();
    backendProcess = null;
  }
});
