"""文件操作工具定义"""

import subprocess
import platform
import zipfile
import shutil
from pathlib import Path
from typing import Optional, List
from openjiuwen.core.utils.tool.function.function import LocalFunction
from openjiuwen.core.utils.tool.param import Param


def _read_file(file_path: str, **kwargs) -> str:
    """读取文件内容。
    
    Args:
        file_path: 要读取的文件路径（相对或绝对路径）
        **kwargs: 接受额外的关键字参数（忽略未使用的参数）
        
    Returns:
        文件内容的字符串
        
    Raises:
        FileNotFoundError: 如果文件不存在
        PermissionError: 如果没有读取权限
    """
    try:
        # 自动去除路径中的反引号（如果存在）
        if file_path.startswith('`') and file_path.endswith('`'):
            file_path = file_path[1:-1]
        
        path = Path(file_path)
        if not path.exists():
            return f"错误: 文件 '{file_path}' 不存在"
        if not path.is_file():
            return f"错误: '{file_path}' 不是一个文件"
        return path.read_text(encoding='utf-8')
    except PermissionError:
        return f"错误: 没有权限读取文件 '{file_path}'"
    except Exception as e:
        return f"错误: 读取文件时发生异常 - {str(e)}"

read_file = LocalFunction(
    name="read_file",
    description="读取文件内容。⚠️⚠️⚠️ 警告：file_path 参数必须使用 list_directory 输出的反引号内的完整文件名，逐字符完全复制，禁止任何修改、理解或纠正文件名。文件名是文件系统标识符，不是可理解的文本。",
    params=[
        Param(
            name="file_path",
            description="要读取的文件路径（相对或绝对路径）",
            param_type="string",
            required=True
        )
    ],
    func=_read_file
)


def _write_file(file_path: str, content: str, append: bool = False, **kwargs) -> str:
    """写入文件内容。
    
    Args:
        file_path: 要写入的文件路径（相对或绝对路径）
        content: 要写入的内容
        append: 如果为 True，追加到文件末尾；否则覆盖文件
        **kwargs: 接受额外的关键字参数（忽略未使用的参数）
        
    Returns:
        操作结果消息
    """
    try:
        path = Path(file_path)
        # 确保父目录存在
        path.parent.mkdir(parents=True, exist_ok=True)
        
        if append:
            with path.open('a', encoding='utf-8') as f:
                f.write(content)
            return f"成功: 内容已追加到文件 '{file_path}'"
        else:
            path.write_text(content, encoding='utf-8')
            return f"成功: 内容已写入文件 '{file_path}'"
    except PermissionError:
        return f"错误: 没有权限写入文件 '{file_path}'"
    except Exception as e:
        return f"错误: 写入文件时发生异常 - {str(e)}"

write_file = LocalFunction(
    name="write_file",
    description="写入文件内容",
    params=[
        Param(
            name="file_path",
            description="要写入的文件路径（相对或绝对路径）",
            param_type="string",
            required=True
        ),
        Param(
            name="content",
            description="要写入的内容",
            param_type="string",
            required=True
        ),
        Param(
            name="append",
            description="如果为 True，追加到文件末尾；否则覆盖文件",
            param_type="boolean",
            default_value=False,
            required=False
        )
    ],
    func=_write_file
)


