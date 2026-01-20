import sys

import pandas as pd
import importlib
from libcst.metadata import PositionProvider, ParentNodeProvider

import difflib
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import OrderedDict, defaultdict
from pathlib import Path
from threading import Lock
from typing import List, Optional
import zipfile
import io
import libcst as cst
from libcst import helpers as cst_helpers
from libcst import metadata
# from tqdm import tqdm

sys.path.append("D:\\openjiuwen\\msadapter-master\\msadapter-master")
installed_msadapter = True
try:
    import msadapter
    import torch
    t1 = torch.tensor([1, 2, 3])
    print("Installed Msadapter.")
except ImportError:
    installed_msadapter = False
    print("Not Installed Msadapter.")


current_file_path = os.path.abspath(__file__)
current_dir_path = os.path.dirname(current_file_path)

MSADAPTER_API_DIR = os.path.join(current_dir_path, "msadapter_api") # "D:\\work\\agent_file\\openjiuwen\\agent-studio\\plugin_server\\openjiuwen_plugin_server\\torch2msadapter\\msadapter_api"


def _load_precision_issues(issue_path: Path) -> dict:
    try:
        with issue_path.open("r", encoding="utf8") as f:
            data = json.load(f)
        return data.get("issues", {})
    except FileNotFoundError:
        print(f"warning: precision issue file not found at {issue_path}")
        return {}
    except json.JSONDecodeError:
        print(f"warning: precision issue file {issue_path} is not valid json")
        return {}


with open(MSADAPTER_API_DIR + "\\torch_api.json", "r", encoding="utf8") as f:
    msadapter_torch_api_list = {}
    api_list = json.load(f)
    for api in api_list:
        # print(api)
        msadapter_torch_api_list[api["name"]] = api

with open(MSADAPTER_API_DIR + "\\torch_tensor_api.json", "r", encoding="utf8") as f:
    msadapter_torch_tensor_api_list ={}
    api_list = json.load(f)
    for api in api_list:
        msadapter_torch_tensor_api_list[api["name"].split(".")[-1]] = api
        # print(api["name"].split(".")[-1])

PRECISION_ISSUES = _load_precision_issues(Path(MSADAPTER_API_DIR + "\\issues.json"))

API_MAP = {}
with open(MSADAPTER_API_DIR + "\\torch_return_tensor_api.json", "r", encoding="utf8") as f:
    RETURN_TENSOR_API_LIST = json.load(f)

validated_api_list = []

# msadapter_module = importlib.import_module("torch")

# 结构：[{file_path: str, lineno: int, api_name: str, warning_type: int, warning_info: str}]
# warning_type: 0-error，1-warning, 
api_warning_list = []
api_warning_lock = Lock()


def drain_api_warnings():
    with api_warning_lock:
        items = list(api_warning_list)
        api_warning_list.clear()
    return items


