# 京房六爻排盘网页部署说明

## 推荐方式：Render

1. 注册或登录 Render。
2. 将当前项目上传到 GitHub 仓库。
3. 在 Render 新建 `Web Service`。
4. 选择这个 GitHub 仓库。
5. Render 会读取 `render.yaml`。
6. 部署完成后，Render 会生成一个公网网址。

## 启动命令

Render 使用：

```bash
python app.py
```

本地测试仍然使用：

```bash
python3 app.py
```

然后打开：

```text
http://127.0.0.1:8000/
```

## 说明

- 当前项目没有数据库。
- 当前项目没有第三方 Python 依赖。
- 排盘逻辑在 `main.py`。
- 网页服务入口在 `app.py`。
- 前端文件在 `static/`。
