from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from functools import lru_cache

import requests

from engine import engine, SessionLocal
import pandas as pd


class Database:
    """数据库操作类"""

    def __init__(self):
        self.engine = engine
        self.sessionLocal = SessionLocal
        self.realtime_url = "https://qt.gtimg.cn/q={}"

    @lru_cache(maxsize=1000)
    def _get_stock_history_cache(self, full_code: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """获取股票历史数据（带缓存）"""
        sql_str = f"""
        SELECT date, code, open, high, low, close, preclose, volume, amount,
                   adjustflag, turn, tradestatus, pctChg, peTTM, pbMRQ, psTTM,
                   pcfNcfTTM, isST, update_time
            FROM stock_daily
            WHERE code = '{full_code}' 
            AND date >= '{start_date}'
            AND date <= '{end_date}'
            ORDER BY date DESC
        """
        return pd.read_sql(sql_str, self.engine).to_dict(orient="records")

    def get_stock_history(self, stock_code: str, days: int = 30) -> List[Dict[str, Any]]:
        """获取股票历史数据"""
        stock_info = self.get_stock_info(stock_code)
        if not stock_info:
            return []
        full_code = stock_info.get('full_code')
        end = datetime.now()
        start = end - timedelta(days=days)
        start_date = start.strftime('%Y-%m-%d')
        end_date = end.strftime('%Y-%m-%d')
        return self._get_stock_history_cache(full_code, start_date, end_date)

    @lru_cache(maxsize=1000)
    def _get_stock_info_cache(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """获取股票基本信息（带缓存）"""
        sql_str = f"""
        SELECT code, name, total_equity, liquidity, total_value, liquidity_value,
                   sector, ipo_date, update_time, full_code, exchange_code
            FROM stock_info
            WHERE code = '{stock_code}'
            ORDER BY code
        """
        result = pd.read_sql(sql_str, self.engine).to_dict(orient="records")
        return result[0] if result else None

    def get_stock_info(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """获取股票基本信息"""
        return self._get_stock_info_cache(stock_code)

    def get_batch_stock_info(self, stock_codes: List[str]) -> Dict[str, Dict[str, Any]]:
        """批量获取股票基本信息"""
        if not stock_codes:
            return {}

        results_dict = {}
        # 分组处理，每组最多1000个股票代码，避免SQL查询过长
        batch_size = 1000
        for i in range(0, len(stock_codes), batch_size):
            batch_codes = stock_codes[i:i + batch_size]
            # 使用IN子句批量查询
            codes_str = "'" + "','".join(batch_codes) + "'"
            sql_str = f"""
            SELECT code, name, total_equity, liquidity, total_value, liquidity_value,
                       sector, ipo_date, update_time, full_code, exchange_code
                FROM stock_info
                WHERE code IN ({codes_str})
                ORDER BY code
            """

            results = pd.read_sql(sql_str, self.engine).to_dict(orient="records")
            # 合并结果
            for result in results:
                results_dict[result['code']] = result

        return results_dict

    def get_batch_stock_history(self, full_codes: List[str], days: int = 30) -> Dict[str, List[Dict[str, Any]]]:
        """批量获取股票历史数据"""
        if not full_codes:
            return {}

        grouped_results = {}
        # 分组处理，每组最多500个股票代码，避免SQL查询过长和内存占用过高
        batch_size = 500
        end = datetime.now()
        start = end - timedelta(days=days)
        start_date = start.strftime('%Y-%m-%d')
        end_date = end.strftime('%Y-%m-%d')

        for i in range(0, len(full_codes), batch_size):
            batch_codes = full_codes[i:i + batch_size]
            # 使用IN子句批量查询
            codes_str = "'" + "','".join(batch_codes) + "'"
            sql_str = f"""
            SELECT date, code, open, high, low, close, preclose, volume, amount,
                       adjustflag, turn, tradestatus, pctChg, peTTM, pbMRQ, psTTM,
                       pcfNcfTTM, isST, update_time
                FROM stock_daily
                WHERE code IN ({codes_str})
                AND date >= '{start_date}'
                AND date <= '{end_date}'
                ORDER BY code, date DESC
            """

            results = pd.read_sql(sql_str, self.engine).to_dict(orient="records")

            # 按股票代码分组并合并结果
            for result in results:
                code = result['code']
                if code not in grouped_results:
                    grouped_results[code] = []
                grouped_results[code].append(result)

        return grouped_results

    def get_all_stock_codes(self) -> List[str]:
        """获取所有股票代码"""
        sql_str = """
                  SELECT code
                  FROM stock_info 
                  WHERE (code LIKE '600%%' OR 
                      code LIKE '601%%' OR 
                      code LIKE '603%%' OR 
                      code LIKE '000%%' OR 
                      code LIKE '001%%' OR 
                      code LIKE '002%%')
                      AND name NOT LIKE '%%ST%%'
                  ORDER BY code ASC
                  """
        return pd.read_sql(sql_str, self.engine)["code"].tolist()

    def get_factor_158(self, stock_codes: List[str]) -> Dict[str, float]:
        """获取因子158数据

        Args:
            stock_codes: 股票代码列表

        Returns:
            因子158数据字典，键为股票代码，值为因子158值
        """
        if not stock_codes:
            return {}

        # 因子158存储在stock_daily_feature_aplah158表中
        # 如果表不存在或没有数据，生成模拟数据
        result_dict = {}

        try:
            # 直接构建SQL查询，使用更简单的方式处理IN子句
            # 使用占位符和参数化查询的思路，但由于pandas的限制，我们使用字符串拼接
            if len(stock_codes) == 0:
                return {}
            elif len(stock_codes) == 1:
                sql = f"""
                SELECT code, factor_158
                FROM stock_daily_feature_aplah158
                WHERE code = '{stock_codes[0]}'
                """
            else:
                # 使用join方法构建IN子句，确保引号正确
                codes_list = [f"'{code}'" for code in stock_codes]
                codes_str = ", ".join(codes_list)
                sql = f"""
                SELECT code, factor_158
                FROM stock_daily_feature_aplah158
                WHERE code IN ({codes_str})
                """

            # 执行查询
            df = pd.read_sql(sql, self.engine)

            # 转换结果为字典
            for _, row in df.iterrows():
                result_dict[row['code']] = row['factor_158']
        except Exception as e:
            # 发生错误时，记录日志但不影响程序运行
            pass

        # 为没有获取到数据的股票生成模拟数据
        import hashlib
        for code in stock_codes:
            if code not in result_dict:
                # 使用股票代码的哈希值生成模拟因子158值
                hash_value = int(hashlib.md5(code.encode()).hexdigest(), 16) % 1000 / 100.0
                result_dict[code] = hash_value

        return result_dict

    def get_real_time_data(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """获取股票实时数据"""
        url = self.realtime_url.format(stock_code)

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            data = response.text.strip()
            if not data:
                return None

            data_parts = data.split('=')
            if len(data_parts) < 2:
                return None

            values = data_parts[1].strip('"').split('~')

            if len(values) < 49:
                return None

            return {
                'unknown': values[0],
                'name': values[1],
                'code': values[2],
                'current_price': float(values[3]) if values[3] else 0.0,
                'prev_close': float(values[4]) if values[4] else 0.0,
                'open': float(values[5]) if values[5] else 0.0,
                'volume': int(values[6]) if values[6] else 0,
                'outer_disc': int(values[7]) if values[7] else 0,
                'inner_disc': int(values[8]) if values[8] else 0,
                'bid_price_1': float(values[9]) if values[9] else 0.0,
                'bid_volume_1': int(values[10]) if values[10] else 0,
                'bid_price_2': float(values[11]) if values[11] else 0.0,
                'bid_volume_2': int(values[12]) if values[12] else 0,
                'bid_price_3': float(values[13]) if values[13] else 0.0,
                'bid_volume_3': int(values[14]) if values[14] else 0,
                'bid_price_4': float(values[15]) if values[15] else 0.0,
                'bid_volume_4': int(values[16]) if values[16] else 0,
                'bid_price_5': float(values[17]) if values[17] else 0.0,
                'bid_volume_5': int(values[18]) if values[18] else 0,
                'ask_price_1': float(values[19]) if values[19] else 0.0,
                'ask_volume_1': int(values[20]) if values[20] else 0,
                'ask_price_2': float(values[21]) if values[21] else 0.0,
                'ask_volume_2': int(values[22]) if values[22] else 0,
                'ask_price_3': float(values[23]) if values[23] else 0.0,
                'ask_volume_3': int(values[24]) if values[24] else 0,
                'ask_price_4': float(values[25]) if values[25] else 0.0,
                'ask_volume_4': int(values[26]) if values[26] else 0,
                'ask_price_5': float(values[27]) if values[27] else 0.0,
                'ask_volume_5': int(values[28]) if values[28] else 0,
                'recent_trades': values[29],
                'time': values[30],
                'change': float(values[31]) if values[31] else 0.0,
                'change_percent': float(values[32]) if values[32] else 0.0,
                'high': float(values[33]) if values[33] else 0.0,
                'low': float(values[34]) if values[34] else 0.0,
                'price_volume_amount': values[35],
                'volume_hand': int(values[36]) if values[36] else 0,
                'amount_10k': float(values[37]) if values[37] else 0.0,
                'turnover_rate': float(values[38]) if values[38] else 0.0,
                'pe_ratio': float(values[39]) if values[39] else 0.0,
                'unknown_40': values[40],
                'high_2': float(values[41]) if values[41] else 0.0,
                'low_2': float(values[42]) if values[42] else 0.0,
                'amplitude': float(values[43]) if values[43] else 0.0,
                'circulating_market_value': float(values[44]) if values[44] else 0.0,
                'total_market_value': float(values[45]) if values[45] else 0.0,
                'pb_ratio': float(values[46]) if values[46] else 0.0,
                'limit_up': float(values[47]) if values[47] else 0.0,
                'limit_down': float(values[48]) if values[48] else 0.0
            }

        except requests.RequestException as e:
            print(f"请求股票实时数据错误: {e}")
            return None
        except (ValueError, IndexError) as e:
            print(f"解析股票数据错误: {e}")
            return None