import sys
import json
import re
import argparse

FIELDS_USERS = [
    'username', 'displayName', 'e-mail', 'groups',
    'oxDepartment', 'oxPosition'
]

FIELDS_GROUPS = [
    'name', 'description', 'memberOf', 'users'
]

def extract_uid(dn_line):
    match = re.search(r'uid=([^,]+)', dn_line)
    return match.group(1) if match else None

def extract_cn(dn_line):
    match = re.search(r'cn=([^,]+)', dn_line)
    return match.group(1) if match else dn_line

def parse_ldap_blocks(file_path, is_user=True):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    blocks = content.strip().split('DN: ')[1:]
    entries = []

    for block in blocks:
        lines = block.strip().split('\n')
        entry = {}

        # First line contains DN
        dn_line = lines[0].strip()
        if is_user:
            uid = extract_uid(dn_line)
            if uid:
                entry['uid'] = uid
        else:
            cn = extract_cn(dn_line)
            if cn:
                entry['cn'] = cn

        for line in lines[1:]:
            if not line.strip() or ':' not in line:
                continue

            key, value = map(str.strip, line.split(':', 1))

            if is_user and key not in FIELDS_USERS:
                continue
            if not is_user and key not in FIELDS_GROUPS:
                continue

            if key == 'groups' or key == 'memberOf':
                value = extract_cn(value)
            if key == 'users':
                value = extract_uid(value)

            if key in entry:
                if isinstance(entry[key], list):
                    entry[key].append(value)
                else:
                    entry[key] = [entry[key], value]
            else:
                entry[key] = value

        entries.append(entry)

    return entries

def normalize_structure(data):
    all_users = set()
    all_groups = set()
    user_group_map = {}

    # Collect from user entries
    for user in data.get('users', []):
        uid = user.get('uid')
        if uid:
            all_users.add(uid)
        for group in user.get('groups', []):
            all_groups.add(group)

    # Collect from group entries
    for group in data.get('groups', []):
        group_name = group.get('name')
        if group_name:
            all_groups.add(group_name)
        for parent_group in group.get('memberOf', []):
            all_groups.add(parent_group)
        for uid in group.get('users', []):
            all_users.add(uid)
            user_group_map.setdefault(uid, []).append(group_name)

    # Sort output for readability
    return {
        "users": sorted(all_users),
        "groups": sorted(all_groups),
        "user_group_membership": {k: sorted(v) for k, v in user_group_map.items()}
    }


def main():
    parser = argparse.ArgumentParser(description='Parse Univention user and group exports to combined JSON.')
    parser.add_argument('-u', '--users', required=True, help='Path to user export file')
    parser.add_argument('-g', '--groups', required=True, help='Path to group export file')
    args = parser.parse_args()

    users = parse_ldap_blocks(args.users, is_user=True)
    groups = parse_ldap_blocks(args.groups, is_user=False)

    result = normalize_structure({
        'users': users,
        'groups': groups
    })

    print(json.dumps(result, indent=4, ensure_ascii=False))

if __name__ == "__main__":
    main()
