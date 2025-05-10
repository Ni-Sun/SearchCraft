from flask import Flask, request, json, jsonify, send_from_directory
from elasticsearch import Elasticsearch
from flask_cors import CORS
import logging
import elasticsearch
from datetime import datetime

app = Flask(__name__)
CORS(app)

# 配置ES连接超时
es = Elasticsearch(
    hosts=["http://localhost:9200"],
    request_timeout=30,
    max_retries=3,
    retry_on_timeout=True
)


#  添加健康检查
@app.route('/health')
def health_check():
    return jsonify({"status": "healthy"}), 200


#  新增前端路由
@app.route('/')
def index():
    return send_from_directory('static', 'search.html')


#  优化错误处理
@app.errorhandler(404)
def not_found(e):
    return jsonify(error=str(e)), 404


@app.after_request
def normalize_json_fields(response):
    """统一JSON字段名为小写"""
    if response.is_json:
        data = response.get_json()

        def normalize_keys(obj):
            if isinstance(obj, dict):
                return {k.lower(): normalize_keys(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [normalize_keys(item) for item in obj]
            return obj

        response.data = json.dumps(normalize_keys(data))
    return response


# 调试端点
@app.route('/api/debug', methods=['GET'])
def debug_search():
    return jsonify({
        "request.args": dict(request.args),
        "processed_query": request.args.get('q', '')
    })


@app.route('/api/search', methods=['GET'])
def search():
    query = request.args.get('q', '').strip()
    app.logger.debug(f"Received query: {query} (type: {type(query)})")
    if not query:
        return jsonify({"error": "Empty query"}), 400

    # 根据Kibana命令构建查询
    search_body = {
        "query": {
            "match": {
                "processed_content": {
                    "query": query,
                    # "analyzer": "ik_smart_cn"  # 强制指定分词器
                }
            }
        },
        "_source": ["url", "language", "timestamp"],  # 指定返回字段
        "size": 100  # 限制返回结果数量
    }

    try:
        response = es.search(index="search_craft", body=search_body)
        results = []
        for hit in response["hits"]["hits"]:
            source = hit.get("_source", {})

            # 处理 URL 字段
            url = source.get("url") or source.get("Url") or "未知URL"

            # 处理语言字段
            language = str(source.get("language") or source.get("Language", "unknown")).lower()

            # 处理时间戳
            timestamp = source.get("timestamp")

            results.append({
                "url": url,
                "language": str(source.get("language", "unknown")).lower(),
                "timestamp": timestamp
            })

        return jsonify({
            "total": response["hits"]["total"]["value"],
            "results": results
        })

    except elasticsearch.NotFoundError:
        return jsonify({"error": "索引不存在"}), 404
    except KeyError as e:
        app.logger.error(f"文档字段缺失: {str(e)}")
        return jsonify({"error": "数据格式异常"}), 500
    except Exception as e:
        app.logger.error(f"ES查询失败: {str(e)}", exc_info=True)  # 添加详细错误日志
        return jsonify({"error": "搜索服务暂时不可用"}), 500



if __name__ == '__main__':
    app.run(port=5000, debug=True)

    print(es.ping())
    print(es.info())

