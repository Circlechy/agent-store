import os
from typing import Dict, Any

from jiuwenfintech.config.env_utils import parse_bool_env, parse_str_env, get_env_info


class TushareConfig:
    """Tushare配置管理器"""
    
    def __init__(self):
        """初始化Tushare配置"""
        self.load_config()
    
    def load_config(self):
        """加载Tushare配置"""
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
        
        self.token = parse_str_env("TUSHARE_TOKEN", "")
        self.enabled = parse_bool_env("TUSHARE_ENABLED", False)
        self.default_source = parse_str_env("DEFAULT_CHINA_DATA_SOURCE", "akshare")
        
        self.cache_enabled = parse_bool_env("ENABLE_DATA_CACHE", True)
        self.cache_ttl_hours = parse_str_env("TUSHARE_CACHE_TTL_HOURS", "24")
        
        self._debug_config()
    
    def _debug_config(self):
        """输出调试配置信息"""
        print(f" Tushare配置调试信息:")
        print(f"   TUSHARE_TOKEN: {'已设置' if self.token else '未设置'} ({len(self.token)}字符)")
        print(f"   TUSHARE_ENABLED: {self.enabled} (原始值: {os.getenv('TUSHARE_ENABLED', 'None')})")
        print(f"   DEFAULT_CHINA_DATA_SOURCE: {self.default_source}")
        print(f"   ENABLE_DATA_CACHE: {self.cache_enabled}")
    
    def is_valid(self) -> bool:
        """检查配置是否有效"""
        if not self.enabled:
            return False
        
        if not self.token:
            return False
        
        if len(self.token) < 30:
            return False
        
        return True
    
    def get_validation_result(self) -> Dict[str, Any]:
        """获取详细的验证结果"""
        result = {
            'valid': False,
            'enabled': self.enabled,
            'token_set': bool(self.token),
            'token_length': len(self.token),
            'issues': [],
            'suggestions': []
        }
        
        if not self.enabled:
            result['issues'].append("TUSHARE_ENABLED未启用")
            result['suggestions'].append("在.env文件中设置 TUSHARE_ENABLED=true")
        
        if not self.token:
            result['issues'].append("TUSHARE_TOKEN未设置")
            result['suggestions'].append("在.env文件中设置 TUSHARE_TOKEN=your_token_here")
        elif len(self.token) < 30:
            result['issues'].append("TUSHARE_TOKEN格式可能不正确")
            result['suggestions'].append("检查token是否完整（通常为40字符）")
        
        if not result['issues']:
            result['valid'] = True
        
        return result
    
    def get_env_debug_info(self) -> Dict[str, Any]:
        """获取环境变量调试信息"""
        env_vars = [
            "TUSHARE_TOKEN",
            "TUSHARE_ENABLED", 
            "DEFAULT_CHINA_DATA_SOURCE",
            "ENABLE_DATA_CACHE"
        ]
        
        debug_info = {}
        for var in env_vars:
            debug_info[var] = get_env_info(var)
        
        return debug_info
    
    def test_boolean_parsing(self) -> Dict[str, Any]:
        """测试布尔值解析的兼容性"""
        test_cases = [
            ("true", True),
            ("True", True), 
            ("TRUE", True),
            ("1", True),
            ("yes", True),
            ("on", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("0", False),
            ("no", False),
            ("off", False),
            ("", False),
            ("invalid", False)
        ]
        
        results = {}
        for test_value, expected in test_cases:
            original_value = os.getenv("TEST_BOOL_VAR")
            os.environ["TEST_BOOL_VAR"] = test_value
            
            parsed = parse_bool_env("TEST_BOOL_VAR", False)
            results[test_value] = {
                'expected': expected,
                'parsed': parsed,
                'correct': parsed == expected
            }
            
            if original_value is not None:
                os.environ["TEST_BOOL_VAR"] = original_value
            else:
                os.environ.pop("TEST_BOOL_VAR", None)
        
        return results
    
    def fix_common_issues(self) -> Dict[str, str]:
        """修复常见配置问题"""
        fixes = {}
        
        enabled_raw = os.getenv("TUSHARE_ENABLED", "")
        if enabled_raw.lower() in ["true", "1", "yes", "on"] and not self.enabled:
            fixes["TUSHARE_ENABLED"] = f"检测到 '{enabled_raw}'，但解析为False，可能存在兼容性问题"
        
        return fixes


def get_tushare_config() -> TushareConfig:
    """获取Tushare配置实例"""
    return TushareConfig()


def check_tushare_compatibility() -> Dict[str, Any]:
    """检查Tushare配置兼容性"""
    config = get_tushare_config()
    
    return {
        'config_valid': config.is_valid(),
        'validation_result': config.get_validation_result(),
        'env_debug_info': config.get_env_debug_info(),
        'boolean_parsing_test': config.test_boolean_parsing(),
        'common_fixes': config.fix_common_issues()
    }


def diagnose_tushare_issues():
    """诊断Tushare配置问题"""
    print(" Tushare配置诊断")
    print("=" * 60)
    
    compatibility = check_tushare_compatibility()
    
    print(f"\n 配置状态:")
    validation = compatibility['validation_result']
    print(f"   配置有效: {'' if validation['valid'] else ''}")
    print(f"   Tushare启用: {'' if validation['enabled'] else ''}")
    print(f"   Token设置: {'' if validation['token_set'] else ''}")
    
    if validation['issues']:
        print(f"\n 发现问题:")
        for issue in validation['issues']:
            print(f"   - {issue}")
    
    if validation['suggestions']:
        print(f"\n修复建议:")
        for suggestion in validation['suggestions']:
            print(f"   - {suggestion}")
    
    print(f"\n 环境变量详情:")
    for var, info in compatibility['env_debug_info'].items():
        status = "" if info['exists'] and not info['empty'] else ""
        print(f"   {var}: {status} {info['value']}")
    
    print(f"\n🧪 布尔值解析测试:")
    bool_tests = compatibility['boolean_parsing_test']
    failed_tests = [k for k, v in bool_tests.items() if not v['correct']]
    
    if failed_tests:
        print(f"    失败的测试: {failed_tests}")
        print(f"    可能存在Python版本兼容性问题")
    else:
        print(f"    所有布尔值解析测试通过")
    
    fixes = compatibility['common_fixes']
    if fixes:
        print(f"\n 自动修复建议:")
        for var, fix in fixes.items():
            print(f"   {var}: {fix}")


if __name__ == "__main__":
    diagnose_tushare_issues()
