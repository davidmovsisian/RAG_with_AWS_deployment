"""
Script 6: Launch EC2 instance with IAM profile and security group for RAG app.
Usage: python 6_launch_ec2.py
Prerequisites: Scripts 1-5 must have been run.
"""

import os
import sys

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
TEAM_NAME = os.environ.get('TEAM_NAME', '')
PROJECT_NAME = os.environ.get('PROJECT_NAME', 'rag-class')
EC2_INSTANCE_TYPE = os.environ.get('EC2_INSTANCE_TYPE', 't3.small')
EC2_KEY_NAME = os.environ.get('EC2_KEY_NAME', '')
EC2_SSH_CIDR = os.environ.get('EC2_SSH_CIDR', '0.0.0.0/0')

USER_DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'configs', 'ec2-user-data.sh')


def get_latest_ubuntu_ami(ec2_client) -> str:
    """Find the latest Ubuntu 22.04 LTS AMI."""
    response = ec2_client.describe_images(
        Owners=['099720109477'],
        Filters=[
            {'Name': 'name', 'Values': ['ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-*']},
            {'Name': 'state', 'Values': ['available']},
        ]
    )
    images = sorted(response['Images'], key=lambda x: x['CreationDate'], reverse=True)
    if not images:
        raise RuntimeError("No Ubuntu 22.04 LTS AMI found.")
    return images[0]['ImageId']


def get_or_create_security_group(ec2_client, sg_name: str, vpc_id: str) -> str:
    """Return existing security group ID or create a new one."""
    response = ec2_client.describe_security_groups(
        Filters=[{'Name': 'group-name', 'Values': [sg_name]}]
    )
    groups = response.get('SecurityGroups', [])
    if groups:
        sg_id = groups[0]['GroupId']
        print(f"Security group {sg_name} already exists: {sg_id}")
        return sg_id

    print(f"Creating security group: {sg_name}")
    sg = ec2_client.create_security_group(
        GroupName=sg_name,
        Description=f"Security group for {PROJECT_NAME} EC2 - {TEAM_NAME}",
        VpcId=vpc_id,
    )
    sg_id = sg['GroupId']

    ingress_rules = [
        {'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22,
         'IpRanges': [{'CidrIp': EC2_SSH_CIDR, 'Description': 'SSH'}]},
        {'IpProtocol': 'tcp', 'FromPort': 80, 'ToPort': 80,
         'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'HTTP'}]},
        {'IpProtocol': 'tcp', 'FromPort': 5000, 'ToPort': 5000,
         'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'Flask API'}]},
    ]
    ec2_client.authorize_security_group_ingress(GroupId=sg_id, IpPermissions=ingress_rules)

    ec2_client.create_tags(
        Resources=[sg_id],
        Tags=[
            {'Key': 'Name', 'Value': sg_name},
            {'Key': 'Project', 'Value': PROJECT_NAME},
            {'Key': 'Team', 'Value': TEAM_NAME},
        ]
    )
    print(f"Security group created: {sg_id}")
    return sg_id


def launch_ec2_instance(region: str) -> bool:
    """Launch EC2 instance with user-data, IAM profile, and security group."""
    ec2 = boto3.client('ec2', region_name=region)

    instance_name = f"{PROJECT_NAME}-ec2-{TEAM_NAME}"
    profile_name = os.environ.get('IAM_INSTANCE_PROFILE', f"{PROJECT_NAME}-ec2-profile-{TEAM_NAME}")
    sg_name = f"{PROJECT_NAME}-sg-{TEAM_NAME}"

    existing = ec2.describe_instances(
        Filters=[
            {'Name': 'tag:Name', 'Values': [instance_name]},
            {'Name': 'instance-state-name', 'Values': ['running', 'stopped', 'pending']},
        ]
    )
    reservations = existing.get('Reservations', [])
    if reservations:
        instance_id = reservations[0]['Instances'][0]['InstanceId']
        print(f"Instance {instance_name} already exists: {instance_id}")
        public_ip = reservations[0]['Instances'][0].get('PublicIpAddress', 'N/A')
        print(f"\nEC2 Instance Info")
        print(f"  Instance ID : {instance_id}")
        print(f"  Public IP   : {public_ip}")
        return True

    ami_id = os.environ.get('EC2_AMI_ID', '')
    if not ami_id:
        print(f"Looking up latest Ubuntu 22.04 LTS AMI for {region}...")
        try:
            ami_id = get_latest_ubuntu_ami(ec2)
            print(f"Found AMI: {ami_id}")
        except (ClientError, RuntimeError) as e:
            print(f"Error finding AMI: {e}")
            return False

    vpc_response = ec2.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}])
    vpcs = vpc_response.get('Vpcs', [])
    if not vpcs:
        print("Error: No default VPC found.")
        return False
    vpc_id = vpcs[0]['VpcId']

    try:
        sg_id = get_or_create_security_group(ec2, sg_name, vpc_id)
    except ClientError as e:
        print(f"Error with security group: {e}")
        return False

    if not os.path.exists(USER_DATA_PATH):
        print(f"Error: User data script not found at {USER_DATA_PATH}")
        return False

    with open(USER_DATA_PATH, 'r') as f:
        user_data = f.read()

    run_kwargs = {
        'ImageId': ami_id,
        'InstanceType': EC2_INSTANCE_TYPE,
        'SecurityGroupIds': [sg_id],
        'IamInstanceProfile': {'Name': profile_name},
        'UserData': user_data,
        'MinCount': 1,
        'MaxCount': 1,
        'BlockDeviceMappings': [{
            'DeviceName': '/dev/sda1',
            'Ebs': {'VolumeSize': 20, 'VolumeType': 'gp3', 'DeleteOnTermination': True},
        }],
        'TagSpecifications': [{
            'ResourceType': 'instance',
            'Tags': [
                {'Key': 'Name', 'Value': instance_name},
                {'Key': 'Project', 'Value': PROJECT_NAME},
                {'Key': 'Team', 'Value': TEAM_NAME},
                {'Key': 'Stage', 'Value': '1'},
                {'Key': 'ManagedBy', 'Value': 'script'},
            ]
        }],
    }
    if EC2_KEY_NAME:
        run_kwargs['KeyName'] = EC2_KEY_NAME

    print(f"Launching EC2 instance: {instance_name}")
    try:
        response = ec2.run_instances(**run_kwargs)
        instance_id = response['Instances'][0]['InstanceId']
        print(f"Instance launched: {instance_id}. Waiting for running state...")
    except ClientError as e:
        print(f"Error launching instance: {e}")
        return False

    waiter = ec2.get_waiter('instance_running')
    waiter.wait(InstanceIds=[instance_id])
    print("Instance is running.")

    instance_info = ec2.describe_instances(InstanceIds=[instance_id])
    public_ip = instance_info['Reservations'][0]['Instances'][0].get('PublicIpAddress', 'N/A')

    print(f"\nEC2 Instance Ready")
    print(f"  Instance ID   : {instance_id}")
    print(f"  Public IP     : {public_ip}")
    print(f"  Instance Type : {EC2_INSTANCE_TYPE}")
    print(f"  AMI           : {ami_id}")
    print(f"  IAM Profile   : {profile_name}")
    if EC2_KEY_NAME:
        print(f"  SSH command   : ssh -i ~/.ssh/{EC2_KEY_NAME}.pem ubuntu@{public_ip}")
    return True


def main():
    if not TEAM_NAME:
        print("Error: TEAM_NAME environment variable is required.")
        sys.exit(1)

    success = launch_ec2_instance(AWS_REGION)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
