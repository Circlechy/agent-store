import unittest
import os
import sys
import json
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

# 导入被测试的模块
from examples.deepcode_agent.tools.code_reference_indexer import (
    search_code_references,
    get_indexes_overview,
    load_index_files_from_directory,
    extract_code_references,
    extract_relationships,
    calculate_relevance_score,
    find_relevant_references_in_cache,
    find_direct_relationships_in_cache,
    format_reference_output,
    CodeReference,
    RelationshipInfo
)


class TestCodeReferenceIndexer(unittest.TestCase):
    """
    测试代码引用索引器的功能
    """

    def setUp(self):
        """设置测试环境"""
        self.test_dir = os.path.dirname(os.path.abspath(__file__))
        self.mock_indexes_dir = os.path.join(self.test_dir, "mock_indexes")
        self.target_file = "test_implementation.py"

        # 创建必要的目录
        if not os.path.exists(self.mock_indexes_dir):
            os.makedirs(self.mock_indexes_dir)

        # 创建模拟索引文件
        self.mock_index_file_path = os.path.join(self.mock_indexes_dir, "mock_repo_index.json")
        self._create_mock_index_file()

    def _create_mock_index_file(self):
        """创建模拟的索引文件"""
        mock_index_data = {
            "repo_name": "mock_repo",
            "total_files": 2,
            "file_summaries": [
                {
                    "file_path": "src/implementation.py",
                    "file_type": "Python module",
                    "main_functions": ["process_data", "analyze_results"],
                    "key_concepts": ["data processing", "analysis"],
                    "dependencies": ["numpy", "pandas"],
                    "summary": "Implementation of data processing functionality",
                    "lines_of_code": 100
                },
                {
                    "file_path": "src/utils.py",
                    "file_type": "Python module",
                    "main_functions": ["helper_function"],
                    "key_concepts": ["utility"],
                    "dependencies": [],
                    "summary": "Utility functions",
                    "lines_of_code": 50
                }
            ],
            "relationships": [
                {
                    "repo_file_path": "src/implementation.py",
                    "target_file_path": "test_implementation.py",
                    "relationship_type": "direct_match",
                    "confidence_score": 0.9,
                    "helpful_aspects": ["implementation pattern"],
                    "potential_contributions": ["core functionality"],
                    "usage_suggestions": "Use this as a reference for implementation"
                }
            ]
        }

        with open(self.mock_index_file_path, 'w') as f:
            json.dump(mock_index_data, f)

    def tearDown(self):
        """清理测试环境"""
        # 删除创建的文件和目录
        if os.path.exists(self.mock_index_file_path):
            os.remove(self.mock_index_file_path)

        if os.path.exists(self.mock_indexes_dir):
            os.rmdir(self.mock_indexes_dir)

    def test_code_reference_dataclass(self):
        """测试 CodeReference 数据类的功能"""
        ref = CodeReference(
            file_path="test.py",
            file_type="Python module",
            main_functions=["main", "helper"],
            key_concepts=["algorithm", "data processing"],
            dependencies=["numpy", "pandas"],
            summary="Test file",
            lines_of_code=42,
            repo_name="test-repo",
            confidence_score=0.8
        )

        self.assertEqual(ref.file_path, "test.py")
        self.assertEqual(ref.file_type, "Python module")
        self.assertEqual(ref.main_functions, ["main", "helper"])
        self.assertEqual(ref.key_concepts, ["algorithm", "data processing"])
        self.assertEqual(ref.dependencies, ["numpy", "pandas"])
        self.assertEqual(ref.summary, "Test file")
        self.assertEqual(ref.lines_of_code, 42)
        self.assertEqual(ref.repo_name, "test-repo")
        self.assertEqual(ref.confidence_score, 0.8)

    def test_relationship_info_dataclass(self):
        """测试 RelationshipInfo 数据类的功能"""
        rel = RelationshipInfo(
            repo_file_path="file1.py",
            target_file_path="file2.py",
            relationship_type="direct_match",
            confidence_score=0.9,
            helpful_aspects=["implementation", "data structures"],
            potential_contributions=["core functionality"],
            usage_suggestions="Use this file for core implementation"
        )

        self.assertEqual(rel.repo_file_path, "file1.py")
        self.assertEqual(rel.target_file_path, "file2.py")
        self.assertEqual(rel.relationship_type, "direct_match")
        self.assertEqual(rel.confidence_score, 0.9)
        self.assertEqual(rel.helpful_aspects, ["implementation", "data structures"])
        self.assertEqual(rel.potential_contributions, ["core functionality"])
        self.assertEqual(rel.usage_suggestions, "Use this file for core implementation")

    def test_load_index_files_from_directory(self):
        """测试从目录加载索引文件"""
        # 测试正常加载
        index_cache = load_index_files_from_directory(self.mock_indexes_dir)
        self.assertEqual(len(index_cache), 1)
        self.assertIn("mock_repo_index", index_cache)
        self.assertEqual(index_cache["mock_repo_index"]["repo_name"], "mock_repo")

        # 测试加载不存在的目录
        non_existent_dir = os.path.join(self.test_dir, "non_existent_dir")
        index_cache = load_index_files_from_directory(non_existent_dir)
        self.assertEqual(len(index_cache), 0)

    def test_extract_code_references(self):
        """测试从索引数据中提取代码引用"""
        index_data = {
            "repo_name": "test-repo",
            "file_summaries": [
                {
                    "file_path": "test.py",
                    "file_type": "Python module",
                    "main_functions": ["main"],
                    "key_concepts": ["test"],
                    "dependencies": [],
                    "summary": "Test file",
                    "lines_of_code": 1
                }
            ]
        }

        references = extract_code_references(index_data)
        self.assertEqual(len(references), 1)
        self.assertEqual(references[0].file_path, "test.py")
        self.assertEqual(references[0].repo_name, "test-repo")

    def test_calculate_relevance_score(self):
        """测试计算相关性分数"""
        ref = CodeReference(
            file_path="implementation.py",
            file_type="Python module",
            main_functions=["process_data"],
            key_concepts=["data processing"],
            dependencies=[],
            summary="Implementation file",
            lines_of_code=100,
            repo_name="test-repo"
        )

        # 测试文件名和类型匹配
        score = calculate_relevance_score("test_implementation.py", ref)
        self.assertGreater(score, 0.0)

        # 测试关键词匹配
        score_with_keywords = calculate_relevance_score("test_implementation.py", ref, ["data", "process"])
        self.assertGreater(score_with_keywords, score)

    @patch('examples.deepcode_agent.tools.code_reference_indexer.load_index_files_from_directory')
    async def test_search_code_references(self, mock_load_indexes):
        """测试搜索代码引用的异步函数"""
        # 模拟索引数据
        mock_index_cache = {
            "mock_repo": {
                "repo_name": "mock_repo",
                "file_summaries": [
                    {
                        "file_path": "implementation.py",
                        "file_type": "Python module",
                        "main_functions": ["process_data"],
                        "key_concepts": ["data processing"],
                        "dependencies": [],
                        "summary": "Implementation file",
                        "lines_of_code": 100
                    }
                ],
                "relationships": []
            }
        }
        mock_load_indexes.return_value = mock_index_cache

        # 执行测试
        result_json = await search_code_references(
            indexes_path="dummy_path",
            target_file="test_implementation.py",
            keywords="data,process"
        )

        # 验证结果
        result = json.loads(result_json)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["target_file"], "test_implementation.py")
        self.assertEqual(result["keywords_used"], ["data", "process"])

    @patch('examples.deepcode_agent.tools.code_reference_indexer.load_index_files_from_directory')
    async def test_get_indexes_overview(self, mock_load_indexes):
        """测试获取索引概览的异步函数"""
        # 模拟索引数据
        mock_index_cache = {
            "mock_repo": {
                "repo_name": "mock_repo",
                "total_files": 2,
                "file_summaries": [
                    {
                        "file_path": "file1.py",
                        "file_type": "Python module",
                        "key_concepts": ["concept1"]
                    },
                    {
                        "file_path": "file2.py",
                        "file_type": "Python script",
                        "key_concepts": ["concept2"]
                    }
                ],
                "relationships": [{}, {}]
            }
        }
        mock_load_indexes.return_value = mock_index_cache

        # 执行测试
        result_json = await get_indexes_overview(indexes_path="dummy_path")

        # 验证结果
        result = json.loads(result_json)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["overview"]["total_repos"], 1)
        self.assertIn("mock_repo", result["overview"]["repositories"])
        self.assertEqual(result["overview"]["repositories"]["mock_repo"]["total_files"], 2)

    @patch('examples.deepcode_agent.tools.code_reference_indexer.load_index_files_from_directory')
    async def test_search_code_references_error(self, mock_load_indexes):
        """测试搜索代码引用时发生错误的情况"""
        # 模拟加载索引文件时发生异常
        mock_load_indexes.side_effect = Exception("Test error")

        # 执行测试
        result_json = await search_code_references(
            indexes_path="dummy_path",
            target_file="test_implementation.py"
        )

        # 验证结果
        result = json.loads(result_json)
        self.assertEqual(result["status"], "error")
        self.assertIn("Test error", result["message"])


if __name__ == "__main__":
    unittest.main()