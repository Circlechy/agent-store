import http.client
import os
import dotenv

from urllib.parse import quote
from typing import Optional

from openjiuwen.core.utils.tool.param import Param
from openjiuwen.core.utils.tool.tool import tool

dotenv.load_dotenv(dotenv_path=".env")
# 从环境变量获取 access_token
ACCESS_TOKEN = os.environ.get("GITCODE_ACCESS_TOKEN", "")

@tool(name="search_repo",
      description="搜索GitCode上的代码仓库",
      params=[
        Param(name="query", description="搜索关键字", type="str", required=True),
        Param(name="sort", description="排序字段，last_push_at(更新时间)、stars_count(收藏数)、forks_count(Fork 数)，默认为最佳匹配", type="str", required=False),
        Param(name="order", description="排序方式，asc(升序)、desc(降序)，默认为 desc", type="str", required=False),
        Param(name="owner", description="仓库所属空间地址(组织或个人的地址path)", type="str", required=False),
        Param(name="language", description="仓库主要编程语言，如：Python、JavaScript 等", type="str", required=False),
        ])
def search_repo(query: str, sort: Optional[str] = None, order: Optional[str] = None, 
                owner: Optional[str] = None, language: Optional[str] = None):
    # 构建查询参数（值需要URL编码）
    params = {
        'access_token': ACCESS_TOKEN,
        'q': quote(query, safe='')
    }

    if sort:
        params['sort'] = quote(sort, safe='')
    if order:
        params['order'] = quote(order, safe='')
    if owner:
        params['owner'] = quote(owner, safe='')
    if language:
        params['language'] = quote(language, safe='')

    # 构建查询字符串
    query_string = '&'.join([f"{k}={v}" for k, v in params.items()])

    conn = http.client.HTTPSConnection("api.gitcode.com")
    payload = ''
    headers = {
        'Accept': 'application/json'
    }
    conn.request("GET", f"/api/v5/search/repositories?{query_string}", payload, headers)
    res = conn.getresponse()
    data = res.read()

    return data.decode("utf-8")


if __name__ == "__main__":
    # 示例调用
    inputs = {
        "query": "studio",
        "owner": "openJiuwen"
    }
    result = search_repo.invoke(inputs=inputs)
    print(result)