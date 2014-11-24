#!/usr/bin/python
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

DOCUMENTATION = '''
---
module: rds_snapshot
version_added: "1.7.3"
short_description: manage RDS database snapshots
description:
     - copy, delete, and describes. This module has a dependency on python-boto >= 2.5.
options:
  state:
    description:
      - Specifies whether the subnet should be present or absent.
    required: true
    default: present
    aliases: []
    choices: [ 'present' , 'absent' ]
  name:
    description:
      - Database snapshot identifier.
    required: true
    default: null
    aliases: []
  source_snapshot:
    description:
      - Identifier of the source database snapshot to copy. Used only when state=present.
    required: false
    default: null
    aliases: []
  region:
    description:
      - The AWS region to use. If not specified then the value of the EC2_REGION environment variable, if any, is used.
    required: true
    default: null
    aliases: [ 'aws_region', 'ec2_region' ]
  aws_access_key:
    description:
      - AWS access key. If not set then the value of the AWS_ACCESS_KEY environment variable is used.
    required: false
    default: null
    aliases: [ 'ec2_access_key', 'access_key' ]
  aws_secret_key:
    description:
      - AWS secret key. If not set then the value of the AWS_SECRET_KEY environment variable is used. 
    required: false
    default: null
    aliases: [ 'ec2_secret_key', 'secret_key' ]
requirements: [ "boto" ]
author: Scott Anderson
'''

EXAMPLES = '''
# Create a copy of an existing snapshot
- local_action:
    module: rds_snapshot
    state: present
    name: copy-of-my-rds
    source_snapshot: my-rds-id

# Remove a snapshot
- rds_snapshot: >
      state=absent
      name=my-rds-id
'''

try:
    import boto.rds
    from boto.exception import BotoServerError
except ImportError:
    print "failed=True msg='boto required for this module'"
    sys.exit(1)


def main():
    argument_spec = ec2_argument_spec()
    argument_spec.update(dict(
        state=dict(required=True, choices=['present', 'absent']),
        name=dict(required=True),
        source_snapshot=dict(required=False),
    ))
    module = AnsibleModule(argument_spec=argument_spec)

    state = module.params.get('state')
    snapshot_name = module.params.get('name').lower()

    if state == 'present':
        for required in ['name', 'source_snapshot']:
            if not module.params.get(required):
                module.fail_json(msg=str("Parameter %s required for state='present'" % required))
    else:
        for not_allowed in ['source_snapshot']:
            if module.params.get(not_allowed):
                module.fail_json(msg=str("Parameter %s not allowed for state='absent'" % not_allowed))

    # Retrieve any AWS settings from the environment.
    ec2_url, aws_access_key, aws_secret_key, region = get_ec2_creds(module)

    if not region:
        module.fail_json(msg=str("region not specified and unable to determine region from EC2_REGION."))

    try:
        conn = boto.rds.connect_to_region(region, aws_access_key_id=aws_access_key,
                                          aws_secret_access_key=aws_secret_key)
    except boto.exception.BotoServerError, e:
        module.fail_json(msg=e.error_message)

    try:
        changed = False
        exists = False

        try:
            matching_snapshots = conn.get_all_dbsnapshots(snapshot_name, max_records=100)
            exists = len(matching_snapshots) > 0
        except BotoServerError, e:
            if e.error_code != 'DBSnapshotNotFound':
                module.fail_json(msg=e.error_message)

        if state == 'absent':
            if exists:
                conn.delete_dbsnapshot(snapshot_name)
                changed = True
        else:
            source_snapshot = module.params.get('source_snapshot').lower()
            if not exists and source_snapshot:
                source_exists = False
                try:
                    matching_source_snapshots = conn.get_all_dbsnapshots(source_snapshot, max_records=100)
                    source_exists = len(matching_source_snapshots) > 0
                except BotoServerError, e:
                    module.fail_json(msg=e.error_message)

                if not source_exists:
                    module.fail_json(msg=str("Source snapshot %s was not found" % source_snapshot))

                other_snapshot = conn.copy_dbsnapshot(source_snapshot, snapshot_name)
                changed = True

    except BotoServerError, e:
        module.fail_json(msg=e.error_message)

    module.exit_json(changed=changed)

# import module snippets
from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *

main()
