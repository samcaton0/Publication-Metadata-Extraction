import cloudscraper
from requests.exceptions import Timeout
from requests import Response
from bs4 import BeautifulSoup
from habanero import Crossref
from config import HEADERS, EMAIL, TIMEOUT
from numpy.random import choice
from html import unescape
import re

class Paper:
    """Class to manage the extraction of metadata for a single paper."""
    def __init__(self, url: str, scraper: cloudscraper.CloudScraper=None, verbose: bool=False):
        # Metadata
        self.url = url
        self.html = None
        self.journal = None
        self.title = None
        self.doi = None
        self.authors = None
        self.status = None
        self.success = None
        self.scraper = scraper
        self.verbose = verbose
        self.errors = []
        self.error_type = None

        # Extracting metadata
        self._extract_metadata()

        # Log summary if verbose
        if self.verbose:
            self._log_summary()

    def _log_error(self, error_type: str, message: str):
        """Record an error that occured when processing the paper."""
        self.errors.append(f"{error_type}: {message}")
        if not self.error_type:
            self.error_type = error_type

    def _log_summary(self):
        """Print a summary of all errors to the console."""
        if self.success:
            email_count = sum(1 for data in self.authors.values() if data['email'])
            print(f"{self.url[:60]}... {email_count}/{len(self.authors)} emails")
        else:
            print(f"{self.url[:60]}... {self.error_type}")

    def _safe_get(self) -> cloudscraper.requests.Response:
        """Request the webpage HTML from a link to the paper with protection for timeouts."""

        # Creating the scraper if not passed as argument
        if not self.scraper:
            self.scraper = cloudscraper.create_scraper()
        
        # Handling timeout exceptions to avoid crashing the pipeline
        try:
            response = self.scraper.get(self.url, timeout=TIMEOUT, headers=choice(HEADERS))
            return response
        
        except Timeout:
            # Creating a dummy response to keep clean logic in _get_html
            response = Response()
            response.status_code = 408
            response._content = b''

            return response

    def _get_html(self) -> bool:
        """Retrieve the webpage HTML as text from a link to the paper."""
        response = self._safe_get()

        # Validating that the request was received correctly
        status = response.status_code
        if status != 200:
            self._log_error('http', f'Status {status}')
            return False

        response.encoding = 'utf-8'
        self.html = response.text
        return True

    def _extract_doi(self) -> bool:
        """Find the paper DOI in the HTML by searching for meta tags commonly associated with the DOI."""

        # Extracting DOI from meta tags
        soup = BeautifulSoup(self.html, 'lxml')

        # Potential names for the meta tags associated with DOI
        citation_meta_names = [
          'citation_doi',
          'dc.Identifier',
      ]
        
        # DOI format Regex
        doi_pattern = r'^10\.\d{4,9}/[-._;()/:A-Za-z0-9]+$'

        for name in citation_meta_names:
            doi_metas = soup.find_all('meta', attrs={'name': name})                
            for doi_meta in doi_metas:
                if re.match(doi_pattern, doi_meta.get('content')):
                    self.doi = doi_meta.get('content')
                    return True
            
        self._log_error('doi', 'Could not extract DOI from meta tags')
        return False
                
    def _get_crossref_metadata(self) -> bool:
        """Query the CrossRef API to extraction the paper title, journal and a list of authors."""

        # Querying Crossref
        cr = Crossref(mailto=EMAIL)
        response = cr.works(ids=self.doi)

        # Validating that Crossref was queried successfully
        status = response['status']
        if status != 'ok':
            self._log_error('crossref', f'Query failed with status: {status}')
            return False
        cr_metadata = response['message']

        # Formatting author names
        author_names = [f'{author.get('given', '')} {author.get('family', '')}' for author in cr_metadata['author']]

        # Updating metadata
        self.journal = cr_metadata['container-title'][0]
        self.title = cr_metadata['title'][0]
        self.authors = {author_name: {'email': None, 'role': [], 'match_method': None, 'ambiguous': False} for author_name in author_names}

        # Identifying the first and last authors
        self.authors[author_names[0]]['role'].append('first_author')
        self.authors[author_names[-1]]['role'].append('last_author')

        return True
    
    def _clean_name(self, name: str) -> str:
        """Remove parentheses and content, hyphens, non-ASCII chars from the name"""
        name = re.sub(r'\([^)]*\)', '', name)
        name = name.replace('-', '').replace('.', '')
        name = ''.join(c for c in name if c.isascii())
        return name.strip().lower()

    def _split_name(self, author_name: str) -> tuple:
        """Break a name down into first, last and middle names"""
        cleaned = self._clean_name(author_name)
        parts = cleaned.split()
        if not parts:
            return '', '', ''
        first = parts[0]
        last = parts[-1]
        middle = parts[1] if len(parts) > 2 else ''
        return first, middle, last

    def _find_emails_in_html(self, html: str) -> list:
        """Find all emails present in the HTML that match a standard pattern or the CloudFare cipher pattern."""

        # Unescape HTML entities first (e.g. &amp; → &)
        html = unescape(html)

        # Finding emails that match a standard email pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+(?:@|\{at\})[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?=\b|[?&])'
        raw_emails = re.findall(email_pattern, html)

        # Finding emails that have been encoded by CloudFare protection cipher
        cf_pattern = r'/cdn-cgi/l/email-protection#([0-9a-f]+)'
        cf_matches = re.findall(cf_pattern, html)
        for encoded in cf_matches:
            try:
                # Decode Cloudflare XOR cipher
                key = int(encoded[:2], 16)
                decoded = ''.join(chr(int(encoded[i:i+2], 16) ^ key) for i in range(2, len(encoded), 2))
                raw_emails.append(decoded)
            except:
                continue

        emails = []

        # Clean any remaining artifacts
        for email in raw_emails:
            clean_email = email.split('?')[0].split('&')[0].strip()
            if clean_email:
                emails.append(clean_email)

        return emails

    def _filter_junk_emails(self, emails: list) -> list:
        """Remove emails in the HTML that are found by the Regex but are placeholders or do not correspond to an author"""

        # List of common words present in junk/placeholder emails
        junk_keywords = ['example', 'permission', 'campaign', 'placeholder', 'noreply',
                         'donotreply', 'support', 'info', 'admin', 'help']
        junk_prefixes = ['name@', 'email@', 'user@', 'author@', 'your@']
        junk_domains = ['university.edu', 'university.ac.uk', 'example.com', 'example.org']

        # Removing any emails that contain the common words
        def is_junk(email: str) -> bool:
            email_lower = email.lower()
            email_domain = email_lower.split('@')[1] if '@' in email_lower else ''
            return (any(kw in email_lower for kw in junk_keywords) or
                    any(email_lower.startswith(p) for p in junk_prefixes) or
                    email_domain in junk_domains)
        
        return [email for email in emails if not is_junk(email)]

    def _progressive_match(self, name: str, email_prefix: str, max_score: float) -> tuple:
        """Check whether progressively shorter substrings of the name are present in the email, return (score, length)"""
        if len(name) <= 3:
            return 0, 0

        for length in range(len(name), 2, -1):
            if name[:length] in email_prefix:
                score = max_score * (length / len(name))
                return score, length
        return 0, 0

    def _pattern_match(self, email: str, available_authors: list) -> list:
        """Match the email to an author by assigning each one a score based on common patterns of how names translate to emails."""
        author_scores = []
        email_prefix = email.split('@')[0].lower()

        # Separating the name into its components
        for author_name in available_authors:
            first, middle, last = self._split_name(author_name)
            if not first or not last:
                continue

            score = 0
            match_length = 0

            # Pattern 1: Full last name in email
            if last in email_prefix:
                score += 3
                match_length += len(last)

            # Pattern 2: Full first name in email
            if first in email_prefix:
                score += 2
                match_length += len(first)

            # Pattern 3: First initial + last initial
            if f'{first[0]}{last[0]}' in email_prefix:
                score += 1
                match_length += 2

            # Pattern 4: First initial + middle initial + partial last
            if middle and f'{first[0]}{middle[0]}' in email_prefix and last[:3] in email_prefix:
                score += 2
                match_length += 5

            # Pattern 5: Last initial + first name
            if f'{last[0]}{first}' in email_prefix:
                score += 2
                match_length += len(first) + 1

            # Pattern 6: First + last without separators
            if f'{first}{last}' in email_prefix.replace('.', '').replace('_', ''):
                score += 3
                match_length += len(first) + len(last)

            # Pattern 7 & 8: Progressive matching - removing one character from the name as a time to see if a substring of
            # the name is used in the email (e.g. Jenkins -> jenk123@gmail.com)
            first_partial_score, first_partial_len = self._progressive_match(first, email_prefix, 2.0)
            if first_partial_score > score or (first_partial_score == score and first_partial_len > match_length):
                score = first_partial_score
                match_length = first_partial_len

            last_partial_score, last_partial_len = self._progressive_match(last, email_prefix, 3.0)
            if last_partial_score > score or (last_partial_score == score and last_partial_len > match_length):
                score = last_partial_score
                match_length = last_partial_len

            if score > 0:
                author_scores.append({'author_name': author_name, 'score': score, 'match_length': match_length})

        if not author_scores:
            return []

        # Find the best score and match_length
        best_score = max(a['score'] for a in author_scores)
        best_matches = [a for a in author_scores if a['score'] == best_score]

        if len(best_matches) == 1:
            return [best_matches[0]['author_name']]

        # If multiple authors have the same score, take the one with a longer match (e.g. take Liu over Li for liu@gmail.com)
        best_length = max(a['match_length'] for a in best_matches)
        tied_matches = [a['author_name'] for a in best_matches if a['match_length'] == best_length]

        return tied_matches

    def _proximity_match(self, text: str, candidates: list, direction: str = 'after') -> str:
        """Find closest candidate to text in HTML 
        (direction: 'after', 'both', 'before', indicates where the email must appear in relation to the author name) """

        # Searching for the first occurrence of the author name within the HTML
        text_match = re.search(re.escape(text), self.html, re.IGNORECASE)
        if not text_match:
            return None

        # Extracting the position of the author name
        text_pos = text_match.start()
        closest = None
        min_distance = float('inf')

        # Finding which email appears closest to the author name within the HTML 
        for candidate in candidates:
            match = re.search(re.escape(candidate), self.html, re.IGNORECASE)
            if match:
                email_pos = match.start()
                if (direction == 'after' and email_pos > text_pos) or \
                   (direction == 'before' and email_pos < text_pos) or \
                   (direction == 'both'):
                    distance = abs(email_pos - text_pos)
                    if distance < min_distance:
                        min_distance = distance
                        closest = candidate

        return closest

    def _identify_corresponding_authors(self) -> None:
        """Identify which authors are labelled as corresponding authors within the HTML"""
        # Find tags containing correspondence markers using BeautifulSoup
        soup = BeautifulSoup(self.html, 'lxml')

        for tag in soup.find_all(text=re.compile(r'Correspondence|Corresponding Author', re.IGNORECASE)):
            # Get parent tag and all its content
            parent = tag.find_parent()
            if not parent:
                continue

            tag_text = parent.get_text()

            # Check if any author name appears in this tag
            for author_name in self.authors.keys():
                if author_name.lower() in tag_text.lower():
                    if 'corresponding_author' not in self.authors[author_name]['role']:
                        self.authors[author_name]['role'].append('corresponding_author')

    def _assign_email(self, author_name: str, email: str, method: str,
                      matched_emails: set, available_authors: list, remaining_emails: set = None, ambiguous: bool = False):
        """Update the metadata to assign the email to the author and update tracking sets"""

        # Updating author metadata
        self.authors[author_name]['email'] = email.replace('{at}', '@')
        self.authors[author_name]['match_method'] = method
        self.authors[author_name]['ambiguous'] = ambiguous

        # Updating the tracking sets of emails and authors that are yet to be matched
        matched_emails.add(email)
        if author_name in available_authors:
            available_authors.remove(author_name)
        if remaining_emails and email in remaining_emails:
            remaining_emails.remove(email)

    def _extract_emails(self) -> bool:
        """Extract emails from the HTML. Matches them to author names using pattern matching (e.g. checking if the surname
        is present in the email) and then proximity in the HTML as a fallback."""

        # Finding and filtering emails from the paper HTML
        all_emails = self._find_emails_in_html(self.html)
        all_emails = set(self._filter_junk_emails(all_emails))

        # Logging an error if no valid emails were found
        if not all_emails:
            self._log_error('email', 'No emails found in HTML')
            return False

        # Email-author matching Stage 1: Pattern Matching
        matched_emails = set()
        available_authors = list(self.authors.keys())

        for email in all_emails:
            matched_authors = self._pattern_match(email.lower(), available_authors)
            if matched_authors:
                is_ambiguous = len(matched_authors) > 1
                for matched_author in matched_authors:
                    self._assign_email(matched_author, email, 'pattern', matched_emails, available_authors, ambiguous=is_ambiguous)

        remaining_emails = all_emails - matched_emails

        # Email-author matching Stage 2a: Proximity to Corresponding Authors (prioritised since they are most likely to have their
        # emails present)
        self._identify_corresponding_authors()
        corresponding_authors = [name for name in available_authors
                                if 'corresponding_author' in self.authors[name]['role']]

        for author_name in corresponding_authors:
            if self.authors[author_name]['email']:
                continue

            # Searching for emails after author name (standard)
            closest_email = self._proximity_match(author_name, list(remaining_emails), 'after')
            if closest_email:
                self._assign_email(author_name, closest_email, 'proximity', matched_emails, available_authors, remaining_emails)

        # Email-author matching Stage 2b: Proximity to other authors (searches both directions as last resort)
        for email in list(remaining_emails):
            closest_author = self._proximity_match(email, available_authors, 'both')
            if closest_author:
                self._assign_email(closest_author, email, 'proximity', matched_emails, available_authors, remaining_emails)

        # Check if any matches were found
        any_matches = any(data['email'] for data in self.authors.values())
        if not any_matches:
            self._log_error('email', 'Could not match emails to author names')
            return False

        return True

    def _extract_metadata(self):
        """Execute all parts of the metadata extraction pipeline and checks whether any steps have failed (returned False)."""

        steps = [self._get_html, self._extract_doi, self._get_crossref_metadata, self._extract_emails]
        self.success = all(step() for step in steps)
        return self.success

    def get_metadata(self) -> list:
        """Return the metadata as a a list of dictionaries, one for each author so it is compatible with the 
         solution pipeline. """
        
        # Return error record for failed papers
        if not self.success or not self.authors:
            return [{
                'link': self.url,
                'error_type': self.error_type,
                'error_message': '; '.join(self.errors) if self.errors else 'Unknown error'
            }]

        # Return successful metadata
        paper_metadata = []
        for author_name, author_metadata in self.authors.items():
            author_dict = {'link': self.url,
                           'journal': self.journal,
                           'title': self.title,
                           'doi': self.doi,
                           'author_name': author_name,
                           'author_role': author_metadata['role'],
                           'author_email': author_metadata['email'],
                           'match_method': author_metadata['match_method'],
                           'ambiguous': author_metadata['ambiguous']}
            paper_metadata.append(author_dict)

        return paper_metadata