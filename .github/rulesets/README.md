# Rulesets

`main-protection.json` is the branch ruleset for `main`: no deletion, no force push, every
change arrives through a pull request, and the five CI check runs (`test` on both runners and
both Pythons, `mobile`) must pass first. Repository admins may bypass only through a pull
request. The file is the source of truth; GitHub holds a copy.

Apply or refresh it with one command (needs a token with `repo` scope and admin on the repo):

```
gh api -X POST repos/Machine-Saver-Inc/shared-skills/rulesets --input .github/rulesets/main-protection.json
```

To change it later, edit the file, then `gh api -X PUT repos/Machine-Saver-Inc/shared-skills/rulesets/<id> --input ...`
with the id from `gh api repos/Machine-Saver-Inc/shared-skills/rulesets`.
