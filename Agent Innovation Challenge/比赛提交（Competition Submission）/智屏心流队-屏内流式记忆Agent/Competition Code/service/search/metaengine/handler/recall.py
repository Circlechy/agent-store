import json
import logging

import requests

from service.process.common.client.es_request import elasticsearch_query

def text_recall(url, text):
    payload = json.dumps({
        "text": text
    })
    headers = {
        'Content-Type': 'application/json'
    }

    try:
        response = requests.request("POST", url, headers=headers, data=payload, timeout=5)
        response.raise_for_status()
        return json.loads(response.text)
    except Exception as e:
        logging.error(f"Other error: {e}")
        return []

def search_documents(ES_URL, index_name, query):

    QUERY_BODY = {
        "query": {
            "match": {
                "caption": query
            }
        }
    }


    result = elasticsearch_query(ES_URL, index_name, QUERY_BODY)


    if result:
        return [hit['_source'] for hit in result['hits']['hits']]

    return []

def search(es_url, index_name, query):
    """保持老接口: return {"data": [ {start_time, caption}, ... ]}"""
    hits = search_documents(es_url, index_name, query)  # List[dict]: 来自 ES
    data_list = [
        {
            "start_time": h.get("start_time", ""),
            "caption":    h.get("caption", "")
        }
        for h in hits
    ]
    return {"data": data_list}

if __name__ == "__main__":
    print(text_recall())
