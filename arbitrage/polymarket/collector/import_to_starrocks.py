import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy import text
from arbitrage.polymarket.engine import polymarket_engine
from arbitrage.polymarket.client import PolyMarketClient

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PolyMarketImporter:
    """
    Polymarket 数据导入器
    
    负责从 Polymarket API 抓取市场和事件数据，并将其清洗后导入到 StarRocks 数据库中。
    支持断点续爬（通过生成器分页获取）和批量插入。
    """
    def __init__(self):
        """
        初始化导入器
        
        设置数据库引擎和 API 客户端。
        """
        self.engine = polymarket_engine
        self.client = PolyMarketClient()

    def create_table_if_not_exists(self):
        """
        确保 StarRocks 中的 polymarket_markets 和 polymarket_events 表存在
        
        如果表不存在，则按照预定义的 Schema 创建 OLAP 表。
        """
        # 创建市场表
        create_markets_sql = """
        CREATE TABLE IF NOT EXISTS polymarket_markets (
            id VARCHAR(64) NOT NULL COMMENT '市场唯一标识 (Primary Key)',
            question STRING COMMENT '市场问题描述',
            conditionId VARCHAR(128) COMMENT '智能合约 condition ID',
            slug VARCHAR(255) COMMENT 'URL Slug',
            category VARCHAR(128) COMMENT '市场分类',
            marketType VARCHAR(64) COMMENT '市场类型 (如 normal)',
            active BOOLEAN COMMENT '是否为活跃状态',
            closed BOOLEAN COMMENT '是否已关闭',
            archived BOOLEAN COMMENT '是否已归档',
            createdAt DATETIME COMMENT '创建时间',
            updatedAt DATETIME COMMENT '最后更新时间',
            endDate DATETIME COMMENT '预期结束时间',
            endDateIso DATE COMMENT '预期结束日期 (ISO 格式)',
            closedTime DATETIME COMMENT '实际关闭时间',
            outcomes JSON COMMENT '结果选项数组 (例如 ["Yes", "No"])',
            outcomePrices JSON COMMENT '当前各个选项的价格/概率数组',
            clobTokenIds JSON COMMENT 'CLOB 订单簿对应的 Token ID 数组',
            umaResolutionStatuses JSON COMMENT 'UMA 预言机解决状态',
            volume STRING COMMENT '总交易量 (精确字符串)',
            volumeNum DOUBLE COMMENT '总交易量 (数值)',
            liquidity STRING COMMENT '总流动性 (精确字符串)',
            liquidityNum DOUBLE COMMENT '总流动性 (数值)',
            volume24hr DOUBLE COMMENT '24小时交易量',
            volume1wk DOUBLE COMMENT '1周交易量',
            volume1mo DOUBLE COMMENT '1月交易量',
            volume1yr DOUBLE COMMENT '1年交易量',
            volume1wkAmm DOUBLE COMMENT '1周 AMM 交易量',
            volume1moAmm DOUBLE COMMENT '1月 AMM 交易量',
            volume1yrAmm DOUBLE COMMENT '1年 AMM 交易量',
            volume1wkClob DOUBLE COMMENT '1周 CLOB 交易量',
            volume1moClob DOUBLE COMMENT '1月 CLOB 交易量',
            volume1yrClob DOUBLE COMMENT '1年 CLOB 交易量',
            lastTradePrice DOUBLE COMMENT '最新一笔成交价',
            bestBid DOUBLE COMMENT '最高买价 (买一)',
            bestAsk DOUBLE COMMENT '最低卖价 (卖一)',
            spread DOUBLE COMMENT '买卖价差',
            oneDayPriceChange DOUBLE COMMENT '24小时价格变动',
            oneHourPriceChange DOUBLE COMMENT '1小时价格变动',
            oneWeekPriceChange DOUBLE COMMENT '1周价格变动',
            oneMonthPriceChange DOUBLE COMMENT '1月价格变动',
            oneYearPriceChange DOUBLE COMMENT '1年价格变动',
            description STRING COMMENT '市场详细规则描述',
            twitterCardImage STRING COMMENT '推特分享卡片图片 URL',
            image STRING COMMENT '市场主图 URL',
            icon STRING COMMENT '市场图标 URL',
            marketMakerAddress VARCHAR(128) COMMENT '做市商钱包地址',
            creator VARCHAR(128) COMMENT '市场创建者地址',
            updatedBy INT COMMENT '最后更新者 ID',
            mailchimpTag VARCHAR(64) COMMENT 'Mailchimp 标签 ID',
            hasReviewedDates BOOLEAN COMMENT '是否审核过日期',
            readyForCron BOOLEAN COMMENT '是否就绪跑定时任务',
            fpmmLive BOOLEAN COMMENT 'FPMM 机制是否上线',
            ready BOOLEAN COMMENT '前端是否准备就绪',
            funded BOOLEAN COMMENT '是否已注资',
            cyom BOOLEAN COMMENT '是否为 Create Your Own Market',
            competitive DOUBLE COMMENT '竞争程度评分',
            pagerDutyNotificationEnabled BOOLEAN COMMENT '异常通知是否开启',
            approved BOOLEAN COMMENT '是否已审核批准',
            rewardsMinSize DOUBLE COMMENT '流动性奖励最小尺寸',
            rewardsMaxSpread DOUBLE COMMENT '流动性奖励最大价差',
            clearBookOnStart BOOLEAN COMMENT '启动时是否清空订单簿',
            manualActivation BOOLEAN COMMENT '是否需手动激活',
            negRiskOther BOOLEAN COMMENT '负风险其他标识',
            pendingDeployment BOOLEAN COMMENT '是否等待上链部署',
            deploying BOOLEAN COMMENT '是否部署中',
            rfqEnabled BOOLEAN COMMENT '是否开启询价机制',
            holdingRewardsEnabled BOOLEAN COMMENT '是否开启持仓奖励',
            feesEnabled BOOLEAN COMMENT '是否开启手续费',
            requiresTranslation BOOLEAN COMMENT '是否需要多语言翻译',
            feeType VARCHAR(64) COMMENT '手续费类型 (通常为 null)',
            event_id VARCHAR(64) COMMENT '所属事件 ID'
        ) ENGINE=OLAP
        PRIMARY KEY(id)
        DISTRIBUTED BY HASH(id) BUCKETS 10
        PROPERTIES (
            "replication_num" = "1",
            "enable_persistent_index" = "true",
            "compression" = "LZ4"
        );
        """

        # 创建事件表
        create_events_sql = """
        CREATE TABLE IF NOT EXISTS polymarket_events (
            id VARCHAR(64) NOT NULL COMMENT '事件唯一标识 (Primary Key)',
            ticker VARCHAR(255) COMMENT 'Ticker',
            slug VARCHAR(255) COMMENT 'URL Slug',
            title STRING COMMENT '事件标题',
            description STRING COMMENT '事件描述',
            resolutionSource STRING COMMENT '解决来源',
            startDate DATETIME COMMENT '开始时间',
            creationDate DATETIME COMMENT '创建时间',
            endDate DATETIME COMMENT '结束时间',
            image STRING COMMENT '主图 URL',
            icon STRING COMMENT '图标 URL',
            active BOOLEAN COMMENT '是否活跃',
            closed BOOLEAN COMMENT '是否已关闭',
            archived BOOLEAN COMMENT '是否已归档',
            category VARCHAR(128) COMMENT '分类',
            createdAt DATETIME COMMENT '创建时间',
            updatedAt DATETIME COMMENT '最后更新时间',
            competitive DOUBLE COMMENT '竞争程度评分',
            volume DOUBLE COMMENT '总交易量',
            volume24hr DOUBLE COMMENT '24小时交易量',
            liquidity DOUBLE COMMENT '总流动性',
            commentCount INT COMMENT '评论数量',
            topic VARCHAR(128) COMMENT '主题标签 (Chess, Sports, etc. or other)'
        ) ENGINE=OLAP
        PRIMARY KEY(id)
        DISTRIBUTED BY HASH(id) BUCKETS 10
        PROPERTIES (
            "replication_num" = "1",
            "enable_persistent_index" = "true",
            "compression" = "LZ4"
        );
        """
        with self.engine.begin() as conn:
            conn.execute(text(create_markets_sql))
            conn.execute(text(create_events_sql))
        logger.info("Tables ensured.")

    def parse_datetime(self, dt_str: Optional[str]) -> Optional[str]:
        if not dt_str:
            return None
        try:
            # Polymarket API usually returns ISO format like "2024-05-15T12:00:00Z"
            # StarRocks DATETIME expects "YYYY-MM-DD HH:MM:SS"
            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            return None

    def parse_date(self, d_str: Optional[str]) -> Optional[str]:
        if not d_str:
            return None
        try:
            dt = datetime.fromisoformat(d_str.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d')
        except:
            return None

    def fetch_markets_generator(self, limit: int = 100) -> Any:
        """分页获取市场数据的生成器"""
        offset = 0
        while True:
            logger.info(f"Fetching markets from API (offset={offset})...")
            try:
                markets = self.client.get_markets(limit=limit, offset=offset, active=False)
                if not markets:
                    break
                for m in markets:
                    yield m
                if len(markets) < limit:
                    break
                offset += limit
            except Exception as e:
                logger.error(f"Error fetching markets at offset {offset}: {e}")
                break

    def fetch_events_generator(self, limit: int = 100) -> Any:
        """分页获取事件数据的生成器"""
        offset = 0
        while True:
            logger.info(f"Fetching events from API (offset={offset})...")
            try:
                events = self.client.get_events(limit=limit, offset=offset, active=False)
                if not events:
                    break
                for e in events:
                    yield e
                if len(events) < limit:
                    break
                offset += limit
            except Exception as e:
                logger.error(f"Error fetching events at offset {offset}: {e}")
                break

    def format_event_data(self, e: Dict[str, Any]) -> Dict[str, Any]:
        """格式化事件数据"""
        return {
            "id": str(e.get("id")),
            "ticker": e.get("ticker"),
            "slug": e.get("slug"),
            "title": e.get("title"),
            "description": e.get("description"),
            "resolutionSource": e.get("resolutionSource"),
            "startDate": self.parse_datetime(e.get("startDate")),
            "creationDate": self.parse_datetime(e.get("creationDate")),
            "endDate": self.parse_datetime(e.get("endDate")),
            "image": e.get("image"),
            "icon": e.get("icon"),
            "active": bool(e.get("active")),
            "closed": bool(e.get("closed")),
            "archived": bool(e.get("archived")),
            "category": e.get("category"),
            "createdAt": self.parse_datetime(e.get("createdAt")),
            "updatedAt": self.parse_datetime(e.get("updatedAt")),
            "competitive": float(e.get("competitive")) if e.get("competitive") is not None else None,
            "volume": float(e.get("volume")) if e.get("volume") is not None else None,
            "volume24hr": float(e.get("volume24hr")) if e.get("volume24hr") is not None else None,
            "liquidity": float(e.get("liquidity")) if e.get("liquidity") is not None else None,
            "commentCount": int(e.get("commentCount")) if e.get("commentCount") is not None else None,
            "topic": e.get("topic")
        }

    def format_market_data(self, m: Dict[str, Any], event_id: Optional[str] = None) -> Dict[str, Any]:
        """将 API 返回的数据格式化为符合 StarRocks 表结构的字典"""
        
        # 转换 JSON 字段
        def to_json_string(val):
            if val is None: return None
            if isinstance(val, str):
                try:
                    # 验证是否已经是 JSON 字符串
                    json.loads(val)
                    return val
                except:
                    # 如果不是，将其包装成 JSON 字符串
                    return json.dumps(val)
            return json.dumps(val)

        return {
            "id": m.get("id"),
            "question": m.get("question"),
            "conditionId": m.get("conditionId"),
            "slug": m.get("slug"),
            "category": m.get("category"),
            "marketType": m.get("marketType"),
            "active": bool(m.get("active")),
            "closed": bool(m.get("closed")),
            "archived": bool(m.get("archived")),
            "createdAt": self.parse_datetime(m.get("createdAt")),
            "updatedAt": self.parse_datetime(m.get("updatedAt")),
            "endDate": self.parse_datetime(m.get("endDate")),
            "endDateIso": self.parse_date(m.get("endDateIso")),
            "closedTime": self.parse_datetime(m.get("closedTime")),
            "outcomes": to_json_string(m.get("outcomes")),
            "outcomePrices": to_json_string(m.get("outcomePrices")),
            "clobTokenIds": to_json_string(m.get("clobTokenIds")),
            "umaResolutionStatuses": to_json_string(m.get("umaResolutionStatuses")),
            "volume": str(m.get("volume")) if m.get("volume") is not None else None,
            "volumeNum": float(m.get("volumeNum")) if m.get("volumeNum") is not None else None,
            "liquidity": str(m.get("liquidity")) if m.get("liquidity") is not None else None,
            "liquidityNum": float(m.get("liquidityNum")) if m.get("liquidityNum") is not None else None,
            "volume24hr": float(m.get("volume24hr")) if m.get("volume24hr") is not None else None,
            "volume1wk": float(m.get("volume1wk")) if m.get("volume1wk") is not None else None,
            "volume1mo": float(m.get("volume1mo")) if m.get("volume1mo") is not None else None,
            "volume1yr": float(m.get("volume1yr")) if m.get("volume1yr") is not None else None,
            "volume1wkAmm": float(m.get("volume1wkAmm")) if m.get("volume1wkAmm") is not None else None,
            "volume1moAmm": float(m.get("volume1moAmm")) if m.get("volume1moAmm") is not None else None,
            "volume1yrAmm": float(m.get("volume1yrAmm")) if m.get("volume1yrAmm") is not None else None,
            "volume1wkClob": float(m.get("volume1wkClob")) if m.get("volume1wkClob") is not None else None,
            "volume1moClob": float(m.get("volume1moClob")) if m.get("volume1moClob") is not None else None,
            "volume1yrClob": float(m.get("volume1yrClob")) if m.get("volume1yrClob") is not None else None,
            "lastTradePrice": float(m.get("lastTradePrice")) if m.get("lastTradePrice") is not None else None,
            "bestBid": float(m.get("bestBid")) if m.get("bestBid") is not None else None,
            "bestAsk": float(m.get("bestAsk")) if m.get("bestAsk") is not None else None,
            "spread": float(m.get("spread")) if m.get("spread") is not None else None,
            "oneDayPriceChange": float(m.get("oneDayPriceChange")) if m.get("oneDayPriceChange") is not None else None,
            "oneHourPriceChange": float(m.get("oneHourPriceChange")) if m.get("oneHourPriceChange") is not None else None,
            "oneWeekPriceChange": float(m.get("oneWeekPriceChange")) if m.get("oneWeekPriceChange") is not None else None,
            "oneMonthPriceChange": float(m.get("oneMonthPriceChange")) if m.get("oneMonthPriceChange") is not None else None,
            "oneYearPriceChange": float(m.get("oneYearPriceChange")) if m.get("oneYearPriceChange") is not None else None,
            "description": m.get("description"),
            "twitterCardImage": m.get("twitterCardImage"),
            "image": m.get("image"),
            "icon": m.get("icon"),
            "marketMakerAddress": m.get("marketMakerAddress"),
            "creator": m.get("creator"),
            "updatedBy": int(m.get("updatedBy")) if m.get("updatedBy") is not None else None,
            "mailchimpTag": m.get("mailchimpTag"),
            "hasReviewedDates": bool(m.get("hasReviewedDates")),
            "readyForCron": bool(m.get("readyForCron")),
            "fpmmLive": bool(m.get("fpmmLive")),
            "ready": bool(m.get("ready")),
            "funded": bool(m.get("funded")),
            "cyom": bool(m.get("cyom")),
            "competitive": float(m.get("competitive")) if m.get("competitive") is not None else None,
            "pagerDutyNotificationEnabled": bool(m.get("pagerDutyNotificationEnabled")),
            "approved": bool(m.get("approved")),
            "rewardsMinSize": float(m.get("rewardsMinSize")) if m.get("rewardsMinSize") is not None else None,
            "rewardsMaxSpread": float(m.get("rewardsMaxSpread")) if m.get("rewardsMaxSpread") is not None else None,
            "clearBookOnStart": bool(m.get("clearBookOnStart")),
            "manualActivation": bool(m.get("manualActivation")),
            "negRiskOther": bool(m.get("negRiskOther")),
            "pendingDeployment": bool(m.get("pendingDeployment")),
            "deploying": bool(m.get("deploying")),
            "rfqEnabled": bool(m.get("rfqEnabled")),
            "holdingRewardsEnabled": bool(m.get("holdingRewardsEnabled")),
            "feesEnabled": bool(m.get("feesEnabled")),
            "requiresTranslation": bool(m.get("requiresTranslation")),
            "feeType": m.get("feeType"),
            "event_id": event_id or m.get("eventId")
        }

    def import_data(self, chunk_size: int = 10000):
        """执行市场数据导入过程"""
        self.create_table_if_not_exists()
        
        insert_markets_sql = text("""
        INSERT INTO polymarket_markets (
            id, question, conditionId, slug, category, marketType, active, closed, archived,
            createdAt, updatedAt, endDate, endDateIso, closedTime, outcomes, outcomePrices,
            clobTokenIds, umaResolutionStatuses, volume, volumeNum, liquidity, liquidityNum,
            volume24hr, volume1wk, volume1mo, volume1yr, volume1wkAmm, volume1moAmm, volume1yrAmm,
            volume1wkClob, volume1moClob, volume1yrClob, lastTradePrice, bestBid, bestAsk, spread,
            oneDayPriceChange, oneHourPriceChange, oneWeekPriceChange, oneMonthPriceChange, oneYearPriceChange,
            description, twitterCardImage, image, icon, marketMakerAddress, creator, updatedBy,
            mailchimpTag, hasReviewedDates, readyForCron, fpmmLive, ready, funded, cyom, competitive,
            pagerDutyNotificationEnabled, approved, rewardsMinSize, rewardsMaxSpread, clearBookOnStart,
            manualActivation, negRiskOther, pendingDeployment, deploying, rfqEnabled, holdingRewardsEnabled,
            feesEnabled, requiresTranslation, feeType, event_id
        ) VALUES (
            :id, :question, :conditionId, :slug, :category, :marketType, :active, :closed, :archived,
            :createdAt, :updatedAt, :endDate, :endDateIso, :closedTime, :outcomes, :outcomePrices,
            :clobTokenIds, :umaResolutionStatuses, :volume, :volumeNum, :liquidity, :liquidityNum,
            :volume24hr, :volume1wk, :volume1mo, :volume1yr, :volume1wkAmm, :volume1moAmm, :volume1yrAmm,
            :volume1wkClob, :volume1moClob, :volume1yrClob, :lastTradePrice, :bestBid, :bestAsk, :spread,
            :oneDayPriceChange, :oneHourPriceChange, :oneWeekPriceChange, :oneMonthPriceChange, :oneYearPriceChange,
            :description, :twitterCardImage, :image, :icon, :marketMakerAddress, :creator, :updatedBy,
            :mailchimpTag, :hasReviewedDates, :readyForCron, :fpmmLive, :ready, :funded, :cyom, :competitive,
            :pagerDutyNotificationEnabled, :approved, :rewardsMinSize, :rewardsMaxSpread, :clearBookOnStart,
            :manualActivation, :negRiskOther, :pendingDeployment, :deploying, :rfqEnabled, :holdingRewardsEnabled,
            :feesEnabled, :requiresTranslation, :feeType, :event_id
        )
        """)

        buffer = []
        total_imported = 0
        
        logger.info(f"Starting markets import in chunks of {chunk_size}...")
        
        for market in self.fetch_markets_generator():
            buffer.append(self.format_market_data(market))
            
            if len(buffer) >= chunk_size:
                with self.engine.begin() as conn:
                    conn.execute(insert_markets_sql, buffer)
                total_imported += len(buffer)
                logger.info(f"Imported {total_imported} markets...")
                buffer = []
        
        if buffer:
            with self.engine.begin() as conn:
                conn.execute(insert_markets_sql, buffer)
            total_imported += len(buffer)
            logger.info(f"Imported final batch of {len(buffer)} markets. Total: {total_imported}")

    def import_events(self, chunk_size: int = 1000):
        """执行事件及关联市场数据导入过程"""
        self.create_table_if_not_exists()

        insert_events_sql = text("""
        INSERT INTO polymarket_events (
            id, ticker, slug, title, description, resolutionSource, startDate, creationDate, endDate,
            image, icon, active, closed, archived, category, createdAt, updatedAt, competitive,
            volume, volume24hr, liquidity, commentCount, topic
        ) VALUES (
            :id, :ticker, :slug, :title, :description, :resolutionSource, :startDate, :creationDate, :endDate,
            :image, :icon, :active, :closed, :archived, :category, :createdAt, :updatedAt, :competitive,
            :volume, :volume24hr, :liquidity, :commentCount, :topic
        )
        """)

        insert_markets_sql = text("""
        INSERT INTO polymarket_markets (
            id, question, conditionId, slug, category, marketType, active, closed, archived,
            createdAt, updatedAt, endDate, endDateIso, closedTime, outcomes, outcomePrices,
            clobTokenIds, umaResolutionStatuses, volume, volumeNum, liquidity, liquidityNum,
            volume24hr, volume1wk, volume1mo, volume1yr, volume1wkAmm, volume1moAmm, volume1yrAmm,
            volume1wkClob, volume1moClob, volume1yrClob, lastTradePrice, bestBid, bestAsk, spread,
            oneDayPriceChange, oneHourPriceChange, oneWeekPriceChange, oneMonthPriceChange, oneYearPriceChange,
            description, twitterCardImage, image, icon, marketMakerAddress, creator, updatedBy,
            mailchimpTag, hasReviewedDates, readyForCron, fpmmLive, ready, funded, cyom, competitive,
            pagerDutyNotificationEnabled, approved, rewardsMinSize, rewardsMaxSpread, clearBookOnStart,
            manualActivation, negRiskOther, pendingDeployment, deploying, rfqEnabled, holdingRewardsEnabled,
            feesEnabled, requiresTranslation, feeType, event_id
        ) VALUES (
            :id, :question, :conditionId, :slug, :category, :marketType, :active, :closed, :archived,
            :createdAt, :updatedAt, :endDate, :endDateIso, :closedTime, :outcomes, :outcomePrices,
            :clobTokenIds, :umaResolutionStatuses, :volume, :volumeNum, :liquidity, :liquidityNum,
            :volume24hr, :volume1wk, :volume1mo, :volume1yr, :volume1wkAmm, :volume1moAmm, :volume1yrAmm,
            :volume1wkClob, :volume1moClob, :volume1yrClob, :lastTradePrice, :bestBid, :bestAsk, :spread,
            :oneDayPriceChange, :oneHourPriceChange, :oneWeekPriceChange, :oneMonthPriceChange, :oneYearPriceChange,
            :description, :twitterCardImage, :image, :icon, :marketMakerAddress, :creator, :updatedBy,
            :mailchimpTag, :hasReviewedDates, :readyForCron, :fpmmLive, :ready, :funded, :cyom, :competitive,
            :pagerDutyNotificationEnabled, :approved, :rewardsMinSize, :rewardsMaxSpread, :clearBookOnStart,
            :manualActivation, :negRiskOther, :pendingDeployment, :deploying, :rfqEnabled, :holdingRewardsEnabled,
            :feesEnabled, :requiresTranslation, :feeType, :event_id
        )
        """)

        event_buffer = []
        market_buffer = []
        total_events = 0
        total_markets = 0

        logger.info(f"Starting events import in chunks of {chunk_size}...")

        for event in self.fetch_events_generator():
            event_buffer.append(self.format_event_data(event))
            
            # 提取事件中的市场
            markets = event.get("markets", [])
            event_id = str(event.get("id"))
            for market in markets:
                # 补全一些可能缺失的字段，确保 format_market_data 正常工作
                if "category" not in market and "category" in event:
                    market["category"] = event["category"]
                market_buffer.append(self.format_market_data(market, event_id=event_id))

            if len(event_buffer) >= chunk_size:
                with self.engine.begin() as conn:
                    conn.execute(insert_events_sql, event_buffer)
                total_events += len(event_buffer)
                event_buffer = []
                logger.info(f"Imported {total_events} events...")

            if len(market_buffer) >= chunk_size:
                with self.engine.begin() as conn:
                    conn.execute(insert_markets_sql, market_buffer)
                total_markets += len(market_buffer)
                market_buffer = []
                logger.info(f"Imported {total_markets} markets from events...")

        # 处理剩余数据
        if event_buffer:
            with self.engine.begin() as conn:
                conn.execute(insert_events_sql, event_buffer)
            total_events += len(event_buffer)
        
        if market_buffer:
            with self.engine.begin() as conn:
                conn.execute(insert_markets_sql, market_buffer)
            total_markets += len(market_buffer)

        logger.info(f"Events import completed. Total events: {total_events}, Total markets: {total_markets}")

if __name__ == "__main__":
    import sys
    importer = PolyMarketImporter()
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "events":
            importer.import_events()
        else:
            # 默认可以两者都导入，或者保持原样
            logger.info("Running both markets and events import...")
            importer.import_data()
            importer.import_events()
    except Exception as e:
        logger.error(f"Import failed: {e}")
