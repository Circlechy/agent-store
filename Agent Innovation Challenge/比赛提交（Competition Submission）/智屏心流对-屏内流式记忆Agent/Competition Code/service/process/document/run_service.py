import argparse
import json
import time

from flask import Flask, request, Blueprint

from service.process.document.pipeline.orkestractor_kernel import UpdateLocalDocsOrchestrator
from service.process.document.parse_config import ParseConfig
from service.process.common.utils.log import logger

# Required parameters
parser = argparse.ArgumentParser()
parser.add_argument(
    "--host",
    default="0.0.0.0",
    type=str,
    help="IP",
)
parser.add_argument(
    "--port",
    default=8084,
    type=int,
    help="Port",
)
args, _ = parser.parse_known_args()  # args, unparsed
options = {"bind": f"{args.host}:{args.port}", "workers": 1, "worker_class": "gthread", "timeout": 180}
logger.info(args)
# 将 args 转换为字典
args_dict = vars(args)

BLUEPRINT_NAME = "doc_process"
blueprint = Blueprint(BLUEPRINT_NAME, __name__)


def create_app(blueprint=None):
    if blueprint is None:
        blueprint = blueprint_default()
    _app = Flask(__name__)
    _app.register_blueprint(blueprint, url_prefix="/process")

    @_app.before_request
    def before_request():
        if request.blueprint == BLUEPRINT_NAME:
            req = request.get_json()
            logger.info("Request: %s", req)

    @_app.teardown_request
    def teardown_request(err):
        if err:
            logger.error("Error: %s", err)

    _app.wsgi_app = TimerMiddleware(_app.wsgi_app)
    return _app


def blueprint_default():
    # 如果需要，可以在这里创建或返回默认的蓝图
    return blueprint


class TimerMiddleware:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        start_time = time.time()
        response = self.wsgi_app(environ, start_response)
        process_time = time.time() - start_time
        logger.info("Duration: %s", process_time)
        return response


yaml_config_path = ParseConfig.parse_config("dev")
process_service = UpdateLocalDocsOrchestrator(yaml_config_path)


@blueprint.route("", methods=["POST"])
def run():
    kwargs = request.get_json()
    response = process_service.process(kwargs)
    return json.dumps(response, ensure_ascii=False)


if __name__ == "__main__":
    app = create_app()
    app.run(debug=False, host=args.host, port=args.port)
    # GunicornApplication(app, options).run()
