import os
import sys
import time
import tkinter as tk
from tkinter import ttk, messagebox
import requests
import json
from datetime import datetime
from subprocess import Popen

class SearchApp:
    def __init__(self, root):
        self.root = root
        root.title("search_craft")
        root.geometry("800x600")

        # 创建界面组件
        self.create_widgets()

        # 配置样式
        self.style = ttk.Style()
        self.style.configure("Treeview", rowheight=25)
        self.style.configure("TButton", padding=5)
        self.style.configure("TEntry", padding=5)

    def create_widgets(self):
        # 搜索框区域
        search_frame = ttk.Frame(self.root)
        search_frame.pack(pady=10, padx=10, fill="x")

        self.search_entry = ttk.Entry(search_frame, width=50)
        self.search_entry.pack(side="left", expand=True, fill="x")

        self.search_btn = ttk.Button(
            search_frame,
            text="搜索",
            command=self.perform_search
        )
        self.search_btn.pack(side="left", padx=5)

        # 搜索结果区域
        self.result_frame = ttk.Frame(self.root)
        self.result_frame.pack(pady=10, padx=10, fill="both", expand=True)

        # 创建树状表格
        self.tree = ttk.Treeview(
            self.result_frame,
            columns=("url", "language", "timestamp"),
            show="headings",
            selectmode="browse"
        )

        # 配置表头
        self.tree.heading("url", text="网页地址")
        self.tree.heading("language", text="语言")
        self.tree.heading("timestamp", text="最后更新时间")

        # 配置列宽
        self.tree.column("url", width=400, anchor="w")
        self.tree.column("language", width=100, anchor="center")
        self.tree.column("timestamp", width=200, anchor="center")

        # 添加滚动条
        scrollbar = ttk.Scrollbar(self.result_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 绑定回车键
        self.root.bind("<Return>", lambda event: self.perform_search())

    def perform_search(self):
        query = self.search_entry.get().strip()
        if not query:
            messagebox.showwarning("输入错误", "请输入搜索关键词")
            return

        try:
            self.search_btn.config(state="disabled")
            response = requests.get(
                "http://localhost:5000/api/search",
                params={"q": query},
                timeout=10
            )

            # 响应内容解析检查
            try:
                response_data = response.json()
            except json.JSONDecodeError:
                messagebox.showerror("数据错误", "服务器返回了非JSON格式的响应")
                return

            if response.status_code == 200:
                data = response.json()
                self.display_results(data)
            else:
                error_msg = f"服务器返回错误: {response.status_code}\n{response.text}"
                messagebox.showerror("搜索错误", error_msg)

        except requests.exceptions.RequestException as e:
            messagebox.showerror("连接错误", f"无法连接服务器: {str(e)}")
        finally:
            self.search_btn.config(state="normal")

    def display_results(self, data):
        # 清空现有结果
        for item in self.tree.get_children():
            self.tree.delete(item)

        # 插入新结果
        for idx, result in enumerate(data["results"], 1):
            self.tree.insert("", "end", values=(
                result["url"],
                result["language"].upper(),
                result["timestamp"][:10]
            ))

        # 显示统计信息
        self.tree.heading("url", text=f"网页地址 ({data['total']} 条结果)")


if __name__ == "__main__":
    flask_process = Popen([sys.executable, "app.py"])  # 启动Flask服务
    time.sleep(1)
    root = tk.Tk()
    app = SearchApp(root)

    # 在窗口关闭时终止 Flask 进程
    def on_close():
        flask_process.terminate()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()
