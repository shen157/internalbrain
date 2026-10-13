"""InternalBrain dataset validation and permission evaluation suite.

Validates the frozen synthetic dataset (checks A-J) and evaluates the
permission test cases in tests/permission_test_cases.json against a reference
implementation of the four platforms' permission semantics:

  Confluence : space permission AND (page restriction, if present)
  Jira       : project role AND Browse Project AND (issue security, if present)
  Slack      : public channel = anyone, private channel = membership only
  Google Drive: direct file permission OR inherited parent folder permission
               (inherit_permissions=false disables inheritance for that file)

Run:  python tests/validate_dataset.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def load(rel):
    with open(DATA / rel, encoding="utf-8") as fh:
        return json.load(fh)


def iso_ok(value):
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except Exception:
        return False


users = {u["user_id"]: u for u in load("users.json")}
groups = {g["group_id"]: g for g in load("groups.json")}
pages = {p["id"]: p for p in load("confluence/pages.json")}
spaces = {s["spaceId"]: s for s in load("confluence/space_permissions.json")}
restrictions = {r["pageId"]: r for r in load("confluence/page_restrictions.json")}
issues = {i["key"]: i for i in load("jira/issues.json")}
proj_roles = {r["projectKey"]: r for r in load("jira/project_roles.json")}
proj_perms = {p["projectKey"]: p for p in load("jira/project_permissions.json")}
issue_security = {s["issueKey"]: s["securityLevel"] for s in load("jira/issue_security.json")}
channels = {c["id"]: c for c in load("slack/channels.json")}
memberships = {m["channel_id"]: set(m["members"]) for m in load("slack/channel_members.json")}
messages = load("slack/messages.json")
files = {f["id"]: f for f in load("gdrive/files.json")}
folders = {f["id"]: f for f in load("gdrive/folders.json")}
file_perms = {p["fileId"]: p["permissions"] for p in load("gdrive/permissions.json")}
folder_perms = {p["folderId"]: p["permissions"] for p in load("gdrive/folder_permissions.json")}
suite = json.load(open(ROOT / "tests" / "permission_test_cases.json", encoding="utf-8"))

errors = []


def err(check, msg):
    errors.append(f"[{check}] {msg}")


def user_groups(uid):
    return set(users[uid]["groups"])


def principal_matches(p, uid):
    if p["type"] == "user":
        return p["principalId"] == uid
    if p["type"] == "group":
        return p["principalId"] in user_groups(uid)
    return False


# ---------------------------------------------------------------- A. duplicate IDs
for name, coll in [("page", pages), ("issue", issues), ("channel", channels),
                   ("gdrive file", files), ("folder", folders)]:
    pass  # dicts already deduplicate by key; detect dupes from raw lists instead

raw_pages = load("confluence/pages.json")
raw_issues = load("jira/issues.json")
raw_files = load("gdrive/files.json")
raw_folders = load("gdrive/folders.json")
raw_channels = load("slack/channels.json")
for label, items, key in [("pages", raw_pages, "id"), ("issues", raw_issues, "key"),
                          ("gdrive files", raw_files, "id"), ("folders", raw_folders, "id"),
                          ("channels", raw_channels, "id")]:
    seen = set()
    for item in items:
        if item[key] in seen:
            err("A", f"duplicate {label} id {item[key]}")
        seen.add(item[key])
msg_keys = [(m["channel_id"], m["ts"]) for m in messages]
if len(msg_keys) != len(set(msg_keys)):
    err("A", "duplicate (channel, ts) in slack messages")
perm_ids = [p["id"] for spec in file_perms.values() for p in spec] + \
           [p["id"] for spec in folder_perms.values() for p in spec]
if len(perm_ids) != len(set(perm_ids)):
    err("A", "duplicate google drive permission ids")

# ------------------------------------------------- B/C. user and group references
for gid, g in groups.items():
    for m in g["members"]:
        if m not in users:
            err("B", f"group {gid} references unknown user {m}")
        elif gid not in users[m]["groups"]:
            err("C", f"user {m} lists {gid} but group does not list the user")
for uid, u in users.items():
    for g in u["groups"]:
        if g not in groups:
            err("C", f"user {uid} references unknown group {g}")
        elif uid not in groups[g]["members"]:
            err("C", f"group {g} lists {uid} but user does not list the group")

for p in pages.values():
    if p["version"]["authorId"] not in users:
        err("B", f"page {p['id']} unknown author")
    if p["spaceId"] not in spaces:
        err("G", f"page {p['id']} references unknown space {p['spaceId']}")
for pid, r in restrictions.items():
    if pid not in pages:
        err("G", f"restriction for unknown page {pid}")
    for u in r["readRestrictions"]["users"]:
        if u not in users:
            err("B", f"restriction {pid} unknown user {u}")
    for g in r["readRestrictions"]["groups"]:
        if g not in groups:
            err("C", f"restriction {pid} unknown group {g}")
for sid, s in spaces.items():
    for u in s["allowedUsers"]:
        if u not in users:
            err("B", f"space {sid} unknown user {u}")
    for g in s["allowedGroups"]:
        if g not in groups:
            err("C", f"space {sid} unknown group {g}")

for i in issues.values():
    if i["fields"]["assignee"]["accountId"] not in users:
        err("B", f"issue {i['key']} unknown assignee")
    if i["fields"]["reporter"]["accountId"] not in users:
        err("B", f"issue {i['key']} unknown reporter")
    for link in i["fields"].get("issuelinks", []):
        if link["outwardIssue"]["key"] not in issues:
            err("F", f"issue {i['key']} links unknown issue {link['outwardIssue']['key']}")

# --------------------------------------------------------------- D/E. folder + permission refs
for fid, f in files.items():
    pfid = f.get("parent_folder_id")
    if pfid is None:
        err("D", f"file {fid} has no parent_folder_id")
    elif pfid not in folders:
        err("D", f"file {fid} references unknown folder {pfid}")
    if f.get("parents") != [pfid]:
        err("D", f"file {fid} parents array inconsistent with parent_folder_id")
for spec in load("gdrive/permissions.json"):
    if spec["fileId"] not in files:
        err("E", f"direct permissions for unknown file {spec['fileId']}")
    for p in spec["permissions"]:
        if p["type"] == "user" and p["principalId"] not in users:
            err("B", f"{spec['fileId']} permission {p['id']} unknown user")
        if p["type"] == "group" and p["principalId"] not in groups:
            err("C", f"{spec['fileId']} permission {p['id']} unknown group")
for spec in load("gdrive/folder_permissions.json"):
    if spec["folderId"] not in folders:
        err("E", f"folder permissions for unknown folder {spec['folderId']}")
    for p in spec["permissions"]:
        if p["type"] == "user" and p["principalId"] not in users:
            err("B", f"{spec['folderId']} permission {p['id']} unknown user")
        if p["type"] == "group" and p["principalId"] not in groups:
            err("C", f"{spec['folderId']} permission {p['id']} unknown group")

# ------------------------------------------------------------------------ F. Jira validity
for pk, spec in proj_perms.items():
    if pk not in proj_roles:
        err("F", f"project_permissions references unknown project {pk}")
        continue
    declared = {r["name"] for r in proj_roles[pk]["roles"]}
    for perm in spec["permissions"]:
        for role in perm["roles"]:
            if role not in declared:
                err("F", f"{pk}.{perm['permission']} references undeclared role {role}")
    if not any(p["permission"] == "BROWSE_PROJECTS" for p in spec["permissions"]):
        err("F", f"{pk} has no BROWSE_PROJECTS entry")
for pk, spec in proj_roles.items():
    if pk not in proj_perms:
        err("F", f"project {pk} missing from project_permissions.json")
    for role in spec["roles"]:
        for u in role["users"]:
            if u not in users:
                err("B", f"{pk}/{role['name']} unknown user {u}")
        for g in role["groups"]:
            if g not in groups:
                err("C", f"{pk}/{role['name']} unknown group {g}")
for key, lvl in issue_security.items():
    if key not in issues:
        err("F", f"issue_security references unknown issue {key}")
    for u in lvl["allowedUsers"]:
        if u not in users:
            err("B", f"issue security {key} unknown user {u}")
    for g in lvl["allowedGroups"]:
        if g not in groups:
            err("C", f"issue security {key} unknown group {g}")
for i in issues.values():
    if i["fields"]["project"]["key"] not in proj_roles:
        err("F", f"issue {i['key']} references project without roles")

# ---------------------------------------------------------------------- H. Slack validity
for m in messages:
    if m["channel_id"] not in channels:
        err("H", f"message {m['ts']} references unknown channel {m['channel_id']}")
        continue
    if m["user"] not in memberships.get(m["channel_id"], set()):
        err("H", f"author {m['user']} of message {m['ts']} is not a member of {m['channel_id']}")
for m in messages:
    if m["thread_ts"]:
        parent = any(x["channel_id"] == m["channel_id"] and x["ts"] == m["thread_ts"] for x in messages)
        if not parent:
            err("H", f"orphan thread reply {m['ts']} -> {m['thread_ts']}")
for cid in channels:
    if cid not in memberships:
        err("H", f"channel {cid} has no membership record")
    else:
        for u in memberships[cid]:
            if u not in users:
                err("B", f"channel {cid} unknown member {u}")

# ------------------------------------------------------------------------ J. timestamps
ts_fields = []
for p in pages.values():
    ts_fields.append(("page " + p["id"], p["version"]["createdAt"]))
for i in issues.values():
    ts_fields.append(("issue " + i["key"], i["fields"]["created"]))
    ts_fields.append(("issue " + i["key"], i["fields"]["updated"]))
    if "resolutiondate" in i["fields"]:
        ts_fields.append(("issue " + i["key"], i["fields"]["resolutiondate"]))
for c in channels.values():
    ts_fields.append(("channel " + c["id"], c["created"]))
for m in messages:
    ts_fields.append((f"message {m['ts']}", m["ts"]))
for f in files.values():
    ts_fields.append(("file " + f["id"], f["modifiedTime"]))
    ts_fields.append(("file " + f["id"], f["createdTime"]))
for f in folders.values():
    ts_fields.append(("folder " + f["id"], f["createdTime"]))
for label, value in ts_fields:
    if not iso_ok(value):
        err("J", f"unparseable timestamp for {label}: {value}")

# ------------------------------------------------------ J. payment migration fact consistency
if "2026-11-05" not in pages["CONF-PAY-001"]["body"]["value"]:
    err("J", "CONF-PAY-001 no longer states the revised cutover date 2026-11-05")
if "2026-11-05" not in files["GDRIVE-PAY-001"]["content"]:
    err("J", "GDRIVE-PAY-001 no longer states the revised cutover date 2026-11-05")
if not any("2026-11-05" in m["text"] for m in messages):
    err("J", "no Slack message states the revised cutover date 2026-11-05")
if issues["PAY-102"]["fields"]["status"]["name"] != "Blocked":
    err("J", "PAY-102 is no longer Blocked")
if issues["PAY-103"]["fields"]["status"]["name"] != "Blocked":
    err("J", "PAY-103 is no longer Blocked")
if not ("nullable" in issues["PAY-102"]["fields"]["description"]
        or "NOT NULL" in issues["PAY-102"]["fields"]["description"]):
    err("J", "PAY-102 no longer describes the nullable-column incompatibility")
if "p99 of 4.2s" not in issues["PAY-103"]["fields"]["description"]:
    err("J", "PAY-103 no longer describes the authentication timeout")

texts = ([p["body"]["value"] for p in pages.values()]
         + [f["content"] for f in files.values()]
         + [m["text"] for m in messages])
for t in texts:
    if "2026-10-15" in t and "riginal" not in t.lower():
        err("J", "old cutover date 2026-10-15 appears without 'original' context")


# ============================================================== permission evaluation
def eval_confluence(uid, page_id):
    page = pages[page_id]
    space = spaces[page["spaceId"]]
    space_ok = uid in space["allowedUsers"] or bool(user_groups(uid) & set(space["allowedGroups"]))
    r = restrictions.get(page_id)
    page_ok = True
    if r:
        page_ok = uid in r["readRestrictions"]["users"] or \
                  bool(user_groups(uid) & set(r["readRestrictions"]["groups"]))
    return space_ok and page_ok


def eval_jira(uid, key):
    pk = issues[key]["fields"]["project"]["key"]
    held = set()
    for role in proj_roles[pk]["roles"]:
        if uid in role["users"] or bool(user_groups(uid) & set(role["groups"])):
            held.add(role["name"])
    browse_roles = set()
    for perm in proj_perms[pk]["permissions"]:
        if perm["permission"] == "BROWSE_PROJECTS":
            browse_roles |= set(perm["roles"])
    if not (held & browse_roles):
        return False
    lvl = issue_security.get(key)
    if not lvl:
        return True
    return uid in lvl["allowedUsers"] or bool(user_groups(uid) & set(lvl["allowedGroups"]))


def eval_slack(uid, channel_id):
    ch = channels[channel_id]
    if not ch["is_private"]:
        return True
    return uid in memberships.get(channel_id, set())


def drive_entry_ok(perms, uid):
    return any(principal_matches(p, uid) for p in perms)


def eval_gdrive(uid, resource_type, resource_id):
    if resource_type == "folder":
        return drive_entry_ok(folder_perms.get(resource_id, []), uid)
    f = files[resource_id]
    if drive_entry_ok(file_perms.get(resource_id, []), uid):
        return True
    if f.get("inherit_permissions", True):
        return drive_entry_ok(folder_perms.get(f["parent_folder_id"], []), uid)
    return False


EVAL = {"confluence": eval_confluence, "jira": eval_jira, "slack": eval_slack,
        "gdrive": lambda uid, rt, rid: eval_gdrive(uid, rt, rid)}

RESOURCES = {
    "confluence": {"page": pages},
    "jira": {"issue": issues},
    "slack": {"channel": channels},
    "gdrive": {"file": files, "folder": folders},
}

passed = failed = false_allows = 0
failures = []
for case in suite["cases"]:
    uid, rid = case["user_id"], case["resource_id"]
    if uid not in users:
        failures.append((case["id"], f"unknown user {uid}", "-"))
        failed += 1
        continue
    table = RESOURCES[case["platform"]].get(case["resource_type"], {})
    if rid not in table:
        failures.append((case["id"], f"unknown resource {rid}", "-"))
        failed += 1
        continue
    if case["platform"] == "slack":
        got = EVAL[case["platform"]](uid, rid)
    elif case["platform"] == "gdrive":
        got = EVAL[case["platform"]](uid, case["resource_type"], rid)
    else:
        got = EVAL[case["platform"]](uid, rid)
    expected = case["expected"] == "ALLOW"
    if got == expected:
        passed += 1
    else:
        failed += 1
        verdict = "ALLOW" if got else "DENY"
        failures.append((case["id"], f"expected {case['expected']}, got {verdict}", case["feature"]))
        if got and not expected:
            false_allows += 1

deny_cases = sum(1 for c in suite["cases"] if c["expected"] == "DENY")
far = (false_allows / deny_cases * 100) if deny_cases else 0.0

# ============================================================================ report
print("=" * 72)
print("InternalBrain dataset validation report")
print("=" * 72)
print(f"Resources: confluence pages={len(pages)}  jira issues={len(issues)}  "
      f"slack messages={len(messages)}  gdrive files={len(files)}  folders={len(folders)}")
total_resources = len(pages) + len(issues) + len(messages) + len(files)
print(f"Unified resources (pages + issues + messages + files): {total_resources}")
print()
print("Permission records:")
print(f"  Confluence : {len(spaces)} space permissions, {len(restrictions)} page restrictions")
print(f"  Jira       : {sum(len(r['roles']) for r in proj_roles.values())} role records across "
      f"{len(proj_roles)} projects, "
      f"{sum(len(p['permissions']) for p in proj_perms.values())} permission entries, "
      f"{len(issue_security)} issue security levels")
print(f"  Slack      : {len(channels)} channels, {len(memberships)} membership records "
      f"({sum(len(v) for v in memberships.values())} memberships)")
print(f"  Google Drive: {sum(len(v) for v in file_perms.values())} direct file permission entries "
      f"across {len(file_perms)} files, "
      f"{sum(len(v) for v in folder_perms.values())} folder permission entries across "
      f"{len(folder_perms)} folders")
print()
print("-" * 72)
print(f"Dataset consistency checks (A-J): {'PASS - 0 errors' if not errors else 'FAIL'}")
for e in errors:
    print("  " + e)
print()
print("-" * 72)
print(f"Permission test cases: {passed}/{passed + failed} passed")
for cid, detail, feature in failures:
    print(f"  FAIL {cid}: {detail} [{feature}]")
print(f"False Allow Rate: {far:.1f}% ({false_allows} false allows out of {deny_cases} DENY cases)")
print("=" * 72)

sys.exit(1 if (errors or failed) else 0)