def _list_directory(directory_path: str = ".", **kwargs) -> str:
    """列出目录内容，包括文件名、类型和扩展名等信息，便于分类。
    
    Args:
        directory_path: 要列出的目录路径（默认为当前目录）
        **kwargs: 接受额外的关键字参数（忽略未使用的参数）
        
    Returns:
        目录内容的格式化字符串，包含文件名、类型、扩展名等信息
    """
    try:
        path = Path(directory_path)
        if not path.exists():
            return f"错误: 目录 '{directory_path}' 不存在"
        if not path.is_dir():
            return f"错误: '{directory_path}' 不是一个目录"
        
        items = []
        files = []
        dirs = []
        
        for item in sorted(path.iterdir()):
            if item.is_dir():
                dirs.append(item.name)
            else:
                files.append(item.name)
        
        # 先列出目录，再列出文件
        if dirs:
            items.append(f"\n【目录】(共 {len(dirs)} 个):")
            for dir_name in dirs:
                items.append(f"  📁 {dir_name}")
        
        if files:
            items.append(f"\n【文件】(共 {len(files)} 个):")
            items.append("=" * 60)
            items.append("⚠️⚠️⚠️ 警告：路径和文件名是精确数据，必须逐字符完全复制！⚠️⚠️⚠️")
            items.append("=" * 60)
            # 获取目录的绝对路径用于构建完整路径
            base_path = str(path.resolve())
            for idx, file_name in enumerate(files, 1):
                file_path = path / file_name
                ext = file_path.suffix.lower() if file_path.suffix else "无扩展名"
                size = file_path.stat().st_size
                size_str = f"{size / 1024:.1f} KB" if size < 1024 * 1024 else f"{size / (1024 * 1024):.1f} MB"
                # 构建完整路径
                full_path = str(file_path.resolve())
                # Windows 路径使用反斜杠，统一转换为正斜杠或保持原样（Path.resolve() 返回的是系统格式）
                # 为了兼容性，使用 Path.as_posix() 转换为正斜杠，但 Windows 也支持
                full_path_posix = file_path.resolve().as_posix()
                items.append(f"[文件#{idx}] 类型: {ext}, 大小: {size_str}")
                items.append(f"  文件名: `{file_name}`")
                items.append(f"  完整路径(精确复制，禁止修改): `{full_path}`")
                items.append("")  # 空行分隔
        
        if not items:
            return f"目录 '{directory_path}' 为空"
        
        result = f"目录 '{directory_path}' 的内容:"
        result += "\n".join(items)
        return result
    except PermissionError:
        return f"错误: 没有权限访问目录 '{directory_path}'"
    except Exception as e:
        return f"错误: 列出目录时发生异常 - {str(e)}"

list_directory = LocalFunction(
    name="list_directory",
    description="列出目录内容，包括文件名、类型、扩展名和大小等信息。这是分析目录结构、识别文件类型和进行分类的第一步。⚠️⚠️⚠️ 警告：输出的文件名（反引号内的内容）是精确的文件系统标识符，必须逐字符完全复制使用，禁止任何修改、理解或纠正。",
    params=[
        Param(
            name="directory_path",
            description="要列出的目录路径（默认为当前目录）",
            param_type="string",
            default_value=".",
            required=False
        )
    ],
    func=_list_directory
)


def _create_directory(directory_path: str, **kwargs) -> str:
    """创建目录。
    
    Args:
        directory_path: 要创建的目录路径（必需）
        **kwargs: 接受额外的关键字参数（忽略未使用的参数）
        
    Returns:
        操作结果消息
    """
    if not directory_path or directory_path.strip() == "":
        return "错误: 创建目录时必须提供 directory_path 参数"
    
    try:
        path = Path(directory_path)
        path.mkdir(parents=True, exist_ok=True)
        if path.exists():
            return f"成功: 目录 '{directory_path}' 已创建或已存在"
        else:
            return f"错误: 无法创建目录 '{directory_path}'"
    except PermissionError:
        return f"错误: 没有权限创建目录 '{directory_path}'"
    except Exception as e:
        return f"错误: 创建目录时发生异常 - {str(e)}"

create_directory = LocalFunction(
    name="create_directory",
    description="创建目录",
    params=[
        Param(
            name="directory_path",
            description="要创建的目录路径",
            param_type="string",
            required=True
        )
    ],
    func=_create_directory
)


