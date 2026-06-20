# Windows 版打包说明

当前项目已加入 Electron 桌面版配置，可以通过 GitHub Actions 自动打包 Windows 安装包。

## 生成 Windows 版

1. 将项目上传到 GitHub 仓库。
2. 打开仓库页面。
3. 点击 `Actions`。
4. 选择 `Build Windows App`。
5. 点击 `Run workflow`。
6. 等待任务完成。
7. 在任务页面底部下载 `liuyao-windows`。

下载后里面会包含 Windows 版安装包或便携版程序。

## 朋友如何使用

你把生成的 `.exe` 发给朋友即可。

朋友双击运行。如果 Windows 提示“未知发布者”，这是因为当前测试版没有代码签名，选择继续运行即可。

## 当前架构

- Electron 负责桌面窗口。
- Python 后端会被 PyInstaller 打包成 `liuyao-backend.exe`。
- App 启动时自动启动后端服务。
- 用户不需要安装 Python。
- 用户不需要打开浏览器。

## 注意

当前是测试版打包方式，没有微软代码签名证书。正式发布前建议购买代码签名证书，减少系统安全提示。
