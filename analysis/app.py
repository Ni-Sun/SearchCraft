from flask import Flask
from flask_cors import CORS
from document_store import DocumentStore
from routes import init_routes
from search_service import SearchService

def create_app():
    app = Flask(__name__)
    CORS(app)
    
    # 应用配置
    app.config['ES_CONFIG'] = {
        'hosts': ["http://localhost:9200"],
        'timeout': 30,
        'retries': 3
    }
    
    # 初始化核心组件
    app.document_store = DocumentStore()
    app.search_service = SearchService()
    
    # 注册路由
    init_routes(app)
    
    # 初始化搜索服务
    app.search_service.init_app(app)
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
