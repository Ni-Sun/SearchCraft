from elasticsearch import Elasticsearch
from flask import current_app

class SearchService:
    def __init__(self):
        self.es = None
    
    def init_app(self, app):
        self.es = Elasticsearch(
            hosts=app.config['ES_CONFIG']['hosts'],
            request_timeout=app.config['ES_CONFIG']['timeout'],
            max_retries=app.config['ES_CONFIG']['retries'],
            retry_on_timeout=True
        )
    
    def handle_search(self, query):
        search_body = {
            "query": {
                "match": {
                    "processed_content": {
                        "query": query,
                    }
                }
            },
            "_source": ["url", "language", "timestamp"],
            "size": 100
        }

        try:
            response = self.es.search(index="search_craft", body=search_body)
            return {
                "total": response["hits"]["total"]["value"],
                "results": [{
                    "url": hit["_source"].get("url", "未知URL"),
                    "language": str(hit["_source"].get("language", "unknown")).lower(),
                    "timestamp": hit["_source"].get("timestamp")
                } for hit in response["hits"]["hits"]]
            }
        except Exception as e:
            current_app.logger.error(f"ES查询失败: {str(e)}")
            raise
