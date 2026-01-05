# Git Setup Guide for HealthDiary

This guide will help you push your HealthDiary project to Git (GitHub, GitLab, etc.).

---

## Option 1: Push to Existing Remote Repository

If you already have a Git repository on GitHub/GitLab and want to push this project:

### Step 1: Initialize Git Repository (if not already initialized)

```bash
cd D:\HealthDairy
git init
```

### Step 2: Add All Files

```bash
git add .
```

### Step 3: Create .gitignore (Recommended)

Before committing, create a `.gitignore` file to exclude unnecessary files:

```bash
# Create .gitignore file
notepad .gitignore
```

Add these contents to `.gitignore`:
```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
.venv/
venv/
ENV/
env/

# Database
*.db
*.sqlite
*.sqlite3

# Environment variables
.env
.env.local

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Project specific
backend/app/data/
temp_audio/
*.pdf
backend/app/static/pdf/

# Logs
*.log
```

Save and close, then add it:
```bash
git add .gitignore
```

### Step 4: Commit Your Changes

```bash
git commit -m "Initial commit: HealthDiary project with Raspberry Pi setup guides"
```

### Step 5: Add Remote Repository

Replace `YOUR_USERNAME` and `YOUR_REPO_NAME` with your actual GitHub/GitLab username and repository name:

```bash
# For GitHub
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git

# OR for GitLab
# git remote add origin https://gitlab.com/YOUR_USERNAME/YOUR_REPO_NAME.git

# OR if using SSH
# git remote add origin git@github.com:YOUR_USERNAME/YOUR_REPO_NAME.git
```

### Step 6: Push to Remote

```bash
git branch -M main
git push -u origin main
```

---

## Option 2: Create New Repository on GitHub/GitLab First

If you don't have a repository yet:

### Step 1: Create Repository on GitHub/GitLab

1. Go to https://github.com (or https://gitlab.com)
2. Click "New repository" (or "New project")
3. Name it (e.g., "HealthDairy")
4. **Don't** initialize with README, .gitignore, or license (since we're pushing existing code)
5. Click "Create repository"

### Step 2: Follow Option 1 Steps Above

After creating the repository, follow the steps in Option 1.

---

## Option 3: Quick Setup (All Commands at Once)

If you already have a repository URL, here's the complete sequence:

```bash
cd D:\HealthDairy

# Initialize Git
git init

# Create .gitignore (see contents above, or skip this step)
# Create .gitignore file with the contents mentioned above

# Add all files
git add .

# Commit
git commit -m "Initial commit: HealthDiary project"

# Add remote (replace with your repository URL)
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git

# Push
git branch -M main
git push -u origin main
```

---

## Authentication

When you push, you may be prompted for credentials:

**For HTTPS:**
- GitHub: Use a Personal Access Token (not password)
  - Generate token: GitHub → Settings → Developer settings → Personal access tokens → Generate new token
  - Give it `repo` permissions
- GitLab: Use your username and password, or Personal Access Token

**For SSH (recommended):**
- Generate SSH key: `ssh-keygen -t ed25519 -C "your_email@example.com"`
- Add to GitHub/GitLab: Settings → SSH Keys
- Use SSH URL: `git@github.com:USERNAME/REPO.git`

---

## Subsequent Pushes (After Initial Setup)

Once your repository is set up, future updates are simple:

```bash
# Check what changed
git status

# Add changes
git add .

# Or add specific files
git add file1.py file2.py

# Commit with message
git commit -m "Description of changes"

# Push to remote
git push
```

---

## Common Issues

### Issue: "fatal: remote origin already exists"
**Solution**: Remove and re-add:
```bash
git remote remove origin
git remote add origin YOUR_REPO_URL
```

### Issue: "error: failed to push some refs"
**Solution**: Pull first, then push:
```bash
git pull origin main --allow-unrelated-histories
git push -u origin main
```

### Issue: Authentication failed
**Solution**: 
- For GitHub: Use Personal Access Token instead of password
- For GitLab: Check your credentials or use SSH

### Issue: Large files
**Solution**: If you have large files, consider:
- Adding them to `.gitignore`
- Using Git LFS (Large File Storage)
- Removing them from history: `git rm --cached large_file.db`

---

## Recommended: Create README.md

Before pushing, consider creating a README.md file:

```bash
notepad README.md
```

Add project description, setup instructions, etc.

---

## Quick Reference

```bash
# Check status
git status

# Add files
git add .

# Commit
git commit -m "Your commit message"

# Push
git push

# Pull (get latest changes)
git pull

# View commit history
git log

# View remote
git remote -v
```

