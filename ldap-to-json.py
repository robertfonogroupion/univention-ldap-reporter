import sys
import json

def parse_user_blocks(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    user_blocks = content.strip().split('\n\n')
    users = []

    for block in user_blocks:
        user_data = {}
        for line in block.strip().split('\n'):
            if not line.strip():
                continue
            if ':' not in line:
                continue
            key, value = map(str.strip, line.split(':', 1))
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
        print("Usage: python3 ldap_to_json.py <input_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    users = parse_user_blocks(input_file)
    print(json.dumps(users, indent=4, ensure_ascii=False))

if __name__ == "__main__":
    main()
