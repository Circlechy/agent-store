import platform
import subprocess
import asyncio
import os
import uuid
import re
from typing import Dict, Any, List, Union

from openjiuwen.core.context_engine.base import Context
from openjiuwen.core.runtime.runtime import Runtime
from openjiuwen.core.component.base import WorkflowComponent
from openjiuwen.core.component.branch_router import BranchRouter
from openjiuwen.core.runtime.base import ComponentExecutable, Input, Output
from openjiuwen.core.component.llm_comp import LLMComponent, LLMCompConfig


os_type = platform.system().lower()


def detect_shell() -> str:
    if os_type == "windows":
        try:
            subprocess.run(["cmd", "/c", "echo 1"],
                           capture_output=True, check=True, timeout=5)
            return "cmd"
        except:
            try:
                subprocess.run(["powershell", "-Command", "echo 1"],
                               capture_output=True, check=True, timeout=5)
                return "powershell"
            except:
                return "cmd"
    else:
        try:
            subprocess.run(["bash", "-c", "echo 1"],
                           capture_output=True, check=True, timeout=5)
            return "bash"
        except:
            return "sh"


def prepare_command(command: Union[str, List[str]]) -> str:
    detected_shell = detect_shell()

    if isinstance(command, list):
        if detected_shell == "powershell":
            command = "; ".join(command)
        else:
            command = " && ".join(command)

    if detected_shell == "powershell":
        command = command.replace(" && ", "; ")
        return f'powershell -Command "{command}"'
    elif detected_shell == "cmd":
        return f'cmd /c "{command}"'
    elif detected_shell in ["bash", "sh"]:
        return f"{detected_shell} -c '{command}'"
    else:
        return f"{detected_shell} -c '{command}'"


