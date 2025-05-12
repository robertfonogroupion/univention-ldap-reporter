import sys
import json
import re
import argparse
from collections import defaultdict
import csv

FIELDS_USERS = [
    'username', 'displayName', 'e-mail', 'groups',
    'oxDepartment', 'oxPosition', 'disabled'
]

FIELDS_GROUPS = [
    'name', 'description', 'memberOf', 'users'
]

def force_list(val):
    if isinstance(val, list):
        return val
    elif val:
        return [val]
    return []

def load_exclusion_filter(path):
    excluded_users = set()
    excluded_groups = set()
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('user:'):
                excluded_users.add(line[5:])
            elif line.startswith('group:'):
                excluded_groups.add(line[6:])
    return excluded_users, excluded_groups

def extract_uid(dn_line):
    match = re.search(r'uid=([^,]+)', dn_line)
    return match.group(1) if match else None

def extract_cn(dn_line):
    match = re.search(r'cn=([^,]+)', dn_line)
    return match.group(1) if match else dn_line

def prune_unused_groups_and_users(normalized_data):
    # 1. Keep only groups used by at least one user
    used_groups = set()
    for membership in normalized_data['user_group_membership'].values():
        used_groups.update(membership.get('direct', []))
        used_groups.update(membership.get('indirect', []))

    # Prune the group list
    normalized_data['groups'] = sorted(g for g in normalized_data['groups'] if g in used_groups)

    # 2. Prune groups from user membership entries
    pruned_membership = {}
    used_users = set()

    for uid, membership in normalized_data['user_group_membership'].items():
        direct = [g for g in membership.get('direct', []) if g in used_groups]
        indirect = [g for g in membership.get('indirect', []) if g in used_groups]

        if direct or indirect:
            pruned_membership[uid] = {
                'direct': sorted(direct),
                'indirect': sorted(indirect)
            }
            used_users.add(uid)

    # Replace user membership and user list
    normalized_data['user_group_membership'] = pruned_membership
    normalized_data['users'] = sorted(used_users)

    return normalized_data

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

def normalize_structure(data, include_disabled=False):
    # enabled users list for filtering out disabled users later
    enabled_uids = set()
    for user in data.get('users', []):
        uid = user.get('uid')
        if uid and (include_disabled or str(user.get('disabled', '0')) != '1'):
            enabled_uids.add(uid)


    all_users = set()
    all_groups = set()
    group_parents = defaultdict(set)   # group → parent groups
    user_direct = defaultdict(set)     # uid → direct groups
    user_indirect = defaultdict(set)   # uid → indirect groups

    # Build group → parent groups
    for group in data.get('groups', []):
        gname = group.get('name')
        if gname:
            all_groups.add(gname)
            for parent in force_list(group.get('memberOf')):
                group_parents[gname].add(parent)
                all_groups.add(parent)

    # Direct user→group from groups[]
    for group in data.get('groups', []):
        gname = group.get('name')
        if not gname:
            continue
        for uid in force_list(group.get('users')):
            if uid in enabled_uids:
                user_direct[uid].add(gname)
                all_users.add(uid)


    # Add direct groups from user objects
    for user in data.get('users', []):
        if not include_disabled and str(user.get('disabled', '0')) == '1':
            continue
        uid = user.get('uid')
        if not uid:
            continue
        all_users.add(uid)
        for g in force_list(user.get('groups')):
            user_direct[uid].add(g)
            all_groups.add(g)


    # Transitive parent resolution
    def get_all_parents(group, visited=None):
        if visited is None:
            visited = set()
        for parent in group_parents.get(group, []):
            if parent not in visited:
                visited.add(parent)
                get_all_parents(parent, visited)
        return visited

    # Compute indirect memberships per user
    for uid in list(user_direct.keys()):  # Use list() to avoid modifying dict while iterating
        if uid not in enabled_uids:
            del user_direct[uid]

    for uid in user_direct:
        indirect = set()
        for g in user_direct[uid]:
            indirect |= get_all_parents(g)
        # Exclude any already direct memberships
        user_indirect[uid] = indirect - user_direct[uid]

    # Output format
    result = {
        "users": sorted(all_users),
        "groups": sorted(all_groups),
        "user_group_membership": {
            uid: {
                "direct": sorted(user_direct[uid]),
                "indirect": sorted(user_indirect[uid])
            } for uid in sorted(all_users)
        }
    }
    return result

def apply_exclusions(normalized_data, excluded_users, excluded_groups):
    # Remove groups
    normalized_data['groups'] = [g for g in normalized_data['groups'] if g not in excluded_groups]

    # Remove users + update memberships
    filtered_membership = {}
    for uid, membership in normalized_data['user_group_membership'].items():
        if uid in excluded_users:
            continue
        direct = [g for g in membership.get('direct', []) if g not in excluded_groups]
        indirect = [g for g in membership.get('indirect', []) if g not in excluded_groups]
        if direct or indirect:
            filtered_membership[uid] = {
                'direct': sorted(direct),
                'indirect': sorted(indirect)
            }

    normalized_data['user_group_membership'] = filtered_membership
    normalized_data['users'] = sorted(filtered_membership.keys())

    return normalized_data


def export_csv_matrix(normalized_data, output_file=None):
    users = sorted(normalized_data['users'])
    groups = sorted(normalized_data['groups'])
    memberships = normalized_data['user_group_membership']

    output = []

    # Header: group names
    header = ['uid'] + groups
    output.append(header)

    for uid in users:
        row = [uid]
        direct = set(memberships.get(uid, {}).get('direct', []))
        indirect = set(memberships.get(uid, {}).get('indirect', []))
        for group in groups:
            if group in direct:
                row.append("x")
            elif group in indirect:
                row.append("i")
            else:
                row.append("")
        output.append(row)

    if output_file:
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerows(output)
    else:
        writer = csv.writer(sys.stdout, delimiter=';')
        writer.writerows(output)

def main():
    parser = argparse.ArgumentParser(description='Parse Univention user and group exports to combined output of group memberships.')
    parser.add_argument('-u', '--users', required=True, help='Path to user export file')
    parser.add_argument('-g', '--groups', required=True, help='Path to group export file')
    parser.add_argument('-f', '--format', choices=['json', 'csv'], default='csv', help='Output format (json or csv)')
    parser.add_argument('-o', '--output', help='Output file path (optional, defaults to stdout)')
    parser.add_argument('--includeDisabled', action='store_true', help='Include users marked as disabled (default: exclude)')
    parser.add_argument('--filter', help='Path to file listing users/groups to exclude')

    args = parser.parse_args()

    users = parse_ldap_blocks(args.users, is_user=True)
    groups = parse_ldap_blocks(args.groups, is_user=False)

    result = normalize_structure({
        'users': users,
        'groups': groups
    }, include_disabled=args.includeDisabled)

    result = prune_unused_groups_and_users(result)

    if args.filter:
        excluded_users, excluded_groups = load_exclusion_filter(args.filter)
        result = apply_exclusions(result, excluded_users, excluded_groups)

    if args.format == 'json':
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=4, ensure_ascii=False)
        else:
            print(json.dumps(result, indent=4, ensure_ascii=False))
    elif args.format == 'csv':
        export_csv_matrix(result, output_file=args.output)

if __name__ == "__main__":
    main()