class TorchToMindSporeTransformer(cst.CSTTransformer):
    """
    使用 LibCST 将 PyTorch API 调用改写为 MindSpore 调用。

    示例:
        >>> code = "import torch.nn as nn\\nx = nn.ReLU()(input)"
        >>> mod = cst.parse_module(code)
        >>> wrapper = metadata.MetadataWrapper(mod)
        >>> new_mod = wrapper.visit(TorchToMindSporeTransformer(API_MAP, pt_aliases={'nn': 'torch.nn'}))
        >>> "mindspore" in new_mod.code
        True

    输出:
        生成的新 AST 在 `code` 属性中包含 MindSpore API 调用及必要的注释。
    """

    METADATA_DEPENDENCIES = (PositionProvider, ParentNodeProvider)

    def __init__(
        self,
        api_map,
        ms_aliases: Optional[dict] = None,
        pt_aliases: Optional[dict] = None,
        pt_assignment_aliases: Optional[dict] = None,
        pt_assignment_wrapped: Optional[dict] = None,
        use_mint: bool = False,
        file_path: str = None,
        precision_issues: Optional[dict] = None,
    ) -> None:
        super().__init__()
        self.api_map = api_map
        self.ms_aliases = ms_aliases or {}
        self.pt_aliases = pt_aliases or {}
        self.pt_assignment_aliases = pt_assignment_aliases or {}
        self.pt_assignment_wrapped = pt_assignment_wrapped or {}
        # 输入代码未显式导入 mindspore 时会启用 mint 模式，
        # 这样 nn/ops 会默认指向 mindspore.mint.nn / mindspore.mint.ops。
        self.use_mint = use_mint
         # 当输入代码中没有显式 mindspore 导入时，use_mint=True，
         # 这样会优先走 mindspore.mint 接口。
        self.use_mint = use_mint
        self.file_path = file_path
        self.notes_by_stmt = defaultdict(list)
        self.precision_notes_by_stmt = defaultdict(list)
        self.added_lines_so_far = 0
        self.precision_issues = precision_issues or {}
        self.api_by_class = {
            conf["pytorch"].split(".")[-1]: conf for conf in api_map.values()
        }
        self.api_by_pt_full = {
            conf["pytorch"]: conf for conf in api_map.values()
        }
        # 输入代码未显式导入 mindspore 时会启用 mint 模式，
        # 这样 nn/ops 会默认指向 mindspore.mint.nn / mindspore.mint.ops。
        self.use_mint = use_mint

    # def leave_Assign(self, original_node: cst.Assign, updated_node: cst.Assign) -> None:
    #     print(f"赋值语句: 行号 {original_node.lineno}")
    #     return updated_node

    def visit_Import(self, node: cst.Import) -> None:
        for alias in node.names:
            full = cst_helpers.get_full_name_for_node(alias.name)
            if not full or not full.startswith("torch"):
                continue
            asname = alias.asname.name.value if alias.asname else None
            self.pt_aliases[asname or full] = full

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        if node.module is None:
            return
        module = cst_helpers.get_full_name_for_node(node.module)
        if not module or not module.startswith("torch"):
            return
        if isinstance(node.names, cst.ImportStar):
            return
        for alias in node.names:
            name_str = cst_helpers.get_full_name_for_node(alias.name)
            if not name_str:
                continue
            asname = alias.asname.name.value if alias.asname else None
            full = f"{module}.{name_str}"
            self.pt_aliases[asname or name_str] = full
    
    def _find_enclosing_stmt(self, node: cst.CSTNode) -> Optional[cst.CSTNode]:
        """
        获取包裹当前节点的最外层简单语句节点，方便追加注释。

        示例:
            >>> wrapper = metadata.MetadataWrapper(cst.parse_module("x = fn()"))
            >>> transformer = TorchToMindSporeTransformer(API_MAP)
            >>> wrapper.visit(transformer)  # 让 transformer 拥有父节点元数据
            >>> expr_node = wrapper.tree.body[0].body[0].value
            >>> isinstance(transformer._find_enclosing_stmt(expr_node), cst.SimpleStatementLine)
            True

        输出:
            返回 `cst.SimpleStatementLine` 或 None（未找到父节点时）。
        """
        parent = self.get_metadata(metadata.ParentNodeProvider, node, None)
        while parent is not None and not isinstance(parent, cst.SimpleStatementLine):
            parent = self.get_metadata(metadata.ParentNodeProvider, parent, None)
        return parent

    def _record_note(self, node: cst.CSTNode, notes) -> None:
        """
        将参数差异等提示记录到语句末尾，方便人工确认。

        示例:
            >>> wrapper = metadata.MetadataWrapper(cst.parse_module("y = fn()"))
            >>> transformer = TorchToMindSporeTransformer(API_MAP)
            >>> wrapper.visit(transformer)
            >>> stmt = wrapper.tree.body[0]
            >>> transformer._record_note(stmt, ["需要确认默认值"])
            >>> transformer.notes_by_stmt[stmt]
            ['需要确认默认值']

        输出:
            `notes_by_stmt` 被填充，后续在 leave_SimpleStatementLine 中会转成行尾注释。
        """        
        stmt = self._find_enclosing_stmt(node)
        if stmt is not None:
            self.notes_by_stmt[stmt].extend(notes)
        if hasattr(node, 'lineno'):
            print(f"lineno:: {node.lineno}")
        if hasattr(node, 'start_line'):
            print(f"lineno:: {node.start_line}")

    def _match_precision_issues(self, torch_api: Optional[str]):
        if not torch_api:
            return []
        matches = []
        direct = self.precision_issues.get(torch_api, [])
        if direct:
            matches.extend(direct)
        backward_key = f"{torch_api}.backward"
        if backward_key in self.precision_issues and backward_key != torch_api:
            matches.extend(self.precision_issues[backward_key])
        return matches

    def _format_precision_comment(self, lineno: int, torch_api: str, issue: dict) -> List[str]:
        return [
            "# [MSA_DETERMINISTIC]",
            f"# issue_id: {issue.get('issue_id', '')}",
            f"# line: {lineno}",
            f"# torch_op: {torch_api}",
            f"# msa_op: {issue.get('msa_op', '') or 'N/A'}",
            f"# 影响: {issue.get('impact', '') or 'N/A'}",
            f"# 根因: {issue.get('cause', '') or 'N/A'}",
            f"# 解决方法: {issue.get('workaround', '') or 'N/A'}",
            f"# src: {issue.get('src', '') or 'N/A'}",
        ]

    def _record_precision_issue(self, node: cst.CSTNode, lineno: int, torch_api: str, issue: dict) -> None:
        stmt = self._find_enclosing_stmt(node)
        if stmt is None:
            return
        self.precision_notes_by_stmt[stmt].append(
            {
                "issue": issue,
                "torch_api": torch_api,
                "orig_line": lineno,
            }
        )
        with api_warning_lock:
            api_warning_list.append(
                {
                    "file_path": self.file_path,
                    "lineno": lineno,
                    "api_name": torch_api,
                    "warning_type": 1,
                    "warning_info": f"[MSA_PRECISION] {issue.get('issue_id', '')}".strip(),
                }
            )


    def _resolve_pt_full_name(self, full_path: Optional[str]) -> Optional[str]:
        """
        将调用名还原成完整的 PyTorch 路径，避免将同名自定义方法误判为 torch API。

        示例:
            >>> transformer = TorchToMindSporeTransformer(API_MAP, pt_aliases={'nn': 'torch.nn'})
            >>> transformer._resolve_pt_full_name("nn.Linear")
            'torch.nn.Linear'

        输出:
            成功匹配时返回以 torch 开头的完整路径，否则返回 None。
        """
        if not full_path:
            return None

        if full_path in self.pt_assignment_aliases:
            return self.pt_assignment_aliases[full_path]

        parts = full_path.split(".")
        for i in range(len(parts), 0, -1):
            prefix = ".".join(parts[:i])
            module = self.pt_aliases.get(prefix)
            if module:
                suffix = parts[i:]
                if suffix:
                    return ".".join([module, *suffix])
                return module

        if full_path.startswith("torch.") or full_path.startswith("torch_npu"):
            return full_path
        return None


    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        """
        在访问完函数/方法调用后，根据映射将 PyTorch 调用替换为 MindSpore 并调整参数。

        示例:
            >>> api_conf = {"pytorch": "torch.nn.ReLU", "mindspore": "mindspore.nn.ReLU", "params": []}
            >>> transformer = TorchToMindSporeTransformer({"torch.nn.ReLU": api_conf}, pt_aliases={"nn": "torch.nn"})
            >>> call = cst.parse_expression("nn.ReLU(x)")
            >>> new_call = transformer.leave_Call(call, call)
            >>> cst_helpers.get_full_name_for_node(new_call.func)
            'mindspore.nn.ReLU'
            True

        输出:
            如果匹配到映射则返回替换后的调用节点，并记录参数差异备注；否则原样返回。
        """
        position = self.get_metadata(PositionProvider, original_node)
        lineno = position.start.line
        src_code = cst.Module([]).code_for_node(original_node)[:100]

        full_name = cst_helpers.get_full_name_for_node(updated_node.func)
        if not full_name:
            return updated_node
        pt_full_name = self._resolve_pt_full_name(full_name)
        api_conf = None

        if pt_full_name:                
            self._check_torch_api(pt_full_name, original_node, lineno)
            for issue in self._match_precision_issues(pt_full_name):
                self._record_precision_issue(original_node, lineno, pt_full_name, issue)
        self.check_special_api(full_name,original_node, lineno)

        return updated_node

    def _installed_msadapter(self, pt_full_name:str):
        note = None
        warning_type = 0
        modules = pt_full_name.split(".")
        last_module =""
        is_return_tensor = False
        is_validated_api = True
        for m in modules:
            if not last_module:
                if m == "torch":
                    last_module = m
                    continue
                else:
                    try:
                        importlib.import_module(m)
                        last_module = m
                        continue
                    except:
                        is_validated_api = False
                        break
            else:
                if last_module + "." + m in validated_api_list:
                    last_module = last_module + "." + m
                    continue
                else:
                    try:
                        exec_str = f"from {last_module} import {m}"
                        exec(exec_str)
                        last_module = last_module + "." + m
                        validated_api_list.append(last_module + "." + m)
                    except ModuleNotFoundError:
                        if last_module in RETURN_TENSOR_API_LIST:
                            if hasattr(t1, m):
                                last_module = last_module + "." + m
                                RETURN_TENSOR_API_LIST.append(last_module)
                                validated_api_list.append(last_module)
                                continue
                            else:
                                is_validated_api = False
                                break
                        try:
                            o = eval(last_module + "()")
                            if hasattr(o, m):
                                last_module = last_module + "." + m
                                validated_api_list.append(last_module)
                                continue
                            else:
                                is_validated_api = False
                                break
                        except Exception as e:
                            pass
                        is_validated_api = False
                        break
                    except ImportError:
                        is_validated_api = False
                        break
        if is_validated_api:
            return note, warning_type
        else:
            note = f"'{pt_full_name}':未适配;"
            warning_type = 1
            return note, warning_type

    def _not_installed_msadapter(self, pt_full_name:str):
        note = None
        warning_type = 0
        msadapter_api = msadapter_torch_api_list.get(pt_full_name,None)
        msadapter_tensor_api = msadapter_torch_tensor_api_list.get(pt_full_name.split(".")[-1], None)
        if msadapter_api:
            if msadapter_api["status"] == 1:
                note = f"'{pt_full_name}':msadapter未适配;"
                warning_type = 0
            elif msadapter_api["notes"]:
                note = f"'{pt_full_name}':未完全适配；{msadapter_api['notes']};"
                warning_type = 1
        elif msadapter_tensor_api:
            if msadapter_tensor_api["status"] == 1:
                note = f"'{pt_full_name}':msadapter未适配;"
                warning_type = 0
            elif msadapter_tensor_api["notes"]:
                note = f"'{pt_full_name}':未完全适配；{msadapter_tensor_api['notes']};"
                warning_type = 1
        else:
            # if not hasattr(torch_nn_module, pt_full_name.replace("torch.nn.", "")) and \
            #    not hasattr(msadapter_module, pt_full_name.replace("torch.", "")):
            note = f"'{pt_full_name}':msadapter未适配;"
            warning_type = 0
        return note, warning_type

    def check_special_api(self, full_name, original_node, lineno):
        if full_name.endswith("load_state_dict"):
            for arg in original_node.args:
                if not arg.keyword:
                    continue
                keyword = arg.keyword.value
                if keyword == "strict" and arg.value.value == "False":
                    for issue in self._match_precision_issues("load_state_dict"):
                        self._record_precision_issue(original_node, lineno, "load_state_dict", issue)

    def _check_torch_api(self, pt_full_name:str, original_node, lineno):
        """
        检查msadapter是否适配该API
        """
        note = None
        warning_type = 0
        if installed_msadapter:
            note, warning_type = self._installed_msadapter(pt_full_name)
        else:
            note, warning_type = self._not_installed_msadapter(pt_full_name)
        if note:
            # file_path: str, lineno: int, api_name: str, warning_type: int, warning_info: str
            with api_warning_lock:
                api_warning_list.append(
                    {
                        "file_path": self.file_path,
                        "lineno": lineno,
                        "api_name": pt_full_name,
                        "warning_type": warning_type,
                        "warning_info": note,
                   }
                )
            self._record_note(original_node, [note])

    def leave_ClassDef(
        self,
        original_node: cst.ClassDef,
        updated_node: cst.ClassDef,
    ) -> cst.ClassDef:
        """
        将继承自 torch.nn.Module 等基类的类，尝试替换为 MindSpore 的对应基类。

        示例:
            >>> code = "import torch.nn as nn\\nclass M(nn.Module):\\n    pass"
            >>> mod = cst.parse_module(code)
            >>> wrapper = metadata.MetadataWrapper(mod)
            >>> new_mod = wrapper.visit(TorchToMindSporeTransformer(API_MAP, pt_aliases={'nn': 'torch.nn'}))
            >>> "mindspore" in new_mod.code
            True

        输出:
            若能根据别名还原出 torch 全路径，并在映射表中找到对应 MindSpore 基类，则替换之。
        """
        return updated_node


    def leave_SimpleStatementLine(
        self,
        original_node: cst.SimpleStatementLine,
        updated_node: cst.SimpleStatementLine,
    ) -> cst.SimpleStatementLine:
        """
        在离开一行简单语句时，若有记录的提示信息则追加为行尾注释。

        示例:
            >>> stmt = cst.parse_statement("x = 1")
            >>> transformer = TorchToMindSporeTransformer(API_MAP)
            >>> transformer.notes_by_stmt[stmt] = ["默认值不一致"]
            >>> new_stmt = transformer.leave_SimpleStatementLine(stmt, stmt)
            >>> new_stmt.trailing_whitespace.comment.value
            '# 默认值不一致'

        输出:
            返回新增行尾注释后的语句节点，若无提示则保持不变。
        """

        notes = self.notes_by_stmt.get(original_node)
        precision_items = self.precision_notes_by_stmt.get(original_node)

        result_node = updated_node

        if not notes:
            extra_lines = []
            if precision_items:
                position = self.get_metadata(PositionProvider, original_node)
                base_line = position.start.line if position else 0
                for item in precision_items:
                    block = self._format_precision_comment(
                        base_line + self.added_lines_so_far,
                        item["torch_api"],
                        item["issue"],
                    )
                    for line in block:
                        extra_lines.append(cst.EmptyLine(comment=cst.Comment(line)))
            if extra_lines:
                self.added_lines_so_far += len(extra_lines)
                return cst.FlattenSentinel([result_node, *extra_lines])
            return result_node

        comment_text = "; ".join(dict.fromkeys(notes))
        tw = result_node.trailing_whitespace
        if tw.comment:
            existing = tw.comment.value.lstrip("#").strip()
            comment_text = f"{existing}; {comment_text}"

        new_trailing = cst.TrailingWhitespace(
            whitespace=cst.SimpleWhitespace("  "),
            comment=cst.Comment(f"# {comment_text}"),
            newline=tw.newline,
        )
        result_node = result_node.with_changes(trailing_whitespace=new_trailing)

        extra_lines = []
        if precision_items:
            position = self.get_metadata(PositionProvider, original_node)
            base_line = position.start.line if position else 0
            for item in precision_items:
                block = self._format_precision_comment(
                    base_line + self.added_lines_so_far,
                    item["torch_api"],
                    item["issue"],
                )
                for line in block:
                    extra_lines.append(cst.EmptyLine(comment=cst.Comment(line)))
        if extra_lines:
            self.added_lines_so_far += len(extra_lines)
            return cst.FlattenSentinel([result_node, *extra_lines])
        return result_node


