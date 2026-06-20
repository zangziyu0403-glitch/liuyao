from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from main import AnalysisEngine, LiuYaoEngine, build_query_info


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"


class LiuYaoRequestHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:
        parsed = urlparse(path)
        if parsed.path == "/":
            return str(STATIC_DIR / "index.html")
        return str(STATIC_DIR / parsed.path.lstrip("/"))

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/divination":
            self.send_error(404, "Not found")
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            totals = payload.get("totals")
            gender = payload.get("gender")
            yongshen_line = payload.get("yongshen_line")

            if not isinstance(totals, list) or len(totals) != 6:
                raise ValueError("必须输入六次摇卦结果")

            totals = [int(total) for total in totals]
            chart = LiuYaoEngine(totals=totals)

            yongshen = None
            if yongshen_line is not None:
                yongshen_line = int(yongshen_line)
                if yongshen_line not in {1, 2, 3, 4, 5, 6}:
                    raise ValueError("用神爻位必须是 1 到 6")
                yongshen = chart.lines[yongshen_line - 1].six_relative

            query_info = build_query_info(
                gender=str(gender or "").strip(),
                yongshen=yongshen,
                yongshen_line=yongshen_line,
            )
            engine = AnalysisEngine(chart=chart, query_info=query_info)
            self.send_json(engine.to_dict())
        except Exception as exc:
            self.send_json({"error": str(exc)}, status=400)

    def send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), LiuYaoRequestHandler)
    print(f"京房六爻排盘服务已启动：http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST") or ("0.0.0.0" if "PORT" in os.environ else "127.0.0.1")
    run(host=host, port=port)
