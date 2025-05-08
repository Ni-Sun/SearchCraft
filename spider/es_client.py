from datetime import datetime
from elasticsearch import Elasticsearch

class ElasticsearchClient:
    def __init__(self, endpoint="http://localhost:9200"):
        self.es = Elasticsearch(
            [endpoint],
            verify_certs=False,
            ssl_show_warn=False
        )
        self._ensure_pipeline()
        self._ensure_index()

    def _ensure_index(self):
        if not self.es.indices.exists(index="search_craft"):
            self._create_index()
        return

    def _create_index(self):
        index_config = {
            "mappings": {
                "properties": {
                    "content": {
                        "type": "text",
                        "fields": {
                            "keyword": {"type": "keyword", "ignore_above": 256}
                        }
                    },
                    "language": {
                        "type": "text",
                        "fields": {
                            "keyword": {"type": "keyword", "ignore_above": 256}
                        }
                    },
                    "processed_content": {
                        "type": "text",
                        "analyzer": "ik_smart",
                        "fields": {
                            "keyword": {"type": "keyword", "ignore_above": 256}
                        }
                    },
                    "timestamp": {"type": "date"},
                    "url": {
                        "type": "text",
                        "fields": {
                            "keyword": {"type": "keyword", "ignore_above": 256}
                        }
                    }
                }
            },
            "settings": {
                "index": {
                    # 分词限制配置
                    "analyze": {
                        "max_token_count": 50000  # 设置为需要的最大值
                    },
                    "number_of_shards": 1,
                    "number_of_replicas": 1
                }
            }
        }
        self.es.indices.create(index="search_craft", body=index_config)
        return

    def _ensure_pipeline(self):
        """确保ingest pipeline存在"""
        pipeline_id = "search_craft_pipeline"
        if not self.es.ingest.get_pipeline(id=pipeline_id, ignore=[404]):
            # 创建简单pipeline代替不存在的ent-search-generic-ingestion
            pipeline_body = {
                "description": "Default text processing pipeline",
                "processors": [
                    {
                        "trim": {
                            "field": "content",
                            "ignore_missing": True
                        }
                    },
                    {
                        "gsub": {
                            "field": "content",
                            "pattern": "\\s+",
                            "replacement": " "
                        }
                    }
                ]
            }
            self.es.ingest.put_pipeline(id=pipeline_id, body=pipeline_body)

    def index_document(self, document):
        try:
            return self.es.index(
                index="search_craft",
                document=document,
                pipeline="search_craft_pipeline",
                timeout='30s'
            )
        except Exception as e:
            print(f"ES写入异常：{str(e)}")
            return None