def convert_code(code: str, file_path: str = None, precision_issues: Optional[dict] = None) -> str:
    """
    将整段 PyTorch 源码转换为 MindSpore 源码（LibCST 版本）。

    示例:
        >>> src = "import torch.nn as nn\\nnet = nn.ReLU()"
        >>> result = convert_code(src)
        >>> "mindspore" in result
        True

    输出:
        返回转换后的 MindSpore 源码字符串，包含必要的参数名替换与行尾提示。
    """
    precision_issues = precision_issues if precision_issues is not None else PRECISION_ISSUES
    module = cst.parse_module(code)

    ms_aliases = {}
    pt_aliases = {}
    pt_assignment_aliases = {}
    pt_assignment_wrapped = {}

    # 没有显式 mindspore 导入时，默认使用 mint 接口，
    # 并在后续自动插入 `from mindspore.mint import nn, ops`。
    use_mint = not bool(ms_aliases)

    wrapper = metadata.MetadataWrapper(module)
    new_module = wrapper.visit(
        TorchToMindSporeTransformer(
            API_MAP,
            ms_aliases=ms_aliases,
            pt_aliases=pt_aliases,
            pt_assignment_aliases=pt_assignment_aliases,
            pt_assignment_wrapped=pt_assignment_wrapped,
            use_mint=use_mint,
            file_path = file_path,
            precision_issues=precision_issues,
        )
    )

    new_code = new_module.code
    return new_code


