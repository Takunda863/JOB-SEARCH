# app.py - Combined Streamlit app and scraper
import streamlit as st
import pandas as pd
import time
import os
import sys
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import logging
import json

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('enhanced_scraper.log'),
        logging.StreamHandler()
    ]
)

class EnhancedJobScraper:
    def __init__(self, headless=True):
        self.driver = None
        self.headless = headless
        self.setup_driver()
        self.jobs_data = []
        
    def setup_driver(self):
        """Setup Chrome driver with enhanced options"""
        chrome_options = Options()
        
        if self.headless:
            chrome_options.add_argument('--headless')
        
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument('--window-size=1920,1080')
        
        # Add more realistic browser behavior
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-popup-blocking')
        
        # For Streamlit Cloud compatibility
        chrome_options.binary_location = "/usr/bin/chromium-browser"
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        logging.info("Chrome driver setup completed")
    
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
        """Scrape ReliefWeb for public health M&E jobs"""
        logging.info(f"Scraping ReliefWeb for: {search_term}")
        
        url = f"https://reliefweb.int/jobs?search={search_term.replace(' ', '+')}"
        
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "article"))
            )
            
            jobs = []
            job_elements = self.driver.find_elements(By.CSS_SELECTOR, "article.rw-river-article--job")[:max_jobs]
            
            for job_element in job_elements:
                try:
                    job_data = self.extract_reliefweb_job_data(job_element)
                    if job_data:
                        job_data['search_term'] = search_term
                        job_data['is_recent'] = self.is_recent_job(job_data.get('date_posted', ''))
                        jobs.append(job_data)
                        
                except Exception as e:
                    logging.warning(f"Error extracting ReliefWeb job: {e}")
                    continue
            
            return jobs
            
        except Exception as e:
            logging.error(f"ReliefWeb scraping failed: {e}")
            return []
    
    def extract_reliefweb_job_data(self, job_element):
        """Extract job data from ReliefWeb job element"""
        try:
            # Title and URL
            title_element = job_element.find_element(By.CSS_SELECTOR, "h3.rw-river-article__title a")
            title = title_element.text.strip()
            url = title_element.get_attribute('href')
            
            # Organization
            try:
                org_element = job_element.find_element(By.CSS_SELECTOR, "dd")
                organization = org_element.text.strip()
            except:
                organization = "Unknown Organization"
            
            # Location
            try:
                location_element = job_element.find_element(By.CSS_SELECTOR, ".rw-river-article__country")
                location = location_element.text.strip()
            except:
                location = "Multiple Locations"
            
            # Date
            try:
                date_element = job_element.find_element(By.CSS_SELECTOR, "time")
                date_posted = date_element.text.strip()
            except:
                date_posted = "Unknown"
            
            return {
                'title': title,
                'organization': organization,
                'location': location,
                'url': url,
                'date_posted': date_posted,
                'source': 'reliefweb',
                'scraped_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logging.warning(f"Failed to extract ReliefWeb job data: {e}")
            return None
    
    def scrape_unjobs(self, search_term, max_jobs=15):
        """Scrape UNjobs for UN system positions"""
        logging.info(f"Scraping UNjobs for: {search_term}")
        
        url = f"https://unjobs.org/search/{search_term.replace(' ', '%20')}"
        
        try:
            self.driver.get(url)
            time.sleep(3)  # UNjobs might need more time to load
            
            jobs = []
            job_elements = self.driver.find_elements(By.CSS_SELECTOR, "div.job, .job-item")[:max_jobs]
            
            for job_element in job_elements:
                try:
                    job_data = self.extract_unjobs_job_data(job_element)
                    if job_data:
                        job_data['search_term'] = search_term
                        job_data['is_recent'] = self.is_recent_job(job_data.get('date_posted', ''))
                        jobs.append(job_data)
                        
                except Exception as e:
                    logging.warning(f"Error extracting UNjobs job: {e}")
                    continue
            
            return jobs
            
        except Exception as e:
            logging.error(f"UNjobs scraping failed: {e}")
            return []
    
    def extract_unjobs_job_data(self, job_element):
        """Extract job data from UNjobs element"""
        try:
            # Title
            title_element = job_element.find_element(By.CSS_SELECTOR, "h2, h3")
            title = title_element.text.strip()
            
            # URL
            link_element = job_element.find_element(By.CSS_SELECTOR, "a")
            url = link_element.get_attribute('href')
            
            # Organization
            try:
                org_element = job_element.find_element(By.CSS_SELECTOR, ".org, .organization")
                organization = org_element.text.strip()
            except:
                organization = "UN Agency"
            
            # Location
            try:
                location_element = job_element.find_element(By.CSS_SELECTOR, ".duty, .location")
                location = location_element.text.strip()
            except:
                location = "Multiple Duty Stations"
            
            return {
                'title': title,
                'organization': organization,
                'location': location,
                'url': url,
                'date_posted': "Recent",  # UNjobs usually shows recent postings
                'source': 'unjobs',
                'scraped_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logging.warning(f"Failed to extract UNjobs data: {e}")
            return None
    
    def scrape_development_sites(self, search_term, sites=None):
        """Scrape multiple development job sites"""
        if sites is None:
            sites = ['reliefweb', 'unjobs']
        
        all_jobs = []
        
        for site in sites:
            try:
                if site == 'reliefweb':
                    jobs = self.scrape_reliefweb(search_term)
                elif site == 'unjobs':
                    jobs = self.scrape_unjobs(search_term)
                else:
                    continue
                
                all_jobs.extend(jobs)
                time.sleep(2)  # Be respectful between sites
                
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
            'global health', 'health systems', 'epidemiology'
        ]
        
        filtered_jobs = []
        
        for job in jobs:
            job_text = f"{job['title']} {job.get('description', '')}".lower()
            
            # Check if job matches public health criteria
            matches = sum(1 for keyword in public_health_keywords if keyword in job_text)
            relevance_score = matches / len(public_health_keywords)
            
            if relevance_score >= 0.3:  # At least 30% match
                job['relevance_score'] = round(relevance_score, 2)
                job['is_public_health'] = True
                filtered_jobs.append(job)
            else:
                job['relevance_score'] = round(relevance_score, 2)
                job['is_public_health'] = False
        
        return filtered_jobs
    
    def close(self):
        """Close the browser"""
        if self.driver:
            self.driver.quit()
            logging.info("Browser closed")

# Streamlit App
class StreamlitJobScraper:
    def __init__(self):
        self.setup_ui()
    
    def setup_ui(self):
        """Setup Streamlit user interface"""
        # Header
        st.title("🔍 Public Health M&E Job Scraper")
        st.markdown("""
        This tool scrapes public health monitoring and evaluation jobs from multiple sources 
        including ReliefWeb and UNjobs. Find the latest opportunities in the global health sector.
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
        if st.sidebar.checkbox("UNjobs", value=True):
            sites.append('unjobs')
        
        # Job limits
        st.sidebar.subheader("Scraping Limits")
        max_jobs_per_search = st.sidebar.slider(
            "Max jobs per search term", 
            min_value=5, 
            max_value=50, 
            value=20
        )
        
        # Recent jobs filter
        show_only_recent = st.sidebar.checkbox("Show only jobs from last 24 hours", value=False)
        
        # Scraping control
        st.sidebar.subheader("Scraping Control")
        run_scraper = st.sidebar.button("🚀 Start Scraping", type="primary")
        
        return {
            'search_terms': search_terms,
            'sites': sites,
            'max_jobs': max_jobs_per_search,
            'show_only_recent': show_only_recent,
            'run_scraper': run_scraper
        }
    
    def display_results(self, jobs, config):
        """Display results in Streamlit"""
        if not jobs:
            st.warning("No jobs found matching your criteria. Try adjusting your search terms.")
            return
        
        # Filter jobs if only recent requested
        if config['show_only_recent']:
            jobs = [job for job in jobs if job.get('is_recent', False)]
            if not jobs:
                st.warning("No recent jobs found in the last 24 hours.")
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
        
        # Reorder columns for better display
        display_columns = ['Job Title', 'organization', 'location', 'date_posted', 'source', 'relevance_score']
        display_df = display_df[['Job Title', 'organization', 'location', 'date_posted', 'source', 'relevance_score']]
        
        # Rename columns for display
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
    
    def run_scraper_with_progress(self, config):
        """Run the scraper with progress indicators"""
        if not config['search_terms']:
            st.error("Please select at least one search term.")
            return []
        
        if not config['sites']:
            st.error("Please select at least one website to scrape.")
            return []
        
        # Initialize scraper
        scraper = EnhancedJobScraper(headless=True)
        
        try:
            # Progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            all_jobs = []
            total_searches = len(config['search_terms'])
            
            for i, search_term in enumerate(config['search_terms']):
                status_text.text(f"🔍 Searching for: '{search_term}'...")
                
                try:
                    # Run search for this term
                    jobs = scraper.scrape_development_sites(
                        search_term, 
                        config['sites']
                    )
                    
                    # Filter for public health relevance
                    filtered_jobs = scraper.filter_public_health_jobs(jobs)
                    all_jobs.extend(filtered_jobs)
                    
                    status_text.text(f"✅ Found {len(filtered_jobs)} jobs for '{search_term}'")
                    
                except Exception as e:
                    st.error(f"Error searching for '{search_term}': {str(e)}")
                    continue
                
                finally:
                    # Update progress
                    progress = (i + 1) / total_searches
                    progress_bar.progress(progress)
                    
                    # Small delay between searches
                    time.sleep(2)
            
            # Remove duplicates
            unique_jobs = []
            seen_urls = set()
            for job in all_jobs:
                if job['url'] not in seen_urls:
                    seen_urls.add(job['url'])
                    unique_jobs.append(job)
            
            progress_bar.progress(1.0)
            status_text.text(f"🎉 Scraping complete! Found {len(unique_jobs)} unique jobs.")
            
            return unique_jobs
            
        finally:
            scraper.close()

def main():
    """Main Streamlit app"""
    app = StreamlitJobScraper()
    config = app.setup_ui()
    
    if config['run_scraper']:
        with st.spinner("Starting job search..."):
            jobs = app.run_scraper_with_progress(config)
            app.display_results(jobs, config)

if __name__ == "__main__":
    main()
