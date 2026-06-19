# POSSE Project Evaluator

A command-line tool that scores the health of a GitHub project against the [FOSS Project Health Evaluation Rubric](Project_Evaluation_Rubric.pdf) from the [Professors' Open Source Software Experience](https://teachingopensource.org/POSSE_2026-06) (POSSE) workshop. This is meant to be a quick first pass for instructors deciding whether an open-source project is a good one to have students contribute to in their course.

The tool inspects a repository through the PyGitHub API and scores nine criteria on a 0–2 scale (18 points total):

| Criterion | What it looks at |
|-----------|------------------|
| Licensing | Presence of an OSI-approved open source license |
| Technology | Top languages vs. your preferred languages |
| Level of Activity | Commit activity across the last four quarters |
| Number of Contributors | Size of the contributor community |
| Product Size | Estimated lines of code |
| Issue Tracker | Open/closed issue counts and recent activity |
| New Contributor | A CONTRIBUTING file and community profile |
| Community Norms | Presence of a Code of Conduct |
| User Base | Stars, forks, and releases |

A guided example from the workshop for the [OpenEnergyDashboard](https://github.com/OpenEnergyDashboard/OED) repository is provided in [Guided_Example.docx](Guided_Example.docx)

## Setup

```bash
pip install -r requirements.txt
export GITHUB_TOKEN=<your GitHub personal access token>
```

A token is required (the GitHub API rate-limits unauthenticated requests). A classic token with the `public_repo` scope is enough for public repositories.

## Usage

### Script

Evaluate a single repository:

```bash
python posse_project_eval.py https://github.com/OpenEnergyDashboard/OED
```

Evaluate multiple repositories from a file and save the results as YAML:

```bash
python posse_project_eval.py -f repos.txt -o results.yaml
```

#### Options

| Flag | Description |
|------|-------------|
| `repo_url` | GitHub URL of a single repository to evaluate |
| `-f`, `--file` | File of GitHub URLs (one per line); mutually exclusive with `repo_url` |
| `-o`, `--output` | Write results to a file in YAML format |
| `-c`, `--config` | Path to a config file (default: `./config.yaml`) |

#### Configuration

Some scoring can be tuned with a YAML config file. See [`config.example.yaml`](config.example.yaml):

```yaml
preferred_languages:
  - Python
  - TypeScript
loc_threshold: 10000
```

- `preferred_languages` — Technology scores 2 when one of these is a top  language; omit to accept any open source language.
- `loc_threshold` — estimated lines of code at or above which Product Size scores 2 (default: 10000).

#### Example Output

```
================================================================================
FOSS Project Name: OED
Description: Open Energy Dashboard
Repository: https://github.com/OpenEnergyDashboard/OED
================================================================================
Licensing — Level 2/2
  Data:   mpl-2.0
  Source: https://github.com/OpenEnergyDashboard/OED/blob/main/LICENSE
  Reason: OSI-approved open source license
--------------------------------------------------------------------------------
...
Total Score: 16/18
```

### AI Agent & Skill

This repository also includes AI-optimized files in the `.ai/` directory:

- **`.ai/agents/project-evaluator.agent.md`** — Executable workflow for evaluating a GitHub project against the POSSE rubric. An AI coding assistant can run this agent to evaluate a repository conversationally, using the Python tool or manual web-fetch evaluation.

- **`.ai/skills/posse-eval.md`** — This outlins the full POSSE FOSS Project Health Evaluation Rubric as a portable skill. Agents load this for rubric definitions, thresholds, and data sources when scoring.

No additional setup required. An AI assistant should be able to access these files directly by loading the agent or skill and providing a GitHub repository in the prompt:

```bash
@project-evaluator evaluate https://github.com/OpenEnergyDashboard/OED
```

## License

The code and configuration files in this repository are licensed under the **MIT License**. See [LICENSE](LICENSE).

The [FOSS Project Health Evaluation Rubric](./Project_Evaluation_Rubric.pdf) and guided example are copyright of Gregory W. Hislop and [TeachingOpenSource.org](https://teachingopensource.org/Main_Page), licensed under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/).
