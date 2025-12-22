# Metadata Extraction Pipeline

Automated extraction of author contact information and metadata from academic paper URLs.

## Features

- Extracts journal name, title, DOI, and author information
- Identifies first, last, and corresponding authors
- Matches author emails using pattern-based and proximity-based approaches
- Tracks errors and coverage statistics

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/samcaton0/NeuroTrends.git
cd NeuroTrends
```

### 2. Create virtual environment

```bash
python -m venv venv
```

### 3. Activate virtual environment

**Windows:**

```bash
venv\Scripts\activate
```

**macOS/Linux:**

```bash
source venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Set up config.py

- In config_example.py, enter your email instead of 'name@example.com' to be put in the CrossRef API polite pool
- Rename the file from config_example.py to config.py

## Input File Format

The pipeline requires an Excel file (`.xlsx`) with paper URLs.

**Format requirements:**

- **No header row**
- **First column only** - all URLs should be in column A
- Each row contains one paper URL

## Usage

### Basic Usage

Extract metadata from URLs in a file:

```bash
python solution.py --readfile example_data/paper_links.xlsx
```

This will create `data/metadata.xlsx` with authors who have email addresses.

### CLI Arguments

| Argument        | Description                                   | Default                                |
| --------------- | --------------------------------------------- | -------------------------------------- |
| `--readfile`  | Path to input `.xlsx` file with URLs        | Required (unless `--urls` used)      |
| `--writefile` | Path to output `.xlsx` file                 | `data/metadata.xlsx`                 |
| `--urls`      | Specify individual URLs instead of file       | None                                   |
| `--full`      | Save all authors (not just those with emails) | False (only saves authors with emails) |
| `--verbose`   | Print detailed extraction progress            | False                                  |

### Usage Examples

**Process specific URLs:**

```bash
python solution.py --urls https://example.com/paper1 https://example.com/paper2
```

**Save all authors (including those without emails):**

```bash
python solution.py --readfile example_data/paper_links.xlsx --full
```

**Custom output path with verbose logging:**

```bash
python solution.py --readfile input.xlsx --writefile output/results.xlsx --verbose
```

**Process URLs and save only authors with emails:**

```bash
python solution.py --readfile papers.xlsx --writefile results.xlsx
```

## Output Files

### Successful Extractions

**File**: `metadata.xlsx` (or custom path via `--writefile`)

**Columns**:

- `link` - Paper URL
- `journal` - Journal name
- `title` - Paper title
- `doi` - Digital Object Identifier
- `author_name` - Author full name
- `author_role` - Role (first_author, last_author, corresponding_author)
- `author_email` - Email address (if found)
- `match_method` - Email matching method (pattern, proximity, or None if no email found)

**Note**: The `match_method` column indicates confidence in email-author pairing. `pattern` means the email contains name components (e.g., "jsmith@" for "John Smith"), which is more reliable. `proximity` means the match was based on HTML distance between author name and email, used when pattern matching fails or for corresponding authors.

### Failed Extractions

**File**: `metadata_errors.xlsx` (auto-generated in same directory as output file)

**Columns**:

- `link` - Paper URL
- `error_type` - Error category (http, doi, crossref, email)
- `error_message` - Detailed error description

## Coverage Analysis

**Completeness Testing**: Measures how complete the extraction is (what % of emails were recovered).

```bash
python analysis_scripts/coverage_analysis.py
```

**Output**: `example_data/coverage_stats.xlsx`

**Statistics computed**:

- % of papers successfully extracted
- % of first authors with emails
- % of last authors with emails
- % of all authors with emails
- % of papers with corresponding authors identified
- Computed overall and per journal

## Validation

**Accuracy Testing**: Validates extraction accuracy against manually verified ground truth (not completeness).

```bash
python analysis_scripts/validate_extraction.py
```

**Output**: `example_data/validation_results.xlsx` (multi-sheet workbook)

**Sheets**:
- **Summary**: Overall accuracy statistics (DOI, title, journal, authors identified, email accuracy, role accuracy by type)
- **Incorrect Papers**: Papers with DOI/title/journal mismatches
- **Missing Authors**: Authors in ground truth but not identified by pipeline
- **Incorrect Emails**: Mismatched email-author pairs

Compares `ground_truth_metadata.xlsx` (manual extraction) with `data/metadata.xlsx` (automated)

## Project Structure

```
NeuroTrends/
├── paper.py                       # Paper class with extraction logic
├── solution.py                    # Pipeline orchestration with CLI
├── config.py                      # Configuration (headers, timeouts)
├── requirements.txt               # Python dependencies
├── analysis_scripts/
│   ├── coverage_analysis.py       # Coverage statistics script
│   └── validate_extraction.py     # Validation against ground truth
├── example_data/
│   ├── paper_links.xlsx           # Example input file
│   ├── metadata.xlsx              # Example output (successful)
│   ├── metadata_errors.xlsx       # Example output (errors)
│   ├── coverage_stats.xlsx        # Example coverage statistics
│   ├── ground_truth_metadata.xlsx # Manual ground truth for validation
│   └── validation_results.xlsx    # Validation results
└── DESIGN_PROCESS.md              # Detailed design documentation
```

## How It Works

1. **DOI Extraction**: Parses HTML meta tags (`citation_doi`, `dc.Identifier`)
2. **Metadata Retrieval**: Queries CrossRef API for journal, title, author names/order
3. **Email Extraction**: Regex + Cloudflare XOR cipher decoder from static HTML
4. **Email Matching**: Pattern scoring (name in email) → proximity fallback (HTML distance)
5. **Error Handling**: Logs failures per-paper, outputs to separate error file

**Note**: 2-5 second delays between requests to avoid IP blocking (~5 mins for 60 papers).

## Design Decisions

- **Rate limiting**: Random 2-5s delays + rotating user-agent headers to mimic human browsing and prevent IP blocking
- **No LLMs**: Deterministic approach is faster, free, reproducible, and achieves 95%+ success without API costs
- **CrossRef for metadata**: Authoritative source for structured author data vs. unreliable HTML parsing
- **Hybrid email matching**: Pattern scoring handles standard cases, proximity fallback handles edge cases (lab emails, arbitrary usernames)

## Assumptions

- DOIs are in standard HTML meta tags
- CrossRef metadata is complete and correctly ordered
- Emails exist in static HTML (not JavaScript-rendered)
- All sites use UTF-8 encoding
- Corresponding authors are only identified when explicitly stated in HTML (proximity to "corresponding"/"correspondence" keywords) - no inference is made
- First/last authors are determined by position in author list (no equal contribution detection)

## Limitations

- Cannot extract emails not present in static HTML (requires JavaScript rendering or manual access)
- Author-email matching is heuristic and may be ambiguous with common surnames or multiple authors with similar names
- No affiliation extraction to help disambiguate authors
- Corresponding author identified by keyword proximity, not explicit markup (may misidentify)
- DOI extraction fails if not in standard meta tags (some preprints, older papers)
- Pattern matching assumes emails contain name components (fails with institutional/lab emails)

## Requirements

- Python 3.8+
- Internet connection
- Excel file with paper URLs

## Author

Sam Caton - [GitHub](https://github.com/samcaton0)
