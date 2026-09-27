# Upload to a private GitHub repository

1. Extract the delivered `reading-tutor-upload.zip`.
2. Create a **private** repository in your own GitHub account.
3. Upload the extracted files and folders so `README.md` is at the repository root. Preserve `.github/`, `.gitignore`, `.gitattributes`, `.editorconfig`, and `apps/gradio/.env.example`.
4. Confirm that `.env`, `data/`, recordings and virtual environments are absent. The supplied ZIP already excludes them.

Do not upload only the ZIP if you want GitHub to display the source and README. Use a Git client if your browser's folder picker omits hidden dotfiles. A ZIP does not contain Git history or credentials.

To regenerate a safe archive locally:

```sh
python scripts/package.py path/to/reading-tutor-upload.zip
```

This command uses an explicit source allowlist and private-directory exclusions. It does not commit, push, create a GitHub repository or change visibility. The completion work left the existing local repository on `main` with files staged; no remote was added or first commit created. Choose licensing and GitHub ownership yourself before sharing beyond the intended private repository.
