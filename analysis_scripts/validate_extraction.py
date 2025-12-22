import pandas as pd

def load_data(ground_truth_file: str, metadata_file: str):
    """Load ground truth and metadata, filter to common links"""
    gt_df = pd.read_excel(ground_truth_file)
    meta_df = pd.read_excel(metadata_file)

    # Get unique links in ground truth
    gt_links = gt_df['link'].unique()

    # Filter metadata to only include ground truth links
    meta_df = meta_df[meta_df['link'].isin(gt_links)]

    return gt_df, meta_df

def compare_paper_metadata(gt_df: pd.DataFrame, meta_df: pd.DataFrame):
    """Compare DOI, title, journal per paper"""
    results = {'papers': 0, 'doi_correct': 0, 'title_correct': 0, 'journal_correct': 0}
    incorrect_papers = []

    # Group by link (one comparison per paper)
    gt_papers = gt_df.groupby('link').first()
    meta_papers = meta_df.groupby('link').first()

    for link in gt_papers.index:
        if link not in meta_papers.index:
            continue

        results['papers'] += 1

        errors = []

        # Compare DOI
        if gt_papers.loc[link, 'doi'] == meta_papers.loc[link, 'doi']:
            results['doi_correct'] += 1
        else:
            errors.append('DOI mismatch')

        # Compare title (case-insensitive, strip whitespace)
        gt_title = str(gt_papers.loc[link, 'title']).strip().lower()
        meta_title = str(meta_papers.loc[link, 'title']).strip().lower()
        if gt_title == meta_title:
            results['title_correct'] += 1
        else:
            errors.append('Title mismatch')

        # Compare journal
        if gt_papers.loc[link, 'journal'] == meta_papers.loc[link, 'journal']:
            results['journal_correct'] += 1
        else:
            errors.append('Journal mismatch')

        # Track papers with errors
        if errors:
            incorrect_papers.append({
                'link': link,
                'errors': '; '.join(errors),
                'ground_truth_doi': gt_papers.loc[link, 'doi'],
                'extracted_doi': meta_papers.loc[link, 'doi'],
                'ground_truth_journal': gt_papers.loc[link, 'journal'],
                'extracted_journal': meta_papers.loc[link, 'journal']
            })

    return results, incorrect_papers

def compare_authors(gt_df: pd.DataFrame, meta_df: pd.DataFrame):
    """Compare author identification and email/role matching"""
    results = {
        'authors_found': 0,
        'total_authors': 0,
        'emails_correct': 0,
        'first_author_correct': 0,
        'first_author_total': 0,
        'last_author_correct': 0,
        'last_author_total': 0,
        'corresponding_author_correct': 0,
        'corresponding_author_total': 0
    }

    missing_authors = []
    incorrect_emails = []

    # Compare per paper
    for link in gt_df['link'].unique():
        gt_paper = gt_df[gt_df['link'] == link]
        meta_paper = meta_df[meta_df['link'] == link]

        gt_authors = set(gt_paper['author_name'].dropna())
        meta_authors = set(meta_paper['author_name'].dropna())

        results['total_authors'] += len(gt_authors)
        results['authors_found'] += len(gt_authors.intersection(meta_authors))

        # Track missing authors
        for missing_author in gt_authors - meta_authors:
            missing_authors.append({
                'link': link,
                'author_name': missing_author
            })

        # For each author in ground truth, check email and role
        for _, gt_row in gt_paper.iterrows():
            gt_name = gt_row['author_name']
            gt_email = gt_row['author_email']
            gt_role = gt_row['author_role']

            # Find matching author in metadata
            meta_row = meta_paper[meta_paper['author_name'] == gt_name]

            if not meta_row.empty:
                meta_row = meta_row.iloc[0]

                # Check email match
                if pd.notna(gt_email) and pd.notna(meta_row['author_email']):
                    if gt_email.lower().strip() == meta_row['author_email'].lower().strip():
                        results['emails_correct'] += 1
                    else:
                        incorrect_emails.append({
                            'link': link,
                            'author_name': gt_name,
                            'ground_truth_email': gt_email,
                            'extracted_email': meta_row['author_email']
                        })

                # Check role match by type
                if pd.notna(gt_role) and pd.notna(meta_row['author_role']):
                    if 'first_author' in gt_role:
                        results['first_author_total'] += 1
                        if 'first_author' in meta_row['author_role']:
                            results['first_author_correct'] += 1

                    if 'last_author' in gt_role:
                        results['last_author_total'] += 1
                        if 'last_author' in meta_row['author_role']:
                            results['last_author_correct'] += 1

                    if 'corresponding_author' in gt_role:
                        results['corresponding_author_total'] += 1
                        if 'corresponding_author' in meta_row['author_role']:
                            results['corresponding_author_correct'] += 1

    return results, missing_authors, incorrect_emails

