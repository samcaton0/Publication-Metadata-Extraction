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

**Example (`paper_links.xlsx`):**

```
https://www.nature.com/articles/s41586-021-03506-2
https://www.science.org/doi/10.1126/science.abj8222
https://www.cell.com/neuron/fulltext/S0896-6273(21)00167-1
```

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

### Failed Extractions

**File**: `metadata_errors.xlsx` (auto-generated in same directory as output file)

**Columns**:

- `link` - Paper URL
- `error_type` - Error category (http, doi, crossref, email)
- `error_message` - Detailed error description

## Coverage Analysis

Run coverage statistics to evaluate pipeline performance:

```bash
python coverage_analysis.py
```

**Output**: `example_data/coverage_stats.xlsx`

**Statistics computed**:

- % of papers successfull extracted
- % of first authors with emails
- % of last authors with emails
- % of all authors with emails
- % of papers with corresponding authors identified
- Computed overall and per journal

## Project Structure

```
NeuroTrends/
├── paper.py                  # Paper class with extraction logic
├── solution.py               # Pipeline orchestration with CLI
├── coverage_analysis.py      # Coverage statistics script
├── config.py                 # Configuration (headers, timeouts)
├── requirements.txt          # Python dependencies
├── example_data/
│   ├── paper_links.xlsx      # Example input file
│   ├── metadata.xlsx         # Example output (successful)
│   ├── metadata_errors.xlsx  # Example output (errors)
│   └── coverage_stats.xlsx   # Example coverage statistics
└── DESIGN_PROCESS.md         # Detailed design documentation
```

## How It Works

1. **HTML Fetching**: Uses `cloudscraper` to retrieve webpage HTML
2. **DOI Extraction**: Parses meta tags for DOI
3. **Metadata Retrieval**: Queries CrossRef API using DOI for author names
4. **Email Extraction**: Extracts emails from HTML using regex
5. **Email Matching**:
   - Pattern-based matching (name components present in email)
   - Proximity-based fallback (distance from author name in HTML)
6. **Error Handling**: Tracks failures without stopping pipeline

**Note**: To avoid being blocked, there is a random delay between requests (2-5 seconds) so 60 papers will take roughly 5 minutes to process.

## Requirements

- Python 3.8+
- Internet connection
- Excel file with paper URLs

## Author

Sam Caton - [GitHub](https://github.com/samcaton0)
