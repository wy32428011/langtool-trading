import argparse
from analysis import Analysis


def main():
    parser = argparse.ArgumentParser(description='股票数据分析与交易建议系统')
    parser.add_argument('--code', type=str, help='指定单只股票代码进行分析 (如: 601096)')
    parser.add_argument('--batch', action='store_true', help='执行全量股票批量分析')
    parser.add_argument('--workers', type=int, default=80, help='批量分析时的并发线程数 (默认: 80)')

    args = parser.parse_args()
    analysis = Analysis()

    if args.code:
        print(f"正在启动单股分析，股票代码: {args.code}")
        analysis.analysis_stock(args.code)
    elif args.batch:
        print(f"正在启动批量分析模式，最大线程数: {args.workers}")
        analysis.batch_analysis(max_workers=args.workers)
    else:
        # 如果没有传入参数，默认打印帮助信息
        parser.print_help()


if __name__ == "__main__":
    main()
