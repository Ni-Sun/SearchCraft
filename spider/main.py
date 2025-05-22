import time
import random
import queue
import threading
from queue import Queue
from pathlib import Path
from spider import Spider
from domain import *
from general import *
from configs import CRAWLER_CONFIGS
from file_manager import FileManager
# from gather import organize_translations

class CrawlerMaster:
    def __init__(self, config):
        self.config = config
        self.project_name = f"../crawler/{'zh' if config['language']=='cn' else 'en'}/{config['name']}-crawler"
        self.domain_name = get_domain_name(config['homepage'])
        self.spider = Spider(
            self.project_name,
            config['homepage'],
            self.domain_name,
            max_pages=config['max_pages'],
            language=config['language']
        )
        self.queue = Queue()
        self.threads = []

    def create_workers(self):
        # 创建多个线程
        for _ in range(self.config['threads']):
            t = threading.Thread(target=self.worker, daemon=True)
            t.start()
            self.threads.append(t)

    def worker(self):
        # 每个线程从队列中获取 URL
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

    # 创建并启动线程池
    def start(self):
        self.load_queue()       # 初始化队列
        self.create_workers()   # 创建工作线程
        self.monitor()          # 监控爬虫状态

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

    # 智能队列补充机制
    def refill_queue(self):
        current_queued = file_to_set(self.spider.queue_file)

        # 添加深度优先补充策略
        if len(current_queued) < self.config['max_pages'] // 2:
            print("智能补充种子URL")
            seed_urls = [
                self.config['homepage'] + '/hot',
                self.config['homepage'] + '/explore',
                self.config['homepage'] + '/roundtable'
            ]
            current_queued.update(seed_urls)

        # 添加分页发现逻辑
        if '/page=' in self.config['homepage']:
            max_page = self.config.get('max_pages', 10)
            current_page = len(current_queued)
            new_urls = [f"{self.config['homepage']}?page={i}" for i in range(current_page, current_page + 5)]
            current_queued.update(new_urls)

        # 写入更新后的队列
        set_to_file(current_queued, self.spider.queue_file)

        # 加载到内存队列
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
        print("=== Starting cleanup ===")
        for config in CRAWLER_CONFIGS:
            project_name = Path(__file__).parent.parent / 'crawler' / f"{'zh' if config['language']=='cn' else 'en'}" / f"{config['name']}-crawler"
            file_manager = FileManager(project_name)
            file_manager.clean_small_files(1)
        print("=== All cleanup operations completed ===")



