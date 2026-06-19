# POSSE FOSS Project Health Evaluation Rubric

> A rubric for evaluating the health and suitability of open-source projects for contribution.
> Derived from the [Professors' Open Source Software Experience](https://teachingopensource.org/POSSE_2026-06) (POSSE) workshop.

## Overview

| Aspect | Detail |
|--------|--------|
| Criteria | 9 |
| Scale | 0-2 per criterion |
| Maximum | 18 points |
| Purpose | Quick first-pass assessment of whether a project is a good candidate for student/contributor engagement |

## Scoring Criteria

### 1. Licensing

| Score | Definition |
|-------|------------|
| 2 | OSI-approved open source license (MIT, Apache-2.0, GPL-3.0, LGPL-2.1, BSD-2/3-Clause, MPL-2.0, ISC, Unlicense, CC0-1.0, CC-BY-4.0, CC-BY-SA-4.0, etc.) |
| 0 | No license, proprietary license, or non-OSI license |

**Data source**: `repo.get_license()` / GitHub license API. Look for a `LICENSE` file.

---

### 2. Technology

| Score | Definition |
|-------|------------|
| 2 | Preferred language(s) appear in the project's top 3 languages |
| 0 | No preferred languages match the top 3 |

**Data source**: `repo.get_languages()` / GitHub language bar. If no preferred languages are specified, any open-source language scores 2.

---

### 3. Level of Activity

| Score | Definition |
|-------|------------|
| 2 | All 4 quarters in the last year were active |
| 1 | 1-3 quarters active |
| 0 | 0 active quarters |

**Active quarter**: A majority (>= 7) of the 13 weeks in the quarter have at least one commit.

**Data source**: `repo.get_stats_commit_activity()` / GitHub Insights -> Commits graph. Returns up to 52 weeks.

---

### 4. Number of Contributors

| Score | Definition |
|-------|------------|
| 2 | >= 10 contributors |
| 1 | 3-9 contributors |
| 0 | 1-2 contributors |

**Data source**: `repo.get_contributors().totalCount` / GitHub Insights -> Contributors.

---

### 5. Product Size

| Score | Definition |
|-------|------------|
| 2 | Estimated LOC >= threshold (default: 10,000) |
| 1 | 1 - (threshold - 1) LOC |
| 0 | ~0 LOC |

**Estimation**: Total bytes in language data / 40 (avg bytes per source line).

**Data source**: `repo.get_languages()` - sum of bytes across all languages.

---

### 6. Issue Tracker

| Score | Definition |
|-------|------------|
| 2 | Active: has both open issues and at least one issue updated within the last 60 days |
| 1 | Low/sporadic activity: issues exist but no recent activity, or no open issues |
| 0 | No issues found or no sign of any activity |

**Data source**: `repo.get_issues(state="open"/"closed", sort="updated")`. Check `totalCount` and most recent `updated_at`.

---

### 7. New Contributor

| Score | Definition |
|-------|------------|
| 2 | Has CONTRIBUTING file AND community profile (discussions or wiki) |
| 1 | Has either CONTRIBUTING file OR community profile |
| 0 | Neither |

**Data source**: Look for `CONTRIBUTING.md`, `.github/CONTRIBUTING.md`, `docs/CONTRIBUTING.md`. Check for discussions (`repo.has_discussions`) or wiki (`repo.has_wiki`).

---

### 8. Community Norms

| Score | Definition |
|-------|------------|
| 2 | Has CODE_OF_CONDUCT.md |
| 1 | No code of conduct but no evidence of toxic behavior |
| 0 | Evidence of rude, unprofessional, harassing, or otherwise undesirable behavior |

**Data source**: Look for `CODE_OF_CONDUCT.md`, `.github/CODE_OF_CONDUCT.md`, `docs/CODE_OF_CONDUCT.md`. Note: the automated check only scores 2 or 1; score 0 requires manual observation.

---

### 9. User Base

| Score | Definition |
|-------|------------|
| 2 | >= 50 stars AND >= 10 forks, OR has any releases |
| 1 | Stars > 0 OR forks > 0 |
| 0 | No stars, no forks, no releases |

**Data source**: `repo.stargazers_count`, `repo.forks_count`, `repo.get_releases().totalCount`.

---

## Default Thresholds

All default values live in [`config.example.yaml`](../config.example.yaml). See that file
for current defaults for each threshold. The table below maps config keys to criteria:

| Config Key | Used By |
|------------|---------|
| `contributor_high`, `contributor_low` | #4 Contributors |
| `user_base_stars`, `user_base_forks` | #9 User Base |
| `issue_recent_days` | #6 Issue Tracker |
| `loc_threshold`, `bytes_per_line` | #5 Product Size |
| `weeks_per_quarter` | #3 Level of Activity |

## Evaluation Workflow

1. **Identify the project** - Get the GitHub repository URL and extract owner/repo name.
2. **Collect data** - For each criterion, fetch the relevant data from GitHub (via API, web scraping, or direct URL inspection).
3. **Score each criterion** - Apply the definitions above to assign 0, 1, or 2.
4. **Sum the scores** - Total out of 18.
5. **Interpret** - Projects scoring 14+ are generally strong candidates. 10-13 may be viable with caveats. Below 10 may need further investigation.

## References

- Full rubric: [`rubric.md`](../rubric.md) (in this repository)
- Example evaluation: [`OED_Project_Eval.md`](../OED_Project_Eval.md)
- Automated evaluation tool: [`posse_project_eval.py`](../posse_project_eval.py)
- Original workshop: [TeachingOpenSource.org / POSSE](https://teachingopensource.org/POSSE_2026-06)
