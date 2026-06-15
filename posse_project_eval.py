from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from github import Github
from github import Auth
from github import GithubException
import sys
import os
import argparse
from pathlib import Path
import yaml


# Scoring thresholds (kept here so the tool is easy to tune).
CONTRIBUTOR_HIGH = 10        # >= this many contributors scores 2
CONTRIBUTOR_LOW = 3          # >= this many (but below HIGH) scores 1
USER_BASE_STARS = 50         # stars + forks needed for a "2" on User Base
USER_BASE_FORKS = 10
ISSUE_RECENT_DAYS = 180      # an issue updated within this window counts as recent
DEFAULT_LOC_THRESHOLD = 10000
BYTES_PER_LINE = 40          # rough avg bytes per source line for LOC estimates
WEEKS_PER_QUARTER = 13


def _band_score(value: int, high: int, low: int) -> int:
    """Score 2 if value >= high, 1 if value >= low, else 0."""
    return 2 if value >= high else (1 if value >= low else 0)


def _pick(score: int, high: str, mid: str, low: str) -> str:
    """Choose a reason string matching a 0-2 score."""
    return {2: high, 1: mid, 0: low}[score]


@dataclass
class CriterionResult:
    name: str
    score: int
    data: str
    source: str
    reason: str


@dataclass
class EvaluationResult:
    project_name: str
    repo_url: str
    description: str
    topics: list[str]
    criteria: list[CriterionResult] = field(default_factory=list)
    total_score: int = 0


def load_config(config_path: str) -> dict:
    path = Path(config_path).expanduser()
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def _get_osf_license_keys() -> set:
    return {
        "mit", "apache-2.0", "gpl-2.0", "gpl-3.0", "lgpl-2.1", "lgpl-3.0",
        "bsd-2-clause", "bsd-3-clause", "mpl-2.0", "isc", "unlicense",
        "cc0-1.0", "cc-by-4.0", "cc-by-sa-4.0"
    }


def eval_licensing(repo) -> CriterionResult:
    try:
        license_info = repo.get_license()
    except GithubException:
        license_info = None
    if license_info is None:
        return CriterionResult("Licensing", 0, "No license found",
                               repo.html_url, "Project has no license file")
    license_key = license_info.license.key if license_info.license else ""
    source = license_info.html_url or repo.html_url
    osf_licenses = _get_osf_license_keys()
    if license_key.lower() in osf_licenses:
        return CriterionResult("Licensing", 2, license_key, source,
                               "OSI-approved open source license")
    return CriterionResult("Licensing", 0, license_key, source,
                           "Non-open-source or proprietary license")


def eval_technology(repo, preferred_languages: list[str]) -> CriterionResult:
    languages = repo.get_languages()
    if not languages:
        return CriterionResult("Technology", 0, "Unknown",
                               repo.html_url, "No language information available")
    total_bytes = sum(languages.values())
    top_langs = sorted(languages.items(), key=lambda x: x[1], reverse=True)[:3]
    top_lang_names = [lang for lang, _ in top_langs]
    top_lang_pcts = {lang: round(count / total_bytes * 100) for lang, count in top_langs}
    data_str = ", ".join(f"{lang} ({pct}%)" for lang, pct in top_lang_pcts.items())
    if not preferred_languages:
        return CriterionResult("Technology", 2, data_str, repo.html_url,
                               "Any open source language acceptable")
    matches = [lang for lang in top_lang_names if lang.lower() in [l.lower() for l in preferred_languages]]
    if matches:
        return CriterionResult("Technology", 2, data_str,
                               f"{repo.html_url}/search?q=language%3A{','.join(top_lang_names)}",
                               f"Preferred languages {matches} found in top languages")
    return CriterionResult("Technology", 0, data_str,
                           f"{repo.html_url}/search?q=language%3A{','.join(top_lang_names)}",
                           "Top languages do not match preferred technologies")


def eval_activity(repo) -> CriterionResult:
    stats = repo.get_stats_commit_activity()
    if not stats:
        return CriterionResult("Level of Activity", 0, "No commit data",
                               f"{repo.html_url}/commits?from=&to=&",
                               "Cannot determine activity levels")
    # get_stats_commit_activity returns up to 52 weekly entries (oldest first).
    # Take the most recent 52 weeks and split into 4 quarters of 13 weeks each.
    # A quarter is "active" if a majority of its weeks have at least one commit.
    weeks = sorted(stats, key=lambda s: s.week)[-52:]
    active_quarters = 0
    for i in range(0, len(weeks), 13):
        quarter = weeks[i:i + 13]
        if not quarter:
            continue
        active_weeks = sum(1 for w in quarter if w.total > 0)
        if active_weeks > len(quarter) / 2:
            active_quarters += 1
    score = 2 if active_quarters >= 4 else (1 if active_quarters > 0 else 0)
    return CriterionResult("Level of Activity", score, f"{active_quarters}/4 quarters active in last year",
                           f"{repo.html_url}/graphs/commit-activity",
                           "Project is actively maintained" if score >= 1 else "No recent activity")


