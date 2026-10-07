"""Local demo HTTP server. This is not a production authentication service."""
import argparse
import json
import mimetypes
import os
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from .catalog import ROOT
from .engine import Engine
from .provider import ProviderError, Settings


def load_env(path):
    """Load plain KEY=VALUE lines without shell expansion or executing .env."""
    if not Path(path).exists():
        return
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip().replace("_", "").isalnum():
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def validate_request(body):
    if not isinstance(body, dict):
        raise ValueError("Body phải là object JSON")
    allowed = {"question", "mode", "dataset", "cohort", "profile", "intent", "target_course",
               "history", "enable_tools", "enable_extra_retrieval"}
    if set(body) - allowed:
        raise ValueError("Body chứa trường không được hỗ trợ")
    if body.get("dataset", "project") not in ("project", "sample"):
        raise ValueError("dataset không hợp lệ")
    if body.get("cohort") is not None and (not isinstance(body["cohort"], str) or len(body["cohort"]) > 20):
        raise ValueError("cohort phải là chuỗi khóa hoặc null")
    if body.get("target_course") is not None and (not isinstance(body["target_course"], str) or len(body["target_course"]) > 40):
        raise ValueError("target_course không hợp lệ")
    history = body.get("history", [])
    if not isinstance(history, list) or len(history) > 6 or any(not isinstance(h, dict) or
            not isinstance(h.get("question"), str) or len(h["question"]) > 3000 for h in history):
        raise ValueError("history tối đa 6 câu hỏi gần nhất")
    return body


def create_server(host="127.0.0.1", port=8765, settings=None):
    settings = settings or Settings.from_env()
    engines = {dataset: Engine(dataset, settings, cache_dir=ROOT / ".runtime" / "vectors" / dataset)
               for dataset in ("project", "sample")}
    locks = {dataset: threading.Lock() for dataset in engines}
    web_root = ROOT / "web"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            # No prompts, API keys or student profiles in console logs.
            return

        def send_bytes(self, status, data, content_type):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(data)

        def send_json(self, status, value):
            self.send_bytes(status, json.dumps(value, ensure_ascii=False, allow_nan=False).encode(), "application/json; charset=utf-8")

        def selected_engine(self, params):
            name = params.get("dataset", ["project"])[0]
            if name not in engines:
                raise ValueError("dataset không hợp lệ")
            return engines[name]

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            try:
                engine = self.selected_engine(params)
                if parsed.path == "/api/health":
                    return self.send_json(200, {"ok": True, "provider": settings.provider, "retriever": settings.retriever,
                                               "model": settings.model if settings.provider == "openai" else None})
                if parsed.path == "/api/catalog":
                    return self.send_json(200, {"manifest": engine.catalog.manifest,
                        "courses": list(engine.catalog.courses.values()), "gaps": engine.catalog.gaps,
                        "sources": list(engine.catalog.sources.values())})
                if parsed.path == "/api/courses":
                    return self.send_json(200, engine.tools.lookup(params.get("q", [""])[0], params.get("cohort", [None])[0]))
                if parsed.path.startswith("/api/chunks/"):
                    chunk_id = urllib.parse.unquote(parsed.path.removeprefix("/api/chunks/"))
                    chunk = next((c for c in engine.catalog.chunks if c["id"] == chunk_id), None)
                    return self.send_json(200 if chunk else 404, engine.catalog.citation(chunk) if chunk else {"error": "Không có đoạn nguồn"})
                if parsed.path.startswith("/api/"):
                    return self.send_json(404, {"error": "Không có endpoint này"})
                name = "index.html" if parsed.path == "/" else urllib.parse.unquote(parsed.path.lstrip("/"))
                path = (web_root / name).resolve()
                if not path.is_relative_to(web_root.resolve()) or not path.is_file():
                    return self.send_json(404, {"error": "Không có tệp này"})
                content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                if content_type.startswith("text/") or content_type == "application/javascript":
                    content_type += "; charset=utf-8"
                self.send_bytes(200, path.read_bytes(), content_type)
            except ValueError as error:
                self.send_json(400, {"error": str(error)})

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path not in ("/api/chat", "/api/prerequisites"):
                return self.send_json(404, {"error": "Không có endpoint này"})
            origin = self.headers.get("Origin")
            if origin:
                origin_url = urllib.parse.urlparse(origin)
                if origin_url.scheme not in ("http", "https") or origin_url.netloc != self.headers.get("Host"):
                    return self.send_json(403, {"error": "Chỉ nhận yêu cầu từ giao diện cùng địa chỉ"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > 32768:
                    raise ValueError("Body phải có 1–32768 byte")
                if self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
                    raise ValueError("Content-Type phải là application/json")
                body = json.loads(self.rfile.read(length), parse_constant=lambda x: (_ for _ in ()).throw(ValueError("JSON không nhận NaN/Infinity")))
                if parsed.path == "/api/prerequisites":
                    if not isinstance(body, dict) or set(body) - {"dataset", "course_code", "cohort", "profile"}:
                        raise ValueError("Body kiểm tra tiên quyết không hợp lệ")
                    engine = self.selected_engine({"dataset": [body.get("dataset", "project")]})
                    code = body.get("course_code")
                    if not isinstance(code, str) or not code.strip() or len(code) > 40:
                        raise ValueError("Cần course_code")
                    return self.send_json(200, engine.tools.prerequisites(code, body.get("cohort"), body.get("profile")))
                body = validate_request(body)
                dataset = body.pop("dataset", "project")
                with locks[dataset]:
                    result = engines[dataset].answer(**body)
                self.send_json(200, result)
            except (ValueError, TypeError) as error:
                self.send_json(400, {"error": str(error)})
            except ProviderError as error:
                self.send_json(502, {"error": str(error), "code": "provider_error"})
            except Exception:
                self.send_json(500, {"error": "Lỗi xử lý ở máy chủ; kiểm tra dữ liệu/cấu hình, không có kết quả thay thế."})

    return ThreadingHTTPServer((host, port), Handler)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    load_env(ROOT / ".env")
    server = create_server(args.host, args.port)
    print(f"Agentic RAG demo: http://{args.host}:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
