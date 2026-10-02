# Machine Saver shared skills

<!-- machine-saver-scope:start -->
## Scope

Reusable Machine Saver development skills and the two application shells — ms-appkit for desktop, ms-mobilekit for iPhone/Android — including common application behavior and conventions.

**Owner:** Machine-Saver-Inc. **Development area:** Developer tooling.

## Ownership boundaries

Product-specific business logic, private company policies and credentials do not belong in this public shared toolkit.

## Development tracking

Track work in this repository's issues and pull requests. Cross-repository work is coordinated through the [Machine Saver development Projects](https://github.com/orgs/Machine-Saver-Inc/projects).

Follow this repository's contribution instructions and preserve links to related product issues. Scope describes responsibility; release and deployment readiness require the repository's own evidence.
<!-- machine-saver-scope:end -->

Everything that should be the same in every Machine Saver application, desktop or mobile,
in one place, so that a lesson learned in one of them lands in all of them.

| | |
| --- | --- |
| [`skills/ms-desktop-app/`](skills/ms-desktop-app/) | The skill an agent reads before scaffolding or changing one of these tools. Currently **2.4.3**. |
| [`packages/ms-appkit/`](packages/ms-appkit/) | The Python package that *is* the shared shell. Currently **1.4.0**. |
| [`skills/ms-mobile-app/`](skills/ms-mobile-app/) | The skill an agent reads before scaffolding or changing a Machine Saver iPhone/Android app. Currently **1.0.0**. |
| [`packages/ms-mobilekit/`](packages/ms-mobilekit/) | The JavaScript package that *is* the shared mobile shell. Currently **1.0.0**. |

## Why this exists

Somebody who has used one Machine Saver tool should already know, without being
told, how to report a problem, see what changed, get the latest version and find
their way around. That only happens if every one of them is built from the same
shell — not from a copy of the same shell, which drifts by the second release.

So the shell is a package an application imports, the vocabulary of buttons is a
register in the skill, and the rules that a machine can check are functions in
`ms_appkit.housekeeping` that fail an application's build.

## Using the skill

Add this repository as a skill source, or point an agent at
[`skills/ms-desktop-app/SKILL.md`](skills/ms-desktop-app/SKILL.md) for a desktop
tool or [`skills/ms-mobile-app/SKILL.md`](skills/ms-mobile-app/SKILL.md) for a
phone app. Start at §0 of either.

## Using the kit

```toml
dependencies = [
  "ms-appkit @ git+https://github.com/Machine-Saver-Inc/shared-skills.git#subdirectory=packages/ms-appkit",
]
```

A runnable two-screen application that uses it correctly, with its own
house-rules test, is in
[`packages/ms-appkit/template/`](packages/ms-appkit/template/).

For a phone app:

```json
"dependencies": {
  "ms-mobilekit": "git+https://github.com/Machine-Saver-Inc/shared-skills.git#subdirectory=packages/ms-mobilekit"
}
```

with the matching template in
[`packages/ms-mobilekit/template/`](packages/ms-mobilekit/template/).

## Versioning

The skill and the kit each carry a version and move together: a change to the
shell bumps the kit, and bumps the skill too if it changes what the skill says.
Both are recorded in [`CHANGELOG.md`](CHANGELOG.md).

## Contributing

Two rules, both learned the hard way:

1. **Fix the class, not the case.** If something was missed once, ask whether it
   can be a check in `ms_appkit.housekeeping` before adding a sentence to the
   skill.
2. **Prove a new check fails when its rule is broken.** Break the rule, watch it
   go red, put it back. A guard nobody has seen fail is decoration.

## Licence

MIT, except the Lucide icon set vendored in each kit, which is ISC and carries
its own `LICENSE` beside the files.
