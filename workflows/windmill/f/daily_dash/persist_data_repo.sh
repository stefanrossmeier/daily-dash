#!/usr/bin/env bash
set -Eeuo pipefail

deploy_key="$1"
repo_path="${2:-/data/daily-dash-data}"
data_path="$3"
remote_url="${4:-}"
branch="${5:-main}"
commit_message="${6:-data: persist generated data}"

author_name="DailyDash Automation"
author_email="daily-dash-automation@users.noreply.github.com"

case "$data_path" in
  ""|/*|..|../*|*/../*|*/..)
    echo "Invalid data path: $data_path" >&2
    exit 2
    ;;
esac

if [[ -z "$remote_url" ]]; then
  echo "Git remote URL is required" >&2
  exit 3
fi

if [[ ! -d "$repo_path/.git" ]]; then
  echo "Git repository not found: $repo_path" >&2
  exit 4
fi

if ! command -v git >/dev/null 2>&1; then
  echo "git is not available" >&2
  exit 5
fi

if ! command -v ssh >/dev/null 2>&1; then
  echo "ssh is not available" >&2
  exit 6
fi

lock_dir="$repo_path/.git/daily-dash-persist.lock"

# Recover a stale lock after 30 minutes. This protects the shared Git checkout
# when multiple pipelines eventually persist into daily-dash-data.
if [[ -d "$lock_dir" ]]; then
  if find "$lock_dir" -maxdepth 0 -mmin +30 -print -quit | grep -q .; then
    echo "Removing stale Git persistence lock"
    rm -rf "$lock_dir"
  fi
fi

if ! mkdir "$lock_dir" 2>/dev/null; then
  echo "Another DailyDash Git persistence operation is running" >&2
  exit 7
fi

tmp_dir="$(mktemp -d)"
key_file="$tmp_dir/deploy_key"
known_hosts="$tmp_dir/known_hosts"

cleanup() {
  rm -rf "$tmp_dir"
  rmdir "$lock_dir" 2>/dev/null || true
}
trap cleanup EXIT

printf '%s\n' "$deploy_key" > "$key_file"
chmod 600 "$key_file"

# GitHub's published Ed25519 host key.
cat > "$known_hosts" <<'KNOWN_HOSTS'
github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl
KNOWN_HOSTS

chmod 600 "$known_hosts"

export GIT_TERMINAL_PROMPT=0
export GIT_SSH_COMMAND="ssh -i $key_file -o IdentitiesOnly=yes -o UserKnownHostsFile=$known_hosts -o StrictHostKeyChecking=yes"

current_branch="$(git -C "$repo_path" branch --show-current)"

if [[ "$current_branch" != "$branch" ]]; then
  echo "Expected branch '$branch', found '$current_branch'" >&2
  exit 8
fi

# Refuse to interact with a repository whose index already contains staged
# changes. This prevents one pipeline from accidentally committing another
# process's staged files.
if ! git -C "$repo_path" diff --cached --quiet; then
  echo "Repository already contains staged changes" >&2
  git -C "$repo_path" diff --cached --name-only >&2
  exit 9
fi

echo "Fetching remote branch..."
git -C "$repo_path" fetch "$remote_url" "$branch"

# Fail closed if somebody else updated the remote repository. We deliberately
# do not perform an automatic merge/rebase over collected data.
if ! git -C "$repo_path" merge-base --is-ancestor FETCH_HEAD HEAD; then
  echo "Remote branch contains commits not present locally" >&2
  echo "Synchronize the data repository before retrying" >&2
  exit 10
fi

git -C "$repo_path" config user.name "$author_name"
git -C "$repo_path" config user.email "$author_email"

echo "Staging: $data_path"
git -C "$repo_path" add -- "$data_path"

created_commit=false

if ! git -C "$repo_path" diff --cached --quiet; then
  echo "Creating data commit..."
  git -C "$repo_path" commit -m "$commit_message"
  created_commit=true
else
  echo "No new changes to commit"
fi

# This also makes the operation retry-safe: if a previous run committed
# successfully but failed during push, the existing local commit is pushed.
ahead="$(
  git -C "$repo_path" rev-list --count FETCH_HEAD..HEAD
)"

pushed=false

if [[ "$ahead" -gt 0 ]]; then
  echo "Pushing $ahead commit(s)..."
  git -C "$repo_path" push \
    "$remote_url" \
    "HEAD:refs/heads/$branch"
  pushed=true
else
  echo "Repository already synchronized"
fi

commit="$(
  git -C "$repo_path" rev-parse HEAD
)"

cat > result.json <<EOF_RESULT
{
  "status": "ok",
  "data_path": "$data_path",
  "commit": "$commit",
  "created_commit": $created_commit,
  "pushed": $pushed
}
EOF_RESULT
