import argparse

from tail_analysis import TailAnalysis


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数。"""
    parser = argparse.ArgumentParser(description="尾盘扫描入口")
    parser.add_argument("--start", default="14:30", help="扫描开始时间，格式 HH:MM")
    parser.add_argument("--deadline", default="14:50", help="扫描截止时间，格式 HH:MM")
    parser.add_argument("--workers", type=int, default=80, help="并发工作线程数")
    parser.add_argument("--top", type=int, default=10, help="保留候选数量")
    return parser


def main() -> None:
    """解析参数并启动尾盘扫描。"""
    args = build_parser().parse_args()
    analysis = TailAnalysis(
        start_time=args.start,
        deadline_time=args.deadline,
        max_workers=args.workers,
        top_n=args.top,
    )
    analysis.run()


if __name__ == "__main__":
    main()
