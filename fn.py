# app.py - Streamlit Job Scraper without Selenium
import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
import logging
import json
import re

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class SimpleJobScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def is_recent_job(self, date_text):
        """Check if job was posted in last 24 hours"""
        if not date_text:
            return False
            
        date_text_lower = date_text.lower()
        recent_indicators = [
            'hours ago',
            'hour ago', 
            'today',
            'just now',
            '1 day ago',
            'yesterday',
            datetime.now().strftime('%d %b %Y'),
            (datetime.now() - timedelta(days=1)).strftime('%d %b %Y')
        ]
        
        return any(indicator in date_text_lower for indicator in recent_indicators)
    
    def scrape_reliefweb(self, search_term, max_jobs=20):
        """Scrape ReliefWeb using API/HTML parsing"""
        logging.info(f"Scraping ReliefWeb for: {search_term}")
        
        # Use ReliefWeb API for more reliable results
        url = f"https://api.reliefweb.int/v1/jobs?appname=publichealth&query[value]={search_term.replace(' ', '+')}&limit={max_jobs}"
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            jobs = []
            for item in data.get('data', [])[:max_jobs]:
                try:
                    fields = item.get('fields', {})
                    
                    job_data = {
                        'title': fields.get('title', 'No title'),
                        'organization': fields.get('source', [{}])[0].get('name', 'Unknown Organization') if fields.get('source') else 'Unknown Organization',
                        'location': ', '.join([loc.get('name', '') for loc in fields.get('country', [])]) or 'Multiple Locations',
                        'url': f"https://reliefweb.int/job/{item['id']}",
                        'date_posted': fields.get('date', {}).get('created', 'Unknown'),
                        'source': 'reliefweb',
                        'scraped_at': datetime.now().isoformat(),
                        'search_term': search_term
                    }
                    
                    job_data['is_recent'] = self.is_recent_job(job_data.get('date_posted', ''))
                    jobs.append(job_data)
                    
                except Exception as e:
                    logging.warning(f"Error processing ReliefWeb job: {e}")
                    continue
            
            return jobs
            
        except Exception as e:
            logging.error(f"ReliefWeb API failed, trying HTML fallback: {e}")
            return self.scrape_reliefweb_html(search_term, max_jobs)
    
    def scrape_reliefweb_html(self, search_term, max_jobs=20):
        """Fallback HTML scraping for ReliefWeb"""
        try:
            url = f"https://reliefweb.int/jobs?search={search_term.replace(' ', '+')}"
            response = self.session.get(url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            jobs = []
            job_elements = soup.find_all('article', class_='rw-river-article--job')[:max_jobs]
            
            for job_element in job_elements:
                try:
                    title_elem = job_element.find('h3').find('a') if job_element.find('h3') else None
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    url = "https://reliefweb.int" + title_elem.get('href', '')
                    
                    # Extract organization
                    org_elem = job_element.find('dd')
                    organization = org_elem.get_text(strip=True) if org_elem else "Unknown Organization"
                    
                    # Extract location
                    location_elem = job_element.find('span', class_='rw-river-article__country')
                    location = location_elem.get_text(strip=True) if location_elem else "Multiple Locations"
                    
                    # Extract date
                    date_elem = job_element.find('time')
                    date_posted = date_elem.get_text(strip=True) if date_elem else "Unknown"
                    
                    job_data = {
                        'title': title,
                        'organization': organization,
                        'location': location,
                        'url': url,
                        'date_posted': date_posted,
                        'source': 'reliefweb',
                        'scraped_at': datetime.now().isoformat(),
                        'search_term': search_term
                    }
                    
                    job_data['is_recent'] = self.is_recent_job(date_posted)
                    jobs.append(job_data)
                    
                except Exception as e:
                    logging.warning(f"Error parsing ReliefWeb HTML job: {e}")
                    continue
            
            return jobs
            
        except Exception as e:
            logging.error(f"ReliefWeb HTML scraping failed: {e}")
            return []
    
    def scrape_devex(self, search_term, max_jobs=15):
        """Scrape Devex for development jobs"""
        logging.info(f"Scraping Devex for: {search_term}")
        
        try:
            url = f"https://www.devex.com/jobs/search?filter[keywords]={search_term.replace(' ', '%20')}"
            response = self.session.get(url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            jobs = []
            # Look for job cards - this selector might need adjustment
            job_elements = soup.find_all('div', class_=re.compile(r'job-item|job-card'))[:max_jobs]
            
            if not job_elements:
                # Alternative selectors
                job_elements = soup.find_all('article')[:max_jobs]
            
            for job_element in job_elements:
                try:
                    title_elem = job_element.find('h3') or job_element.find('h2')
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    
                    # Find link
                    link_elem = job_element.find('a')
                    url = link_elem.get('href', '') if link_elem else ''
                    if url and not url.startswith('http'):
                        url = 'https://www.devex.com' + url
                    
                    # Extract organization
                    org_text = job_element.get_text()
                    organization = "Development Organization"
                    
                    # Try to find organization in text
                    org_patterns = [r'at\s+([A-Z][a-zA-Z\s&]+)', r'-\s*([A-Z][a-zA-Z\s&]+)$']
                    for pattern in org_patterns:
                        match = re.search(pattern, title)
                        if match:
                            organization = match.group(1).strip()
                            break
                    
                    job_data = {
                        'title': title,
                        'organization': organization,
                        'location': 'Global',  # Devex jobs are often global
                        'url': url,
                        'date_posted': 'Recent',
                        'source': 'devex',
                        'scraped_at': datetime.now().isoformat(),
                        'search_term': search_term
                    }
                    
                    job_data['is_recent'] = True  # Devex shows recent jobs
                    jobs.append(job_data)
                    
                except Exception as e:
                    logging.warning(f"Error parsing Devex job: {e}")
                    continue
            
            return jobs
            
        except Exception as e:
            logging.error(f"Devex scraping failed: {e}")
            return []
    
    def scrape_development_sites(self, search_term, sites=None):
        """Scrape multiple development job sites"""
        if sites is None:
            sites = ['reliefweb', 'devex']
        
        all_jobs = []
        
        for site in sites:
            try:
                if site == 'reliefweb':
                    jobs = self.scrape_reliefweb(search_term)
                elif site == 'devex':
                    jobs = self.scrape_devex(search_term)
                else:
                    continue
                
                all_jobs.extend(jobs)
                time.sleep(1)  # Be respectful between sites
                
            except Exception as e:
                logging.error(f"Failed to scrape {site}: {e}")
                continue
        
        return all_jobs
    
    def filter_public_health_jobs(self, jobs):
        """Filter jobs for public health M&E relevance"""
        public_health_keywords = [
            'public health', 'monitoring', 'evaluation', 'm&e', 'data',
            'health', 'strategic information', 'commcare', 'dhis2',
            'survey', 'research', 'impact assessment', 'health program',
            'global health', 'health systems', 'epidemiology', 'health',
            'maternal', 'child health', 'hiv', 'tb', 'malaria', 'nutrition'
        ]
        
        filtered_jobs = []
        
        for job in jobs:
            job_text = f"{job['title']} {job.get('organization', '')}".lower()
            
            # Check if job matches public health criteria
            matches = sum(1 for keyword in public_health_keywords if keyword in job_text)
            relevance_score = matches / len(public_health_keywords)
            
            if relevance_score >= 0.2:  # At least 20% match
                job['relevance_score'] = round(relevance_score, 2)
                job['is_public_health'] = True
                filtered_jobs.append(job)
            else:
                job['relevance_score'] = round(relevance_score, 2)
                job['is_public_health'] = False
        
        return filtered_jobs

# Streamlit App
def main():
    """Main Streamlit app"""
    st.set_page_config(
        page_title="Public Health M&E Job Scraper",
        page_icon="🔍",
        layout="wide"
    )
    
    # Header
    st.title("🔍 Public Health M&E Job Scraper")
    st.markdown("""
    This tool scrapes public health monitoring and evaluation jobs from development job boards.
    *No browser automation required - faster and more reliable!*
    """)
    
    # Sidebar configuration
    st.sidebar.header("🔧 Configuration")
    
    # Search terms
    st.sidebar.subheader("Search Terms")
    default_terms = [
        "monitoring and evaluation",
        "M&E officer", 
        "strategic information",
        "public health data",
        "health information systems"
    ]
    
    search_terms = []
    for i, term in enumerate(default_terms):
        if st.sidebar.checkbox(term, value=True, key=f"term_{i}"):
            search_terms.append(term)
    
    # Additional custom search term
    custom_term = st.sidebar.text_input("Add custom search term:")
    if custom_term and custom_term not in search_terms:
        search_terms.append(custom_term)
    
    # Target sites
    st.sidebar.subheader("Target Sites")
    sites = []
    if st.sidebar.checkbox("ReliefWeb", value=True):
        sites.append('reliefweb')
    if st.sidebar.checkbox("Devex", value=True):
        sites.append('devex')
    
    # Job limits
    st.sidebar.subheader("Scraping Limits")
    max_jobs_per_search = st.sidebar.slider(
        "Max jobs per search term", 
        min_value=5, 
        max_value=30, 
        value=15
    )
    
    # Recent jobs filter
    show_only_recent = st.sidebar.checkbox("Show only recent jobs", value=False)
    
    # Scraping control
    st.sidebar.subheader("Scraping Control")
    run_scraper = st.sidebar.button("🚀 Start Scraping", type="primary")
    
    # Main content
    if run_scraper:
        if not search_terms:
            st.error("Please select at least one search term.")
            return
        
        if not sites:
            st.error("Please select at least one website to scrape.")
            return
        
        # Initialize scraper
        scraper = SimpleJobScraper()
        
        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        all_jobs = []
        total_searches = len(search_terms)
        
        for i, search_term in enumerate(search_terms):
            status_text.text(f"🔍 Searching for: '{search_term}'...")
            
            try:
                jobs = scraper.scrape_development_sites(search_term, sites)
                filtered_jobs = scraper.filter_public_health_jobs(jobs)
                all_jobs.extend(filtered_jobs)
                
                status_text.text(f"✅ Found {len(filtered_jobs)} jobs for '{search_term}'")
                
            except Exception as e:
                st.error(f"Error searching for '{search_term}': {str(e)}")
                continue
            
            finally:
                progress = (i + 1) / total_searches
                progress_bar.progress(progress)
                time.sleep(1)
        
        # Remove duplicates
        unique_jobs = []
        seen_urls = set()
        for job in all_jobs:
            if job['url'] not in seen_urls:
                seen_urls.add(job['url'])
                unique_jobs.append(job)
        
        progress_bar.progress(1.0)
        status_text.text(f"🎉 Scraping complete! Found {len(unique_jobs)} unique jobs.")
        
        # Display results
        display_results(unique_jobs, show_only_recent)

def display_results(jobs, show_only_recent):
    """Display results in Streamlit"""
    if not jobs:
        st.warning("No jobs found matching your criteria. Try adjusting your search terms.")
        return
    
    # Filter jobs if only recent requested
    if show_only_recent:
        jobs = [job for job in jobs if job.get('is_recent', False)]
        if not jobs:
            st.warning("No recent jobs found.")
            return
    
    # Create dataframe
    df = pd.DataFrame(jobs)
    
    # Display summary
    recent_count = sum(1 for job in jobs if job.get('is_recent', False))
    high_match_count = sum(1 for job in jobs if job.get('relevance_score', 0) > 0.7)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Jobs", len(jobs))
    with col2:
        st.metric("Recent Jobs", recent_count)
    with col3:
        st.metric("High Matches", high_match_count)
    with col4:
        sources = set(df['source'].tolist()) if not df.empty else set()
        st.metric("Sources", ", ".join(sources))
    
    if df.empty:
        return
        
    # Display jobs in an interactive table
    st.subheader("📋 Job Results")
    
    # Create a display dataframe with clickable links
    display_df = df.copy()
    display_df['Job Title'] = display_df.apply(
        lambda x: f'<a href="{x["url"]}" target="_blank">{x["title"]}</a>', 
        axis=1
    )
    
    # Select and rename columns for display
    display_df = display_df[['Job Title', 'organization', 'location', 'date_posted', 'source', 'relevance_score']]
    display_df.columns = ['Job Title', 'Organization', 'Location', 'Date Posted', 'Source', 'Relevance Score']
    
    # Display the dataframe
    st.write(display_df.to_html(escape=False, index=False), unsafe_allow_html=True)
    
    # Download options
    st.subheader("📥 Download Results")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # CSV download
        csv = df.to_csv(index=False)
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name=f"public_health_jobs_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )
    
    with col2:
        # JSON download
        json_str = df.to_json(orient='records', indent=2)
        st.download_button(
            label="Download JSON",
            data=json_str,
            file_name=f"public_health_jobs_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
            mime="application/json"
        )

if __name__ == "__main__":
    main()
