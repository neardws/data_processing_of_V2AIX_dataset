#!/usr/bin/env python3
"""
测试改进的V2AIX数据处理流程

主要改进:
1. 车辆ID推断（从V2X消息）
2. 发送/接收节点信息
3. 只处理指定的scenarios目录
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from v2aix_pipeline.processor import process_dataset
from v2aix_pipeline.config import load_config
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    print("="*70)
    print("V2AIX数据处理 - 改进版测试")
    print("="*70)

    # 加载配置
    config_path = Path("config_scenarios_only.yaml")

    if not config_path.exists():
        print(f"❌ 配置文件不存在: {config_path}")
        return

    print(f"\n加载配置文件: {config_path}")
    cfg = load_config(config_path)

    print(f"\n配置信息:")
    print(f"  输入目录: {cfg.input_dir}")
    print(f"  输出目录: {cfg.output_dir}")
    print(f"  scenario目录: {len(cfg.scenario_dirs if cfg.scenario_dirs else [])} 个")

    if cfg.scenario_dirs:
        print(f"\n  指定的scenarios目录:")
        for d in cfg.scenario_dirs:
            print(f"    - {d}")

    print(f"\n开始处理...")
    print("-"*70)

    # 调用处理函数
    try:
        stats = process_dataset(
            input_dir=cfg.input_dir,
            output_dir=cfg.output_dir,
            output_format=cfg.format,
            scenario_dirs=cfg.scenario_dirs
        )

        print("\n" + "="*70)
        print("处理完成！")
        print("="*70)

        print(f"\n统计信息:")
        print(f"  处理文件数: {stats['total_files']}")
        print(f"  轨迹点数: {stats['trajectory_points']:,}")
        print(f"  V2X消息数: {stats['v2x_messages']:,}")
        print(f"  融合数据点: {stats['fused_points']:,}")
        print(f"  识别车辆数: {stats['unique_vehicles']}")
        print(f"  总发送字节数: {stats['total_bytes_sent']:,}")
        print(f"  平均消息大小: {stats['avg_message_size']:.1f} bytes")

        print(f"\n输出文件:")
        output_dir = Path(cfg.output_dir)
        for file in ['trajectories', 'v2x_messages', 'fused_data']:
            parquet_file = output_dir / f"{file}.parquet"
            if parquet_file.exists():
                size_mb = parquet_file.stat().st_size / (1024 * 1024)
                print(f"  ✓ {file}.parquet ({size_mb:.1f} MB)")

    except Exception as e:
        print(f"\n❌ 处理出错: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\n" + "="*70)
    print("测试完成！")
    print("="*70)


if __name__ == "__main__":
    main()
