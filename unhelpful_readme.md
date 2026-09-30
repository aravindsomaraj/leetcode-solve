# LeetCode Daily Automation

**For GitHub-hosted execution with your computer off, start with [GITHUB_ACTIONS.md](GITHUB_ACTIONS.md).** The package includes a daily workflow and persistent checkpoints. Local Windows/Linux scheduling remains available below.

An unattended Python runner: fetch today's challenge, generate C++ with the Gemini API free tier, run the examples on LeetCode, submit, read the judge verdict, and revise failures automatically. No daily confirmation or manual testing is required.

**Delivery status:** implemented and tested using simulated API responses. No live account login, paid model request, or real submission was performed during development. LeetCode's undocumented endpoints may change or reject the client immediately; this is an experimental integration, not a guarantee of daily acceptance.

## What you need

- Python 3.11 or newer. No third-party Python packages or C++ compiler are needed.
- Your own LeetCode account on `leetcode.com` (not `leetcode.cn`).
- A Gemini API key with free tier access and available quota. Create it at https://aistudio.google.com/app/apikey in a project without paid billing enabled.
- A computer/server that is powered on and connected to the internet when scheduled. A website host such as GitHub Pages cannot run this job.

**Add credentials on your computer. Do not send your cookies or API key in chat.**

## 1. Extract and configure

Extract the ZIP to a permanent folder. For the examples below, use `C:\leetcode-daily` on Windows or `/home/YOUR_USER/leetcode-daily` on Linux. If the ZIP creates an extra nested folder, use the folder containing `bot.py`.

Copy `config.example.json` to `config.json`. Fill in these four values, preserving JSON quotes and commas:

| Setting | Value to enter |
| --- | --- |
| `gemini_api_key` | Your API key from https://aistudio.google.com/app/apikey |
| `leetcode_session` | The value of your `LEETCODE_SESSION` cookie |
| `csrf_token` | The value of your `csrftoken` cookie |
| `username` | Your LeetCode username, not your email or display name |

### Find your own LeetCode cookies in Chrome or Edge

1. Open https://leetcode.com and sign in normally.
2. Press **F12** to open Developer Tools.
3. Open **Application → Storage → Cookies → https://leetcode.com**. The Application tab may be in the `>>` menu.
4. Find `LEETCODE_SESSION`; copy its **Value** into `leetcode_session`.
5. Find `csrftoken`; copy its **Value** into `csrf_token`.

Copy only each cookie's value, without the cookie name, semicolons, surrounding browser UI, or an entire Cookie header. Cookies can expire or be invalidated when you log out. Refresh both when authentication stops working.

The runner verifies the authenticated username before it performs any judge operations. Use one project folder per account and retain its `runs` directory across invocations.

### Model and attempt settings

Defaults are `gemini-3.8-flash`, `medium` thinking level, three generation attempts per UTC day, and 16,000 maximum output tokens per generation. The configured model must be available to your Google project. `thinking_level` can be `low`, `medium`, or `high` for this model. Google limits 2.5 model access on new projects, so do not use the previous package's `gemini-2.5-flash` default.

Thinking tokens count toward the output budget. If responses are incomplete, raising `max_output_tokens` or reducing `thinking_level` can help. The allowed maximum is 32,000. This model's published free tier has no per-token charge within quota; Google's current limits are shown in AI Studio. Keep the project on the free tier if you want no API charges. Google says free-tier prompts and responses may be used to improve its products.

Alternatively, the environment variables `GEMINI_API_KEY`, `LEETCODE_SESSION`, `LEETCODE_CSRF_TOKEN`, and `LEETCODE_USERNAME` override the corresponding JSON fields. Scheduled jobs must receive those variables too. `config.json` is usually simpler for a personal machine.

## 2. First run — Windows

Install Python from https://www.python.org/downloads/windows/ with the Python launcher enabled. Open PowerShell in the extracted folder:

```powershell
py -3 --version
Copy-Item config.example.json config.json
notepad config.json
```

Skip the copy command if you already created and edited `config.json`; it would overwrite your configuration.

Check account access and today's problem:

```powershell
py -3 bot.py check
```

`check` reads LeetCode and Gemini model metadata, including whether this key can access the configured model. It does not generate code, run examples, or submit anything.

Start the complete automatic workflow:

```powershell
py -3 bot.py run
```

This command **really submits** to the configured account. It can take several minutes. You do not need to review or approve the solution. Generated code runs on LeetCode's judge; this program does not execute model-generated code on your computer.

