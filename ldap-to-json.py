import sys
import json
import re
import argparse

FIELDS_TO_INCLUDE = [
    'uid',
    'username',
    'displayName',
    'e-mail',
    'groups',
    'disabled',
    "oxDepartment",
    "oxPosition",
]

def extract_group_name(dn_string):
    match = re.match(r'cn=([^,]+)', dn_string, re.IGNORECASE)
    return match.group(1) if match else dn_string

def extract_uid(dn_line):
    match = re.search(r'uid=([^,]+)', dn_line)
    return match.group(1) if match else None

def parse_user_blocks(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    user_blocks = content.strip().split('DN: ')[1:]
    users = []

    for block in user_blocks:
        lines = block.strip().split('\n')
        user_data = {}
        dn_line = lines[0].strip()
        uid = extract_uid(dn_line)
        if uid:
            user_data['uid'] = uid

        for line in lines[1:]:
            if not line.strip() or ':' not in line:
                continue
            key, value = map(str.strip, line.split(':', 1))
            if key not in FIELDS_TO_INCLUDE:
                continue
            # Special handling for group CN extraction
            if key == 'groups':
                value = extract_group_name(value)
            if key in user_data:
                if isinstance(user_data[key], list):
                    user_data[key].append(value)
                else:
                    user_data[key] = [user_data[key], value]
            else:
                user_data[key] = value
        if user_data:
            users.append(user_data)

    return users

def main():
    parser = argparse.ArgumentParser(description='Parse Univention LDAP export to JSON.')
    parser.add_argument('-u', '--users', required=True, help='Path to users.txt export file')
    args = parser.parse_args()

    users = parse_user_blocks(args.users)
    
    print(json.dumps(users, indent=4, ensure_ascii=False))

if __name__ == "__main__":
    main()
