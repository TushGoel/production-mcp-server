# Push to GitHub — Personal Mac Steps

## Prerequisites
- Personal Mac (not Amazon corporate laptop)
- GitHub account: TushGoel
- Repo already created at: https://github.com/TushGoel/production-mcp-server (Private)

## Step 1: Install GitHub CLI
```bash
brew install gh
```

## Step 2: Authenticate
```bash
gh auth login
# Select: GitHub.com → HTTPS → Yes (authenticate Git) → Login with a web browser
# Enter the one-time code shown in terminal at: github.com/login/device
```

## Step 3: Clone/copy the repo to personal Mac
Either copy the zip (see below) or manually recreate the files.

## Step 4: Push
```bash
cd production-mcp-server
git remote set-url origin https://github.com/TushGoel/production-mcp-server.git
git push -u origin main
```

## Step 5: Verify
Visit https://github.com/TushGoel/production-mcp-server — should show all files.

---

## Notes
- Repo is PRIVATE on GitHub — only you can see it
- No Amazon systems involved — do everything from personal Mac
- When ready to make public: GitHub → Settings → Change visibility → Public
