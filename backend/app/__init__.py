"""
HiveMind Backend - Flask Application Factory

HiveMind is a swarm-intelligence prediction engine: it builds a parallel
digital society of AI agents from seed material and simulates how public
opinion evolves, producing prediction reports and explorable agent worlds.

Based on MiroFish (https://github.com/666ghj/MiroFish) — AGPL-3.0.
Heavily extended and redesigned by the HiveMind contributors.
"""

import os
import warnings

# 抑制 multiprocessing resource_tracker 的警告（来自第三方库如 transformers）
# 需要在所有其他导入之前设置
warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, request
from flask_cors import CORS

from .config import Config
from .utils.logger import setup_logger, get_logger


def create_app(config_class=Config):
    """Flask应用工厂函数"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # 设置JSON编码：确保中文直接显示（而不是 \uXXXX 格式）
    # Flask >= 2.3 使用 app.json.ensure_ascii，旧版本使用 JSON_AS_ASCII 配置
    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False
    
    # 设置日志
    logger = setup_logger('hivemind')
    
    # 只在 reloader 子进程中打印启动信息（避免 debug 模式下打印两次）
    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    debug_mode = app.config.get('DEBUG', False)
    should_log_startup = not debug_mode or is_reloader_process
    
    if should_log_startup:
        logger.info("=" * 50)
        logger.info("HiveMind Backend 启动中...")
        logger.info("=" * 50)
    
    # 启用CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # 注册模拟进程清理函数（确保服务器关闭时终止所有模拟进程）
    from .services.simulation_runner import SimulationRunner
    SimulationRunner.register_cleanup()
    if should_log_startup:
        logger.info("已注册模拟进程清理函数")
    
    # 请求日志中间件
    @app.before_request
    def log_request():
        logger = get_logger('hivemind.request')
        logger.debug(f"请求: {request.method} {request.path}")
        if request.content_type and 'json' in request.content_type:
            logger.debug(f"请求体: {request.get_json(silent=True)}")
    
    @app.after_request
    def log_response(response):
        logger = get_logger('hivemind.request')
        logger.debug(f"响应: {response.status_code}")
        return response
    
    # 注册蓝图
    from .api import graph_bp, simulation_bp, report_bp, analytics_bp
    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
    app.register_blueprint(report_bp, url_prefix='/api/report')
    app.register_blueprint(analytics_bp, url_prefix='/api/analytics')
    
    # 健康检查
    @app.route('/health')
    def health():
        return {'status': 'ok', 'service': 'HiveMind Backend'}

    # Friendly root page — visiting the API root in a browser shows a
    # small status card instead of a confusing "Not Found" error.
    @app.route('/')
    def index():
        return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>HiveMind API</title>
<style>
  body {{ background:#0D1117; color:#E6EDF3; font-family:ui-monospace,monospace;
         display:flex; align-items:center; justify-content:center; min-height:96vh; margin:0; }}
  .card {{ border:1px solid #2A323D; border-radius:14px; padding:34px 44px; max-width:560px;
           background:#161C24; }}
  h1 {{ color:#F0A500; font-size:1.25rem; margin:0 0 6px; letter-spacing:1px; }}
  p  {{ color:#9AA7B4; font-size:.85rem; line-height:1.7; margin:6px 0; }}
  code {{ color:#FFC933; }}
  .ok {{ color:#3FB68B; }}
</style></head>
<body><div class="card">
  <h1>🐝 HiveMind API</h1>
  <p class="ok">● status: ok — backend is running</p>
  <p>This is the <b>API service</b>. The website itself is served by the
     frontend (port <code>3000</code> locally, or your Vercel URL in production).</p>
  <p>Health: <code>/health</code><br>
     Analytics demo: <code>POST /api/analytics/demo</code></p>
</div></body></html>"""

    # JSON 404 for unknown API routes (frontends expect JSON, not HTML)
    @app.errorhandler(404)
    def not_found(e):
        from flask import request, jsonify
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': f'Unknown API route: {request.path}'}), 404
        return e

    
    if should_log_startup:
        logger.info("HiveMind Backend 启动完成")
    
    return app

