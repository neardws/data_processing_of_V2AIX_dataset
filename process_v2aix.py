#!/usr/bin/env python3
"""
V2AIX Data Processor - Command line tool

Extract vehicle trajectories and V2X communication metrics from V2AIX dataset.
"""

import argparse
import logging
import sys
from pathlib import Path

from src.v2aix_pipeline.processor import process_dataset


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def main():
    parser = argparse.ArgumentParser(
        description='Process V2AIX dataset to extract trajectories and V2X metrics'
    )
    parser.add_argument(
        '--input', '-i',
        required=True,
        type=Path,
        help='Input directory with JSON files'
    )
    parser.add_argument(
        '--output', '-o',
        required=True,
        type=Path,
        help='Output directory for results'
    )
    parser.add_argument(
        '--format', '-f',
        choices=['parquet', 'csv'],
        default='parquet',
        help='Output format (default: parquet)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("V2AIX Data Processor")
    logger.info("=" * 60)
    logger.info(f"Input: {args.input}")
    logger.info(f"Output: {args.output}")
    logger.info(f"Format: {args.format}")
    logger.info("=" * 60)

    try:
        stats = process_dataset(
            input_dir=args.input,
            output_dir=args.output,
            output_format=args.format
        )

        logger.info("=" * 60)
        logger.info("Processing Complete!")
        logger.info("=" * 60)
        logger.info(f"Total files processed: {stats['total_files']}")
        logger.info(f"Trajectory points: {stats['trajectory_points']}")
        logger.info(f"V2X messages: {stats['v2x_messages']}")
        logger.info(f"Fused data points: {stats['fused_points']}")
        logger.info(f"Unique vehicles: {stats['unique_vehicles']}")
        logger.info(f"Total bytes sent: {stats['total_bytes_sent']:,}")
        logger.info(f"Avg message size: {stats['avg_message_size']:.1f} bytes")
        logger.info("=" * 60)
        logger.info(f"Output files:")
        logger.info(f"  - {args.output}/trajectories.{args.format}")
        logger.info(f"  - {args.output}/v2x_messages.{args.format}")
        logger.info(f"  - {args.output}/fused_data.{args.format}")
        logger.info("=" * 60)

        return 0

    except Exception as e:
        logger.error(f"Processing failed: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