def generate_diff(old: str, new: str) -> str:
    """
    生成原文件和新文件之间的 diff。

    示例:
        >>> old = "a = 1\\n"
        >>> new = "a = 2\\n"
        >>> print(generate_diff(old, new))
        --- pytorch
        +++ msadapter
        @@
        -a = 1
        +a = 2

    输出:
        返回标准 unified diff 文本，可直接写入 .diff 文件或打印。
    """
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines, new_lines,
        fromfile="pytorch",
        tofile="mindspore",
        lineterm=""
    )
    return "".join(diff)


def _convert_and_save(filename: str, input_root: Optional[str] = None, show_diff: bool = True) -> None:
    """
    转换单个文件并写入 output 目录，同时生成 diff。

    当传入 input_root 时，会在 output 下保留相对目录结构:
        input_root/foo/bar.py -> output/foo/bar.py
    否则:
        some.py -> output/some.py
    """
    with open(filename, "r", encoding="utf8") as f:
        code = f.read()

    result = convert_code(code, filename)

    base, ext = os.path.splitext(filename)
    if input_root:
        abs_input = os.path.abspath(input_root)
        abs_file = os.path.abspath(filename)
        try:
            common = os.path.commonpath([abs_input, abs_file])
        except ValueError:
            common = ""

        root_name = os.path.basename(os.path.normpath(abs_input))
        output_root = os.path.join("output", f"{root_name}_ms")

        if common == abs_input:
            rel_base = os.path.relpath(base, abs_input)
            out_base = os.path.join(output_root, rel_base)
        else:
            out_base = os.path.join(output_root, os.path.basename(base))
    else:
        out_base = os.path.join("output", os.path.basename(base))

    new_filename = f"{out_base}{ext}"
    out_dir = os.path.dirname(new_filename)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(new_filename, "w", encoding="utf8") as f:
        f.write(result)

    diff = generate_diff(code, result)
    if show_diff:
        print("=== 转换 DIFF 开始 ===")
        print(diff)
        print("=== 转换 DIFF 结束 ===")

    os.makedirs("diff", exist_ok=True)
    diff_filename = f"diff_({os.path.basename(filename)}-{os.path.basename(new_filename)}).diff"
    diff_path = os.path.join("diff", diff_filename)
    with open(diff_path, "w", encoding="utf8") as f:
        f.write(diff)
    if show_diff:
        print(f"已保存 diff 到: {diff_path}")



