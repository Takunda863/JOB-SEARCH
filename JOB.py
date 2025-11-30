import streamlit as st
import pandas as pd
import time
from datetime import datetime
import sys
import os

# Add the scraper class to the path
sys.path.append(os.path.dirname(__file__))

# Import your existing scraper class
from enhanced_scraper import EnhancedJobScraper

# Streamlit app configuration
st.set_page_config(
    page_title="Public Health M&E Job Scraper",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

class StreamlitJobScraper:
    def __init__(self):
        self.scraper = None
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
            sources = set(df['source'].tolist())
            st.metric("Sources", ", ".join(sources))
        
        # Display jobs in an interactive table
        st.subheader("📋 Job Results")
        
        # Create a display dataframe with clickable links
        display_df = df.copy()
        display_df['title'] = display_df.apply(
            lambda x: f'<a href="{x["url"]}" target="_blank">{x["title"]}</a>', 
            axis=1
        )
        
        # Reorder columns for better display
        display_columns = ['title', 'organization', 'location', 'date_posted', 'source', 'relevance_score']
        display_df = display_df[display_columns]
        
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
        
        # Recent jobs section (if any)
        recent_jobs = [job for job in jobs if job.get('is_recent', False)]
        if recent_jobs and not config['show_only_recent']:
            st.subheader("🆕 Recent Jobs (Last 24 Hours)")
            for job in recent_jobs:
                self.display_job_card(job)
    
    def display_job_card(self, job):
        """Display individual job as a card"""
        with st.container():
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown(f"### [{job['title']}]({job['url']})")
                st.markdown(f"**Organization:** {job['organization']} | **Location:** {job['location']}")
                st.markdown(f"**Posted:** {job.get('date_posted', 'Unknown')} | **Source:** {job['source']}")
            
            with col2:
                relevance_score = job.get('relevance_score', 0)
                st.metric("Match Score", f"{relevance_score*100:.0f}%")
            
            st.markdown("---")
    
    def run_scraper_with_progress(self, config):
        """Run the scraper with progress indicators"""
        if not config['search_terms']:
            st.error("Please select at least one search term.")
            return []
        
        if not config['sites']:
            st.error("Please select at least one website to scrape.")
            return []
        
        # Initialize scraper
        self.scraper = EnhancedJobScraper(headless=True)
        
        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        all_jobs = []
        total_searches = len(config['search_terms'])
        
        for i, search_term in enumerate(config['search_terms']):
            status_text.text(f"🔍 Searching for: '{search_term}'...")
            
            try:
                # Run search for this term
                jobs = self.scraper.scrape_development_sites(
                    search_term, 
                    config['sites']
                )
                
                # Filter for public health relevance
                filtered_jobs = self.scraper.filter_public_health_jobs(jobs)
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
