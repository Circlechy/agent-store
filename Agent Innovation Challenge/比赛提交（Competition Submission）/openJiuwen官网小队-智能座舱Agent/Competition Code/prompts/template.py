import os
from datetime import datetime, timezone

from jinja2 import Environment, FileSystemLoader, select_autoescape
from openjiuwen.core.common.exception.exception import JiuWenBaseException
from openjiuwen.core.common.exception.status_code import StatusCode


jinja_env = Environment(
    trim_blocks=True,
    lstrip_blocks=True,
    autoescape=select_autoescape(),
    loader=FileSystemLoader(os.path.dirname(__file__))
)

def apply_template(file_name: str, context_vars: dict) -> list:
    context_vars["CURRENT_TIME"] = datetime.now(timezone.utc).astimezone().isoformat()

    try:
        template = jinja_env.get_template(f"{file_name}.md")
        rendered_prompt = template.render(**context_vars)
        if not context_vars.get("messages"):
            return [{"role": "system", "content": rendered_prompt}]
        return [{"role": "system", "content": rendered_prompt}, *context_vars["messages"]]
    except FileNotFoundError as e:
        raise JiuWenBaseException(StatusCode.PROMPT_TEMPLATE_NOT_FOUND_ERROR.code,
                                  StatusCode.PROMPT_TEMPLATE_NOT_FOUND_ERROR.errmsg) from e
    except Exception as e:
        raise JiuWenBaseException(StatusCode.PROMPT_TEMPLATE_INCORRECT_ERROR.code,
                                  StatusCode.PROMPT_TEMPLATE_INCORRECT_ERROR.errmsg) from e