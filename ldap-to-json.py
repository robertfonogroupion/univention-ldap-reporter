import sys
import json
import re

FIELDS_TO_INCLUDE = [
    'uid',
    'username',
    'displayName',
    'e-mail',
    'groups',
    'disabled',

]

def extract_group_name(dn_string):
    match = re.match(r'cn=([^,]+)', dn_string, re.IGNORECASE)
    return match.group(1) if match else dn_string

def parse_user_blocks(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    user_blocks = content.strip().split('DN: ')[1:]
    users = []

    for block in user_blocks:
        lines = block.strip().split('\n')
        user_data = {}
        dn_line = lines[0].strip()
        user_data['DN'] = dn_line  # always include DN
        
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
    if len(sys.argv) != 2:
        print("Usage: python3 ldap-to-json.py <input_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    users = parse_user_blocks(input_file)
    print(json.dumps(users, indent=4, ensure_ascii=False))

if __name__ == "__main__":
    main()