def _delete_file(file_path: str, **kwargs) -> str:
    """删除文件。
    
    Args:
        file_path: 要删除的文件路径
        **kwargs: 接受额外的关键字参数（忽略未使用的参数）
        
    Returns:
        操作结果消息
    """
    try:
        # 自动去除路径中的反引号（如果存在）
        if file_path.startswith('`') and file_path.endswith('`'):
            file_path = file_path[1:-1]
        
        path = Path(file_path)
        if not path.exists():
            return f"错误: 文件 '{file_path}' 不存在"
        if path.is_dir():
            return f"错误: '{file_path}' 是一个目录，请使用删除目录工具"
        
        path.unlink()
        return f"成功: 文件 '{file_path}' 已删除"
    except PermissionError:
        return f"错误: 没有权限删除文件 '{file_path}'"
    except Exception as e:
        return f"错误: 删除文件时发生异常 - {str(e)}"

delete_file = LocalFunction(
    name="delete_file",
    description="删除文件。⚠️⚠️⚠️ 警告：file_path 参数必须使用 list_directory 输出的反引号内的完整文件名，逐字符完全复制，禁止任何修改、理解或纠正文件名。文件名是文件系统标识符，不是可理解的文本。",
    params=[
        Param(
            name="file_path",
            description="要删除的文件路径",
            param_type="string",
            required=True
        )
    ],
    func=_delete_file
)


def _move_file(source_path: str, destination_path: str, **kwargs) -> str:
    """移动文件或目录。
    
    使用 Python 的 shutil.move，可以正确处理包含中文字符的路径，
    并且在 Windows 和 Linux 上都能正常工作。
    
    Args:
        source_path: 源文件或目录路径
        destination_path: 目标路径
        **kwargs: 接受额外的关键字参数（忽略未使用的参数）
        
    Returns:
        操作结果消息
    """
    try:
        # 自动去除路径中的反引号（如果存在）
        # 这是为了防止 Agent 在复制 list_directory 输出时误包含反引号
        if source_path.startswith('`') and source_path.endswith('`'):
            source_path = source_path[1:-1]
        if destination_path.startswith('`') and destination_path.endswith('`'):
            destination_path = destination_path[1:-1]
        
        source = Path(source_path)
        destination = Path(destination_path)
        
        # 检查源路径是否存在
        if not source.exists():
            return f"错误: 源路径 '{source_path}' 不存在"
        
        # 确保目标目录的父目录存在
        if destination.suffix or not destination.exists():
            # 如果目标有扩展名或不存在，说明目标是文件
            destination.parent.mkdir(parents=True, exist_ok=True)
        else:
            # 目标是目录
            destination.mkdir(parents=True, exist_ok=True)
        
        # 使用 shutil.move 移动文件或目录
        # shutil.move 可以正确处理跨文件系统移动
        shutil.move(str(source), str(destination))
        
        return f"成功: '{source_path}' 已移动到 '{destination_path}'"
    except PermissionError:
        return f"错误: 没有权限移动文件或目录 '{source_path}' 到 '{destination_path}'"
    except shutil.Error as e:
        return f"错误: 移动文件时发生异常 - {str(e)}"
    except Exception as e:
        return f"错误: 移动文件时发生异常 - {str(e)}"

move_file = LocalFunction(
    name="move_file",
    description="移动文件或目录到新位置。可以正确处理包含中文字符的路径，适用于 Windows 和 Linux 系统。用于将文件分类整理到对应的目录中。⚠️⚠️⚠️ 警告：1) source_path 和 destination_path 参数必须使用 list_directory 输出的完整路径，但要去掉反引号字符（`），路径参数中不能包含反引号；2) 路径必须逐字符完全复制，禁止任何修改、理解或纠正文件名。文件名是文件系统标识符，不是可理解的文本。",
    params=[
        Param(
            name="source_path",
            description="要移动的源文件或目录路径（相对或绝对路径）",
            param_type="string",
            required=True
        ),
        Param(
            name="destination_path",
            description="目标路径（相对或绝对路径）。如果目标路径是目录，文件将被移动到该目录下；如果目标路径是文件，文件将被重命名并移动到该位置",
            param_type="string",
            required=True
        )
    ],
    func=_move_file
)


