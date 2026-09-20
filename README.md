# Machine Saver shared skills

Everything that should be the same in every Machine Saver desktop application,
in one place, so that a lesson learned in one of them lands in all of them.

| | |
| --- | --- |
| [`skills/ms-desktop-app/`](skills/ms-desktop-app/) | The skill an agent reads before scaffolding or changing one of these tools. Currently **2.1.0**. |
| [`packages/ms-appkit/`](packages/ms-appkit/) | The Python package that *is* the shared shell. Currently **1.0.0**. |

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
[`skills/ms-desktop-app/SKILL.md`](skills/ms-desktop-app/SKILL.md). Start at §0.

## Using the kit

```toml
dependencies = [
  "ms-appkit @ git+https://github.com/Machine-Saver-Inc/shared-skills.git#subdirectory=packages/ms-appkit",
]
```

A runnable two-screen application that uses it correctly, with its own
house-rules test, is in
[`packages/ms-appkit/template/`](packages/ms-appkit/template/).

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

MIT, except the Lucide icon set vendored in the kit, which is ISC and carries
its own `LICENSE` beside the files.