class CreateEnvComponent(WorkflowComponent, ComponentExecutable):
    def __init__(self):
        super().__init__()
        self._router = BranchRouter()
    
    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        print("CreateEnvComponent invoked with inputs:", inputs)
        print("runtime debug_messages:", runtime.get_global_state("debug_messages"))
        
        if inputs.get('precommand') is not None and inputs['precommand']:
            print("Executing precommand:", inputs['precommand'])
            try:
                cmd = prepare_command(inputs['precommand'])
                subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            except subprocess.CalledProcessError as e:
                return {
                    "result": f"Failed!!!: {e.stderr.strip()}",
                    "env_name": inputs['env_name']
                }
        
        cmd = f"conda create -n {inputs['env_name']} {inputs['version']} -y && conda activate {inputs['env_name']} && python --version"
        prepared_cmd = prepare_command(cmd)
        try:
            print("Executing command:", prepared_cmd)
            result = subprocess.run(prepared_cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return {
                "result": result.stdout.strip(),
                "env_name": inputs['env_name']
            }
        except subprocess.CalledProcessError as e:
            return {
                "result": f"Failed!!!: {e.stderr.strip()}",
                "env_name": inputs['env_name']
            }


class BuildEnvComponent(WorkflowComponent, ComponentExecutable):
    def __init__(self):
        super().__init__()
        self._router = BranchRouter()
    
    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        try:
            result = []
            for cmd in inputs['commands']:
                full_cmd = f'conda activate {inputs["env_name"][0]} && {cmd}'
                prepared_cmd = prepare_command(full_cmd)
                print(f"Executing: {prepared_cmd}")
                result.append(subprocess.run(prepared_cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
            return {
                "result": "\n".join([r.stdout.strip() for r in result]),
                "env_name": inputs['env_name']
            }
        except subprocess.CalledProcessError as e:
            return {
                "result": f"Failed: {e.stderr.strip()}",
                "env_name": inputs['env_name']
            }


class FileScannerComponent(WorkflowComponent, ComponentExecutable):
    def __init__(self):
        super().__init__()
        self._router = BranchRouter()
    
    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        repo_path = inputs.get('repo_path')
        if not repo_path or not os.path.exists(repo_path):
             return {
                 "context": "Error: Repository path not found.",
                 "repo_name": "unknown_repo"
             }
        
        files = os.listdir(repo_path)
        priority_files = ['environment.yml', 'environment.yaml', 'requirements.txt', 'setup.py', 'pyproject.toml', 'README.md']
        
        context_str = f"Target Repository Path: {repo_path}\nFile List: {', '.join(files)}\n\n"
        found_config = False
        
        for f in priority_files:
            matching_files = [file for file in files if file.lower() == f.lower()]
            for match in matching_files:
                found_config = True
                path = os.path.join(repo_path, match)
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as file:
                        content = file.read(4000)
                        context_str += f"--- START OF FILE: {match} ---\n{content}\n--- END OF FILE: {match} ---\n\n"
                except Exception as e:
                    context_str += f"--- Error reading {match}: {str(e)} ---\n"
        
        if not found_config:
            context_str += "No standard configuration files (environment.yml, requirements.txt, setup.py) found.\n"
        
        repo_name = os.path.basename(os.path.normpath(repo_path))
        return {
            "context": context_str,
            "repo_name": repo_name
        }


class GitCloneComponent(WorkflowComponent, ComponentExecutable):
    def __init__(self):
        super().__init__()
        self._router = BranchRouter()
    
    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        repo_url = inputs.get('repo_url')
        target_dir = inputs.get('target_dir', '')

        if target_dir and os.path.exists(target_dir):
             return {
                "result": "Success",
                "output": f"Directory {target_dir} already exists.",
                "repo_url": repo_url
            }

        precommand = inputs.get('precommand')
        token = inputs.get('token')
        
        if precommand:
            print("Executing precommand:", precommand)
            try:
                prepared_precommand = prepare_command(precommand)
                subprocess.run(prepared_precommand, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            except subprocess.CalledProcessError as e:
                return {
                    "result": f"Failed!!!: Precommand error: {e.stderr.strip()}",
                    "repo_url": repo_url
                }

        final_repo_url = repo_url
        if token and repo_url.startswith("https://"):
            prefix = "https://"
            suffix = repo_url[len(prefix):]
            final_repo_url = f"{prefix}{token}@{suffix}"
            
        cmd = f"git clone {final_repo_url}"
        if target_dir:
            cmd += f" {target_dir}"
        
        prepared_cmd = prepare_command(cmd)
        log_cmd = prepared_cmd.replace(token, "******") if token else prepared_cmd
        print("Executing command:", log_cmd)
        
        try:
            result = subprocess.run(prepared_cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return {
                "result": "Success",
                "output": result.stdout.strip(),
                "repo_url": repo_url
            }
        except subprocess.CalledProcessError as e:
            return {
                "result": f"Failed!!!: {e.stderr.strip()}",
                "output": "",
                "repo_url": repo_url
            }


class RequirementScannerComponent(WorkflowComponent, ComponentExecutable):
    def __init__(self):
        super().__init__()
        self._router = BranchRouter()

    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        repo_path = inputs.get('repo_path')
        if not repo_path or not os.path.exists(repo_path):
            return {
                "requirements_context": "Error: Repository path not found or invalid.",
                "has_packages": False
            }

        packages = []
        
        req_path = os.path.join(repo_path, "requirements.txt")
        if os.path.exists(req_path):
            try:
                with open(req_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        packages.append(line)
            except Exception as e:
                print(f"Error parsing requirements.txt: {e}")

        env_path = os.path.join(repo_path, "environment.yml")
        if not os.path.exists(env_path):
            env_path = os.path.join(repo_path, "environment.yaml")
        
        if os.path.exists(env_path):
            try:
                in_dependencies = False
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        stripped = line.strip()
                        if stripped == "dependencies:":
                            in_dependencies = True
                            continue
                        
                        if in_dependencies and stripped.startswith("-"):
                            content = stripped[1:].strip()
                            if content.startswith("pip:"): 
                                continue
                            if ":" in content and not re.search(r"[=<>!~]", content):
                                continue
                            
                            packages.append(content)
            except Exception as e:
                print(f"Error parsing environment.yml: {e}")

        # Check setup.py for install_requires
        setup_py_path = os.path.join(repo_path, "setup.py")
        if os.path.exists(setup_py_path):
            try:
                with open(setup_py_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    import ast
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Call):
                            if isinstance(node.func, ast.Name) and node.func.id == "setup":
                                for keyword in node.keywords:
                                    if keyword.arg == "install_requires":
                                        if isinstance(keyword.value, ast.List):
                                            for elt in keyword.value.elts:
                                                if isinstance(elt, ast.Constant):
                                                    packages.append(elt.value)
            except Exception as e:
                print(f"Error parsing setup.py: {e}")

        # Check pyproject.toml for dependencies
        pyproject_path = os.path.join(repo_path, "pyproject.toml")
        if os.path.exists(pyproject_path):
            try:
                with open(pyproject_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    import toml
                    data = toml.loads(content)
                    if "project" in data and "dependencies" in data["project"]:
                        packages.extend(data["project"]["dependencies"])
                    elif "tool" in data and "poetry" in data["tool"] and "dependencies" in data["tool"]["poetry"]:
                        poetry_deps = data["tool"]["poetry"]["dependencies"]
                        for name, version in poetry_deps.items():
                            if name != "python":
                                version_str = version if isinstance(version, str) else f"^{version}"
                                packages.append(f"{name}{version_str}")
            except Exception as e:
                print(f"Error parsing pyproject.toml: {e}")

        # Check Pipfile for dependencies
        pipfile_path = os.path.join(repo_path, "Pipfile")
        if os.path.exists(pipfile_path):
            try:
                with open(pipfile_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    import toml
                    data = toml.loads(content)
                    if "packages" in data:
                        pipfile_packages = data["packages"]
                        for name, version in pipfile_packages.items():
                            if name != "python":
                                version_str = version if isinstance(version, str) else ""
                                if version_str and not version_str.startswith((">=", "<=", "!=", ">", "<", "===", "==", "~=", "^")):
                                    version_str = f"=={version_str}"
                                packages.append(f"{name}{version_str}")
            except Exception as e:
                print(f"Error parsing Pipfile: {e}")

        unique_packages = sorted(list(set(packages)))
        
        if not unique_packages:
            return {
                "requirements_context": "No requirements found in requirements.txt, environment.yml, setup.py, pyproject.toml, or Pipfile.",
                "has_packages": False
            }
        
        context_str = "Found the following packages/requirements in the repository:\n"
        context_str += "\n".join([f"- {p}" for p in unique_packages])
        
        return {
            "requirements_context": context_str,
            "has_packages": True
        }


class PythonEnvTestExecutor(WorkflowComponent, ComponentExecutable):
    def __init__(self):
        super().__init__()
        self._router = BranchRouter()

    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        env_name = inputs.get('env_name')
        script_content = inputs.get('script_content')
        repo_path = inputs.get('repo_path')

        if not env_name or not script_content:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Missing env_name or script_content"
            }
            
        filename = f"env_test_{uuid.uuid4().hex[:8]}.py"
        file_path = os.path.join(repo_path, filename) if repo_path else filename
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(script_content)
                
            cmd = ["conda", "run", "-n", env_name, "python", filename]
            cmd_str = " ".join(cmd)
            
            if repo_path and platform.system() == 'Windows':
                repo_path = repo_path.replace('\\', '/')

            cwd = repo_path if repo_path and os.path.exists(repo_path) else os.getcwd()
            

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)
            

            return {
                "success": process.returncode == 0,
                "stdout": stdout.decode('utf-8', errors='ignore'),
                "stderr": stderr.decode('utf-8', errors='ignore'),
                "executed_command": cmd_str
            }

        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Execution Error: {str(e)}",
                "executed_command": "generation_failed"
            }
        finally:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass


class CrossPlatformCommandExecutor(WorkflowComponent, ComponentExecutable):
    def __init__(self):
        super().__init__()
        self._router = BranchRouter()
        self.os_type = os_type
        self.timeout = 30
        self.working_dir = None
        self.env = {}

    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        command = inputs.get('command') or inputs.get('cmd')
        if not command:
            return {
                "success": False,
                "stdout": "",
                "stderr": "No command provided",
                "platform_info": f"os: {self.os_type}, shell: {detect_shell()}"
            }

        timeout = inputs.get('timeout', self.timeout)
        working_dir = inputs.get('working_dir', self.working_dir)
        env_override = inputs.get('env', {})
        env = {**os.environ, **self.env, **env_override}

        try:
            cmd = prepare_command(command)

            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
                env=env
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )

                return {
                    "success": process.returncode == 0,
                    "stdout": stdout.decode('utf-8', errors='ignore') if stdout else "",
                    "stderr": stderr.decode('utf-8', errors='ignore') if stderr else "",
                    "platform_info": f"os: {self.os_type}, shell: {detect_shell()}"
                }

            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Command timed out after {timeout} seconds",
                    "platform_info": f"os: {self.os_type}, shell: {detect_shell()}"
                }

        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Execution error: {str(e)}",
                "platform_info": f"os: {self.os_type}, shell: {detect_shell()}"
            }


class CondaEnvSaverComponent(WorkflowComponent, ComponentExecutable):
    def __init__(self):
        super().__init__()
        from openjiuwen.core.component.branch_router import BranchRouter
        self._router = BranchRouter()

    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        env_name = inputs.get('env_name')
        repo_path = inputs.get('repo_path')
        
        if not env_name:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Missing env_name",
                "export_file": None
            }
        
        try:
            env_dir = os.path.join(repo_path, "saved_environments") if repo_path else "saved_environments"
            os.makedirs(env_dir, exist_ok=True)
            
            import time
            timestamp = int(time.time())
            export_file = os.path.join(env_dir, f"{env_name}_{timestamp}.yml")
            
            cmd = ["conda", "env", "export", "-n", env_name]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
            
            if process.returncode == 0:
                with open(export_file, 'w', encoding='utf-8') as f:
                    f.write(stdout.decode('utf-8'))
                
                return {
                    "success": True,
                    "stdout": f"Environment '{env_name}' exported successfully to {export_file}",
                    "stderr": "",
                    "export_file": export_file,
                    "env_name": env_name
                }
            else:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": stderr.decode('utf-8', errors='ignore'),
                    "export_file": None
                }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Export Error: {str(e)}",
                "export_file": None
            }