def _execute_command(command: str, working_directory: Optional[str] = None, **kwargs) -> str:
    """执行 bash/shell 命令。
    
    Args:
        command: 要执行的命令（可以是单个命令或命令序列，用 && 或 ; 分隔）
        working_directory: 执行命令的工作目录（默认为当前目录）
        **kwargs: 接受额外的关键字参数（忽略未使用的参数）
        
    Returns:
        命令执行结果（标准输出和标准错误）
    """
    try:
        # 确定使用哪个 shell
        if platform.system() == "Windows":
            shell = True
            # Windows 使用 cmd 或 PowerShell
            shell_executable = "cmd.exe"
        else:
            shell = True
            shell_executable = "/bin/bash"
        
        # 设置工作目录
        cwd = working_directory if working_directory else None
        
        try:
            # 执行命令
            result = subprocess.run(
                command,
                shell=shell,
                executable=shell_executable if platform.system() != "Windows" else None,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                cwd=cwd,
                timeout=60  # 60秒超时
            )
            
            output_parts = []
            
            # 添加返回码信息
            if result.returncode == 0:
                output_parts.append("命令执行成功")
            else:
                output_parts.append(f"命令执行失败，返回码: {result.returncode}")
            
            # 添加标准输出
            if result.stdout:
                output_parts.append(f"\n标准输出:\n{result.stdout}")
            
            # 添加标准错误（如果有）
            if result.stderr:
                output_parts.append(f"\n标准错误:\n{result.stderr}")
            
            # 如果没有任何输出
            if not result.stdout and not result.stderr:
                output_parts.append("\n（命令执行完成，无输出）")
            
            return "\n".join(output_parts)
            
        except subprocess.TimeoutExpired:
            return "错误: 命令执行超时（超过60秒）"
        except Exception as e:
            return f"错误: 执行命令时发生异常 - {str(e)}"
    
    except Exception as e:
        return f"错误: 准备执行命令时发生异常 - {str(e)}"

execute_command = LocalFunction(
    name="execute_command",
    description="执行 bash/shell 命令。可以执行系统命令、脚本、程序等。在 Windows 上执行 cmd 命令，在 Linux/Mac 上执行 bash 命令。注意：如果要在 Windows 上移动包含中文字符的文件，建议使用 move_file 工具而不是 bash 命令。",
    params=[
        Param(
            name="command",
            description="要执行的命令。可以是单个命令（如 'ls'、'dir'、'python script.py'）或命令序列（用 && 或 ; 分隔，如 'cd /path && ls'）。",
            param_type="string",
            required=True
        ),
        Param(
            name="working_directory",
            description="执行命令的工作目录（可选，默认为当前目录）",
            param_type="string",
            required=False
        )
    ],
    func=_execute_command
)


def _compress_directory(directory_path: str, output_path: Optional[str] = None, **kwargs) -> str:
    """压缩文件夹为 ZIP 文件。
    
    Args:
        directory_path: 要压缩的文件夹路径（相对或绝对路径）
        output_path: 输出的 ZIP 文件路径（可选，默认为文件夹名.zip）
        **kwargs: 接受额外的关键字参数（忽略未使用的参数）
        
    Returns:
        操作结果消息
    """
    try:
        dir_path = Path(directory_path)
        if not dir_path.exists():
            return f"错误: 目录 '{directory_path}' 不存在"
        if not dir_path.is_dir():
            return f"错误: '{directory_path}' 不是一个目录"
        
        # 如果没有指定输出路径，使用默认路径
        if output_path is None:
            output_path = str(dir_path) + ".zip"
        
        zip_path = Path(output_path)
        
        # 确保输出目录存在
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 创建 ZIP 文件
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 遍历目录中的所有文件
            for file_path in dir_path.rglob('*'):
                if file_path.is_file():
                    # 计算相对路径（相对于要压缩的目录）
                    arcname = file_path.relative_to(dir_path)
                    zipf.write(file_path, arcname)
        
        # 获取压缩文件大小
        zip_size = zip_path.stat().st_size
        size_mb = zip_size / (1024 * 1024)
        
        return f"成功: 目录 '{directory_path}' 已压缩为 '{output_path}' (大小: {size_mb:.2f} MB)"
    except PermissionError:
        return f"错误: 没有权限压缩目录 '{directory_path}' 或写入文件 '{output_path}'"
    except zipfile.BadZipFile:
        return f"错误: 无法创建 ZIP 文件 '{output_path}'"
    except Exception as e:
        return f"错误: 压缩目录时发生异常 - {str(e)}"

