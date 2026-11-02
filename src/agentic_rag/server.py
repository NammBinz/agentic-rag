"""Flask application factory for the K37 curriculum demo."""
import argparse
import json
import os
import threading
from pathlib import Path
from urllib.parse import urlparse
from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException
from werkzeug.serving import make_server
from .catalog import ROOT
from .engine import Engine
from .demo import DemoEngine
from .provider import ProviderError, Settings


def load_env(path):
    if not Path(path).exists():
        return
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        if key.strip().replace('_', '').isalnum():
            os.environ.setdefault(key.strip(), value.strip().strip('\"\''))


def validate_request(body):
    allowed = {'question', 'mode', 'dataset', 'cohort', 'curriculum_id', 'profile', 'intent',
               'target_course', 'history', 'enable_tools', 'enable_extra_retrieval', 'planner'}
    if not isinstance(body, dict) or set(body) - allowed:
        raise ValueError('Body phải là object JSON đúng schema')
    if body.get('dataset', 'project') not in ('project', 'sample'):
        raise ValueError('dataset không hợp lệ')
    if body.get('cohort') is not None and (not isinstance(body['cohort'], str) or len(body['cohort']) > 20):
        raise ValueError('cohort phải là chuỗi khóa hoặc null')
    if body.get('target_course') is not None and (not isinstance(body['target_course'], str) or len(body['target_course']) > 40):
        raise ValueError('target_course không hợp lệ')
    history = body.get('history', [])
    if not isinstance(history, list) or len(history) > 6 or any(not isinstance(h, dict) or
            not isinstance(h.get('question'), str) or len(h['question']) > 3000 for h in history):
        raise ValueError('history tối đa 6 câu hỏi gần nhất')
    return body


def create_app(settings=None, demo_only=True, provider=None):
    settings = settings or Settings.from_env()
    app = Flask(__name__, static_folder=None)
    app.json.ensure_ascii = False
    app.config['MAX_CONTENT_LENGTH'] = 32768
    engine_class = DemoEngine if demo_only else Engine
    engines = {d: engine_class(d, settings, provider=provider, cache_dir=ROOT / '.runtime' / 'vectors' / d)
               for d in (('project',) if demo_only else ('project', 'sample'))}
    locks = {d: threading.RLock() for d in engines}
    app.extensions['rag_engines'] = engines

    def select(values):
        dataset = values.get('dataset', 'project')
        if dataset not in engines:
            raise ValueError('Demo chỉ bật dữ liệu K37 thật; sample và khóa khác không được mở' if demo_only else 'dataset không hợp lệ')
        cohort = values.get('cohort', 'K37' if demo_only else None)
        if cohort is not None and (not isinstance(cohort, str) or len(cohort) > 20):
            raise ValueError('cohort không hợp lệ')
        if demo_only and (cohort != 'K37' or values.get('curriculum_id', 'CNTT-2024') != 'CNTT-2024'):
            raise ValueError('Bản demo chỉ phục vụ K37 — CNTT-2024')
        with locks[dataset]:
            return engines[dataset].for_cohort(cohort)

    @app.before_request
    def validate_origin():
        if request.method == 'POST':
            origin = request.headers.get('Origin')
            if origin and (urlparse(origin).scheme not in ('http', 'https') or urlparse(origin).netloc != request.host):
                return jsonify(error='Chỉ nhận yêu cầu từ giao diện cùng địa chỉ'), 403

    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
        return response

    @app.errorhandler(Exception)
    def error(exc):
        if isinstance(exc, (ValueError, TypeError)):
            return jsonify(error=str(exc)), 400
        if isinstance(exc, ProviderError):
            return jsonify(error=str(exc), code='provider_error'), 502
        if isinstance(exc, HTTPException):
            return jsonify(error=exc.name), exc.code
        return jsonify(error='Lỗi xử lý máy chủ; không có câu trả lời thay thế ngầm.'), 500

    def body():
        if request.mimetype != 'application/json':
            raise ValueError('Content-Type phải là application/json')
        data = json.loads(request.get_data(), parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Không nhận NaN/Infinity')))
        if not isinstance(data, dict):
            raise ValueError('Body phải là object JSON')
        return data

    @app.get('/api/health')
    def health():
        return jsonify(ok=True, framework='Flask', provider=settings.provider, retriever=settings.retriever,
                       model=settings.model if settings.provider != 'offline' else None,
                       scope='K37 — CNTT-2024' if demo_only else 'Research test mode', demo_only=demo_only)

    @app.get('/api/catalog')
    def catalog():
        c = select(request.args).catalog
        return jsonify(manifest=c.manifest, context=c.context, courses=list(c.courses.values()),
                       gaps=c.gaps, sources=[s for s in c.sources.values() if c.source_applies(s)])

    @app.get('/api/courses')
    def courses():
        e = select(request.args)
        return jsonify(e.tools.lookup(request.args.get('q', ''), e.catalog.cohort))

    @app.get('/api/conditions')
    def conditions():
        e = select(request.args)
        return jsonify(e.tools.conditions(request.args.get('q', ''), e.catalog.cohort, depth=int(request.args.get('depth', '0'))))

    @app.get('/api/chunks/<chunk_id>')
    def chunk(chunk_id):
        c = select(request.args).catalog
        found = next((x for x in c.chunks if x['id'] == chunk_id), None)
        return (jsonify(c.citation(found)), 200) if found else (jsonify(error='Không có đoạn nguồn đúng phạm vi'), 404)

    @app.post('/api/chat')
    def chat():
        data = validate_request(body())
        # Explicitly rejected scopes never reach retrieval or LLM.
        dataset = data.get('dataset', 'project')
        if demo_only and data.get('cohort', 'K37') != 'K37':
            e = select({'dataset': dataset})
        else:
            e = select(data)
        data.pop('dataset', None)
        data.pop('curriculum_id', None)
        if demo_only:
            data.setdefault('cohort', 'K37')
        with locks[dataset]:
            return jsonify(e.answer(**data))

    @app.post('/api/prerequisites')
    def prerequisites():
        data = body()
        if set(data) - {'dataset', 'cohort', 'curriculum_id', 'course_code', 'profile'}:
            raise ValueError('Body kiểm tra tiên quyết không hợp lệ')
        e = select(data)
        code = data.get('course_code')
        if not isinstance(code, str) or not code.strip() or len(code) > 40:
            raise ValueError('Cần course_code')
        return jsonify(e.tools.prerequisites(code, e.catalog.cohort, data.get('profile')))

    @app.get('/')
    def index():
        return send_from_directory(ROOT / 'web', 'index.html')

    @app.get('/<path:name>')
    def static(name):
        if name not in ('app.js', 'style.css'):
            return jsonify(error='Không có tệp này'), 404
        return send_from_directory(ROOT / 'web', name)

    return app


def create_server(host='127.0.0.1', port=8765, settings=None, demo_only=True):
    """Werkzeug server handle for local execution and HTTP integration tests."""
    return make_server(host, port, create_app(settings, demo_only), threaded=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    load_env(ROOT / '.env')
    app = create_app()
    print(f'K37 — CNTT-2024 · Flask: http://{args.host}:{args.port}', flush=True)
    app.run(host=args.host, port=args.port, debug=False, use_reloader=False)

if __name__ == '__main__':
    main()
