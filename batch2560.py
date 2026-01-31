import argparse
from analysis2560 import Analysis2560

def main():
    parser = argparse.ArgumentParser(description='A股 2560 战法批量分析工具')
    parser.add_argument('--workers', type=int, default=80, help='批量分析时的并发线程数 (默认: 80)')

    args = parser.parse_args()
    analyzer = Analysis2560()

    print(f"正在启动 2560 批量分析模式，最大线程数: {args.workers}")
    analyzer.batch_analysis(max_workers=args.workers)

if __name__ == "__main__":
    main()