def _convert_and_save_with_warnings(filename: str, input_root: Optional[str] = None, show_diff: bool = True):
    drain_api_warnings()
    _convert_and_save(filename, input_root=input_root, show_diff=show_diff)
    return drain_api_warnings()


def _convert_code_with_warnings(code: str, file_path: str):
    drain_api_warnings()
    result = convert_code(code=code, file_path=file_path)
    return result, drain_api_warnings()


def create_zip_in_memory(files_dict):
    """
    在内存中创建ZIP文件
    :param files_dict: 字典 {文件名: 文件内容（字节流或字符串）}
    :return: ZIP文件的二进制数据（bytes）
    """
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for name, content in files_dict.items():
            if isinstance(content, str):
                content = content.encode('utf-8')  # 字符串转为字节流
            zipf.writestr(name, content)
    zip_buffer.seek(0)
    return zip_buffer.getvalue()


def unzip_to_memory(zip_bytes):
    """
    将ZIP文件的二进制数据解压到内存中
    :param zip_bytes: ZIP文件的二进制数据（bytes类型）
    :return: 字典 {文件名: 文件内容字节流}
    """
    in_memory_files = {}
    with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zip_ref:
        for file_name in zip_ref.namelist():
            if not file_name.endswith('.py'):
                continue
            with zip_ref.open(file_name) as file:
                in_memory_files[file_name] = io.BytesIO(file.read())
    return in_memory_files

