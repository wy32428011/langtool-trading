import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import json
import sys
import os
from typing import List, Dict, Any, Union

# 确保项目根目录在 sys.path 中
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.append(project_root)

from arbitrage.polymarket.redis_client import get_redis_client
from arbitrage.polymarket.engine import polymarket_engine
from sqlalchemy import text
from arbitrage.polymarket.stats.analyze_sport_matrix import parse_matrix, check_combination_rules

REDIS_KEY_ACTIVE_MARKETS = "polymarket:active_markets"

class RedisQueryView(ttk.Frame):
    def __init__(self, parent, redis_client):
        super().__init__(parent)
        self.redis_client = redis_client
        self.current_results = []
        self._init_ui()

    def _init_ui(self):
        # 顶部输入区域
        top_frame = ttk.Frame(self, padding="10")
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="输入市场 ID (多个 ID 请用逗号或换行分隔):").pack(side=tk.LEFT)
        
        self.input_text = scrolledtext.ScrolledText(top_frame, height=3, width=50)
        self.input_text.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)

        self.query_btn = ttk.Button(top_frame, text="查询", command=self.query_markets)
        self.query_btn.pack(side=tk.LEFT)

        # 中部主体区域 (使用 PanedWindow 分隔列表和详情)
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 左侧列表区域
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        ttk.Label(left_frame, text="市场列表:").pack(anchor=tk.W)
        self.listbox = tk.Listbox(left_frame, exportselection=False)
        self.listbox.pack(fill=tk.BOTH, expand=True)
        self.listbox.bind("<<ListboxSelect>>", self.on_market_select)

        # 右侧详情区域
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=3)

        detail_header = ttk.Frame(right_frame)
        detail_header.pack(fill=tk.X)
        ttk.Label(detail_header, text="市场详情 (JSON):").pack(side=tk.LEFT)
        
        self.copy_btn = ttk.Button(detail_header, text="复制 JSON", command=self.copy_json)
        self.copy_btn.pack(side=tk.RIGHT)

        self.result_text = scrolledtext.ScrolledText(right_frame, wrap=tk.NONE)
        self.result_text.pack(fill=tk.BOTH, expand=True)

    def query_markets(self):
        input_data = self.input_text.get("1.0", tk.END).strip()
        if not input_data:
            messagebox.showwarning("输入错误", "请输入至少一个市场 ID")
            return

        # 解析 ID，支持逗号或换行分隔
        ids = [i.strip() for i in input_data.replace(",", "\n").split("\n") if i.strip()]
        
        if not ids:
            return

        self.listbox.delete(0, tk.END)
        self.result_text.delete("1.0", tk.END)
        self.current_results = []
        
        try:
            # 批量获取 Redis 数据
            all_data = self.redis_client.hgetall(REDIS_KEY_ACTIVE_MARKETS)
            
            for m_id in ids:
                if m_id in all_data:
                    try:
                        market_json = json.loads(all_data[m_id])
                        self.current_results.append(market_json)
                        title = market_json.get("question") or market_json.get("title") or f"ID: {m_id}"
                        self.listbox.insert(tk.END, title)
                    except Exception as e:
                        err_obj = {"id": m_id, "error": f"解析错误: {str(e)}"}
                        self.current_results.append(err_obj)
                        self.listbox.insert(tk.END, f"❌ 错误: {m_id}")
                else:
                    err_obj = {"id": m_id, "error": "未在 Redis 中找到"}
                    self.current_results.append(err_obj)
                    self.listbox.insert(tk.END, f"❓ 未找到: {m_id}")
            
            if self.current_results:
                self.listbox.selection_set(0)
                self.on_market_select(None)
            
        except Exception as e:
            messagebox.showerror("查询失败", f"访问 Redis 时出错: {str(e)}")

    def on_market_select(self, event):
        selection = self.listbox.curselection()
        if not selection:
            return
        
        idx = selection[0]
        market_data = self.current_results[idx]
        
        self.result_text.delete("1.0", tk.END)
        formatted_json = json.dumps(market_data, indent=4, ensure_ascii=False)
        self.result_text.insert(tk.END, formatted_json)

    def copy_json(self):
        content = self.result_text.get("1.0", tk.END).strip()
        if content:
            self.clipboard_clear()
            self.clipboard_append(content)

