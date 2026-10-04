# Contributing

Platforms and project policies change, so a correction with a source is the most useful contribution.

## Report a correction

[Open an issue](https://github.com/iAnonymous3000/opensource-contribution-guide/issues/new) with the section, what is wrong now and a link to a source, or send a pull request. The guide's steps [4](README.md#4-set-up-your-copy) to [6](README.md#6-open-the-pull-request) show how.

## House rules

1. Source every factual claim, and put the link next to the step it supports.
2. Prefer primary sources: git-scm.com, docs.github.com, docs.gitlab.com, docs.codeberg.org, a project's own CONTRIBUTING or policy pages, opensource.org, spdx.org and peer-reviewed research. Use press only to fill gaps, and say so.
3. Never invent a fact or a source. If you cannot find a source, leave the claim out.
4. Run every command you add in a scratch repository first, and give the output of `git --version` in the pull request.
5. Write plainly: short sentences, active voice, and no jargon without a definition.
6. No em or en dashes. Use a period, a comma or a new sentence.
7. Write dates as month and year, and use numbered steps instead of wide tables.
8. Stay vendor neutral. Name a platform or a paid course only when the step needs it, put the free option first, and use no affiliate links.
9. Say each thing once, in one place, and link to it from elsewhere.
10. Every section must help a reader toward a merged contribution or away from a harm. Cut anything that does not.
11. Leave out bold-label bullets as the default format, advice with no action, lists of tools with no word on when to pick which, filler such as comprehensive, rewarding or journey, bullets nested more than one level, and a contents list longer than a screen.

## Visuals

[`scripts/build_visuals.py`](scripts/build_visuals.py) generates the fork diagram's light and dark SVGs in `assets/`. Edit the script, never the SVGs, then run:

```sh
python3 scripts/build_visuals.py --check
```

It fails if a label does not fit or the README alt text differs from the diagram's. Without Pillow and DejaVu fonts (Arial and Menlo on a Mac), only the automated checks run the fit check. Commit what changes.

## Automated checks and review cycle

Every pull request and push to main runs [checks.yml](.github/workflows/checks.yml). It fails on em or en dashes, on `assets/` files the script would change, and on broken links or missing sections (`#anchors`) in Markdown files, except the new-issue link. Monthly runs open an issue for broken links.

After a full re-check against the sources, update Last reviewed in the README.

## License

By contributing, you [agree](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service#6-contributions-under-repository-license) that your contributions are licensed under [CC BY-SA 4.0](LICENSE).
