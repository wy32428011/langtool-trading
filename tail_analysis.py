import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta

import pandas as pd

from agent import Agent
from analysis import Analysis
from database import Database


# 全市场扫描间隔。
FULL_SCAN_INTERVAL_SECONDS = 180
# 重点池扫描间隔。
FOCUS_SCAN_INTERVAL_SECONDS = 30
# 重点股票池上限。
FOCUS_UNIVERSE_LIMIT = 200
# LLM 精判候选上限。
LLM_CANDIDATE_LIMIT = 15
# LLM 精判最大并发，保守控制调用压力。
LLM_REFINE_MAX_WORKERS = 4
# Excel 输出字段顺序，保证空结果也能带表头。
RESULT_COLUMNS = [
    "stock_code",
    "stock_name",
    "analysis_time",
    "current_price",
    "change_percent",
    "turnover_rate",
    "volume_ratio",
    "tail_price_change",
    "tail_amount_delta",
    "order_book_imbalance",
    "tail_strength_score",
    "selection_reason",
    "recommended_buy_price",
    "next_day_target_price",
    "next_day_exit_rule",
    "recommendation",
    "confidence",
    "risk_warning",
]


@dataclass
class TailSnapshot:
    # 股票代码。
    stock_code: str
    # 股票名称。
    stock_name: str
    # 带交易所前缀代码。
    full_code: str
    # 当前价。
    current_price: float
    # 涨跌幅。
    change_percent: float
    # 换手率。
    turnover_rate: float
    # 成交额，单位万元。
    amount_10k: float
    # 成交量，单位手。
    volume_hand: int
    # 买盘总量。
    bid_total: int
    # 卖盘总量。
    ask_total: int
    # 最高价。
    high: float
    # 最低价。
    low: float
    # 抓取时间。
    captured_at: datetime