def eval_contributors(repo) -> CriterionResult:
    count = repo.get_contributors().totalCount
    score = _band_score(count, CONTRIBUTOR_HIGH, CONTRIBUTOR_LOW)
    reason = _pick(score, "Healthy contributor community",
                   "Moderate contributor base", "Very few contributors")
    return CriterionResult("Number of Contributors", score, f"{count} contributors",
                           f"{repo.html_url}/graphs/contributors",
                           reason)


def eval_product_size(repo, loc_threshold: int) -> CriterionResult:
    languages = repo.get_languages()
    total_bytes = sum(languages.values())
    # Rough heuristic: source lines average ~BYTES_PER_LINE bytes once
    # whitespace and punctuation are included.
    est_loc = round(total_bytes / BYTES_PER_LINE)
    if est_loc == 0:
        return CriterionResult("Product Size", 0, "~0 LOC",
                               repo.html_url, "Project has no meaningful code base")
    score = 2 if est_loc >= loc_threshold else 1
    return CriterionResult("Product Size", score, f"~{est_loc:,} LOC (threshold: {loc_threshold})",
                           f"{repo.html_url}/search?q=language%3A*",
                           f"Substantial codebase ({est_loc:,} LOC)" if score == 2 else "Smaller codebase but still meaningful")


def eval_issue_tracker(repo) -> CriterionResult:
    # PaginatedList.totalCount and list[0] each cost a single request, so we
    # never page through the whole (potentially huge) issue history.
    open_issues = repo.get_issues(state="open", sort="updated", direction="desc")
    closed_issues = repo.get_issues(state="closed", sort="updated", direction="desc")
    open_count = open_issues.totalCount
    closed_count = closed_issues.totalCount
    total_count = open_count + closed_count
    if total_count == 0:
        return CriterionResult("Issue Tracker", 0, "No issues found",
                               f"{repo.html_url}/issues", "No issue tracker activity")
    cutoff = datetime.now(timezone.utc) - timedelta(days=ISSUE_RECENT_DAYS)
    has_recent = any(lst.totalCount > 0 and lst[0].updated_at >= cutoff
                     for lst in (open_issues, closed_issues))
    score = 2 if has_recent and open_count > 0 else 1
    return CriterionResult("Issue Tracker", score, f"{open_count} open, {closed_count} closed",
                           f"{repo.html_url}/issues",
                           _pick(score, "Active issue tracking",
                                 "Low or sporadic activity", "No recent activity"))


def eval_new_contributor(repo) -> CriterionResult:
    contributing_url = None
    for path in ("CONTRIBUTING.md", ".github/CONTRIBUTING.md", "docs/CONTRIBUTING.md"):
        try:
            contributing_url = repo.get_contents(path).html_url
            break
        except GithubException:
            continue
    has_contributing = contributing_url is not None
    has_profile = repo.has_discussions or repo.has_wiki
    score = _band_score(int(has_contributing) + int(has_profile), 2, 1)
    sources = [contributing_url] if contributing_url else []
    sources.append(f"{repo.html_url}/community")
    reason = _pick(score, "Clear instructions and welcome for new contributors",
                   "Some evidence of welcome", "Little or no evidence of welcome")
    return CriterionResult("New Contributor", score, "CONTRIBUTING file and community profile",
                           ", ".join(sources), reason)


def eval_community_norms(repo) -> CriterionResult:
    coc_url = None
    for path in ("CODE_OF_CONDUCT.md", ".github/CODE_OF_CONDUCT.md", "docs/CODE_OF_CONDUCT.md"):
        try:
            coc_url = repo.get_contents(path).html_url
            break
        except GithubException:
            continue
    has_coc = coc_url is not None
    score = 2 if has_coc else 1
    return CriterionResult("Community Norms", score,
                           "Code of Conduct present" if has_coc else "No Code of Conduct",
                           coc_url or f"{repo.html_url}/community",
                           "Documented and welcoming community norms" if score == 2
                           else "No signs of poor behavior but no stated code of conduct")


def eval_user_base(repo) -> CriterionResult:
    stars = repo.stargazers_count
    forks = repo.forks_count
    release_count = repo.get_releases().totalCount
    if (stars >= USER_BASE_STARS and forks >= USER_BASE_FORKS) or release_count > 0:
        score = 2
    elif stars > 0 or forks > 0:
        score = 1
    else:
        score = 0
    return CriterionResult("User Base", score, f"{stars} stars, {forks} forks, {release_count} releases",
                           f"{repo.html_url}/releases",
                           _pick(score, "Active and engaged user base",
                                 "Some evidence of user base",
                                 "Little to no evidence of product use beyond development team"))