class ReadmeScannerComponent(WorkflowComponent, ComponentExecutable):
    """扫描 README 文件并提取安装说明"""
    def __init__(self):
        super().__init__()
    
    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        repo_path = inputs.get('repo_path')
        print("\n" + "="*60)
        print("步骤 1: 扫描 README 文件")
        print("="*60)
        
        if not repo_path or not os.path.exists(repo_path):
            print(f"❌ 错误: 仓库路径不存在: {repo_path}")
            return {
                "context": "Error: Repository path not found.",
                "repo_name": "unknown_repo",
                "readme_found": False
            }
        
        files = os.listdir(repo_path)
        readme_files = ['README.md', 'README.txt', 'README.rst', 'README', 'readme.md', 'readme.txt']
        context_str = f"Target Repository Path: {repo_path}\nFile List: {', '.join(files)}\n\n"
        readme_found = False
        
        for readme_name in readme_files:
            matching_files = [file for file in files if file.lower() == readme_name.lower()]
            for match in matching_files:
                readme_found = True
                path = os.path.join(repo_path, match)
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as file:
                        full_content = file.read()  # 读取完整内容
                        
                        # 优先提取 Installation 部分
                        installation_section = ""
                        installation_keywords = ['## Installation', '### Installation', '## Getting Started', 
                                                '### Getting Started', '## Setup', '### Setup', 
                                                '## Quick Start', '### Quick Start']
                        
                        for keyword in installation_keywords:
                            idx = full_content.find(keyword)
                            if idx != -1:
                                end_idx = full_content.find('\n## ', idx + len(keyword))
                                end_idx = min(end_idx if end_idx != -1 else len(full_content), 
                                            idx + len(keyword) + 5000, len(full_content))
                                installation_section = full_content[idx:end_idx]
                                print(f"✅ 找到 Installation 部分 (关键词: {keyword})")
                                break
                        
                        # 如果找到了 Installation 部分，优先使用它；否则使用前 15000 字符
                        if installation_section:
                            context_str += f"--- START OF README FILE: {match} ---\n"
                            context_str += f"=== INSTALLATION SECTION (PRIORITY) ===\n{installation_section}\n"
                            context_str += f"=== ADDITIONAL CONTEXT (first 8000 chars) ===\n{full_content[:8000]}\n"
                            context_str += f"--- END OF README FILE: {match} ---\n"
                        else:
                            context_str += f"--- START OF README FILE: {match} ---\n{full_content[:15000]}\n"
                            context_str += f"--- END OF README FILE: {match} ---\n"
                            print(f"⚠️  未找到明确的 Installation 部分，使用前 15000 字符")
                    
                    print(f"✅ 找到 README 文件: {match}")
                except Exception as e:
                    context_str += f"--- Error reading {match}: {str(e)} ---\n"
                    print(f"❌ 读取 README 文件失败: {str(e)}")
                break  # 找到第一个就停止
        
        if not readme_found:
            context_str += "No README file found in the repository.\n"
            print("⚠️  未找到 README 文件")
        
        repo_name = os.path.basename(os.path.normpath(repo_path))
        print(f"仓库名称: {repo_name}")
        
        if readme_found:
            print("⏳ 正在调用 LLM 分析 README 文件并生成安装计划...")
        
        return {
            "context": context_str,
            "repo_name": repo_name,
            "readme_found": readme_found
        }


