"""
Mermaid 流程图生成器 - 从工作流代码解析并生成 Mermaid 流程图
"""
import re
from typing import Dict, List, Set, Tuple, Optional
from loguru import logger


class MermaidGenerator:
    """Mermaid 流程图生成器"""
    
    def __init__(self):
        self.node_types = {
            'start': 'Start',
            'end': 'End',
            'intent': 'IntentDetection',
            'llm': 'LLM',
            'tool': 'Tool',
            'questioner': 'Questioner',
            'code': 'Code',
            'condition': 'Condition',
            'loop': 'Loop',
        }
    
    def _extract_keyword_arg(self, params_str: str, arg_name: str) -> Optional[str]:
        """从参数字符串中提取关键字参数的值（支持字符串和变量名）"""
        # 首先尝试匹配字符串值: arg_name="value" 或 arg_name='value'
        str_pattern = rf'{re.escape(arg_name)}\s*=\s*(["\'])((?:(?!\1).|\\\1)*)\1'
        match = re.search(str_pattern, params_str)
        if match:
            return match.group(2)
        
        # 如果字符串匹配失败，尝试匹配变量名: arg_name=variable_name
        # 变量名通常是字母、数字、下划线的组合，不能以数字开头
        var_pattern = rf'{re.escape(arg_name)}\s*=\s*([a-zA-Z_][a-zA-Z0-9_]*)'
        match = re.search(var_pattern, params_str)
        if match:
            return match.group(1)
        
        return None
    
    def _extract_positional_arg(self, params_str: str, index: int) -> Optional[str]:
        """从参数字符串中提取位置参数的值（支持字符串和变量名）"""
        # 找到第 index 个参数（从0开始）
        # 简化版本：只处理前两个参数（节点ID和变量名），它们通常是简单的字符串或变量名
        parts = []
        paren_count = 0
        bracket_count = 0
        brace_count = 0
        in_str = False
        str_char = None
        current = ''
        i = 0
        
        while i < len(params_str) and len(parts) <= index + 1:
            char = params_str[i]
            
            if not in_str:
                if char in ['"', "'"]:
                    in_str = True
                    str_char = char
                    current += char
                elif char == '(':
                    paren_count += 1
                    current += char
                elif char == ')':
                    paren_count -= 1
                    current += char
                elif char == '[':
                    bracket_count += 1
                    current += char
                elif char == ']':
                    bracket_count -= 1
                    current += char
                elif char == '{':
                    brace_count += 1
                    current += char
                elif char == '}':
                    brace_count -= 1
                    current += char
                elif char == ',' and paren_count == 0 and bracket_count == 0 and brace_count == 0:
                    parts.append(current.strip())
                    current = ''
                else:
                    current += char
            else:
                current += char
                if char == str_char and (i == 0 or params_str[i-1] != '\\'):
                    in_str = False
                    str_char = None
            
            i += 1
        
        if current.strip():
            parts.append(current.strip())
        
        if index < len(parts):
            arg = parts[index]
            # 如果是字符串，提取内容
            str_match = re.match(r'^(["\'])(.*)\1$', arg)
            if str_match:
                return str_match.group(2)
            # 否则返回变量名（去除空格和可能的等号）
            arg = arg.strip()
            # 如果包含等号，可能是关键字参数，跳过
            if '=' in arg:
                return None
            return arg
        
        return None
    
    def parse_workflow_code(self, code: str) -> Dict[str, any]:
        """
        从工作流代码中解析节点和连接关系
        
        Args:
            code: workflow_builder.py 的代码内容
            
        Returns:
            包含节点和边的字典
        """
        nodes = []
        edges = []
        node_ids_set = set()  # 用于快速检查节点是否已存在
        var_to_node_id = {}  # 变量名到节点ID的映射
        
        # 第一步：解析所有节点（先解析所有节点，再解析连接）
        
        # 1. 解析 set_start_comp 调用（优先级最高，确保 start 节点存在）
        # 支持两种格式：
        # - 位置参数: flow.set_start_comp("node_id", variable_name, inputs_schema={...})
        # - 关键字参数: flow.set_start_comp(start_comp_id="node_id", component=variable_name, inputs_schema={...})
        start_pattern = r'flow\.set_start_comp\s*\('
        for match in re.finditer(start_pattern, code):
            start_pos = match.end()
            # 找到匹配的右括号
            paren_count = 1
            end_pos = -1
            in_double_quote = False
            in_single_quote = False
            i = 0
            remaining = code[start_pos:]
            while i < len(remaining) and paren_count > 0:
                char = remaining[i]
                if char == '"' and (i == 0 or remaining[i-1] != '\\'):
                    in_double_quote = not in_double_quote
                elif char == "'" and (i == 0 or remaining[i-1] != '\\'):
                    in_single_quote = not in_single_quote
                elif not in_double_quote and not in_single_quote:
                    if char == '(':
                        paren_count += 1
                    elif char == ')':
                        paren_count -= 1
                        if paren_count == 0:
                            end_pos = i
                            break
                i += 1
            
            if end_pos == -1:
                continue
            
            params_str = remaining[:end_pos]
            
            # 尝试关键字参数格式
            start_id = self._extract_keyword_arg(params_str, 'start_comp_id')
            start_var = self._extract_keyword_arg(params_str, 'component')
            
            # 如果关键字参数格式失败，尝试位置参数格式
            if not start_id:
                start_id = self._extract_positional_arg(params_str, 0)
            if not start_var:
                start_var = self._extract_positional_arg(params_str, 1)
            
            if start_id:
                if start_var:
                    var_to_node_id[start_var] = start_id
                if start_id not in node_ids_set:
                    nodes.append({
                        'id': start_id,
                        'label': 'Start',
                        'type': 'start'
                    })
                    node_ids_set.add(start_id)
        
        # 2. 解析 add_workflow_comp 调用，提取中间节点
        # 支持两种格式：
        # - 位置参数: flow.add_workflow_comp("node_id", variable_name, inputs_schema={...})
        # - 关键字参数: flow.add_workflow_comp(comp_id="node_id", workflow_comp=variable_name, inputs_schema={...})
        add_comp_pattern = r'flow\.add_workflow_comp\s*\('
        for match in re.finditer(add_comp_pattern, code):
            start_pos = match.end()
            # 找到匹配的右括号
            paren_count = 1
            end_pos = -1
            in_double_quote = False
            in_single_quote = False
            i = 0
            remaining = code[start_pos:]
            while i < len(remaining) and paren_count > 0:
                char = remaining[i]
                if char == '"' and (i == 0 or remaining[i-1] != '\\'):
                    in_double_quote = not in_double_quote
                elif char == "'" and (i == 0 or remaining[i-1] != '\\'):
                    in_single_quote = not in_single_quote
                elif not in_double_quote and not in_single_quote:
                    if char == '(':
                        paren_count += 1
                    elif char == ')':
                        paren_count -= 1
                        if paren_count == 0:
                            end_pos = i
                            break
                i += 1
            
            if end_pos == -1:
                continue
            
            params_str = remaining[:end_pos]
            
            # 尝试关键字参数格式
            node_id = self._extract_keyword_arg(params_str, 'comp_id')
            var_name = self._extract_keyword_arg(params_str, 'workflow_comp')
            
            # 如果关键字参数格式失败，尝试位置参数格式
            if not node_id:
                node_id = self._extract_positional_arg(params_str, 0)
            if not var_name:
                var_name = self._extract_positional_arg(params_str, 1)
            
            if node_id:
                if var_name:
                    var_to_node_id[var_name] = node_id
                if node_id not in node_ids_set:
                    nodes.append({
                        'id': node_id,
                        'label': self._format_node_label(node_id),
                        'type': self._infer_node_type(node_id, code)
                    })
                    node_ids_set.add(node_id)
        
        # 3. 解析 set_end_comp 调用（确保 end 节点存在）
        # 支持两种格式：
        # - 位置参数: flow.set_end_comp("node_id", variable_name, inputs_schema={...})
        # - 关键字参数: flow.set_end_comp(end_comp_id="node_id", component=variable_name, inputs_schema={...})
        end_pattern = r'flow\.set_end_comp\s*\('
        for match in re.finditer(end_pattern, code):
            start_pos = match.end()
            # 找到匹配的右括号
            paren_count = 1
            end_pos = -1
            in_double_quote = False
            in_single_quote = False
            i = 0
            remaining = code[start_pos:]
            while i < len(remaining) and paren_count > 0:
                char = remaining[i]
                if char == '"' and (i == 0 or remaining[i-1] != '\\'):
                    in_double_quote = not in_double_quote
                elif char == "'" and (i == 0 or remaining[i-1] != '\\'):
                    in_single_quote = not in_single_quote
                elif not in_double_quote and not in_single_quote:
                    if char == '(':
                        paren_count += 1
                    elif char == ')':
                        paren_count -= 1
                        if paren_count == 0:
                            end_pos = i
                            break
                i += 1
            
            if end_pos == -1:
                continue
            
            params_str = remaining[:end_pos]
            
            # 尝试关键字参数格式
            end_id = self._extract_keyword_arg(params_str, 'end_comp_id')
            end_var = self._extract_keyword_arg(params_str, 'component')
            
            # 如果关键字参数格式失败，尝试位置参数格式
            if not end_id:
                end_id = self._extract_positional_arg(params_str, 0)
            if not end_var:
                end_var = self._extract_positional_arg(params_str, 1)
            
            if end_id:
                if end_var:
                    var_to_node_id[end_var] = end_id
                if end_id not in node_ids_set:
                    nodes.append({
                        'id': end_id,
                        'label': 'End',
                        'type': 'end'
                    })
                    node_ids_set.add(end_id)
        
        # 第二步：解析 add_branch 分支关系
        # 格式: variable_name.add_branch("condition", ["target1", "target2"], "branch_name")
        # 或: variable_name.add_branch("condition", "target", "branch_name")
        
        # 使用更灵活的方法：先找到所有 add_branch 调用的位置，然后解析参数
        # 这样可以处理条件字符串中包含引号、变量引用等复杂情况
        
        # 查找所有 add_branch 调用
        add_branch_pattern = r'(\w+)\.add_branch\s*\('
        for match in re.finditer(add_branch_pattern, code):
            var_name = match.group(1)
            start_pos = match.end()
            
            # 通过变量名找到对应的节点ID
            source_node_id = var_to_node_id.get(var_name)
            if not source_node_id:
                # 如果变量名就是节点ID
                if var_name in node_ids_set:
                    source_node_id = var_name
                else:
                    continue
            
            # 从 add_branch( 开始，解析参数
            # 使用简单的字符串解析方法
            remaining = code[start_pos:]
            
            # 找到匹配的右括号（考虑字符串中的引号）
            paren_count = 1
            end_pos = -1
            in_double_quote = False
            in_single_quote = False
            i = 0
            while i < len(remaining) and paren_count > 0:
                char = remaining[i]
                if char == '"' and (i == 0 or remaining[i-1] != '\\'):
                    in_double_quote = not in_double_quote
                elif char == "'" and (i == 0 or remaining[i-1] != '\\'):
                    in_single_quote = not in_single_quote
                elif not in_double_quote and not in_single_quote:
                    if char == '(':
                        paren_count += 1
                    elif char == ')':
                        paren_count -= 1
                        if paren_count == 0:
                            end_pos = i
                            break
                i += 1
            
            if end_pos == -1:
                continue
            
            # 提取参数部分
            params_str = remaining[:end_pos].strip()
            
            # 解析参数：查找字符串和列表
            # 第一个参数：条件字符串
            # 第二个参数：目标列表或单个目标字符串
            # 第三个参数：分支名称字符串
            
            # 匹配第一个字符串参数（支持单引号和双引号）
            # 使用非贪婪匹配，匹配到第一个 ", 或 ', 
            first_str_match = re.search(r'(["\'])((?:(?!\1).|\\\1)*)\1', params_str)
            if not first_str_match:
                continue
            
            # 跳过第一个参数后的逗号
            after_first = params_str[first_str_match.end():].lstrip()
            if not after_first.startswith(','):
                continue
            after_first = after_first[1:].lstrip()
            
            # 匹配第二个参数：可能是列表 ["target1", "target2"] 或单个字符串 "target"
            targets = []
            branch_name = ''
            
            # 尝试匹配列表
            if after_first.startswith('['):
                # 找到匹配的 ]
                bracket_count = 1
                list_end = 1
                in_str = False
                str_char = None
                while list_end < len(after_first) and bracket_count > 0:
                    char = after_first[list_end]
                    if not in_str:
                        if char in ['"', "'"]:
                            in_str = True
                            str_char = char
                        elif char == '[':
                            bracket_count += 1
                        elif char == ']':
                            bracket_count -= 1
                            if bracket_count == 0:
                                break
                    else:
                        if char == str_char and (list_end == 0 or after_first[list_end-1] != '\\'):
                            in_str = False
                            str_char = None
                    list_end += 1
                
                if bracket_count == 0:
                    list_content = after_first[1:list_end]
                    # 解析列表内容
                    for t in list_content.split(','):
                        t = t.strip().strip('"\'')
                        if t:
                            targets.append(t)
                    after_second = after_first[list_end+1:].lstrip()
                else:
                    continue
            else:
                # 尝试匹配单个字符串
                str_match = re.match(r'(["\'])((?:(?!\1).|\\\1)*)\1', after_first)
                if str_match:
                    targets = [str_match.group(2)]
                    after_second = after_first[str_match.end():].lstrip()
                else:
                    continue
            
            # 跳过第二个参数后的逗号
            if after_second.startswith(','):
                after_second = after_second[1:].lstrip()
                # 匹配第三个参数：分支名称字符串
                branch_match = re.match(r'(["\'])((?:(?!\1).|\\\1)*)\1', after_second)
                if branch_match:
                    branch_name = branch_match.group(2)
            
            # 为每个目标节点创建从源节点的边
            for target in targets:
                target = target.strip()
                if target in node_ids_set:
                    # 避免重复添加相同的边
                    if not any(e['from'] == source_node_id and e['to'] == target for e in edges):
                        edges.append({
                            'from': source_node_id,
                            'to': target,
                            'label': branch_name if branch_name else ''
                        })
        
        # 第三步：解析显式连接关系（add_connection）
        # 格式: flow.add_connection("source", "target")
        connection_pattern = r'flow\.add_connection\s*\(\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']\s*\)'
        for match in re.finditer(connection_pattern, code):
            source = match.group(1)
            target = match.group(2)
            # 只添加存在的节点之间的连接
            if source in node_ids_set and target in node_ids_set:
                # 检查是否已经有从该源节点到目标节点的边（通过 add_branch 创建）
                has_branch_edge = any(e['from'] == source and e['to'] == target for e in edges)
                # 如果已经有分支边，则跳过 add_connection（分支边优先级更高）
                if not has_branch_edge:
                    # 避免重复添加相同的边
                    if not any(e['from'] == source and e['to'] == target for e in edges):
                        edges.append({
                            'from': source,
                            'to': target,
                            'label': ''
                        })
        
        # 第四步：如果没有显式连接，从 inputs_schema 推断连接关系
        if not edges:
            inferred_edges = self._infer_connections_from_inputs(code, nodes)
            # 过滤掉不存在的节点之间的连接
            for edge in inferred_edges:
                if edge['from'] in node_ids_set and edge['to'] in node_ids_set:
                    if not any(e['from'] == edge['from'] and e['to'] == edge['to'] for e in edges):
                        edges.append(edge)
        
        # 第五步：确保有 start 和 end 节点（如果代码中没有定义）
        if 'start' not in node_ids_set:
            nodes.insert(0, {'id': 'start', 'label': 'Start', 'type': 'start'})
            node_ids_set.add('start')
        if 'end' not in node_ids_set:
            nodes.append({'id': 'end', 'label': 'End', 'type': 'end'})
            node_ids_set.add('end')
        
        # 第六步：如果没有连接，创建默认的 start -> end 连接
        if not edges and len(nodes) >= 2:
            edges.append({'from': 'start', 'to': 'end', 'label': ''})
        
        logger.debug(f"解析到 {len(nodes)} 个节点，{len(edges)} 条边")
        logger.debug(f"节点列表: {[n['id'] for n in nodes]}")
        logger.debug(f"边列表: {[(e['from'], e['to']) for e in edges]}")
        
        return {
            'nodes': nodes,
            'edges': edges
        }
    
    def _infer_connections_from_inputs(self, code: str, nodes: List[Dict]) -> List[Dict]:
        """从 inputs_schema 推断连接关系"""
        edges = []
        node_ids = {n['id'] for n in nodes}
        
        # 查找 inputs_schema 中的变量引用
        # 格式: "${node_id.field}" 或 "${node_id}"
        input_pattern = r'\$\{([^}]+)\}'
        
        for node in nodes:
            node_id = node['id']
            # 查找该节点的定义（支持 add_workflow_comp, set_start_comp, set_end_comp）
            # 支持位置参数和关键字参数两种格式
            patterns = [
                # 位置参数格式
                rf'flow\.add_workflow_comp\s*\(\s*["\']{re.escape(node_id)}["\']',
                rf'flow\.set_start_comp\s*\(\s*["\']{re.escape(node_id)}["\']',
                rf'flow\.set_end_comp\s*\(\s*["\']{re.escape(node_id)}["\']',
                # 关键字参数格式
                rf'flow\.add_workflow_comp\s*\([^)]*comp_id\s*=\s*["\']{re.escape(node_id)}["\']',
                rf'flow\.set_start_comp\s*\([^)]*start_comp_id\s*=\s*["\']{re.escape(node_id)}["\']',
                rf'flow\.set_end_comp\s*\([^)]*end_comp_id\s*=\s*["\']{re.escape(node_id)}["\']'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, code)
                if match:
                    # 找到该节点定义的位置，提取后续的 inputs_schema
                    start_pos = match.end()
                    # 查找 inputs_schema 块（支持多行和嵌套大括号）
                    remaining_code = code[start_pos:start_pos+3000]
                    schema_start = remaining_code.find('inputs_schema')
                    if schema_start != -1:
                        # 找到第一个 {
                        brace_start = remaining_code.find('{', schema_start)
                        if brace_start != -1:
                            # 计算匹配的大括号
                            brace_count = 0
                            brace_end = -1
                            for i in range(brace_start, len(remaining_code)):
                                if remaining_code[i] == '{':
                                    brace_count += 1
                                elif remaining_code[i] == '}':
                                    brace_count -= 1
                                    if brace_count == 0:
                                        brace_end = i
                                        break
                            
                            if brace_end != -1:
                                schema_content = remaining_code[brace_start+1:brace_end]
                                # 提取所有变量引用
                                for var_match in re.finditer(input_pattern, schema_content):
                                    var_path = var_match.group(1)
                                    # 提取节点ID（第一个点之前的部分，如果没有点则整个都是节点ID）
                                    source_node = var_path.split('.')[0]
                                    if source_node in node_ids and source_node != node_id:
                                        # 避免重复添加
                                        if not any(e['from'] == source_node and e['to'] == node_id for e in edges):
                                            edges.append({
                                                'from': source_node,
                                                'to': node_id,
                                                'label': ''
                                            })
                    break  # 找到匹配就退出
        
        return edges
    
    def _infer_node_type(self, node_id: str, code: str) -> str:
        """从节点ID和代码推断节点类型"""
        node_id_lower = node_id.lower()
        
        # 根据节点ID命名推断类型
        if 'start' in node_id_lower:
            return 'start'
        elif 'end' in node_id_lower:
            return 'end'
        elif 'intent' in node_id_lower:
            return 'intent'
        elif 'llm' in node_id_lower or 'analyzer' in node_id_lower or 'generator' in node_id_lower or 'format' in node_id_lower:
            return 'llm'
        elif 'tool' in node_id_lower or 'search' in node_id_lower or 'api' in node_id_lower:
            return 'tool'
        elif 'question' in node_id_lower:
            return 'questioner'
        elif 'condition' in node_id_lower or 'branch' in node_id_lower:
            return 'condition'
        elif 'loop' in node_id_lower:
            return 'loop'
        else:
            return 'process'
    
    def _format_node_label(self, node_id: str) -> str:
        """格式化节点标签"""
        # 将 snake_case 转换为 Title Case
        label = node_id.replace('_', ' ').title()
        return label
    
    def _sanitize_node_id(self, node_id: str) -> str:
        """
        清理节点ID，避免使用 Mermaid 保留关键字
        
        Mermaid 保留关键字包括：end, class, style, click, linkStyle, etc.
        """
        # Mermaid 保留关键字列表
        reserved_keywords = {
            'end', 'class', 'style', 'click', 'linkStyle', 'subgraph',
            'direction', 'graph', 'flowchart', 'TD', 'LR', 'RL', 'BT'
        }
        
        # 如果节点ID是保留关键字，添加后缀
        if node_id.lower() in reserved_keywords:
            return f"{node_id}_node"
        
        return node_id
    
    def _filter_isolated_nodes(self, nodes: List[Dict], edges: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        过滤掉孤立节点（既没有入边也没有出边的节点）
        
        注意：start 和 end 节点即使只有一边的连接也会被保留
        
        Args:
            nodes: 节点列表
            edges: 边列表
            
        Returns:
            过滤后的节点列表和边列表
        """
        if not nodes:
            return nodes, edges
        
        # 收集所有有连接的节点ID（出现在边的 from 或 to 中）
        connected_node_ids = set()
        for edge in edges:
            connected_node_ids.add(edge['from'])
            connected_node_ids.add(edge['to'])
        
        # 识别孤立节点：既不在 connected_node_ids 中，也不是 start/end 节点
        node_ids_set = {node['id'] for node in nodes}
        isolated_node_ids = set()
        
        for node in nodes:
            node_id = node['id']
            node_type = node.get('type', 'process')
            
            # start 和 end 节点即使没有连接也保留（它们可能是工作流的入口/出口）
            if node_type in ['start', 'end']:
                continue
            
            # 如果节点既没有入边也没有出边，则认为是孤立的
            if node_id not in connected_node_ids:
                isolated_node_ids.add(node_id)
        
        # 如果没有孤立节点，直接返回
        if not isolated_node_ids:
            return nodes, edges
        
        # 过滤掉孤立节点
        filtered_nodes = [node for node in nodes if node['id'] not in isolated_node_ids]
        
        # 过滤掉与孤立节点相关的边（虽然理论上不应该有，但为了安全起见）
        filtered_edges = [
            edge for edge in edges 
            if edge['from'] not in isolated_node_ids and edge['to'] not in isolated_node_ids
        ]
        
        logger.debug(f"过滤掉 {len(isolated_node_ids)} 个孤立节点: {isolated_node_ids}")
        
        return filtered_nodes, filtered_edges
    
    def generate_mermaid(self, workflow_data: Dict[str, any]) -> str:
        """
        生成 Mermaid 流程图代码
        
        Args:
            workflow_data: 包含 nodes 和 edges 的字典
            
        Returns:
            Mermaid 流程图代码
        """
        nodes = workflow_data.get('nodes', [])
        edges = workflow_data.get('edges', [])
        
        # 过滤掉孤立节点
        nodes, edges = self._filter_isolated_nodes(nodes, edges)
        
        if not nodes:
            return "graph TD\n    Start[开始] --> End[结束]"
        
        lines = ["graph TD"]
        
        # 创建节点ID映射（原始ID -> 清理后的ID）
        node_id_map = {}
        for node in nodes:
            original_id = node['id']
            sanitized_id = self._sanitize_node_id(original_id)
            node_id_map[original_id] = sanitized_id
        
        # 生成节点定义
        for node in nodes:
            original_id = node['id']
            sanitized_id = node_id_map[original_id]
            label = node.get('label', original_id)
            node_type = node.get('type', 'process')
            
            # 根据节点类型选择不同的形状
            shape = self._get_node_shape(node_type, label)
            lines.append(f"    {sanitized_id}{shape}")
        
        # 生成连接（使用清理后的节点ID）
        for edge in edges:
            from_node = node_id_map.get(edge['from'], self._sanitize_node_id(edge['from']))
            to_node = node_id_map.get(edge['to'], self._sanitize_node_id(edge['to']))
            label = edge.get('label', '')
            
            if label:
                lines.append(f"    {from_node} -->|{label}| {to_node}")
            else:
                lines.append(f"    {from_node} --> {to_node}")
        
        return "\n".join(lines)
    
    def _get_node_shape(self, node_type: str, label: str) -> str:
        """根据节点类型返回 Mermaid 形状"""
        # 转义特殊字符，Mermaid 使用双引号
        label = label.replace('"', "'")
        
        if node_type == 'start':
            return f'["{label}"]'
        elif node_type == 'end':
            return f'["{label}"]'
        elif node_type == 'intent':
            return f'{{"{label}"}}'
        elif node_type == 'condition':
            return f'{{"{label}"}}'
        elif node_type == 'llm':
            return f'["{label}"]'
        elif node_type == 'tool':
            return f'["{label}"]'
        elif node_type == 'questioner':
            return f'["{label}"]'
        elif node_type == 'loop':
            return f'["{label}"]'
        else:
            return f'["{label}"]'
    
    def generate_from_code(self, code: str) -> str:
        """
        从工作流代码直接生成 Mermaid 流程图
        
        Args:
            code: workflow_builder.py 的代码内容
            
        Returns:
            Mermaid 流程图代码
        """
        try:
            workflow_data = self.parse_workflow_code(code)
            mermaid_code = self.generate_mermaid(workflow_data)
            return mermaid_code
        except Exception as e:
            logger.error(f"生成 Mermaid 流程图失败: {e}", exc_info=True)
            return "graph TD\n    Error[生成流程图失败]"
