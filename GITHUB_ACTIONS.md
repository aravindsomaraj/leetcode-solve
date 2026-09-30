# Run daily on GitHub Actions

Your laptop can be off. GitHub starts a hosted runner for each scheduled job; the Python process exits when finished. Nothing needs to stay running in your local background.

## Publish the project

Create an empty **private** GitHub repository named `leetcode-daily`. From the extracted directory containing `bot.py` and `.github`, use these commands after replacing `YOUR_USERNAME`:

```bash
git init
git add bot.py config.example.json test_bot.py README.md GITHUB_ACTIONS.md .gitignore .github run.cmd run.sh install-task.ps1
git commit -m "Add daily solver and GitHub Actions schedule"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/leetcode-daily.git
git push -u origin main
```

Authenticate through your normal Git credential manager/browser when prompted. Never place a token in the remote URL. If Git asks for a commit identity, configure your name and email locally before committing. These commands assume a new project, not an existing Git checkout.

The repository root must contain `bot.py`, `config.example.json`, and `.github/workflows/daily.yml`. Do not upload only the ZIP, or wrap these files inside another folder. The explicit `git add` list excludes your filled-in `config.json` and all previous run data.

## Add repository secrets

In the repo open **Settings → Secrets and variables → Actions → New repository secret**. Add exactly these names:

| Secret | Value |
| --- | --- |
| `GEMINI_API_KEY` | Gemini API key from https://aistudio.google.com/app/apikey, with free-tier access |
| `LEETCODE_SESSION` | Value of your own `LEETCODE_SESSION` cookie |
| `LEETCODE_CSRF_TOKEN` | Value of your own `csrftoken` cookie |
| `LEETCODE_USERNAME` | Your LeetCode username |

You do not create a GitHub personal access token for the workflow. GitHub supplies its job token; the workflow requests repository `contents: write` to store checkpoints. Organization policies or branch rules must allow it to create and update the `bot-state` branch. If the organization forbids this permission, the job stops before solving/submitting rather than running without persistent state.

To change the model or attempt limit, edit the non-secret settings in `config.example.json` on `main`. Keep credential values as placeholders there; the workflow replaces them through environment variables. The current default is `gemini-3.8-flash`; the older `gemini-2.5-flash` is restricted for new Google projects.

## Start and inspect it

Open **Actions → LeetCode Daily → Run workflow**, choose the default branch, and run once. This performs a real model call, example test and submission automatically. Expand the job steps to see its result. A green job means the problem was accepted or an accepted checkpoint already existed; a red job exposes a sanitized error.

Scheduled runs are set to **00:17 UTC / 05:47 IST** and a recovery run at **01:17 UTC / 06:47 IST**. If the first run was accepted, the second skips model/judge work. GitHub's schedule is best effort: busy periods can delay or occasionally drop runs. The schedule runs from the default branch. The minute 17 avoids the busiest start of the hour.

The workflow is triggered only by the schedule or manual dispatch, not by pull requests or pushes. It refuses execution on a non-default branch, and serializes runs with a concurrency group.

Disable the previous Windows task/Linux cron when moving to Actions. They do not share state or concurrency protection with the hosted workflow and could submit independently.

## Persistence and recovery

GitHub runners are temporary. Before every consequential step the bot saves the day's state using GitHub's Contents API to `state/YYYY-MM-DD.json` on a separate **bot-state** branch. It restores that state on the next run. State includes the generated code, attempt count and selected verdict details, but never credentials. The branch initially copies the default branch and thereafter receives state commits; your default branch remains the source of runnable code.

This storage is synchronous: if a checkpoint cannot be confirmed, the bot stops before the next action. That preserves the daily cap and catches ambiguous submissions even if the runner crashes. Local caches/artifacts alone would not provide this guarantee. The Contents API's file SHA guards updates, and workflow concurrency prevents normal simultaneous runs. Do not delete or reset this branch while the job is operating.

For the rare `sending_submit`/`sending_test` uncertainty described in README, edit the day's JSON on **bot-state** through GitHub instead of editing a local `runs` file. Pause the workflow first, reconcile the judge result, save the corrected phase/ID, then run the workflow again on the default branch. Local files are discarded between hosted runs. State is retained in repository history until you deliberately remove it.

Keep the repository private if you do not want your account name, generated code or judge details visible. GitHub hosting does not make cookie sessions permanent: update the repository secrets when cookies expire. LeetCode may also block GitHub's hosted IP addresses, even if the same credentials work on your PC. There is no challenge bypass or fallback that silently changes execution location.

Actions usage is subject to your GitHub plan's included minutes and billing limits; the Gemini 2.5 Flash API has a published free tier within quota. Public repositories also have an inactivity rule that can disable schedules after 60 days without repository activity. See GitHub's current documentation rather than assuming an unlimited or exact-time service.

## Validation status

The Python runner and checkpoint behavior were tested offline. The workflow has not been pushed, executed on GitHub, or live-tested against your LeetCode/Gemini accounts. Connection to GitHub and the four secrets are still needed to activate it.

Sources:

- Scheduling and limitations: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
- Secrets: https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets
- Contents API: https://docs.github.com/en/rest/repos/contents
- Git references: https://docs.github.com/en/rest/git/refs

## Email and phone alerts when a run fails

The `notify-failure` job runs after a failed `solve` job. Each alert contains a link to that run. Add these repository secrets under **Settings → Secrets and variables → Actions**:

| Secret | Value |
| --- | --- |
| `ALERT_SMTP_HOST` | Your mail provider's SMTP host (for Gmail, `smtp.gmail.com`) |
| `ALERT_SMTP_PORT` | `465` for SMTP over TLS (default), or `587` for STARTTLS |
| `ALERT_SMTP_USER` | Sending account's full email address |
| `ALERT_SMTP_PASSWORD` | SMTP credential; for Gmail, use an app password rather than your normal account password |
| `ALERT_EMAIL_TO` | Email address that should receive alerts |
| `ALERT_NTFY_URL` | Full HTTPS topic URL, such as `https://ntfy.sh/a-long-random-private-topic` |
| `ALERT_NTFY_TOKEN` | Optional bearer token if the ntfy topic requires authentication |

Install the [ntfy phone app](https://docs.ntfy.sh/subscribe/phone/) and subscribe to the exact topic in `ALERT_NTFY_URL`. A topic on the public ntfy.sh server is accessible to anyone who knows its name, so choose a long random name or use a protected topic. The alert contains only the failure notice and run link, not credentials or judge output. See [ntfy's getting started guide](https://docs.ntfy.sh/) for topic setup and [its publishing guide](https://docs.ntfy.sh/publish/) for token authentication.

The email and push attempts are independent: if one service is unavailable, the other is still attempted. The alert job reports an error when either channel fails or its secrets are missing. A cancelled or skipped run does not trigger alerts. To test without a LeetCode submission, push this workflow change to the default branch, then open **Actions → LeetCode Daily → Run workflow**. Select the default branch, check **Send test alerts only (do not run the solver)**, and click **Run workflow**. The `solve` job should show as skipped; `notify-failure` should run. Check both your inbox (including spam) and the ntfy app. The test messages say "Test: LeetCode Daily alerts". If the alert job fails, expand its **Send email and phone alerts** step to see which channel failed. Do not share any secret values from GitHub. No live alert has been sent from this repository during development.
