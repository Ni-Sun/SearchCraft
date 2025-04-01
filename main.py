import queue
import threading
from queue import Queue
from spider import Spider
from domain import *
from general import *
import time
import random

# 配置多个爬虫任务
CRAWLER_CONFIGS = [
    {
        'name': 'cnblogs',
        'homepage': 'https://www.cnblogs.com/',
        'max_pages': 10,  # 控制爬取数量
        'threads': 4,
        'delay': (1, 3)  # 自定义延迟范围
    }
    # {
    #     'name': 'baidu',
    #     'homepage': 'https://www.baidu.com',
    #     'max_pages': 10,
    #     'threads': 4
    # },
    # {
    #     'name': 'zhihu',
    #     'homepage': 'https://www.zhihu.com',
    #     'max_pages': 10,
    #     'threads': 4
    # }
]


class CrawlerMaster:
    def __init__(self, config):
        self.config = config
        self.project_name = f"{config['name']}-crawler"
        self.domain_name = get_domain_name(config['homepage'])
        self.spider = Spider(
            self.project_name,
            config['homepage'],
            self.domain_name,
            max_pages=config['max_pages']
        )
        self.queue = Queue()
        self.threads = []

    def create_workers(self):
        for _ in range(self.config['threads']):
            t = threading.Thread(target=self.worker, daemon=True)
            t.start()
            self.threads.append(t)

    def worker(self):
        while self.spider.crawled_count < self.spider.max_pages:
            try:
                url = self.queue.get(timeout=10)
                if url is None:
                    break

                self.spider.crawl_page(threading.current_thread().name, url)
                self.queue.task_done()

                # 动态限速（不同站点不同速度）
                # time.sleep(self.config.get('delay', random.uniform(1, 3)))
            except queue.Empty:
                print(f"{self.config['name']} queue is empty, refilling...")
                self.refill_queue()
            except Exception as e:
                print(f"{self.config['name']} worker error: {str(e)}")
                self.queue.task_done()

    def start(self):
        # 初始化队列
        self.load_queue()
        # 创建工作线程
        self.create_workers()
        # 开始爬取
        self.monitor()

    def load_queue(self):
        queued = file_to_set(self.spider.queue_file)
        for url in queued:
            self.queue.put(url)

    def monitor(self):
        while self.spider.crawled_count < self.spider.max_pages:
            remaining = self.spider.max_pages - self.spider.crawled_count
            print(f"[{self.config['name']}] Progress: {self.spider.crawled_count}/{self.spider.max_pages} "
                  f"| Queue: {self.queue.qsize()}")

            # 动态调整队列
            if self.queue.qsize() < remaining * 2:
                self.refill_queue()

            time.sleep(5)

    def refill_queue(self):
        """从文件重新加载队列防止内存消耗过大"""
        current_queued = file_to_set(self.spider.queue_file)

        # 添加自动补充初始URL的机制
        if len(current_queued) == 0:
            print("Queue empty, adding base URL to restart")
            write_file(self.spider.queue_file, self.config['homepage'])
            current_queued = {self.config['homepage']}

        for url in current_queued:
            if not self.queue.full():
                self.queue.put(url)


if __name__ == '__main__':
    masters = []
    for config in CRAWLER_CONFIGS:
        master = CrawlerMaster(config)
        master.start()
        masters.append(master)

    try:
        # 保持主线程运行
        while any(m.spider.crawled_count < m.spider.max_pages for m in masters):
            time.sleep(10)
            print("\n=== Current Status ===")
            for m in masters:
                print(f"{m.config['name']}: {m.spider.crawled_count} pages")
    finally:
        # 所有任务完成后执行清理
        print("\n=== Starting cleanup ===")
        for config in CRAWLER_CONFIGS:
            project_name = f"{config['name']}-crawler"
            clean_small_files(project_name)
            print(f"Cleanup completed for {project_name}")
        print("=== All cleanup operations completed ===")





