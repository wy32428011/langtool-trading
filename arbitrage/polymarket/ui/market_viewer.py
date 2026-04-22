import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import json
import sys
import os
from datetime import datetime
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

class MarketSearchView(ttk.Frame):
    def __init__(self, parent, redis_client):
        super().__init__(parent)
        self.redis_client = redis_client
        self.current_results = []
        self._init_ui()

    def _init_ui(self):
        # 顶部搜索区域
        top_frame = ttk.Frame(self, padding="10")
        top_frame.pack(fill=tk.X)

        # 第一行：关键字搜索
        row1 = ttk.Frame(top_frame)
        row1.pack(fill=tk.X, pady=2)
        ttk.Label(row1, text="输入关键字 (多个用分号;分隔):").pack(side=tk.LEFT)
        self.keyword_entry = ttk.Entry(row1, width=40)
        self.keyword_entry.pack(side=tk.LEFT, padx=10)
        self.keyword_entry.bind("<Return>", lambda e: self.search_markets())

        # 第二行：Token ID 搜索
        row2 = ttk.Frame(top_frame)
        row2.pack(fill=tk.X, pady=2)
        ttk.Label(row2, text="输入Token ID (多个用分号;分隔):").pack(side=tk.LEFT)
        self.token_entry = ttk.Entry(row2, width=40)
        self.token_entry.pack(side=tk.LEFT, padx=10)
        self.token_entry.bind("<Return>", lambda e: self.search_markets())

        # 第三行：市场 ID 搜索
        row3 = ttk.Frame(top_frame)
        row3.pack(fill=tk.X, pady=2)
        ttk.Label(row3, text="输入市场 ID (多个用分号;分隔):").pack(side=tk.LEFT)
        self.id_entry = ttk.Entry(row3, width=40)
        self.id_entry.pack(side=tk.LEFT, padx=10)
        self.id_entry.bind("<Return>", lambda e: self.search_markets())

        # 第四行：到期日搜索
        row4 = ttk.Frame(top_frame)
        row4.pack(fill=tk.X, pady=2)
        ttk.Label(row4, text="输入到期日 (YYYY-MM-DD, 多个用分号;分隔):").pack(side=tk.LEFT)
        self.date_entry = ttk.Entry(row4, width=40)
        self.date_entry.pack(side=tk.LEFT, padx=10)
        self.date_entry.bind("<Return>", lambda e: self.search_markets())

        # 默认填写今日日期
        today_str = datetime.now().strftime("%Y-%m-%d")
        self.date_entry.insert(0, today_str)

        # 第五行：Spread 和 RewardsMinSize 区间过滤
        row5 = ttk.Frame(top_frame)
        row5.pack(fill=tk.X, pady=2)
        
        ttk.Label(row5, text="Spread (Min-Max):").pack(side=tk.LEFT)
        self.spread_min_entry = ttk.Entry(row5, width=8)
        self.spread_min_entry.pack(side=tk.LEFT, padx=2)
        ttk.Label(row5, text="-").pack(side=tk.LEFT)
        self.spread_max_entry = ttk.Entry(row5, width=8)
        self.spread_max_entry.pack(side=tk.LEFT, padx=2)

        ttk.Label(row5, text="  RewardsMinSize (Min-Max):").pack(side=tk.LEFT, padx=(10, 0))
        self.rewards_min_entry = ttk.Entry(row5, width=8)
        self.rewards_min_entry.pack(side=tk.LEFT, padx=2)
        ttk.Label(row5, text="-").pack(side=tk.LEFT)
        self.rewards_max_entry = ttk.Entry(row5, width=8)
        self.rewards_max_entry.pack(side=tk.LEFT, padx=2)

        ttk.Label(row5, text="  DailyRate (Min-Max):").pack(side=tk.LEFT, padx=(10, 0))
        self.daily_rate_min_entry = ttk.Entry(row5, width=8)
        self.daily_rate_min_entry.pack(side=tk.LEFT, padx=2)
        ttk.Label(row5, text="-").pack(side=tk.LEFT)
        self.daily_rate_max_entry = ttk.Entry(row5, width=8)
        self.daily_rate_max_entry.pack(side=tk.LEFT, padx=2)

        # 第六行：逻辑组合关系
        row6 = ttk.Frame(top_frame)
        row6.pack(fill=tk.X, pady=2)
        
        ttk.Label(row6, text="条件组合逻辑:").pack(side=tk.LEFT)
        self.logic_var = tk.StringVar(value="OR")
        ttk.Radiobutton(row6, text="满足任一条件 (OR)", variable=self.logic_var, value="OR").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(row6, text="满足所有条件 (AND)", variable=self.logic_var, value="AND").pack(side=tk.LEFT, padx=5)

        self.search_btn = ttk.Button(row6, text="查询", command=self.search_markets)
        self.search_btn.pack(side=tk.LEFT, padx=(20, 0))

        self.count_label = ttk.Label(row6, text="总数量: 0")
        self.count_label.pack(side=tk.LEFT, padx=20)

        # 中部主体区域 (使用 PanedWindow 分隔列表和详情)
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 左侧列表区域
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        ttk.Label(left_frame, text="搜索结果:").pack(anchor=tk.W)
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
        self.copy_btn.pack(side=tk.RIGHT, padx=2)

        self.copy_tokens_btn = ttk.Button(detail_header, text="复制 Token", command=self.copy_tokens)
        self.copy_tokens_btn.pack(side=tk.RIGHT, padx=2)

        self.copy_desc_btn = ttk.Button(detail_header, text="复制描述", command=self.copy_description)
        self.copy_desc_btn.pack(side=tk.RIGHT, padx=2)

        self.result_text = scrolledtext.ScrolledText(right_frame, wrap=tk.NONE)
        self.result_text.pack(fill=tk.BOTH, expand=True)

    def search_markets(self):
        input_keyword = self.keyword_entry.get().strip().lower()
        input_token = self.token_entry.get().strip()
        input_id = self.id_entry.get().strip()
        input_date = self.date_entry.get().strip()
        
        spread_min_str = self.spread_min_entry.get().strip()
        spread_max_str = self.spread_max_entry.get().strip()
        rewards_min_str = self.rewards_min_entry.get().strip()
        rewards_max_str = self.rewards_max_entry.get().strip()
        daily_rate_min_str = self.daily_rate_min_entry.get().strip()
        daily_rate_max_str = self.daily_rate_max_entry.get().strip()
        
        logic_mode = self.logic_var.get() # OR 或 AND

        # 判断是否有输入
        has_input = any([input_keyword, input_token, input_id, input_date, 
                        spread_min_str, spread_max_str, rewards_min_str, rewards_max_str,
                        daily_rate_min_str, daily_rate_max_str])

        if not has_input:
            messagebox.showwarning("输入错误", "请输入至少一个搜索条件")
            return

        # 解析数值区间
        def parse_float(s):
            try:
                return float(s)
            except:
                return None

        spread_min = parse_float(spread_min_str)
        spread_max = parse_float(spread_max_str)
        rewards_min = parse_float(rewards_min_str)
        rewards_max = parse_float(rewards_max_str)
        daily_rate_min = parse_float(daily_rate_min_str)
        daily_rate_max = parse_float(daily_rate_max_str)

        # 分隔符统一使用分号
        keywords = [k.strip() for k in input_keyword.split(";") if k.strip()]
        token_ids = [t.strip() for t in input_token.split(";") if t.strip()]
        market_ids = [mid.strip() for mid in input_id.split(";") if mid.strip()]
        dates = [d.strip() for d in input_date.split(";") if d.strip()]

        self.listbox.delete(0, tk.END)
        self.result_text.delete("1.0", tk.END)
        self.current_results = []
        
        try:
            # 获取 Redis 数据
            all_data = self.redis_client.hgetall(REDIS_KEY_ACTIVE_MARKETS)
            
            count = 0
            for m_id, m_json in all_data.items():
                try:
                    market = json.loads(m_json)
                    
                    conditions_results = []

                    # 1. 市场 ID 匹配
                    if market_ids:
                        conditions_results.append(m_id in market_ids)
                    
                    # 2. 关键字匹配 (Question/Description)
                    if keywords:
                        question = (market.get("question") or "").lower()
                        description = (market.get("description") or "").lower()
                        match_kw = any(kw in question or kw in description for kw in keywords)
                        conditions_results.append(match_kw)
                    
                    # 3. Token ID 匹配 (clobTokenIds)
                    if token_ids:
                        clob_tokens_raw = market.get("clobTokenIds")
                        market_tokens = []
                        if clob_tokens_raw:
                            if isinstance(clob_tokens_raw, str):
                                try:
                                    market_tokens = json.loads(clob_tokens_raw)
                                except:
                                    market_tokens = []
                            else:
                                market_tokens = clob_tokens_raw
                        
                        match_token = False
                        if isinstance(market_tokens, list):
                            match_token = any(tid in market_tokens for tid in token_ids)
                        conditions_results.append(match_token)

                    # 4. 到期日匹配 (endDateISO)
                    if dates:
                        end_date = market.get("endDateISO") or market.get("endDateIso") or ""
                        match_date = any(dt in end_date for dt in dates)
                        conditions_results.append(match_date)

                    # 5. Spread 区间匹配
                    if spread_min is not None or spread_max is not None:
                        val = parse_float(market.get("spread"))
                        if val is None:
                            conditions_results.append(False)
                        else:
                            res = True
                            if spread_min is not None and val < spread_min:
                                res = False
                            if spread_max is not None and val > spread_max:
                                res = False
                            conditions_results.append(res)

                    # 6. RewardsMinSize 区间匹配
                    if rewards_min is not None or rewards_max is not None:
                        val = parse_float(market.get("rewardsMinSize"))
                        if val is None:
                            conditions_results.append(False)
                        else:
                            res = True
                            if rewards_min is not None and val < rewards_min:
                                res = False
                            if rewards_max is not None and val > rewards_max:
                                res = False
                            conditions_results.append(res)
                    
                    # 7. RewardsDailyRate 区间匹配 (clobRewards 数组)
                    if daily_rate_min is not None or daily_rate_max is not None:
                        clob_rewards = market.get("clobRewards")
                        if not clob_rewards or not isinstance(clob_rewards, list):
                            conditions_results.append(False)
                        else:
                            match_rate = False
                            for reward in clob_rewards:
                                rate = parse_float(reward.get("rewardsDailyRate"))
                                if rate is not None:
                                    res = True
                                    if daily_rate_min is not None and rate < daily_rate_min:
                                        res = False
                                    if daily_rate_max is not None and rate > daily_rate_max:
                                        res = False
                                    if res:
                                        match_rate = True
                                        break
                            conditions_results.append(match_rate)

                    # 逻辑组合
                    if not conditions_results:
                        match = False
                    elif logic_mode == "AND":
                        match = all(conditions_results)
                    else: # OR
                        match = any(conditions_results)
                    
                    if match:
                        self.current_results.append(market)
                except Exception:
                    continue
            
            # 按照 volumeNum 排序 (从大到小)
            self.current_results.sort(key=lambda x: float(x.get("volumeNum") or 0), reverse=True)
            
            # 清空并重新插入到 listbox
            self.listbox.delete(0, tk.END)
            for m in self.current_results:
                title = m.get("question") or m.get("title") or f"ID: {m.get('marketId') or 'unknown'}"
                # 如果有成交量，显示在标题中
                vol = m.get("volumeNum") or 0
                self.listbox.insert(tk.END, f"[{vol}] {title}")
                count += 1
            
            self.count_label.config(text=f"总数量: {count}")
            
            if self.current_results:
                self.listbox.selection_set(0)
                self.on_market_select(None)
            else:
                messagebox.showinfo("无结果", "未找到匹配的市场")
            
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

    def copy_description(self):
        selection = self.listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        market_data = self.current_results[idx]
        description = market_data.get("description") or ""
        if description:
            self.clipboard_clear()
            self.clipboard_append(description)

    def copy_tokens(self):
        selection = self.listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        market_data = self.current_results[idx]
        tokens = market_data.get("clobTokenIds")
        if tokens:
            if isinstance(tokens, (list, dict)):
                tokens_str = json.dumps(tokens, ensure_ascii=False)
            else:
                tokens_str = str(tokens)
            self.clipboard_clear()
            self.clipboard_append(tokens_str)

