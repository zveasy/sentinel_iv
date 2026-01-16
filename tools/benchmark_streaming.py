#!/usr/bin/env python3
import argparse
import time

from hb.adapters import pba_excel_adapter


def main():
    parser = argparse.ArgumentParser(description="Benchmark streaming vs non-streaming ingestion.")
    parser.add_argument("--file", required=True)
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()

    for mode in ["stream", "standard"]:
        durations = []
        for _ in range(args.runs):
            start = time.time()
            if mode == "stream":
                pba_excel_adapter.parse_stream(args.file)
            else:
                pba_excel_adapter.parse(args.file)
            durations.append(time.time() - start)
        avg = sum(durations) / len(durations)
        print(f"{mode}: avg {avg:.3f}s over {args.runs} runs")


if __name__ == "__main__":
    main()
