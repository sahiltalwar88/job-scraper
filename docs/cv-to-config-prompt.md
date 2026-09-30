# Generate your `config.json` from your résumé

This is the starting point for setting up this scraper for **your** search. Sit down once with:

- your **résumé** (or CV),
- your **LinkedIn profile** (a PDF export or the URL), and
- an idea of **what and where** you want to work.

An AI assistant interviews you, then writes `config.json` (and, if you want fit-scored phone alerts, `scoring_profile.json`). The [checklist at the end](#after-the-files-are-written) takes you from those files to a running scraper.

**How to use it:**
- **With an AI agent** (Claude Code, Devin, Cursor, …) in a clone of your fork: ask it to follow this file. It asks the questions below, writes the files, and runs the checklist with you.
- **With a chatbot** (ChatGPT, Claude, Gemini, …): paste the text in the box, attach your résumé and LinkedIn PDF, answer its questions, then save what it returns and follow the checklist yourself.

The full list of everything the setup covers, including sources and features you might not use, is in [`docs/setup-skill-plan.md`](setup-skill-plan.md).

---

```
You are setting up a personal job scraper for me. It searches job boards for
postings whose TITLE matches my search, and shows them on a dashboard. Read my
résumé and LinkedIn profile (attached or pasted below), then INTERVIEW me before
writing anything. Ask in small groups, propose answers from my résumé, and let
me confirm or change them.

## Ask me about

1. Target roles: which job titles, which seniority, which field or domain; any
   titles or seniority levels to exclude (always exclude internships/co-ops).
2. Locations: which states, cities or countries, and whether remote counts.
   The one-time parallel backfill only covers the US (states, US-wide, Remote).
   Places outside the US work for the hourly watcher, and for the watcher's
   single-job backfill, as long as their country is in location_filter.terms;
   otherwise postings in a built-in list of non-US countries (Canada, UK,
   Australia, India, …) are dropped.
3. Sources. LinkedIn is always on. Optional sources (each is a workflow I move
   from .github/workflows/disabled/ to .github/workflows/ to turn on):
   Indeed, Glassdoor, ZipRecruiter, Google Jobs (these four need no key; Google
   Jobs can use a SerpAPI or Oxylabs key as a fallback), HiringCafe, USAJOBS (US
   federal), CalCareers (California state), CSU Careers (California State
   University), and NEOGOV/GovernmentJobs + CalOpps (US state/local government).
4. Employers: companies I'd most like to work for (they get a daily digest and
   loosen the title filter), and company names to always drop (e.g. staffing
   agencies).
5. Highlights: 3-6 skills or topics that should get a gold star on the
   dashboard and trigger a phone alert when a job mentions them.
6. Dashboard: a short tracker title, a subtitle (my locations), and one emoji.
7. Phone alerts (Pushover): do I want them? If yes, do I also want alerts for
   jobs that score well against my résumé (then write scoring_profile.json too),
   and do I want a weekly digest?
8. AI fit-scoring with the Claude API (optional, costs API credit): do I want
   it? If yes, which role families should jobs be sorted into.

## Then output config.json

Output ONE JSON object: valid JSON, no comments, no markdown fences. Include
EVERY key below, exactly this shape. Use [] or "" for anything I don't use:
any key you leave out falls back to config.example.json, which is someone
else's search.

{
  "profile": { "title": "<e.g. 'Data Analyst Tracker'>", "subtitle": "<e.g. 'Chicago · Remote'>", "emoji": "<one emoji>" },
  "keywords": {
    "include": [ "<20-60 lowercase job-TITLE phrases that fit me>" ],
    "exclude": [ "intern", "internship", "co-op", "trainee", "<other titles to drop>" ],
    "fuzzy_seniority": [ "<seniority words, e.g. 'senior', 'lead', 'principal'; [] to turn fuzzy matching off>" ],
    "fuzzy_domain": [ "<domain words, e.g. 'data', 'analytics'; [] to turn fuzzy matching off>" ],
    "fuzzy_exclude": [ "<words that disqualify a fuzzy match, e.g. 'sales'>" ]
  },
  "search_terms": {
    "linkedin": [ "<at most 8 LinkedIn search queries>" ],
    "indeed": [ "<6-10 broad queries, or [] if Indeed is off>" ],
    "glassdoor": [], "ziprecruiter": [], "google_jobs": [], "hiring_cafe": [],
    "usajobs": [ "<queries if USAJOBS is on, else []>" ],
    "calcareers": [ "<queries if CalCareers is on, else []>" ],
    "governmentjobs": [ "<queries if NEOGOV is on, else []>" ],
    "workday": []
  },
  "locations": {
    "linkedin": [ { "name": "<label>", "location": "<City, State, United States | State, United States | United States | Remote>", "geoId": "" } ],
    "linkedin_partitions": {
      "states": [ <COPY THE 50-STATE LIST BELOW VERBATIM, or [] if I only want specific places> ],
      "high_volume": {
        "locations": [ <see the high-volume rule below> ],
        "day_slices": true
      }
    },
    "indeed": [ { "location": "<City, ST or State>", "country": "USA" } ],
    "glassdoor": [], "ziprecruiter": [], "google_jobs": []
  },
  "location_filter": { "terms": [ "<lowercase place substrings, e.g. 'chicago', ', il', 'illinois', 'remote', 'united states'>" ] },
  "google_jobs": { "queries": [], "serpapi_api_key": "", "oxylabs_username": "", "oxylabs_password": "" },
  "jobspy": { "proxies": [], "user_agent": "" },
  "hiring_cafe": { "max_pages": 3 },
  "csucareers": { "max_pages": 30 },
  "employers": { "priority": [ "<companies, or []>" ], "exclude": [ "<company-name substrings, or []>" ] },
  "priority_topics": { "terms": [ [ "<label>", "<regex>" ] ] },
  "role_categories": { "terms": [ [ "<role bucket>", "<regex over the title>" ] ] },
  "sector_classification": { "terms": [ [ "<sector>", "<regex over the company name>" ] ] },
  "notify": { "weekly_digest": { "enabled": false, "days": 7 } },
  "triage": { "role_families": "<pipe-separated role families if AI fit-scoring is on, else 'other'>" }
}

50-state list for locations.linkedin_partitions.states (copy verbatim):
[
  { "name": "Alabama", "location": "Alabama, United States" },
  { "name": "Alaska", "location": "Alaska, United States" },
  { "name": "Arizona", "location": "Arizona, United States" },
  { "name": "Arkansas", "location": "Arkansas, United States" },
  { "name": "California", "location": "California, United States" },
  { "name": "Colorado", "location": "Colorado, United States" },
  { "name": "Connecticut", "location": "Connecticut, United States" },
  { "name": "Delaware", "location": "Delaware, United States" },
  { "name": "Florida", "location": "Florida, United States" },
  { "name": "Georgia", "location": "Georgia, United States" },
  { "name": "Hawaii", "location": "Hawaii, United States" },
  { "name": "Idaho", "location": "Idaho, United States" },
  { "name": "Illinois", "location": "Illinois, United States" },
  { "name": "Indiana", "location": "Indiana, United States" },
  { "name": "Iowa", "location": "Iowa, United States" },
  { "name": "Kansas", "location": "Kansas, United States" },
  { "name": "Kentucky", "location": "Kentucky, United States" },
  { "name": "Louisiana", "location": "Louisiana, United States" },
  { "name": "Maine", "location": "Maine, United States" },
  { "name": "Maryland", "location": "Maryland, United States" },
  { "name": "Massachusetts", "location": "Massachusetts, United States" },
  { "name": "Michigan", "location": "Michigan, United States" },
  { "name": "Minnesota", "location": "Minnesota, United States" },
  { "name": "Mississippi", "location": "Mississippi, United States" },
  { "name": "Missouri", "location": "Missouri, United States" },
  { "name": "Montana", "location": "Montana, United States" },
  { "name": "Nebraska", "location": "Nebraska, United States" },
  { "name": "Nevada", "location": "Nevada, United States" },
  { "name": "New Hampshire", "location": "New Hampshire, United States" },
  { "name": "New Jersey", "location": "New Jersey, United States" },
  { "name": "New Mexico", "location": "New Mexico, United States" },
  { "name": "New York", "location": "New York, United States" },
  { "name": "North Carolina", "location": "North Carolina, United States" },
  { "name": "North Dakota", "location": "North Dakota, United States" },
  { "name": "Ohio", "location": "Ohio, United States" },
  { "name": "Oklahoma", "location": "Oklahoma, United States" },
  { "name": "Oregon", "location": "Oregon, United States" },
  { "name": "Pennsylvania", "location": "Pennsylvania, United States" },
  { "name": "Rhode Island", "location": "Rhode Island, United States" },
  { "name": "South Carolina", "location": "South Carolina, United States" },
  { "name": "South Dakota", "location": "South Dakota, United States" },
  { "name": "Tennessee", "location": "Tennessee, United States" },
  { "name": "Texas", "location": "Texas, United States" },
  { "name": "Utah", "location": "Utah, United States" },
  { "name": "Vermont", "location": "Vermont, United States" },
  { "name": "Virginia", "location": "Virginia, United States" },
  { "name": "Washington", "location": "Washington, United States" },
  { "name": "West Virginia", "location": "West Virginia, United States" },
  { "name": "Wisconsin", "location": "Wisconsin, United States" },
  { "name": "Wyoming", "location": "Wyoming, United States" }
]

## Rules

- keywords.include / keywords.exclude: full lowercase words or phrases as they
  appear in real titles ("data analyst", not "analy"). A single word only
  matches as a whole word, so stems never match; a multi-word phrase matches
  anywhere in the title.
- Fuzzy matching (fuzzy_seniority + fuzzy_domain): when BOTH are non-empty,
  LinkedIn titles are kept if they pair a seniority word with a domain word,
  instead of needing a keywords.include phrase. Use whole words. Set both to []
  unless my titles vary a lot (e.g. "Director, Engineering" vs "Head of
  Engineering").
- search_terms.linkedin: AT MOST 8. The one-time backfill runs 2 search terms
  per job across all 50 states, and GitHub allows at most 256 jobs per phase
  (8 terms = 4 batches x 43 states = 172 jobs; 10 would be 215, but then
  high-volume locations no longer fit). Pick the 8 queries that cover my
  titles best.
- Other boards' search_terms are broader than keywords (what you'd type in a
  search box). Glassdoor, ZipRecruiter, Google Jobs and HiringCafe use Indeed's
  terms and locations when theirs are []. Leave a disabled board's lists [].
- High-volume rule: if states is the 50-state list, set high_volume.locations to
  these 9 (their "location" must match the states entries exactly):
  "United States", "Remote", and California, Texas, New York, Washington,
  Virginia, Massachusetts, Illinois as { "name": "<State>", "location":
  "<State>, United States" }. With at most 8 search terms that is 4 x 9 x 7 =
  252 jobs. Use fewer if my field is small; if states is [], use [].
- locations.linkedin: one entry per place I named, plus { "name": "Remote",
  "location": "Remote", "geoId": "" } if remote counts. Leave geoId "" unless I
  give one.
- location_filter.terms: every way my places appear in a job's location text
  (city, ", ST", state name, metro name), plus "remote" and "united states" if
  those count. US state names are always accepted anyway. For a place outside
  the US, include its country as a whole word (e.g. "australia"), or its
  postings are dropped.
- employers.priority: full company names, 6+ characters where possible
  (matching is a loose substring match).
- Regexes (priority_topics, role_categories, sector_classification): plain
  regex source that works in BOTH Python and JavaScript: no slashes, no flags,
  no inline (?i); matching is already case-insensitive. Double every backslash
  for JSON (write \\b, not \b). role_categories: 5-9 buckets, most specific
  first. sector_classification: 3-8 sectors matched against company names
  (e.g. [ "Healthcare", "health|hospital|medical" ]), or [] to skip.
- google_jobs keys, jobspy proxies: keep empty; credentials go in GitHub
  secrets, not in this file.

## If I want résumé-scored alerts, also output scoring_profile.json

A second JSON object, same rules:

{
  "version": 1,
  "description": "<one line: whose search this scores>",
  "settings": { "title_multiplier": 3, "body_multiplier": 1, "score_multiplier": 1.6, "generic_cap": 35, "standout_threshold": 60 },
  "fit_terms": [ { "pattern": "<regex>", "weight": <1-16> } ],
  "signature_terms": [ "<regex for my rarest, most specific strengths>" ],
  "poor_fit_terms": [ { "pattern": "<regex>", "penalty": <1-20> } ]
}

- fit_terms: 10-25 regexes for my skills, tools, domains and titles; weight
  16 for exact target titles down to 3 for generic skills. A title match counts
  3x a description match.
- signature_terms: 3-8 regexes that only a strong match would mention. Jobs
  matching none are capped at generic_cap.
- poor_fit_terms: regexes for things I don't want (wrong seniority, domains).

Output ONLY the JSON object(s).

MY RÉSUMÉ AND LINKEDIN:
<attach or paste>
```

---

## After the files are written

1. **Save** the output as `config.json` in the repo root, and `scoring_profile.json` if you made one. Don't commit either: `config.json` is gitignored. This repo commits a `scoring_profile.json` that has fit scoring turned off; keep your own as a secret instead.
2. **Store them as secrets** (single line, made by the export script; see README "Setup" → Step 4):
   - `bash scripts/export-config-secret.sh` → repository secret **`CONFIG_JSON`**
   - `bash scripts/export-config-secret.sh scoring_profile.json` → secret **`SCORING_PROFILE_JSON`** (optional)
3. **GitHub settings** (README "Setup" → Steps 3–4): enable Actions; Settings → Actions → General → Workflow permissions → **Read and write**; Pages from `main`, `/`; repository **variable** `ENABLE_DATA_COMMITS` = `true`.
4. **Optional secrets and variables**, for what you chose:
   - Phone alerts: secrets `PUSHOVER_TOKEN`, `PUSHOVER_USER`; variable `NOTIFY_MIN_FIT` (default 75). Weekly digest: variable `WEEKLY_DIGEST_PUSHOVER` = `true` (and optionally `WEEKLY_DIGEST_DAYS`, `DASHBOARD_URL`).
   - Google Jobs fallback: secret `SERPAPI_API_KEY`, or `OXYLABS_USERNAME` + `OXYLABS_PASSWORD`. Indeed/Glassdoor/ZipRecruiter/Google Jobs: optional secret `JOBSPY_PROXIES`, variable `JOBSPY_USER_AGENT`. Glassdoor's schedule: variable `ENABLE_GLASSDOOR_WATCHER` = `true`.
   - AI fit-scoring: secrets `ANTHROPIC_API_KEY`, `CANDIDATE_PROFILE` (required), `CANDIDATE_RESUME`.
   - Weekly upstream sync: secret `SYNC_TOKEN` (README "Staying up to date with upstream").
5. **Turn on the sources you chose**: move each one's workflow from `.github/workflows/disabled/` to `.github/workflows/` and push. The same goes for `triage.yml` (AI fit-scoring) and `weekly_digest.yml`.
6. **First runs**, one at a time (they share a lock, and GitHub cancels queued runs): **Validate Setup** → **LinkedIn Backfill (Parallel)** → each other source you turned on, with its backfill option → **Test Pushover Notification** if you set up alerts.
7. **Check**: open `https://<you>.github.io/<repo>/triage.html` and spot-check that the jobs match your search.

## Optional: LinkedIn `geoId`

`geoId: ""` works for most places (LinkedIn resolves the text). For tighter filtering, fill in the numeric geoId from the `geoId=` value in a LinkedIn job-search URL:

| Place | geoId |
|---|---|
| United States | `103644278` |
| San Francisco Bay Area | `90000084` |
| California | `102095887` |
| New York City Metro | `90000070` |
| Greater Boston | `90000007` |
| Greater Seattle | `90000091` |

(Region geoIds occasionally drift; check that a search returns jobs from the right place.)

## Without an AI

Copy `config.example.json` to `config.json` and edit it by hand; every key is commented there. Keep every section (use `[]` for unused lists), for the same reason as above.
