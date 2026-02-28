"""
worker.py: Orchestrate all AWS infrastructure setup scripts automatically.
Usage: from worker import InfrastructureWorker
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Optional
from dotenv import load_dotenv
import boto3

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), 'scripts')

STEPS = [
    (1, '1_create_s3_bucket.py',    'Create S3 bucket'),
    (2, '2_create_sqs_queue.py',    'Create SQS queue'),
    (3, '3_setup_s3_event.py',      'Setup S3 event notification'),
    (4, '4_create_iam_role.py',     'Create IAM role'),
    (5, '5_setup_opensearch.py',    'Setup OpenSearch domain'),
    (6, '6_launch_ec2.py',          'Launch EC2 instance'),
]

REQUIRED_ENV_VARS = ['AWS_REGION', 'TEAM_NAME', 'PROJECT_NAME']

class InfrastructureWorker:
    """Orchestrate AWS infrastructure setup scripts."""

    def __init__(self, env_file: str = '.env',
                 state_file: str = '.infrastructure_state.json'):
        self.env_file = env_file
        self.state_file = state_file
        self.state: dict = {}

    def validate_prerequisites(self) -> bool:
        if not os.path.exists(self.env_file):
            print(f"Error: {self.env_file} not found.")
            return False
        if not self.load_environment():
            return False
        try:
            identity = boto3.client('sts').get_caller_identity()
            print(f"AWS credentials OK - Account: {identity['Account']}, ARN: {identity['Arn']}")
        except Exception as e:
            print(f"Error: AWS credentials not configured or invalid: {e}")
            return False

        return True

    def load_environment(self) -> bool:
        try:
            load_dotenv(self.env_file)

            for var in REQUIRED_ENV_VARS:
                if not os.environ.get(var):
                    print(f"Error: {var} is not set in {self.env_file}")
                    return False
            
        except Exception as e:
            print(f"Error loading .env: {e}")
            return False
        return True

    def execute_step(self, step_number: int) -> bool:
        """Execute a specific infrastructure script by step number."""
        step = next((s for s in STEPS if s[0] == step_number), None)
        if step is None:
            print(f"Error: Step {step_number} not found.")
            return False

        _, script_name, description = step
        script_path = os.path.join(SCRIPTS_DIR, script_name)

        if not os.path.exists(script_path):
            print(f"Error: Script not found: {script_path}")
            self.save_state(step_number, 'failed', error=f"Script not found: {script_path}")
            return False

        print(f"\n{'='*60}")
        print(f"Step {step_number}: {description}")
        print(f"{'='*60}")

        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=False,
        )

        if result.returncode == 0:
            self.save_state(step_number, 'completed')
            print(f"Step {step_number} completed successfully.")
            return True
        else:
            error_msg = f"Script exited with code {result.returncode}"
            self.save_state(step_number, 'failed', error=error_msg)
            print(f"Step {step_number} failed: {error_msg}")
            return False

    def execute_all(self) -> bool:
        """Run all infrastructure scripts in order, stopping on first failure."""
        if not self.validate_prerequisites():
            print("Prerequisites check failed. Aborting.")
            return False

        self.state = self.load_state()
        completed = {s['step'] for s in self.state.get('steps', []) if s['status'] == 'completed'}

        print(f"\nStarting infrastructure setup ({len(STEPS)} steps total)")

        for step_number, script_name, description in STEPS:
            if step_number in completed:
                print(f"\nStep {step_number}: {description} - already completed, skipping.")
                continue

            success = self.execute_step(step_number)
            if not success:
                print(f"\nSetup failed at step {step_number}. "
                      f"Fix the error and resume with: python setup.py resume --step {step_number}")
                return False

        print("\nAll infrastructure steps completed successfully!")
        return True

    def save_state(self, step_number: int, status: str,
                   resource_info: Optional[dict] = None,
                   error: Optional[str] = None) -> None:
        """Persist step status to the state file."""
        state = self.load_state()
        steps = state.get('steps', [])

        existing = next((s for s in steps if s['step'] == step_number), None)
        entry: dict[str, Any] = {
            'step': step_number,
            'status': status,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
        if resource_info:
            entry['resource_info'] = resource_info
        if error:
            entry['error'] = error

        if existing:
            steps[steps.index(existing)] = entry
        else:
            steps.append(entry)

        state['steps'] = steps
        state['last_updated'] = datetime.now(timezone.utc).isoformat()

        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)

    def load_state(self) -> dict:
        """Load state from the state file."""
        if not os.path.exists(self.state_file):
            return {'steps': []}
        try:
            with open(self.state_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {'steps': []}

    def get_status(self) -> str:
        """Return a formatted status report of the infrastructure setup."""
        state = self.load_state()
        steps_map = {s['step']: s for s in state.get('steps', [])}

        lines = ["\nInfrastructure Setup Status", "=" * 40]
        for step_number, _, description in STEPS:
            step_state = steps_map.get(step_number)
            if step_state:
                status = step_state['status'].upper()
                ts = step_state.get('timestamp', '')[:19]
                line = f"  Step {step_number}: {description} [{status}] {ts}"
                if step_state.get('error'):
                    line += f"\n    Error: {step_state['error']}"
            else:
                line = f"  Step {step_number}: {description} [PENDING]"
            lines.append(line)

        if state.get('last_updated'):
            lines.append(f"\nLast updated: {state['last_updated'][:19]}")
        return '\n'.join(lines)

    def cleanup(self) -> bool:
        """Run the cleanup script to remove all resources."""
        cleanup_script = os.path.join(SCRIPTS_DIR, 'cleanup.py')
        if not os.path.exists(cleanup_script):
            print(f"Error: Cleanup script not found: {cleanup_script}")
            return False
        result = subprocess.run([sys.executable, cleanup_script])
        return result.returncode == 0
