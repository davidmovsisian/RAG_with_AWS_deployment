"""
setup.py: CLI interface for AWS infrastructure setup.
Usage: python setup.py <command> [--step N]
Commands: setup, status, resume, cleanup
"""

import argparse
import sys

from worker import InfrastructureWorker


def main():
    parser = argparse.ArgumentParser(
        description='AWS Infrastructure Setup for RAG System'
    )
    parser.add_argument(
        'command',
        choices=['setup', 'status', 'resume', 'cleanup'],
        help='Command to execute'
    )
    parser.add_argument(
        '--step',
        type=int,
        help='Step number to resume from (required for resume command)'
    )
    parser.add_argument(
        '--env',
        default='.env',
        help='Path to .env file (default: .env)'
    )

    args = parser.parse_args()
    worker = InfrastructureWorker(env_file=args.env)

    if args.command == 'setup':
        success = worker.execute_all()
        sys.exit(0 if success else 1)

    elif args.command == 'status':
        print(worker.get_status())

    elif args.command == 'resume':
        if not args.step:
            print("Error: --step is required for the resume command.")
            sys.exit(1)
        if not worker.load_environment():
            sys.exit(1)
        success = worker.execute_step(args.step)
        sys.exit(0 if success else 1)

    elif args.command == 'cleanup':
        success = worker.cleanup()
        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