class PlanDisplayComponent(WorkflowComponent, ComponentExecutable):
    """显示 README planner 生成的 plan"""
    def __init__(self):
        super().__init__()
    
    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        env_name = inputs.get('env_name', '')
        version = inputs.get('version', '')
        args = inputs.get('args', '')
        
        print("\n" + "="*60)
        print("步骤 2: 基于 README 生成的 Plan (LLM 分析结果)")
        print("="*60)
        print(f"环境名称: {env_name}")
        print(f"Python 版本: {version}")
        print(f"安装命令: {args}")
        
        return {
            "env_name": env_name,
            "version": version,
            "args": args
        }


class PlanValidatorAndFallbackComponent(WorkflowComponent, ComponentExecutable):
    """验证 plan 是否有效，如果无效则执行回退到配置文件逻辑（使用LLM生成）"""
    def __init__(self, config_llm_comp_config: LLMCompConfig):
        super().__init__()
        self._config_llm_comp = LLMComponent(config_llm_comp_config)
    
    async def _scan_config_files(self, repo_path: str) -> tuple[str, str]:
        if not repo_path or not os.path.exists(repo_path):
            return "Error: Repository path not found.", "unknown_repo"
        
        files = os.listdir(repo_path)
        priority_files = ['environment.yml', 'environment.yaml', 'requirements.txt', 'setup.py', 'pyproject.toml']
        
        context_str = f"Target Repository Path: {repo_path}\nFile List: {', '.join(files)}\n\n"
        found_config = False
        
        for f in priority_files:
            matching_files = [file for file in files if file.lower() == f.lower()]
            for match in matching_files:
                found_config = True
                path = os.path.join(repo_path, match)
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as file:
                        content = file.read(4000)
                        context_str += f"--- START OF FILE: {match} ---\n{content}\n--- END OF FILE: {match} ---\n\n"
                except Exception as e:
                    context_str += f"--- Error reading {match}: {str(e)} ---\n"
        
        if not found_config:
            context_str += "No standard configuration files (environment.yml, requirements.txt, setup.py) found.\n"
        
        repo_name = os.path.basename(os.path.normpath(repo_path))
        return context_str, repo_name
    
    async def _generate_config_based_plan_with_llm(self, config_context: str, repo_name: str, runtime: Runtime, context: Context) -> dict:
        """使用LLM基于配置文件生成plan"""
        llm_inputs = Input({
            "context": config_context,
            "repo_name": repo_name
        })
        llm_output = await self._config_llm_comp.invoke(llm_inputs, runtime, context)
        return {
            "env_name": llm_output.get("env_name", ""),
            "version": llm_output.get("version", ""),
            "args": llm_output.get("args", "")
        }
    
    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        env_name = inputs.get('env_name', '')
        version = inputs.get('version', '')
        args = inputs.get('args', '')
        repo_path = inputs.get('repo_path', '')
        repo_name = inputs.get('repo_name', '')
        
        has_plan = bool(env_name and version and args)
        
        if has_plan:
            return {
                "env_name": env_name,
                "version": version,
                "args": args,
                "is_valid": True,
            }
        else:
            # Plan 未生成（字段缺失），执行回退逻辑：扫描配置文件并生成新的 plan
            print("⚠️  README 未生成完整 Plan，执行回退逻辑...")
            print("\n" + "="*60)
            print("步骤 4: 回退 - 扫描配置文件")
            print("="*60)
            
            config_context, config_repo_name = await self._scan_config_files(repo_path)
            
            # 检查找到了哪些配置文件
            found_files = []
            if 'environment.yml' in config_context or 'environment.yaml' in config_context:
                found_files.append("environment.yml/yaml")
            if 'requirements.txt' in config_context:
                found_files.append("requirements.txt")
            if 'setup.py' in config_context:
                found_files.append("setup.py")
            if 'pyproject.toml' in config_context:
                found_files.append("pyproject.toml")
            
            if found_files:
                print(f"✅ 找到配置文件: {', '.join(found_files)}")
            else:
                print("⚠️  未找到标准配置文件")
            
            print("⏳ 正在调用 LLM 分析配置文件并生成安装计划...")
            
            print("\n" + "="*60)
            print("步骤 5: 基于配置文件生成 Plan (LLM 分析)")
            print("="*60)
            fallback_plan = await self._generate_config_based_plan_with_llm(
                config_context, config_repo_name or repo_name, runtime, context
            )
            
            print(f"环境名称: {fallback_plan['env_name']}")
            print(f"Python 版本: {fallback_plan['version']}")
            print(f"安装命令: {fallback_plan['args']}")
            
            print(f"✅ 最终 Plan 来源: 配置文件 (LLM生成)")
            
            return {
                "env_name": fallback_plan["env_name"],
                "version": fallback_plan["version"],
                "args": fallback_plan["args"],
                "is_valid": True,
            }
