# Protect `main` on GitHub: pull requests only, 1 approving review, passing tests,
# no force pushes or deletion, and auto-merge disabled for the repository.
# Branches are kept after merging (the long-lived `dev` branch must survive).
# Usage (after the repo exists on GitHub and `gh auth login` is done):
#   powershell -File tools\setup_github_protection.ps1 -Repo OWNER/photophoenix
param([Parameter(Mandatory = $true)][string]$Repo)

gh repo edit $Repo --enable-auto-merge=false --delete-branch-on-merge=false
if (-not $?) { exit 1 }

$body = '{"required_status_checks":{"strict":true,"contexts":["test (ubuntu-latest)","test (windows-latest)"]},' +
        '"enforce_admins":false,' +
        '"required_pull_request_reviews":{"required_approving_review_count":1,"dismiss_stale_reviews":true},' +
        '"restrictions":null,"allow_force_pushes":false,"allow_deletions":false,"required_conversation_resolution":true}'
# Windows PowerShell 5.1 garbles JSON piped to native programs, so pass it as a file.
$tmp = [IO.Path]::GetTempFileName()
[IO.File]::WriteAllText($tmp, $body)
gh api -X PUT "repos/$Repo/branches/main/protection" --input $tmp > $null
$ok = $?
Remove-Item $tmp
if ($ok) { "main is protected: PRs + review + tests required, auto-merge off." } else { exit 1 }