def handler_plugin(origin_code,zip_file_path=None):
    target = origin_code
    # downloads()
    msadapter_new_files = {}
    if True:

        py_files = target
        py_items = [(name, data) for name, data in py_files.items()]
        all_warnings = []
        for name, code in py_items:
            result, warnings = _convert_code_with_warnings(code, name)
            msadapter_new_files[name] = result
            all_warnings.extend(warnings)

    else:
        all_warnings = []
        all_warnings.extend(_convert_and_save_with_warnings(target, show_diff=True))

    if 'all_warnings' in locals() and all_warnings:
        with api_warning_lock:
            api_warning_list.clear()
            api_warning_list.extend(all_warnings)

    print(f"api_warning_list: {len(api_warning_list)}")
    if api_warning_list:
        pdf = pd.DataFrame(api_warning_list)
        pdf.rename(columns={"warning_type": "warning_type(0-error，1-warning)"}, inplace=True)

        if True:
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                print(f"excel_bytes: {pdf.shape}")
                pdf.to_excel(writer, index=False)
            excel_bytes = excel_buffer.getvalue()
            print(f"excel_bytes: {len(excel_bytes)}")
            msadapter_new_files["msadapter_api_warning.xlsx"] = excel_bytes

            zip_buffer = create_zip_in_memory(msadapter_new_files)
            with open(zip_file_path, 'wb') as f:
                f.write(zip_buffer)
            excel_buffer.close()

        else:
            pdf.to_excel("api_warning.xlsx", index=False)
    return api_warning_list, msadapter_new_files

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  python torch2msadapter.py xxx.py")
        print("  python torch2msadapter.py xxx_dir   # 批量转换目录下所有 .py 文件")
        print("  python torch2msadapter.py xxx.zip   # 批量转换压缩包所有 .py 文件")
        sys.exit(0)

    target = sys.argv[1]

    if os.path.isdir(target):
        print(f"检测到目录，开始批量转换: {target}")
        py_files = []
        for root, _, files in os.walk(target):
            for name in files:
                if name.endswith(".py"):
                    py_files.append(os.path.join(root, name))

        if not py_files:
            print("未找到需要转换的 .py 文件")
            sys.exit(0)

        max_workers = min(32, os.cpu_count() or 4)
        all_warnings = []
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_convert_and_save_with_warnings, path, target, False) for path in py_files]
            with tqdm(total=len(futures), desc="Converting", unit="file") as pbar:
                for fut in as_completed(futures):
                    all_warnings.extend(fut.result())
                    pbar.update(1)
        print("\n批量转换完成。")
    elif target.endswith(".zip"):
        msadapter_new_files ={}
        with open(target, "rb") as f:
            zip_bytes = f.read()
            py_files = unzip_to_memory(zip_bytes)
            py_items = [(name, data.read().decode("utf-8")) for name, data in py_files.items()]
            max_workers = min(32, os.cpu_count() or 4)
            all_warnings = []
            with ProcessPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(_convert_code_with_warnings, code, name): name for name, code in py_items}
                with tqdm(total=len(futures), desc="Converting zip", unit="file") as pbar:
                    for fut in as_completed(futures):
                        name = futures[fut]
                        result, warnings = fut.result()
                        msadapter_new_files[name] = result
                        all_warnings.extend(warnings)
                        pbar.update(1)

    else:
        all_warnings = []
        all_warnings.extend(_convert_and_save_with_warnings(target, show_diff=True))
    
    if 'all_warnings' in locals() and all_warnings:
        with api_warning_lock:
            api_warning_list.clear()
            api_warning_list.extend(all_warnings)

    print(f"api_warning_list: {len(api_warning_list)}")
    if api_warning_list:
        pdf = pd.DataFrame(api_warning_list)
        pdf.rename(columns={"warning_type":"warning_type(0-error，1-warning)"}, inplace=True)

        if target.endswith(".zip"):
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                print(f"excel_bytes: {pdf.shape}")
                pdf.to_excel(writer, index=False)
            excel_bytes = excel_buffer.getvalue()
            print(f"excel_bytes: {len(excel_bytes)}")
            msadapter_new_files["msadapter_api_warning.xlsx"] = excel_bytes
            with open(MSADAPTER_API_DIR + "\\issues.json", 'rb') as f:  # 'rb' 表示二进制读取
                binary_data = f.read()
                msadapter_new_files["msadapter_precision_issues_config.json"] = excel_bytes

            zip_buffer = create_zip_in_memory(msadapter_new_files)
            with open('output\\output.zip', 'wb') as f:
                f.write(zip_buffer)
            excel_buffer.close()

        else:
            pdf.to_excel("api_warning.xlsx", index=False)
    