def evaluate_project(repo, preferred_languages: list[str], loc_threshold: int) -> EvaluationResult:
    result = EvaluationResult(
        project_name=repo.name,
        repo_url=repo.html_url,
        description=repo.description or "No description available",
        topics=list(repo.get_topics())
    )
    result.criteria = [
        eval_licensing(repo),
        eval_technology(repo, preferred_languages),
        eval_activity(repo),
        eval_contributors(repo),
        eval_product_size(repo, loc_threshold),
        eval_issue_tracker(repo),
        eval_new_contributor(repo),
        eval_community_norms(repo),
        eval_user_base(repo),
    ]
    result.total_score = sum(c.score for c in result.criteria)
    return result


def format_console(result: EvaluationResult) -> str:
    max_width = 80
    header = f"{'=' * max_width}\n"
    header += f"FOSS Project Name: {result.project_name}\n"
    header += f"Description: {result.description[:max_width - 20]}\n"
    header += f"Topics: {', '.join(result.topics[:5])}\n"
    header += f"Repository: {result.repo_url}\n"
    header += f"{'=' * max_width}\n"
    for c in result.criteria:
        header += f"{c.name} — Level {c.score}/2\n"
        header += f"  Data:   {c.data}\n"
        header += f"  Source: {c.source}\n"
        header += f"  Reason: {c.reason}\n"
        header += f"{'-' * max_width}\n"
    header += f"Total Score: {result.total_score}/18\n"
    return header


def format_yaml(result: EvaluationResult) -> str:
    data = {
        "project_name": result.project_name,
        "repo_url": result.repo_url,
        "description": result.description,
        "topics": result.topics,
        "criteria": [
            {
                "name": c.name,
                "score": c.score,
                "data": c.data,
                "source": c.source,
                "reason": c.reason
            }
            for c in result.criteria
        ],
        "total_score": result.total_score
    }
    return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)


def _parse_url(url):
    cleaned = url.strip().rstrip('/')
    if cleaned.endswith('.git'):
        cleaned = cleaned[:-len('.git')]
    parts = [p for p in cleaned.split('/') if p]
    # Expect ".../owner/repo" — take the two segments after the host.
    owner, repo = parts[-2], parts[-1]
    return f"{owner}/{repo}"


def main():
    parser = argparse.ArgumentParser(description='Evaluate a GitHub project based on POSSE criteria.')
    parser.add_argument('repo_url', nargs='?', help='GitHub URL of the repository to evaluate')
    parser.add_argument('-f', '--file', type=str, help='Optional file of GitHub URLs to evaluate')
    parser.add_argument('-o', '--output', type=str, help='Optional output file to save results (YAML format)')
    parser.add_argument('-c', '--config', type=str, default='./config.yaml',
                        help='Path to config file (default: ./config.yaml)')

    args = parser.parse_args()

    if args.repo_url and args.file:
        parser.error('positional repo_url and --file are mutually exclusive')
    if not args.repo_url and not args.file:
        parser.error('one of repo_url or --file must be provided')

    config = load_config(args.config)
    preferred_languages = []
    if config.get('preferred_languages'):
        preferred_languages = config['preferred_languages']
    loc_threshold = config.get('loc_threshold', DEFAULT_LOC_THRESHOLD)

    token = os.getenv('GITHUB_TOKEN')
    if not token:
        print("❌ Error: GITHUB_TOKEN environment variable is not set.", file=sys.stderr)
        sys.exit(1)
    g = Github(auth=Auth.Token(token))

    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"❌ Error: File '{args.file}' not found.", file=sys.stderr)
            sys.exit(1)
        with open(file_path, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip()]
    else:
        urls = [args.repo_url]

    results = []
    for url in urls:
        full_name = _parse_url(url)
        try:
            repo = g.get_repo(full_name)
        except GithubException as exc:
            print(f"❌ Error: Failed to fetch repository '{full_name}'.", file=sys.stderr)
            print(f"   Check the URL, repository visibility, and GITHUB_TOKEN permissions.", file=sys.stderr)
            print(f"   GitHub API error: {exc.data if hasattr(exc, 'data') else exc}", file=sys.stderr)
            continue
        result = evaluate_project(repo, preferred_languages, loc_threshold)
        results.append(result)
        print(format_console(result))

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            for result in results:
                f.write(format_yaml(result))
                f.write("---\n")


if __name__ == "__main__":
    main()
