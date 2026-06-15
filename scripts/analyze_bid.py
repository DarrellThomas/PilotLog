#!/usr/bin/env python3
"""Analyze a bid package and produce a ranked bid recommendation.

Usage:
    python3 analyze_bid.py /path/to/HOUCPA.ZIP                     # from ZIP
    python3 analyze_bid.py /path/to/extracted/                      # from directory
    python3 analyze_bid.py /path/to/HOUCPA.ZIP --awards /path/to/HOUCPM.ZIP  # with awards
    python3 analyze_bid.py /path/to/HOUCPA.ZIP --top 50            # show top 50
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def main():
    parser = argparse.ArgumentParser(description="Analyze SWA bid package")
    parser.add_argument("package", help="Path to bid package ZIP or extracted directory")
    parser.add_argument("--awards", help="Path to awards ZIP or TXT file")
    parser.add_argument("--top", type=int, default=30, help="Show top N lines (default 30)")
    parser.add_argument("--base", default="HOU", help="Base code (default HOU)")
    parser.add_argument("--seat", default="CA", help="Seat (default CA)")
    parser.add_argument("--period", default=None, help="Schedule period (e.g., JUL26)")
    parser.add_argument("--save", action="store_true", help="Save to historical archive")
    args = parser.parse_args()

    from pilotlog.swapa.bidding import (
        load_bid_package, load_awards, score_all_lines, format_bid_report,
        compute_effective_seniority, available_lines, save_bid_package,
    )
    from pilotlog.swapa.seniority import _get_employee_id

    path = Path(args.package)

    # Load bid package
    if path.suffix.upper() == '.ZIP':
        print(f"Loading bid package from {path}...")
        package = load_bid_package(zip_path=path, base=args.base, seat=args.seat)
    elif path.is_dir():
        print(f"Loading bid package from {path}/...")
        package = load_bid_package(txt_dir=path, base=args.base, seat=args.seat)
    else:
        print(f"Error: {path} is not a ZIP file or directory")
        sys.exit(1)

    lines = package.get('lines', [])
    pairings = package.get('pairings', {})
    bidders = package.get('bidders', [])

    print(f"Parsed: {len(lines)} lines, {len(pairings)} pairings, {len(bidders)} bidders")

    # Compute effective seniority
    emp_id = _get_employee_id()
    effective_sen = None
    if emp_id and bidders:
        effective_sen = compute_effective_seniority(bidders, emp_id)
        if effective_sen:
            print(f"Your seniority: #{effective_sen['sq']} system, "
                  f"#{effective_sen['effective_sq']} effective "
                  f"({effective_sen['paper_above']} paper bids above)")

    # Load awards if provided
    awards = []
    if args.awards:
        awards_path = Path(args.awards)
        if awards_path.suffix.upper() == '.ZIP':
            awards = load_awards(zip_path=awards_path, base=args.base, seat=args.seat)
        else:
            awards = load_awards(txt_path=awards_path, base=args.base, seat=args.seat)
        print(f"Awards loaded: {len(awards)} entries")

        # Filter to available lines
        if effective_sen:
            avail = available_lines(lines, awards, effective_sen['sq'])
            print(f"Lines available at your pick: {len(avail)} of {len(lines)}")
            lines = avail

    # Score and rank
    ranked = score_all_lines(lines)

    # Print report
    print()
    print(format_bid_report(ranked, top_n=args.top, effective_sen=effective_sen))

    # Detect period from cover memo
    period = args.period
    if not period and package.get('cover'):
        import re
        period_m = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+20\d{2}',
                             package['cover'])
        if period_m:
            period = period_m.group(0).upper()[:5].replace(' ', '')

    # Save if requested
    if args.save and period:
        outfile = save_bid_package(package, period, args.base)
        print(f"\nSaved to {outfile}")

    # Summary stats
    print(f"\n{'='*75}")
    print(f"SUMMARY")
    print(f"  Lines scored: {len(ranked)}")
    if ranked:
        best = ranked[0]
        print(f"  Best line: #{best.number} (score {best.score:.1f}, "
              f"{best.tfp:.1f} TFP, {best.off_days} off, {best.avg_legs_per_day:.1f} legs/day)")
        # Find your actual line if awards loaded
        if awards and emp_id:
            my_award = next((a for a in awards if a.emp_id == emp_id), None)
            if my_award:
                my_line = next((l for l in ranked if l.number == my_award.line), None)
                if my_line:
                    print(f"  Your line: #{my_line.number} (score {my_line.score:.1f}, "
                          f"rank {my_line.rank} of {len(ranked)}, "
                          f"{my_line.tfp:.1f} TFP, {my_line.off_days} off, "
                          f"{my_line.avg_legs_per_day:.1f} legs/day)")


if __name__ == "__main__":
    main()