class MatrixAnalyzerView(ttk.Frame):
    def __init__(self, parent, table_name="polymarket_sport_matrix", mark_table_name="polymarket_sport_matrix_marks"):
        super().__init__(parent)
        self.table_name = table_name
        self.mark_table_name = mark_table_name
        self.current_data = []
        # 分页相关
        self.page_size = 50
        self.current_page = 1
        self.total_pages = 1
        self._init_ui()

    def _init_ui(self):
        # 顶部操作区域
        top_frame = ttk.Frame(self, padding="10")
        top_frame.pack(fill=tk.X)

        self.load_btn = ttk.Button(top_frame, text="刷新数据", command=self.load_data)
        self.load_btn.pack(side=tk.LEFT, padx=5)

        # 标注无效按钮 (红色)
        self.invalid_btn = tk.Button(top_frame, text="标注无效", command=self.mark_invalid, 
                                     bg="#FF4444", fg="white", font=("Arial", 9, "bold"))
        self.invalid_btn.pack(side=tk.LEFT, padx=5)

        # 标注有效按钮 (绿色)
        self.valid_btn = tk.Button(top_frame, text="标注有效", command=self.mark_valid, 
                                   bg="#44BB44", fg="white", font=("Arial", 9, "bold"))
        self.valid_btn.pack(side=tk.LEFT, padx=5)

        # 分页控制区域
        self.pagination_frame = ttk.Frame(self, padding="5")
        self.pagination_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.prev_btn = ttk.Button(self.pagination_frame, text="上一页", command=self.prev_page)
        self.prev_btn.pack(side=tk.LEFT, padx=5)

        self.page_label = ttk.Label(self.pagination_frame, text="第 1 页 / 共 1 页")
        self.page_label.pack(side=tk.LEFT, padx=10)

        self.next_btn = ttk.Button(self.pagination_frame, text="下一页", command=self.next_page)
        self.next_btn.pack(side=tk.LEFT, padx=5)

        ttk.Label(self.pagination_frame, text="每页:").pack(side=tk.LEFT, padx=(20, 5))
        self.page_size_combo = ttk.Combobox(self.pagination_frame, values=[20, 50, 100, 200], width=5)
        self.page_size_combo.set(self.page_size)
        self.page_size_combo.pack(side=tk.LEFT)
        self.page_size_combo.bind("<<ComboboxSelected>>", self.on_page_size_change)

        # 数据列表展示区域 (放在分页之后 pack，但因为分页是 side=BOTTOM，所以它会占据剩余空间)
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

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.load_data()

    def next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.load_data()

    def on_page_size_change(self, event):
        self.page_size = int(self.page_size_combo.get())
        self.current_page = 1
        self.load_data()

    def load_data(self):
        # 创建标记表
        create_marks_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {self.mark_table_name} (
            market_a_id VARCHAR(255) NOT NULL,
            market_b_id VARCHAR(255) NOT NULL,
            mark VARCHAR(255) NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=OLAP
        UNIQUE KEY(market_a_id, market_b_id)
        DISTRIBUTED BY HASH(market_a_id) BUCKETS 5
        PROPERTIES ("replication_num" = "1");
        """
        
        # 为了分页且支持 Python 过滤，我们需要分两种策略：
        # 1. 如果数据量不大，继续获取全量然后在内存中分页
        # 2. 如果数据量很大，需要在 SQL 中过滤（但 SQL 难以过滤 check_combination_rules）
        # 目前看来采取“全量获取 -> 内存过滤 -> 内存分页”的策略对当前规模比较稳妥
        
        query = text(f"""
            SELECT m.market_a_id, m.market_b_id, m.market_a_question, m.market_b_question, 
                   m.matrix, m.market_a_generated_questions, m.market_b_generated_questions 
            FROM {self.table_name} m
            LEFT JOIN {self.mark_table_name} marks 
              ON m.market_a_id = marks.market_a_id AND m.market_b_id = marks.market_b_id
            WHERE marks.mark IS NULL
        """)
        
        # 清空当前列表
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.current_data = []

        try:
            with polymarket_engine.begin() as conn:
                conn.execute(text(create_marks_table_sql))
                
            filtered_rows = []
            with polymarket_engine.connect() as conn:
                result = conn.execute(query)
                for row in result:
                    m_a_id, m_b_id, q_a, q_b, matrix_raw, gen_q_a_raw, gen_q_b_raw = row
                    combinations = parse_matrix(matrix_raw)
                    if combinations and check_combination_rules(combinations):
                        filtered_rows.append(row)

            # 内存分页
            total_count = len(filtered_rows)
            self.total_pages = max(1, (total_count + self.page_size - 1) // self.page_size)
            
            # 修正当前页码
            if self.current_page > self.total_pages:
                self.current_page = self.total_pages
            
            start_idx = (self.current_page - 1) * self.page_size
            end_idx = start_idx + self.page_size
            page_rows = filtered_rows[start_idx:end_idx]

            for row in page_rows:
                m_a_id, m_b_id, q_a, q_b, matrix_raw, gen_q_a_raw, gen_q_b_raw = row
                # 格式化生成的问题
                gen_q_a = str(gen_q_a_raw)
                gen_q_b = str(gen_q_b_raw)
                
                item_id = self.tree.insert("", tk.END, values=(m_a_id, m_b_id, q_a, q_b, gen_q_a, gen_q_b))
                self.current_data.append({"id": item_id, "a_id": m_a_id, "b_id": m_b_id})

            # 更新分页标签
            self.page_label.config(text=f"第 {self.current_page} 页 / 共 {self.total_pages} 页 (总数: {total_count})")
            
        except Exception as e:
            messagebox.showerror("加载错误", f"从数据库获取数据失败: {str(e)}")

    def mark_invalid(self):
        self._update_mark('n', "无效")

    def mark_valid(self):
        self._update_mark('y', "有效")

    def _update_mark(self, mark_value, label):
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("未选择", "请先选择要标注的数据")
            return
        
        if not messagebox.askyesno("确认", f"确定要将选中的 {len(selected_items)} 条数据标注为{label}吗？"):
            return

        to_update = []
        for item_id in selected_items:
            for data in self.current_data:
                if data["id"] == item_id:
                    to_update.append((data["a_id"], data["b_id"]))
                    break

        try:
            # 将标记写入专门的标记表，避免 StarRocks 不支持部分列更新的问题
            update_sql = text(f"INSERT INTO {self.mark_table_name} (market_a_id, market_b_id, mark) VALUES (:a_id, :b_id, '{mark_value}')")
            
            with polymarket_engine.begin() as conn:
                for a_id, b_id in to_update:
                    conn.execute(update_sql, {"a_id": a_id, "b_id": b_id})
            
            messagebox.showinfo("成功", f"已成功将 {len(to_update)} 条数据标注为{label}")
            self.load_data()
        except Exception as e:
            messagebox.showerror("更新错误", f"更新数据库失败: {str(e)}")

class MarkedFifaMatrixView(ttk.Frame):
    def __init__(self, parent, redis_client):
        super().__init__(parent)
        self.redis_client = redis_client
        self.table_name = "polymarket_fifa_matrix"
        self.mark_table_name = "polymarket_fifa_matrix_marks"
        self._init_ui()

    def _init_ui(self):
        # 顶部操作区域
        top_frame = ttk.Frame(self, padding="10")
        top_frame.pack(fill=tk.X)

        self.load_btn = ttk.Button(top_frame, text="刷新已标记数据", command=self.load_data)
        self.load_btn.pack(side=tk.LEFT, padx=5)

        self.export_btn = ttk.Button(top_frame, text="导出 JSON", command=self.export_to_json)
        self.export_btn.pack(side=tk.LEFT, padx=5)

        self.export_csv_btn = ttk.Button(top_frame, text="导出 CSV", command=self.export_to_csv)
        self.export_csv_btn.pack(side=tk.LEFT, padx=5)

        # 数据列表展示区域
        columns = ("a_id", "b_id", "gen_q_a", "tokens_a", "gen_q_b", "tokens_b")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        
        self.tree.heading("a_id", text="Market A ID")
        self.tree.heading("b_id", text="Market B ID")
        self.tree.heading("gen_q_a", text="Market A Questions")
        self.tree.heading("tokens_a", text="Market A Tokens")
        self.tree.heading("gen_q_b", text="Market B Questions")
        self.tree.heading("tokens_b", text="Market B Tokens")
        
        self.tree.column("a_id", width=100)
        self.tree.column("b_id", width=100)
        self.tree.column("gen_q_a", width=300)
        self.tree.column("tokens_a", width=200)
        self.tree.column("gen_q_b", width=300)
        self.tree.column("tokens_b", width=200)

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

    def show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.menu.post(event.x_root, event.y_root)
            self.clicked_item = item
            self.clicked_column = self.tree.identify_column(event.x)

    def copy_cell(self):
        if hasattr(self, 'clicked_item') and hasattr(self, 'clicked_column'):
            col_idx = int(self.clicked_column.replace('#', '')) - 1
            values = self.tree.item(self.clicked_item, "values")
            if 0 <= col_idx < len(values):
                content = str(values[col_idx])
                self.clipboard_clear()
                self.clipboard_append(content)

    def export_to_json(self):
        items = self.tree.get_children()
        if not items:
            messagebox.showwarning("导出警告", "没有可导出的数据")
            return

        export_data = []
        for item in items:
            values = self.tree.item(item, "values")
            if len(values) >= 6:
                # 解析 Token 字符串回列表
                tokens_a = [t.strip() for t in str(values[3]).split(",") if t.strip()]
                tokens_b = [t.strip() for t in str(values[5]).split(",") if t.strip()]
                
                entry = {
                    "market_a": {
                        "id": values[0],
                        "question": values[2],
                        "tokens": tokens_a
                    },
                    "market_b": {
                        "id": values[1],
                        "question": values[4],
                        "tokens": tokens_b
                    }
                }
                export_data.append(entry)

        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="导出数据为 JSON",
            initialfile="marked_fifa_markets.json"
        )

        if file_path:
            try:
                import json
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=4, ensure_ascii=False)
                messagebox.showinfo("导出成功", f"数据已成功导出至: {file_path}")
            except Exception as e:
                messagebox.showerror("导出错误", f"导出文件失败: {str(e)}")

    def export_to_csv(self):
        items = self.tree.get_children()
        if not items:
            messagebox.showwarning("导出警告", "没有可导出的数据")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="导出数据为 CSV",
            initialfile="marked_fifa_markets.csv"
        )

        if file_path:
            try:
                import csv
                with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    # 写入表头
                    headers = [self.tree.heading(col)["text"] for col in self.tree["columns"]]
                    writer.writerow(headers)
                    # 写入内容
                    for item in items:
                        writer.writerow(self.tree.item(item, "values"))
                messagebox.showinfo("导出成功", f"数据已成功导出至: {file_path}")
            except Exception as e:
                messagebox.showerror("导出错误", f"导出文件失败: {str(e)}")

    def load_data(self):
        # 清空当前列表
        for i in self.tree.get_children():
            self.tree.delete(i)

        query = text(f"""
            SELECT m.market_a_id, m.market_b_id, m.market_a_generated_questions, m.market_b_generated_questions
            FROM {self.table_name} m
            JOIN {self.mark_table_name} marks 
              ON m.market_a_id = marks.market_a_id AND m.market_b_id = marks.market_b_id
            WHERE marks.mark = 'y'
        """)

        try:
            # 获取 Redis 缓存数据以提取 Token
            all_redis_data = self.redis_client.hgetall(REDIS_KEY_ACTIVE_MARKETS)
            
            with polymarket_engine.connect() as conn:
                result = conn.execute(query)
                for row in result:
                    m_a_id, m_b_id, gen_q_a_raw, gen_q_b_raw = row
                    
                    # 获取 A 和 B 的 Token
                    tokens_a = self._get_tokens(m_a_id, all_redis_data)
                    tokens_b = self._get_tokens(m_b_id, all_redis_data)
                    
                    # 格式化显示
                    gen_q_a = str(gen_q_a_raw)
                    gen_q_b = str(gen_q_b_raw)
                    
                    self.tree.insert("", tk.END, values=(
                        m_a_id, m_b_id, 
                        gen_q_a, ", ".join(tokens_a),
                        gen_q_b, ", ".join(tokens_b)
                    ))
                    
        except Exception as e:
            messagebox.showerror("加载错误", f"获取已标记数据失败: {str(e)}")

    def _get_tokens(self, market_id, all_redis_data) -> List[str]:
        if market_id not in all_redis_data:
            return ["N/A"]
        try:
            market = json.loads(all_redis_data[market_id])
            clob_token_ids = market.get("clobTokenIds")
            if clob_token_ids:
                if isinstance(clob_token_ids, str):
                    clob_token_ids = json.loads(clob_token_ids)
                if isinstance(clob_token_ids, list):
                    return clob_token_ids
        except:
            pass
        return ["N/A"]

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
        
        view_menu.add_command(label="市场搜索 (关键字/ID/Token)", command=lambda: self.show_view("search"))
        view_menu.add_command(label="矩阵分析展示", command=lambda: self.show_view("matrix"))
        view_menu.add_command(label="FIFA 矩阵分析展示", command=lambda: self.show_view("fifa_matrix"))
        view_menu.add_command(label="FIFA 已标记有效", command=lambda: self.show_view("fifa_marked"))
        view_menu.add_separator()
        view_menu.add_command(label="退出", command=self.quit)

    def _init_views(self):
        self.views["search"] = MarketSearchView(self.container, self.redis_client)
        self.views["matrix"] = MatrixAnalyzerView(self.container)
        self.views["fifa_matrix"] = MatrixAnalyzerView(self.container, table_name="polymarket_fifa_matrix", mark_table_name="polymarket_fifa_matrix_marks")
        self.views["fifa_marked"] = MarkedFifaMatrixView(self.container, self.redis_client)
        
        for view in self.views.values():
            view.place(relx=0, rely=0, relwidth=1, relheight=1)

    def show_view(self, view_name):
        view = self.views.get(view_name)
        if view:
            view.tkraise()
            if view_name in ["matrix", "fifa_matrix", "fifa_marked"]:
                view.load_data()
            self.title(f"Polymarket 综合工具 - {view_name.upper()}")

if __name__ == "__main__":
    app = MarketViewer()
    app.mainloop()