compress_directory = LocalFunction(
    name="compress_directory",
    description="压缩文件夹为 ZIP 文件",
    params=[
        Param(
            name="directory_path",
            description="要压缩的文件夹路径（相对或绝对路径）",
            param_type="string",
            required=True
        ),
        Param(
            name="output_path",
            description="输出的 ZIP 文件路径（可选，默认为文件夹名.zip）",
            param_type="string",
            required=False
        )
    ],
    func=_compress_directory
)


def _read_directory_files(directory_path: str, file_extensions: Optional[str] = None, max_file_size_kb: int = 1024, **kwargs) -> str:
    """读取目录中所有文件的内容，用于分析和总结。
    
    此工具会读取目录及其子目录中的所有文本文件（如 .txt, .md, .py, .json 等），
    返回文件路径和内容的汇总，便于后续生成总结。
    
    Args:
        directory_path: 要读取的目录路径
        file_extensions: 要读取的文件扩展名（逗号分隔，如 ".txt,.md,.py"，默认读取所有文本文件）
        max_file_size_kb: 单个文件的最大大小（KB），超过此大小的文件会被跳过（默认 1024 KB = 1MB）
        **kwargs: 接受额外的关键字参数（忽略未使用的参数）
        
    Returns:
        包含所有文件路径和内容的汇总字符串
    """
    try:
        path = Path(directory_path)
        if not path.exists():
            return f"错误: 目录 '{directory_path}' 不存在"
        if not path.is_dir():
            return f"错误: '{directory_path}' 不是一个目录"
        
        # 解析文件扩展名列表
        extensions = None
        if file_extensions:
            extensions = [ext.strip().lower() for ext in file_extensions.split(',')]
        
        # 常见的文本文件扩展名
        default_text_extensions = {
            '.txt', '.md', '.markdown', '.py', '.js', '.java', '.cpp', '.c', '.h',
            '.json', '.xml', '.yaml', '.yml', '.csv', '.html', '.css', '.sql',
            '.sh', '.bat', '.ps1', '.log', '.ini', '.cfg', '.conf', '.properties'
        }
        
        files_content = []
        skipped_files = []
        total_files = 0
        total_size = 0
        
        # 递归遍历目录
        for file_path in path.rglob('*'):
            if not file_path.is_file():
                continue
            
            total_files += 1
            
            # 检查文件扩展名
            ext = file_path.suffix.lower()
            if extensions:
                if ext not in extensions:
                    continue
            else:
                # 如果没有指定扩展名，只读取文本文件
                if ext and ext not in default_text_extensions:
                    skipped_files.append((file_path.name, f"非文本文件扩展名: {ext}"))
                    continue
            
            # 检查文件大小
            try:
                file_size = file_path.stat().st_size
                file_size_kb = file_size / 1024
                if file_size_kb > max_file_size_kb:
                    skipped_files.append((file_path.name, f"文件太大: {file_size_kb:.1f} KB"))
                    continue
                
                total_size += file_size
                
                # 尝试读取文件内容
                try:
                    content = file_path.read_text(encoding='utf-8')
                    relative_path = file_path.relative_to(path)
                    files_content.append({
                        'path': str(relative_path),
                        'full_path': str(file_path.resolve()),
                        'size': file_size_kb,
                        'content': content
                    })
                except UnicodeDecodeError:
                    skipped_files.append((file_path.name, "无法解码为 UTF-8 文本"))
                except Exception as e:
                    skipped_files.append((file_path.name, f"读取错误: {str(e)}"))
            except Exception as e:
                skipped_files.append((file_path.name, f"获取文件信息失败: {str(e)}"))
        
        # 构建返回结果
        result_parts = []
        result_parts.append(f"目录 '{directory_path}' 的文件内容汇总：")
        result_parts.append(f"总共扫描文件: {total_files} 个")
        result_parts.append(f"成功读取: {len(files_content)} 个文件（总大小: {total_size/1024:.1f} KB）")
        if skipped_files:
            result_parts.append(f"跳过文件: {len(skipped_files)} 个")
        
        result_parts.append("\n" + "=" * 80)
        result_parts.append("文件内容列表：")
        result_parts.append("=" * 80)
        
        for idx, file_info in enumerate(files_content, 1):
            result_parts.append(f"\n[文件 #{idx}] 路径: {file_info['path']}")
            result_parts.append(f"完整路径: {file_info['full_path']}")
            result_parts.append(f"大小: {file_info['size']:.1f} KB")
            result_parts.append(f"内容预览（前500字符）: {file_info['content'][:500]}...")
            result_parts.append("-" * 80)
        
        # 添加完整内容部分（用于总结）
        result_parts.append("\n" + "=" * 80)
        result_parts.append("完整文件内容（用于生成总结）：")
        result_parts.append("=" * 80)
        
        for file_info in files_content:
            result_parts.append(f"\n\n文件: {file_info['path']}")
            result_parts.append(f"路径: {file_info['full_path']}")
            result_parts.append("-" * 80)
            result_parts.append(file_info['content'])
            result_parts.append("=" * 80)
        
        if skipped_files:
            result_parts.append("\n跳过的文件：")
            for file_name, reason in skipped_files[:10]:  # 只显示前10个
                result_parts.append(f"  - {file_name}: {reason}")
            if len(skipped_files) > 10:
                result_parts.append(f"  ... 还有 {len(skipped_files) - 10} 个文件被跳过")
        
        return "\n".join(result_parts)
        
    except PermissionError:
        return f"错误: 没有权限访问目录 '{directory_path}'"
    except Exception as e:
        return f"错误: 读取目录文件时发生异常 - {str(e)}"

read_directory_files = LocalFunction(
    name="read_directory_files",
    description="读取目录中所有文本文件的内容，用于分析和总结。此工具会递归读取目录及子目录中的所有文本文件（如 .txt, .md, .py, .json 等），返回文件路径和内容的汇总。适用于需要分析整个目录内容并生成总结的场景。",
    params=[
        Param(
            name="directory_path",
            description="要读取的目录路径（相对或绝对路径）",
            param_type="string",
            required=True
        ),
        Param(
            name="file_extensions",
            description="要读取的文件扩展名（逗号分隔，如 '.txt,.md,.py'）。如果不指定，默认读取所有常见的文本文件类型。",
            param_type="string",
            required=False
        ),
        Param(
            name="max_file_size_kb",
            description="单个文件的最大大小（KB），超过此大小的文件会被跳过（默认 1024 KB = 1MB）",
            param_type="integer",
            default_value=1024,
            required=False
        )
    ],
    func=_read_directory_files
)


def get_tools():
    """获取所有工具列表。
    
    Returns:
        工具列表
    """
    return [
        read_file,
        write_file,
        list_directory,
        create_directory,
        delete_file,
        move_file,
        execute_command,
        compress_directory,
        read_directory_files,
    ]
