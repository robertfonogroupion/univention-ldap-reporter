# univention-ldap-reporter
Export and format ldap group memberships in easy to digest matrix (csv) format.

## usage

Accepts user and group lists as exported via `udm users/user list > users.txt` and `udm groups/group list > users.txt`

```
ldap-to-json.py [-h] -u USERS -g GROUPS [-f {json,csv}] [-o OUTPUT] [--includeDisabled] [--filter FILTER]

Parse Univention user and group exports to combined output of group
memberships.

optional arguments:
  -h, --help            show this help message and exit
  -u USERS, --users USERS
                        Path to user export file
  -g GROUPS, --groups GROUPS
                        Path to group export file
  -f {json,csv}, --format {json,csv}
                        Output format (json or csv)
  -o OUTPUT, --output OUTPUT
                        Output file path (optional, defaults to stdout)
  --includeDisabled     Include users marked as disabled (default: exclude)
  --filter FILTER       Path to file listing users/groups to exclude
```

### filter file format

Filter file can be any plaintext file with excluded items on separate lines, with `user:` or `group:` before the item's name. Groups excluded by group name, users by uid.

Example:

```
user:robert.fono
group:Domain Admins
group:AA-Admin
user:richard.bak
group:DC Backup Hosts
```