### Schedule Windows to run daily

LeetCode's daily challenge resets at **00:00 UTC = 05:30 India Standard Time**. The included installer defaults to **05:40 local time**, assuming your Windows timezone is India Standard Time. Running at 00:10 IST would pick the previous UTC day's challenge.

From the project folder:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install-task.ps1
```

The process-specific execution-policy option runs the included installer without changing the machine's permanent policy. It registers a visible task named **LeetCode Daily Runner**; it does not run a submission immediately. If task registration is denied, use an elevated PowerShell window under the same Windows account.

If your machine uses another timezone, specify the local time corresponding to shortly after 00:00 UTC. For a UTC-configured machine:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install-task.ps1 -At "00:10"
```

The task:

- Runs daily at the selected local time.
- Requests waking from sleep; actual wake support depends on Windows/power settings and hardware.
- Runs missed tasks when available, and retries a failed process up to twice, 30 minutes apart.
- Prevents overlapping task instances and has a one-hour execution limit.
- Uses your current signed-in Windows user. It works with a locked screen, but **the default task will not run while you are signed out**.

For signed-out operation, open **Task Scheduler → Task Scheduler Library → LeetCode Daily Runner → Properties → General**, select **Run whether user is logged on or not**, and supply the Windows account password if requested. Keep network access available. A powered-off computer cannot run this job. Use an always-on server if you want independence from your PC.

Inspect or trigger the scheduled task:

```powershell
Get-ScheduledTask -TaskName "LeetCode Daily Runner"
Start-ScheduledTask -TaskName "LeetCode Daily Runner"
py -3 bot.py status
Get-Content .\runs\bot.log -Tail 30
```

To disable it:

```powershell
Disable-ScheduledTask -TaskName "LeetCode Daily Runner"
```

The installer refuses to overwrite an existing task. Edit its trigger in Task Scheduler to change the time. Local schedules in timezones with daylight saving can shift relative to UTC; IST does not.

## 3. Linux/server setup and cron

Install Python 3.11+ using your distribution's package manager, copy the project to a permanent directory, and configure `config.json` as above. In that directory:

```bash
python3 --version
chmod 700 .
chmod 600 config.json
python3 bot.py check
python3 bot.py run
```

Run `crontab -e`. Replace `/home/YOUR_USER/leetcode-daily` with your actual absolute folder. Pick **one** schedule based on the cron host's timezone:

For a host configured to **UTC**:

```cron
10 0,1 * * * /usr/bin/python3 /home/YOUR_USER/leetcode-daily/bot.py run
```

For a host configured to **Asia/Kolkata (IST)**:

```cron
40 5,6 * * * /usr/bin/python3 /home/YOUR_USER/leetcode-daily/bot.py run
```

These run at 00:10 and 01:10 UTC, or 05:40 and 06:40 IST. The second run resumes a pending job or handles a transient failure; if already accepted it does no model/judge work. The three-attempt limit is shared across both runs. Cron's timezone is the host/daemon timezone, not necessarily your terminal's `TZ` variable. Confirm it with your server configuration. Also verify the Python executable path with `command -v python3` and adjust the cron line if needed.

Unlike the Windows task, ordinary cron does not catch up when the host was powered off at trigger time. Keep the server running. Do not use an ephemeral filesystem: saved state is required to prevent repeated work.

## 4. What happens each day

1. Acquire a process lock and verify your LeetCode session and username.
2. Read the current UTC daily question, its statement and C++ template.
3. Reserve one attempt in durable local state, then request a C++ solution from Gemini.
4. Run the provided example test inputs using LeetCode's `interpret_solution` endpoint.
5. If the example run succeeds, submit to the full judge. An example run is not proof of correctness; the full verdict decides acceptance.
6. Feed compile/runtime/wrong-answer/timeout verdicts back to the model for another solution, within the daily attempt limit.
7. Save code, judge feedback and phase. Finish on acceptance or stop at the limit/error.

State and results live in `runs/YYYY-MM-DD/`. Operational logs rotate in `runs/bot.log`. The runner resumes known judge IDs after a timeout and skips an already accepted local run. It does not check whether you manually solved the problem elsewhere; the skip is based on this runner's saved state.

Only the problem statement, code template, previous generated code and selected judge feedback go to Gemini. LeetCode cookies remain in the LeetCode client. Google's published free-tier data policy permits use to improve its products. Secrets are omitted from logs and no external notification service is configured.

