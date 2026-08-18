#!/usr/bin/env python3
"""
Verification sampling script.
Usage: python scripts/verify_sample.py [--sample N] [--input FILE] [--output FILE]
"""

import argparse
import json
import os
import sys

# Load .env file from project root
from dotenv import load_dotenv
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(project_root, '.env'))

sys.path.insert(0, project_root)

from agent.verifier import run_verification, load_research_results, calculate_accuracy, save_verification_records
from agent.models import VerificationRecord, VerificationStatus


def main():
    parser = argparse.ArgumentParser(description="Create verification sample and calculate accuracy")
    parser.add_argument("--sample", type=int, default=20, help="Sample size")
    parser.add_argument("--input", default="data/research_raw.jsonl", help="Input research file")
    parser.add_argument("--output", default="data/verification.csv", help="Output verification CSV")
    parser.add_argument("--calculate", action="store_true", help="Calculate accuracy from existing verification")
    args = parser.parse_args()
    
    if args.calculate:
        # Calculate accuracy from filled verification.csv
        if not os.path.exists(args.output):
            print(f"Verification file {args.output} not found")
            return 1
        
        import csv
        records = []
        with open(args.output) as f:
            reader = csv.DictReader(f)
            for row in reader:
                row["correct"] = row["correct"].lower() == "true"
                if row["error_type"]:
                    from agent.models import ErrorType
                    row["error_type"] = ErrorType(row["error_type"])
                records.append(VerificationRecord(**row))
        
        accuracy = calculate_accuracy(records)
        print("\n=== VERIFICATION ACCURACY ===")
        print(f"Overall: {accuracy['overall']}")
        print("\nBy Field:")
        for field, acc in accuracy["by_field"].items():
            print(f"  {field}: {acc}")
        print("\nError Distribution:")
        for error, count in accuracy["error_distribution"].items():
            print(f"  {error}: {count}")
        return 0
    
    # Create sample
    import asyncio
    sample = asyncio.run(run_verification(args.input, args.output, args.sample))
    
    print(f"\nVerification sample created!")
    print(f"Sample size: {len(sample)}")
    print(f"Sample saved to: {args.output.replace('.csv', '.verification_sample.json')}")
    print(f"\nNext steps:")
    print(f"1. Manually verify each app in the sample against official docs")
    print(f"2. Fill in {args.output} with columns: app,field,agent_answer,verified_answer,correct,error_type,evidence")
    print(f"3. Run: python scripts/verify_sample.py --calculate")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())