def save_results(paper_results: dict, author_results: dict, incorrect_papers: list,
                 missing_authors: list, incorrect_emails: list, output_file: str):
    """Save validation statistics to Excel with multiple sheets"""

    # Summary statistics
    summary_data = []
    total_papers = paper_results['papers']
    total_authors = author_results['total_authors']
    authors_found = author_results['authors_found']

    # Paper metadata
    summary_data.append({
        'Metric': 'Total Papers',
        'Ground Truth': total_papers,
        'Automated Correct': total_papers,
        'Percentage': 100.0
    })
    summary_data.append({
        'Metric': 'DOI Correct',
        'Ground Truth': total_papers,
        'Automated Correct': paper_results['doi_correct'],
        'Percentage': paper_results['doi_correct'] / total_papers * 100 if total_papers > 0 else 0
    })
    summary_data.append({
        'Metric': 'Title Correct',
        'Ground Truth': total_papers,
        'Automated Correct': paper_results['title_correct'],
        'Percentage': paper_results['title_correct'] / total_papers * 100 if total_papers > 0 else 0
    })
    summary_data.append({
        'Metric': 'Journal Correct',
        'Ground Truth': total_papers,
        'Automated Correct': paper_results['journal_correct'],
        'Percentage': paper_results['journal_correct'] / total_papers * 100 if total_papers > 0 else 0
    })

    # Author identification
    summary_data.append({
        'Metric': 'Authors Identified',
        'Ground Truth': total_authors,
        'Automated Correct': authors_found,
        'Percentage': authors_found / total_authors * 100 if total_authors > 0 else 0
    })
    summary_data.append({
        'Metric': 'Emails Correct',
        'Ground Truth': authors_found,
        'Automated Correct': author_results['emails_correct'],
        'Percentage': author_results['emails_correct'] / authors_found * 100 if authors_found > 0 else 0
    })

    # Role accuracy by type
    if author_results['first_author_total'] > 0:
        summary_data.append({
            'Metric': 'First Author Role Correct',
            'Ground Truth': author_results['first_author_total'],
            'Automated Correct': author_results['first_author_correct'],
            'Percentage': author_results['first_author_correct'] / author_results['first_author_total'] * 100
        })

    if author_results['last_author_total'] > 0:
        summary_data.append({
            'Metric': 'Last Author Role Correct',
            'Ground Truth': author_results['last_author_total'],
            'Automated Correct': author_results['last_author_correct'],
            'Percentage': author_results['last_author_correct'] / author_results['last_author_total'] * 100
        })

    if author_results['corresponding_author_total'] > 0:
        summary_data.append({
            'Metric': 'Corresponding Author Role Correct',
            'Ground Truth': author_results['corresponding_author_total'],
            'Automated Correct': author_results['corresponding_author_correct'],
            'Percentage': author_results['corresponding_author_correct'] / author_results['corresponding_author_total'] * 100
        })

    summary_df = pd.DataFrame(summary_data)

    # Save to Excel with multiple sheets
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        summary_df.to_excel(writer, sheet_name='Summary', index=False)

        if incorrect_papers:
            pd.DataFrame(incorrect_papers).to_excel(writer, sheet_name='Incorrect Papers', index=False)

        if missing_authors:
            pd.DataFrame(missing_authors).to_excel(writer, sheet_name='Missing Authors', index=False)

        if incorrect_emails:
            pd.DataFrame(incorrect_emails).to_excel(writer, sheet_name='Incorrect Emails', index=False)

    print(f"\nValidation results saved to: {output_file}")
    print("\nSummary Statistics:")
    print(summary_df.to_string(index=False))

    if incorrect_papers:
        print(f"\n{len(incorrect_papers)} papers with incorrect metadata (see 'Incorrect Papers' sheet)")
    if missing_authors:
        print(f"{len(missing_authors)} authors not identified (see 'Missing Authors' sheet)")
    if incorrect_emails:
        print(f"{len(incorrect_emails)} incorrect email assignments (see 'Incorrect Emails' sheet)")

def run_validation():
    """Main validation function"""
    gt_df, meta_df = load_data('../example_data/ground_truth_metadata.xlsx', '../example_data/metadata.xlsx')

    print(f"\nLoaded {len(gt_df['link'].unique())} papers from ground truth")
    print(f"Found {len(meta_df['link'].unique())} matching papers in metadata")

    paper_results, incorrect_papers = compare_paper_metadata(gt_df, meta_df)
    author_results, missing_authors, incorrect_emails = compare_authors(gt_df, meta_df)

    save_results(paper_results, author_results, incorrect_papers, missing_authors,
                 incorrect_emails, '../example_data/validation_results.xlsx')

if __name__ == "__main__":
    run_validation()