## Troubleshooting and occasional recovery

| Symptom | Action |
| --- | --- |
| Missing config or invalid JSON | Check `config.json`, quotes, commas, and that placeholders were replaced. |
| Wrong username or expired session | Sign in to LeetCode and refresh both cookies and the configured username. |
| HTTP 403 or non-JSON response | The site may be blocking automated access, or the session/CSRF pair may be invalid. Refresh credentials. The client does not bypass site challenges; valid cookies alone may not be enough. |
| HTTP 400 from Gemini | Check model name, free-tier access and thinking level settings. |
| HTTP 404 from Gemini | The selected model may not be available to this project. Run `check` after switching to `gemini-3.8-flash` and check model availability in AI Studio. |
| HTTP 429 | Check API quota/rate limits; later scheduled runs can retry within the daily cap. |
| Incomplete model response | Increase the output-token budget within the configured limit, or reduce the thinking level. A failed generation still consumes a reserved daily attempt. |
| Judge polling timeout | Run again; the saved job is polled without another submission. |
| Daily problem date mismatch | Wait for the UTC rollover data to update. |
| Daily attempt limit reached | The runner stops for that date. It starts with a fresh budget on the next UTC date. |
| Windows job never ran | Check the task's history, signed-in status, Python launcher path, network, and wake settings. |
| HTTP/schema errors after previously working | LeetCode may have changed an endpoint; update `LeetCode` in `bot.py`. |

### A request whose outcome is uncertain

If a submit request reaches LeetCode but the network drops before its ID is saved, automatic repetition could duplicate it. The runner leaves phase `sending_submit` and stops. This rare case needs recovery; successful ordinary days remain unattended.

Stop/disable scheduling before editing `runs/YYYY-MM-DD/state.json`, and keep a backup. In LeetCode's submission history, find the submission corresponding to the saved code and time:

- If there is a matching submission, put its numeric ID in the state's `judge_id` field and change `phase` to `poll_submit`. Keep all other fields. On the same UTC day, `run` will resume polling it.
- If you have established that no submission was created, change `phase` from `sending_submit` to `submit_ready` to send that saved code once.
- For `sending_test`, change `phase` to `test_ready` to retry the examples. This may duplicate a test run, but does not create a graded submission.

A definite rejected judge request, such as HTTP 403, also leaves a `sending_*` phase. Fix the underlying error, then restore the relevant `*_ready` phase as above. Do not delete state merely to silence an error: deletion also removes the attempt limit and duplicate protection for that day. Previous UTC days are not automatically replayed.

## Development checks

```bash
python3 -m unittest -v
```

On Windows use `py -3 -m unittest -v`. The 20 offline tests cover success, automatic repair, example failures, persistent limits, timeout resumption, ambiguous submissions, model-call failures, UTC rollover, account separation, process locking, payload shape and credential separation. They simulate external responses and cannot establish that current LeetCode endpoints accept this client. The PowerShell installer was reviewed against Microsoft documentation but could not be executed in the Linux development environment.

## Interface notes and sources

LeetCode uses undocumented/internal interfaces here. Its terms prohibit scraping and its robots policy disallows these paths; the account risk discussed before implementation remains. This project does not include challenge bypass, stealth tools or contest support.

- LeetCode terms: https://leetcode.com/terms/
- LeetCode robots policy: https://leetcode.com/robots.txt
- Daily challenge UTC timing: https://leetcode.com/discuss/post/655704/april-leetcoding-challenge/
- Community-maintained API schema reference, not an official contract: https://github.com/fspv/leetcode-swagger/blob/master/swagger.yml
- Gemini free-tier pricing: https://ai.google.dev/gemini-api/docs/pricing
- Gemini API generation: https://ai.google.dev/gemini-api/docs/generate-content/text-generation
- Gemini thinking and output budgets: https://ai.google.dev/gemini-api/docs/generate-content/thinking
- Gemini model access for new projects: https://ai.google.dev/gemini-api/docs/models
- Windows task settings: https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/new-scheduledtasksettingsset

Files: `bot.py` (runner), `config.example.json`, `install-task.ps1`, `run.cmd`, `run.sh`, `test_bot.py`, `.gitignore`, and this README. Also included: `GITHUB_ACTIONS.md` and `.github/workflows/daily.yml`. The ZIP contains no credentials or prior run state.