class MatrixAnalyzerView(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.current_data = []
        self._init_ui()

    def _init_ui(self):
        # 顶部操作区域
        top_frame = ttk.Frame(self, padding="10")
        top_frame.pack(fill=tk.X)

        self.load_btn = ttk.Button(top_frame, text="刷新数据", command=self.load_data)
        self.load_btn.pack(side=tk.LEFT, padx=5)

        self.invalid_btn = ttk.Button(top_frame, text="标注无效", command=self.mark_invalid)
        self.invalid_btn.pack(side=tk.LEFT, padx=5)

        # 数据列表展示区域
        columns = ("a_id", "b_id", "question_a", "question_b", "gen_q_a", "gen_q_b")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="extended")
        
        self.tree.heading("a_id", text="Market A ID")
        self.tree.heading("b_id", text="Market B ID")
        self.tree.heading("question_a", text="Market A Question")
        self.tree.heading("question_b", text="Market B Question")
        self.tree.heading("gen_q_a", text="Market A Gen Q")
        self.tree.heading("gen_q_b", text="Market B Gen Q")
        
        self.tree.column("a_id", width=100)
        self.tree.column("b_id", width=100)
        self.tree.column("question_a", width=200)
        self.tree.column("question_b", width=200)
        self.tree.column("gen_q_a", width=300)
        self.tree.column("gen_q_b", width=300)

        scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 绑定右键点击事件
        self.tree.bind("<Button-3>", self.show_context_menu)
        self._create_context_menu()

    def _create_context_menu(self):
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="复制单元格内容", command=self.copy_cell)
        self.menu.add_command(label="复制整行内容", command=self.copy_row)

    def show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.menu.post(event.x_root, event.y_root)
            self.clicked_item = item
            self.clicked_column = self.tree.identify_column(event.x)

    def copy_cell(self):
        if hasattr(self, 'clicked_item') and hasattr(self, 'clicked_column'):
            # identify_column 返回的是 #1, #2 这种格式
            col_idx = int(self.clicked_column.replace('#', '')) - 1
            values = self.tree.item(self.clicked_item, "values")
            if 0 <= col_idx < len(values):
                content = str(values[col_idx])
                self.clipboard_clear()
                self.clipboard_append(content)
                # messagebox.showinfo("复制成功", f"已复制到剪贴板: {content[:20]}...")

    def copy_row(self):
        if hasattr(self, 'clicked_item'):
            values = self.tree.item(self.clicked_item, "values")
            content = "\t".join(str(v) for v in values)
            self.clipboard_clear()
            self.clipboard_append(content)

    def load_data(self):
        query = text("SELECT market_a_id, market_b_id, market_a_question, market_b_question, matrix, market_a_generated_questions, market_b_generated_questions FROM polymarket_sport_matrix WHERE mark IS NULL OR mark != 'n'")
        
        # 清空当前列表
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.current_data = []

        try:
            with polymarket_engine.connect() as conn:
                result = conn.execute(query)
                for row in result:
                    m_a_id, m_b_id, q_a, q_b, matrix_raw, gen_q_a_raw, gen_q_b_raw = row
                    combinations = parse_matrix(matrix_raw)
                    if combinations and check_combination_rules(combinations):
                        # 格式化生成的问题
                        gen_q_a = str(gen_q_a_raw)
                        gen_q_b = str(gen_q_b_raw)
                        
                        item_id = self.tree.insert("", tk.END, values=(m_a_id, m_b_id, q_a, q_b, gen_q_a, gen_q_b))
                        self.current_data.append({"id": item_id, "a_id": m_a_id, "b_id": m_b_id})
        except Exception as e:
            messagebox.showerror("加载错误", f"从数据库获取数据失败: {str(e)}")

    def mark_invalid(self):
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("未选择", "请先选择要标注的数据")
            return
        
        if not messagebox.askyesno("确认", f"确定要将选中的 {len(selected_items)} 条数据标注为无效吗？"):
            return

        to_update = []
        for item_id in selected_items:
            for data in self.current_data:
                if data["id"] == item_id:
                    to_update.append((data["a_id"], data["b_id"]))
                    break

        try:
            # 对于 StarRocks 的 UNIQUE KEY 表，使用 INSERT 覆盖更新（部分列更新要求指定相关列）
            # 为了确保只更新 mark 字段，SR 推荐在开启部分更新属性的情况下使用 INSERT
            # 这里的语法是针对 StarRocks 2.2+ 的部分列更新功能
            update_sql = text("INSERT INTO polymarket_sport_matrix (market_a_id, market_b_id, mark) VALUES (:a_id, :b_id, 'n')")
            with polymarket_engine.begin() as conn:
                for a_id, b_id in to_update:
                    conn.execute(update_sql, {"a_id": a_id, "b_id": b_id})
            
            messagebox.showinfo("成功", f"已成功更新 {len(to_update)} 条数据")
            self.load_data()
        except Exception as e:
            messagebox.showerror("更新错误", f"更新数据库失败: {str(e)}")

class MarketViewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Polymarket 综合工具")
        self.geometry("1100x750")
        
        self.redis_client = get_redis_client()
        self._setup_menu()
        
        self.container = ttk.Frame(self)
        self.container.pack(fill=tk.BOTH, expand=True)
        
        self.views = {}
        self._init_views()
        self.show_view("redis")

    def _setup_menu(self):
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="功能", menu=view_menu)
        
        view_menu.add_command(label="Redis 市场查询", command=lambda: self.show_view("redis"))
        view_menu.add_command(label="矩阵分析展示", command=lambda: self.show_view("matrix"))
        view_menu.add_separator()
        view_menu.add_command(label="退出", command=self.quit)

    def _init_views(self):
        self.views["redis"] = RedisQueryView(self.container, self.redis_client)
        self.views["matrix"] = MatrixAnalyzerView(self.container)
        
        for view in self.views.values():
            view.place(relx=0, rely=0, relwidth=1, relheight=1)

    def show_view(self, view_name):
        view = self.views.get(view_name)
        if view:
            view.tkraise()
            if view_name == "matrix":
                view.load_data()
            self.title(f"Polymarket 综合工具 - {view_name.upper()}")

if __name__ == "__main__":
    app = MarketViewer()
    app.mainloop()