class TailAnalysis:
    """尾盘扫描骨架。"""

    def __init__(
        self,
        start_time: str = "14:30",
        deadline_time: str = "14:50",
        max_workers: int = 80,
        top_n: int = 10,
    ):
        # 复用现有数据库能力。
        self.db = Database()
        # 复用现有分析能力。
        self.analysis = Analysis()
        # 预留后续 Agent 接入点。
        self.agent_cls = Agent
        # 输出目录沿用仓库约定。
        self.output_dir = "output"
        # 基线快照缓存。
        self.baseline_snapshots = {}
        # 所有已采集快照。
        self.snapshot_history = {}
        # 最新快照缓存。
        self.latest_snapshots = {}
        # 最新排序结果。
        self.latest_ranked = []
        # 稳定候选池，避免最后一轮局部刷新丢失全市场候选。
        self.candidate_pool = {}
        # 重点关注股票池。
        self.focus_codes = []
        # 保存入口参数。
        self.start_time = start_time
        self.deadline_time = deadline_time
        self.max_workers = max_workers
        self.top_n = top_n

        # 若输出目录不存在则创建。
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def _parse_clock(self, clock_text: str) -> datetime:
        """将 HH:MM 文本解析为当天时间。"""
        parsed = datetime.strptime(clock_text, "%H:%M")
        now = datetime.now()
        return now.replace(hour=parsed.hour, minute=parsed.minute, second=0, microsecond=0)

    def _resolve_window(self) -> tuple[datetime, datetime]:
        """解析扫描时间窗口。"""
        start_at = self._parse_clock(self.start_time)
        deadline_at = self._parse_clock(self.deadline_time)

        # 若截止时间早于开始时间，则顺延到次日，避免窗口无效。
        if deadline_at < start_at:
            deadline_at = deadline_at + timedelta(days=1)

        return start_at, deadline_at

    def _load_static_context(self) -> dict:
        """预载全市场静态上下文，减少运行期重复查询。"""
        try:
            stock_codes = self.db.get_all_stock_codes()
        except Exception as exc:
            print(f"加载股票列表失败: {exc}")
            return {}

        if not stock_codes:
            print("未获取到股票列表。")
            return {}

        try:
            stock_info_map = self.db.get_batch_stock_info(stock_codes)
        except Exception as exc:
            print(f"加载股票静态信息失败: {exc}")
            return {}

        full_codes = []
        for stock_code in stock_codes:
            stock_info = stock_info_map.get(stock_code) or {}
            full_code = stock_info.get("full_code")
            if full_code:
                full_codes.append(full_code)

        try:
            history_map = self.db.get_batch_stock_history(full_codes, days=120)
        except Exception as exc:
            print(f"加载股票历史数据失败: {exc}")
            history_map = {}

        context_map = {}
        for stock_code in stock_codes:
            stock_info = stock_info_map.get(stock_code)
            if not stock_info:
                continue

            full_code = stock_info.get("full_code")
            history_data = history_map.get(full_code, []) if full_code else []
            indicators = self.analysis._calculate_indicators(history_data)

            context_map[stock_code] = {
                "stock_code": stock_code,
                "stock_name": stock_info.get("name", "未知"),
                "full_code": full_code,
                "history_data": history_data,
                "indicators": indicators,
            }

        print(f"静态预载完成，共 {len(context_map)} 只股票。")
        return context_map

    def _fetch_realtime_batch(self, context_map: dict, stock_codes: list[str]) -> dict:
        """并发抓取一批实时行情，并落地为快照。"""
        if not stock_codes:
            return {}

        snapshots = {}

        def fetch_one(stock_code: str):
            # 若上下文缺失，则直接跳过。
            context = context_map.get(stock_code)
            if not context:
                return None

            full_code = context.get("full_code")
            if not full_code:
                return None

            realtime_data = self.db.get_real_time_data(full_code)
            if not realtime_data:
                return None

            current_price = float(realtime_data.get("current_price") or 0)
            prev_close = float(realtime_data.get("prev_close") or 0)
            if current_price <= 0 or prev_close <= 0:
                return None

            bid_total = sum(int(realtime_data.get(f"bid_volume_{level}") or 0) for level in range(1, 6))
            ask_total = sum(int(realtime_data.get(f"ask_volume_{level}") or 0) for level in range(1, 6))

            snapshot = TailSnapshot(
                stock_code=stock_code,
                stock_name=context.get("stock_name", realtime_data.get("name", "未知")),
                full_code=full_code,
                current_price=current_price,
                change_percent=float(realtime_data.get("change_percent") or 0),
                turnover_rate=float(realtime_data.get("turnover_rate") or 0),
                amount_10k=float(realtime_data.get("amount_10k") or 0),
                volume_hand=int(realtime_data.get("volume_hand") or 0),
                bid_total=bid_total,
                ask_total=ask_total,
                high=float(realtime_data.get("high") or current_price),
                low=float(realtime_data.get("low") or current_price),
                captured_at=datetime.now(),
            )
            return stock_code, snapshot

        with ThreadPoolExecutor(max_workers=min(self.max_workers, 20)) as executor:
            future_map = {
                executor.submit(fetch_one, stock_code): stock_code
                for stock_code in stock_codes
                if stock_code in context_map
            }
            for future in as_completed(future_map):
                try:
                    result = future.result()
                except Exception as exc:
                    print(f"抓取实时行情失败: {exc}")
                    continue

                if not result:
                    continue

                stock_code, snapshot = result
                snapshots[stock_code] = snapshot
                self.latest_snapshots[stock_code] = snapshot
                self.snapshot_history.setdefault(stock_code, []).append(snapshot)

        return snapshots

    def _capture_baseline_if_needed(self, snapshots: dict, start_at: datetime) -> None:
        """为 14:30 之后首次出现的股票保存基准快照。"""
        for stock_code, snapshot in snapshots.items():
            if stock_code in self.baseline_snapshots:
                continue
            if snapshot.captured_at < start_at:
                continue
            self.baseline_snapshots[stock_code] = snapshot

    def _build_tail_metrics(self, stock_code: str, snapshot: TailSnapshot, start_at: datetime) -> dict:
        """基于尾盘区间快照构建增量指标。"""
        history = self.snapshot_history.get(stock_code, [])
        tail_snapshots = [item for item in history if item.captured_at >= start_at]
        baseline = self.baseline_snapshots.get(stock_code)

        if not baseline and tail_snapshots:
            baseline = tail_snapshots[0]
        if not baseline:
            baseline = snapshot

        tail_high = max((item.high or item.current_price) for item in tail_snapshots) if tail_snapshots else snapshot.high
        ask_total = snapshot.ask_total or 0
        bid_total = snapshot.bid_total or 0
        total_order = bid_total + ask_total
        order_book_imbalance = ((bid_total - ask_total) / total_order) if total_order > 0 else 0
        pullback_base = tail_high if tail_high and tail_high > 0 else snapshot.current_price
        pullback_from_high = ((snapshot.current_price - pullback_base) / pullback_base * 100) if pullback_base > 0 else 0
        tail_price_change = ((snapshot.current_price - baseline.current_price) / baseline.current_price * 100) if baseline.current_price > 0 else 0

        return {
            "tail_price_change": round(tail_price_change, 2),
            "tail_amount_delta": round(snapshot.amount_10k - baseline.amount_10k, 2),
            "tail_turnover_delta": round(snapshot.turnover_rate - baseline.turnover_rate, 2),
            "order_book_imbalance": round(order_book_imbalance, 4),
            "pullback_from_high": round(pullback_from_high, 2),
        }

    def _score_candidate(self, context: dict, snapshot: TailSnapshot, start_at: datetime) -> dict | None:
        """按快筛规则打分，并返回候选结果。"""
        indicators = context.get("indicators") or {}
        metrics = self._build_tail_metrics(snapshot.stock_code, snapshot, start_at)
        ma5 = indicators.get("ma5")
        volume_ratio = float(indicators.get("volume_ratio") or 0)

        # 先执行硬性规则，未通过则不进入候选池。
        if snapshot.change_percent <= 0:
            return None
        if snapshot.change_percent >= 9.5:
            return None
        if snapshot.turnover_rate < 2:
            return None
        if metrics["tail_price_change"] <= 0:
            return None
        if ma5 and snapshot.current_price < ma5:
            return None
        if volume_ratio < 1.1:
            return None

        # 使用直接加权方式形成尾盘强度分，便于实时排序。
        tail_strength_score = 0.0
        tail_strength_score += min(snapshot.change_percent, 9.0) * 2.0
        tail_strength_score += min(snapshot.turnover_rate, 15.0) * 1.2
        tail_strength_score += min(metrics["tail_price_change"], 5.0) * 5.0
        tail_strength_score += min(max(metrics["tail_amount_delta"], 0.0) / 1000.0, 10.0) * 1.5
        tail_strength_score += min(max(metrics["tail_turnover_delta"], 0.0), 5.0) * 2.5
        tail_strength_score += max(volume_ratio - 1.0, 0.0) * 8.0
        tail_strength_score += metrics["order_book_imbalance"] * 10.0
        tail_strength_score += max(metrics["pullback_from_high"], -2.0) * 1.5
        if ma5 and snapshot.current_price >= ma5:
            tail_strength_score += 3.0

        return {
            "stock_code": snapshot.stock_code,
            "stock_name": snapshot.stock_name,
            "full_code": context.get("full_code"),
            "analysis_time": snapshot.captured_at.strftime("%Y-%m-%d %H:%M:%S"),
            "current_price": round(snapshot.current_price, 2),
            "change_percent": round(snapshot.change_percent, 2),
            "turnover_rate": round(snapshot.turnover_rate, 2),
            "volume_ratio": round(volume_ratio, 2),
            "indicators": indicators,
            "tail_price_change": metrics["tail_price_change"],
            "tail_amount_delta": metrics["tail_amount_delta"],
            "tail_turnover_delta": metrics["tail_turnover_delta"],
            "order_book_imbalance": metrics["order_book_imbalance"],
            "pullback_from_high": metrics["pullback_from_high"],
            "tail_strength_score": round(tail_strength_score, 2),
        }

    def _rank_candidates(self, context_map: dict, snapshots: dict, start_at: datetime) -> list:
        """将当前快照批次转换为排序后的候选列表。"""
        candidates = []
        for stock_code, snapshot in snapshots.items():
            context = context_map.get(stock_code)
            if not context:
                continue
            candidate = self._score_candidate(context, snapshot, start_at)
            if candidate:
                candidates.append(candidate)

        ranked = sorted(
            candidates,
            key=lambda item: (
                item["tail_strength_score"],
                item["tail_amount_delta"],
                item["tail_price_change"],
                item["change_percent"],
            ),
            reverse=True,
        )

        # 将当前批次候选合并进稳定候选池，保留历史更强结果。
        for item in ranked:
            stock_code = item.get("stock_code")
            if not stock_code:
                continue
            cached_item = self.candidate_pool.get(stock_code)
            if not cached_item or item.get("tail_strength_score", 0) > cached_item.get("tail_strength_score", 0):
                self.candidate_pool[stock_code] = item

        # 最新排序结果基于整个稳定候选池生成，避免最终收口只看到最后一轮局部刷新。
        self.latest_ranked = sorted(
            self.candidate_pool.values(),
            key=lambda item: (
                item["tail_strength_score"],
                item["tail_amount_delta"],
                item["tail_price_change"],
                item["change_percent"],
            ),
            reverse=True,
        )
        self.focus_codes = [item["stock_code"] for item in self.latest_ranked[:FOCUS_UNIVERSE_LIMIT]]
        return ranked

    def _build_tail_prompt(self, item: dict) -> str:
        """构造尾盘专用精判提示词。"""
        indicators = item.get("indicators") or {}
        indicators_text = json.dumps(indicators, ensure_ascii=False) if indicators else "{}"
        extra_lines = []

        # 仅在字段存在时补充附加信息，避免提示词冗余。
        if item.get("pullback_from_high") is not None:
            extra_lines.append(f"- 尾盘相对区间高点回撤: {item.get('pullback_from_high')}%")
        if item.get("tail_turnover_delta") is not None:
            extra_lines.append(f"- 尾盘换手增量: {item.get('tail_turnover_delta')}%")
        if indicators:
            extra_lines.append(f"- 技术指标: {indicators_text}")

        extra_text = "\n".join(extra_lines)
        if extra_text:
            extra_text = f"\n{extra_text}"

        # 提示词严格聚焦尾盘买入、次日冲高卖出，不讨论中长期逻辑。
        prompt = f"""
你是一名A股超短交易员，只从“尾盘买入、次日冲高卖出”的角度评估下面这只候选股票是否值得参与。
请基于给定字段进行审慎判断，不要扩展无依据的信息，不要输出任何 JSON 以外的内容。

候选数据：
- 股票名称: {item.get('stock_name', '未知')}
- 股票代码: {item.get('stock_code', '未知')}
- 分析时间: {item.get('analysis_time', '')}
- 当前价格: {item.get('current_price', 0)}
- 当日涨跌幅: {item.get('change_percent', 0)}%
- 当前换手率: {item.get('turnover_rate', 0)}%
- 量比: {item.get('volume_ratio', 0)}
- 尾盘价格变化: {item.get('tail_price_change', 0)}%
- 尾盘成交额增量: {item.get('tail_amount_delta', 0)}万
- 委比失衡度: {item.get('order_book_imbalance', 0)}
- 尾盘强度得分: {item.get('tail_strength_score', 0)}{extra_text}

要求：
1. 只分析尾盘介入后，次日是否具备冲高卖出机会。
2. 如果不适合买入，也要明确说明核心原因。
3. recommended_buy_price 与 next_day_target_price 尽量给出明确数值；若确实不适合买入，可给出 0。
4. next_day_exit_rule 必须给出次日可执行的卖出/退出规则，不能空泛。
5. recommendation 只能是“买入”或“观望”。
6. confidence 必须是 0 到 1 之间的小数。
7. risk_warning 必须指出至少一个主要风险。
8. 严格返回 JSON，对象字段至少包含：
{{
  "selection_reason": "中文说明",
  "recommended_buy_price": 0,
  "next_day_target_price": 0,
  "next_day_exit_rule": "中文规则",
  "recommendation": "买入/观望",
  "confidence": 0.0,
  "risk_warning": "中文风险提示"
}}
"""
        return prompt.strip()

    def _extract_json_text(self, text: str) -> str:
        """从模型文本中提取 JSON 主体，兼容 fenced code block。"""
        if not text:
            return ""

        clean_text = text.strip()

        # 优先提取 ```json 代码块中的内容。
        fenced_match = re.search(r"```json\s*(.*?)\s*```", clean_text, flags=re.IGNORECASE | re.DOTALL)
        if fenced_match:
            return fenced_match.group(1).strip()

        # 兼容普通 ``` 代码块。
        generic_match = re.search(r"```\s*(.*?)\s*```", clean_text, flags=re.DOTALL)
        if generic_match:
            return generic_match.group(1).strip()

        # 若存在首尾大括号，则截取最外层 JSON 对象。
        start_index = clean_text.find("{")
        end_index = clean_text.rfind("}")
        if start_index != -1 and end_index != -1 and end_index > start_index:
            return clean_text[start_index : end_index + 1].strip()

        return clean_text

    def _fallback_refine_result(self, item: dict, error_message: str) -> dict:
        """当 LLM 调用或 JSON 解析失败时，构造兜底结果。"""
        fallback = dict(item)
        fallback.setdefault("analysis_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        fallback["selection_reason"] = f"LLM 精判失败，回退使用规则候选。原因: {error_message}"
        fallback["recommended_buy_price"] = item.get("current_price", 0)
        fallback["next_day_target_price"] = item.get("current_price", 0)
        fallback["next_day_exit_rule"] = "若次日未能冲高走强或开盘后快速转弱，则以观望为主并避免追价。"
        fallback["recommendation"] = "观望"
        fallback["confidence"] = 0.0
        fallback["risk_warning"] = f"模型输出不可用，需人工复核。{error_message}"
        return fallback

    def _parse_llm_json_result(self, item: dict, raw_text: str) -> dict:
        """解析模型 JSON 结果，失败时优雅回退。"""
        try:
            json_text = self._extract_json_text(raw_text)
            parsed = json.loads(json_text)
            if not isinstance(parsed, dict):
                raise ValueError("模型返回的 JSON 不是对象")
        except Exception as exc:
            return self._fallback_refine_result(item, str(exc))

        # 将 LLM 返回合并回原候选，保留规则阶段已有字段。
        merged = dict(item)
        merged.update(parsed)
        merged.setdefault("selection_reason", "")
        merged.setdefault("recommended_buy_price", item.get("current_price", 0))
        merged.setdefault("next_day_target_price", item.get("current_price", 0))
        merged.setdefault("next_day_exit_rule", "次日依据盘中强弱执行退出。")
        merged.setdefault("recommendation", "观望")
        merged.setdefault("confidence", 0.0)
        merged.setdefault("risk_warning", "")

        # 对关键字段做轻量规范化，避免排序时报错。
        try:
            merged["confidence"] = float(merged.get("confidence", 0) or 0)
        except Exception:
            merged["confidence"] = 0.0
        if merged["confidence"] < 0:
            merged["confidence"] = 0.0
        elif merged["confidence"] > 1:
            merged["confidence"] = 1.0

        for price_field in ["recommended_buy_price", "next_day_target_price"]:
            try:
                merged[price_field] = float(merged.get(price_field, 0) or 0)
            except Exception:
                merged[price_field] = 0.0

        recommendation = str(merged.get("recommendation", "观望") or "观望").strip()
        merged["recommendation"] = "买入" if recommendation == "买入" else "观望"
        merged["selection_reason"] = str(merged.get("selection_reason", "") or "")
        merged["next_day_exit_rule"] = str(merged.get("next_day_exit_rule", "") or "")
        merged["risk_warning"] = str(merged.get("risk_warning", "") or "")
        return merged

    def _llm_refine_candidate(self, item: dict) -> dict:
        """调用 LLM 对规则候选进行尾盘场景精判。"""
        prompt = self._build_tail_prompt(item)

        try:
            agent = self.agent_cls()
            llm = agent.get_agent()
            response = llm.invoke({"messages": [{"role": "user", "content": prompt}]})

            # 兼容 analysis.py 中已有的响应读取方式。
            if isinstance(response, dict) and "messages" in response:
                final_result = response["messages"][-1].content
            else:
                final_result = response.content if hasattr(response, "content") else str(response)

            return self._parse_llm_json_result(item, final_result)
        except Exception as exc:
            return self._fallback_refine_result(item, str(exc))

    def _finalize_candidates(self, ranked: list) -> tuple[list, list]:
        """对规则候选做 LLM 精判并产出最终入选结果。"""
        if not ranked:
            return [], []

        refine_targets = ranked[:LLM_CANDIDATE_LIMIT]
        refined = []

        # 并发控制保守一些，避免短时间内发起过多模型请求。
        with ThreadPoolExecutor(max_workers=min(LLM_REFINE_MAX_WORKERS, len(refine_targets))) as executor:
            future_map = {
                executor.submit(self._llm_refine_candidate, item): item.get("stock_code")
                for item in refine_targets
            }
            for future in as_completed(future_map):
                stock_code = future_map[future]
                try:
                    refined.append(future.result())
                except Exception as exc:
                    original_item = next((item for item in refine_targets if item.get("stock_code") == stock_code), {})
                    refined.append(self._fallback_refine_result(original_item, str(exc)))

        # 按“买入优先、信心优先、规则强度次之”进行最终排序。
        refined.sort(
            key=lambda item: (
                1 if item.get("recommendation") == "买入" else 0,
                float(item.get("confidence", 0) or 0),
                float(item.get("tail_strength_score", 0) or 0),
            ),
            reverse=True,
        )
        selected = refined[: self.top_n]
        return refined, selected

    def _build_result_frame(self, items: list) -> pd.DataFrame:
        """构造结果表，保证空列表也能输出标准表头。"""
        rows = []
        for item in items:
            row = {}
            for column in RESULT_COLUMNS:
                row[column] = item.get(column, "")
            rows.append(row)
        return pd.DataFrame(rows, columns=RESULT_COLUMNS)

    def _save_results(self, all_items: list, selected_items: list) -> tuple[str, str]:
        """将全量精判结果与最终入选结果写入 Excel。"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        scan_path = os.path.join(self.output_dir, f"tail_scan_{timestamp}.xlsx")
        selected_path = os.path.join(self.output_dir, f"tail_selected_{timestamp}.xlsx")

        all_df = self._build_result_frame(all_items)
        selected_df = self._build_result_frame(selected_items)

        # 直接输出为 Excel，空列表时 DataFrame 仍会保留表头。
        all_df.to_excel(scan_path, index=False)
        selected_df.to_excel(selected_path, index=False)

        print(f"尾盘全量结果已保存至: {scan_path}")
        print(f"尾盘精选结果已保存至: {selected_path}")
        return scan_path, selected_path

    def _print_live_top(self, ranked: list) -> None:
        """打印当前候选摘要。"""
        if not ranked:
            print("当前无符合条件的尾盘候选。")
            return

        print("=" * 120)
        print(f"尾盘候选摘要 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 展示前 {min(len(ranked), self.top_n)} 条")
        for index, item in enumerate(ranked[: self.top_n], start=1):
            print(
                f"{index:02d}. {item['stock_name']}({item['stock_code']}) "
                f"现价={item['current_price']:.2f} "
                f"涨幅={item['change_percent']:.2f}% "
                f"换手={item['turnover_rate']:.2f}% "
                f"量比={item['volume_ratio']:.2f} "
                f"尾盘涨幅={item['tail_price_change']:.2f}% "
                f"尾盘成交额增量={item['tail_amount_delta']:.2f}万 "
                f"委比={item['order_book_imbalance']:.4f} "
                f"得分={item['tail_strength_score']:.2f}"
            )
        print("=" * 120)

    def _monitor_until_deadline(self, context_map: dict, start_at: datetime, deadline_at: datetime) -> None:
        """以低频全扫和高频焦点刷新模式持续监控至截止时间。"""
        next_full_scan_at = start_at
        next_focus_scan_at = start_at

        while True:
            now = datetime.now()
            if now > deadline_at:
                break

            # 未到开始时间时只做等待，避免提前抓取干扰基准。
            if now < start_at:
                wait_seconds = min((start_at - now).total_seconds(), 1)
                if wait_seconds > 0:
                    time.sleep(wait_seconds)
                continue

            did_scan = False

            # 先做全市场低频扫描，刷新候选池和焦点池。
            if now >= next_full_scan_at:
                all_codes = list(context_map.keys())
                snapshots = self._fetch_realtime_batch(context_map, all_codes)
                self._capture_baseline_if_needed(snapshots, start_at)
                ranked = self._rank_candidates(context_map, snapshots, start_at)
                self._print_live_top(ranked)
                next_full_scan_at = now + timedelta(seconds=FULL_SCAN_INTERVAL_SECONDS)
                next_focus_scan_at = now + timedelta(seconds=FOCUS_SCAN_INTERVAL_SECONDS)
                did_scan = True

            # 若当前已有焦点池，则执行高频刷新。
            if not did_scan and self.focus_codes and now >= next_focus_scan_at:
                snapshots = self._fetch_realtime_batch(context_map, self.focus_codes)
                self._capture_baseline_if_needed(snapshots, start_at)
                ranked = self._rank_candidates(context_map, snapshots, start_at)
                self._print_live_top(ranked)
                next_focus_scan_at = now + timedelta(seconds=FOCUS_SCAN_INTERVAL_SECONDS)
                did_scan = True

            # 若尚未形成焦点池，则尽快补一次全扫，避免长时间无输出。
            if not did_scan and not self.focus_codes and now >= next_focus_scan_at:
                all_codes = list(context_map.keys())
                snapshots = self._fetch_realtime_batch(context_map, all_codes)
                self._capture_baseline_if_needed(snapshots, start_at)
                ranked = self._rank_candidates(context_map, snapshots, start_at)
                self._print_live_top(ranked)
                next_full_scan_at = now + timedelta(seconds=FULL_SCAN_INTERVAL_SECONDS)
                next_focus_scan_at = now + timedelta(seconds=FOCUS_SCAN_INTERVAL_SECONDS)
                did_scan = True

            # 控制循环频率，避免空转占满 CPU。
            if not did_scan:
                time.sleep(1)

    def run(self) -> None:
        """运行尾盘扫描。"""
        context_map = self._load_static_context()
        start_at, deadline_at = self._resolve_window()
        now = datetime.now()

        print(
            "尾盘扫描已启动 | "
            f"开始时间={start_at.strftime('%Y-%m-%d %H:%M:%S')} | "
            f"截止时间={deadline_at.strftime('%Y-%m-%d %H:%M:%S')} | "
            f"workers={self.max_workers} | top={self.top_n}"
        )

        # 静态上下文为空时也生成空结果文件，确保流程收口一致。
        if not context_map:
            print("静态上下文为空，无法继续扫描，将输出空结果文件。")
            self._save_results([], [])
            return

        # 若已过截止时间，则直接执行一次即时全扫并输出结果。
        if now > deadline_at:
            snapshots = self._fetch_realtime_batch(context_map, list(context_map.keys()))
            self._capture_baseline_if_needed(snapshots, start_at)
            ranked = self._rank_candidates(context_map, snapshots, start_at)
            self._print_live_top(ranked)
            refined, selected = self._finalize_candidates(ranked)
            if not refined:
                print("即时全扫结束，但未筛到候选，已输出空结果文件。")
            self._save_results(refined, selected)
            return

        # 否则进入监控循环，直到截止时间。
        self._monitor_until_deadline(context_map, start_at, deadline_at)
        self._print_live_top(self.latest_ranked)

        # 监控结束后，无论是否有候选，都进入最终收口与输出。
        refined, selected = self._finalize_candidates(self.latest_ranked)
        if not self.latest_ranked:
            print("监控结束后未获取到候选，已输出空结果文件。")
        self._save_results(refined, selected)
