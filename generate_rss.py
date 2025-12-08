import json
import re
from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
import os

class RSSFeedGenerator:
    def __init__(self, html_file='opinion.html', output_file='feed.xml'):
        self.html_file = html_file
        self.output_file = output_file
        self.max_articles = 500
        
    def read_html_file(self):
        """Read the opinion.html file from local directory"""
        try:
            with open(self.html_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Error reading HTML file: {e}")
            return None
    
    def extract_articles(self, html_content):
        """Extract article data from the HTML content"""
        try:
            # Find the JSON data in the script tag
            pattern = r'"initialContents":\[(.*?)\],"id"'
            match = re.search(pattern, html_content, re.DOTALL)
            
            if not match:
                print("Could not find article data")
                return []
            
            json_str = '[' + match.group(1) + ']'
            # Clean up escaped characters
            json_str = json_str.replace('\\u0026', '&')
            json_str = json_str.replace('\\"', '"')
            
            articles = json.loads(json_str)
            return articles[:self.max_articles]
        except Exception as e:
            print(f"Error extracting articles: {e}")
            return []
    
    def parse_bangla_date(self, bangla_date):
        """Convert Bangla date to RFC 822 format"""
        # Map Bangla month names to numbers
        bangla_months = {
            'জানুয়ারি': 1, 'ফেব্রুয়ারি': 2, 'মার্চ': 3, 'এপ্রিল': 4,
            'মে': 5, 'জুন': 6, 'জুলাই': 7, 'আগস্ট': 8,
            'সেপ্টেম্বর': 9, 'অক্টোবর': 10, 'নভেম্বর': 11, 'ডিসেম্বর': 12
        }
        
        bangla_digits = {'০': '0', '১': '1', '২': '2', '৩': '3', '৪': '4',
                        '৫': '5', '৬': '6', '৭': '7', '৮': '8', '৯': '9'}
        
        try:
            # Convert Bangla digits to English
            english_date = bangla_date
            for bn, en in bangla_digits.items():
                english_date = english_date.replace(bn, en)
            
            # Parse date string (e.g., "8 ডিসেম্বর 2025, 09:10")
            parts = english_date.split(',')
            date_part = parts[0].strip()
            time_part = parts[1].strip() if len(parts) > 1 else "00:00"
            
            # Split date part
            date_components = date_part.split()
            day = int(date_components[0])
            month_name = date_components[1]
            year = int(date_components[2])
            
            # Get month number
            month = bangla_months.get(month_name, 1)
            
            # Parse time
            time_components = time_part.split(':')
            hour = int(time_components[0])
            minute = int(time_components[1]) if len(time_components) > 1 else 0
            
            # Create datetime object
            dt = datetime(year, month, day, hour, minute)
            
            # Return RFC 822 format
            return dt.strftime('%a, %d %b %Y %H:%M:%S +0600')
        except:
            # Fallback to current time
            return datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0600')
    
    def generate_rss(self, articles):
        """Generate RSS 2.0 XML from articles"""
        # Create RSS root
        rss = Element('rss', version='2.0')
        rss.set('xmlns:atom', 'http://www.w3.org/2005/Atom')
        rss.set('xmlns:dc', 'http://purl.org/dc/elements/1.1/')
        rss.set('xmlns:content', 'http://purl.org/rss/1.0/modules/content/')
        
        # Create channel
        channel = SubElement(rss, 'channel')
        
        # Channel metadata
        SubElement(channel, 'title').text = 'Dhaka Post - Opinion'
        SubElement(channel, 'link').text = 'https://www.dhakapost.com/opinion'
        SubElement(channel, 'description').text = 'Latest opinion articles from Dhaka Post'
        SubElement(channel, 'language').text = 'bn'
        SubElement(channel, 'lastBuildDate').text = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0600')
        SubElement(channel, 'generator').text = 'Dhaka Post RSS Generator'
        
        # Self link
        atom_link = SubElement(channel, '{http://www.w3.org/2005/Atom}link')
        atom_link.set('href', 'https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/feed.xml')
        atom_link.set('rel', 'self')
        atom_link.set('type', 'application/rss+xml')
        
        # Add articles as items (they come pre-sorted, newest first)
        for article in articles:
            item = SubElement(channel, 'item')
            
            # Title
            title = article.get('Heading', 'No Title')
            if article.get('Subheading'):
                title += f" | {article['Subheading']}"
            SubElement(item, 'title').text = title
            
            # Link
            link = article.get('URL', '')
            SubElement(item, 'link').text = link
            
            # Description/Brief
            description = article.get('Brief', '')
            SubElement(item, 'description').text = description
            
            # GUID
            SubElement(item, 'guid', isPermaLink='true').text = link
            
            # Pub Date
            pub_date = self.parse_bangla_date(article.get('CreatedAtBangla', ''))
            SubElement(item, 'pubDate').text = pub_date
            
            # Category
            SubElement(item, 'category').text = 'Opinion'
            
            # Author/Creator
            SubElement(item, '{http://purl.org/dc/elements/1.1/}creator').text = 'Dhaka Post'
            
            # Enclosure for image
            if article.get('ImagePathMd'):
                enclosure = SubElement(item, 'enclosure')
                enclosure.set('url', article['ImagePathMd'])
                enclosure.set('type', 'image/jpeg')
                enclosure.set('length', '0')
            
            # Content encoded (full HTML description with image)
            if article.get('ImagePathMd') or description:
                content_html = ''
                if article.get('ImagePathMd'):
                    content_html += f'<img src="{article["ImagePathMd"]}" alt="{title}" /><br/><br/>'
                content_html += description
                SubElement(item, '{http://purl.org/rss/1.0/modules/content/}encoded').text = content_html
        
        return rss
    
    def prettify_xml(self, elem):
        """Return a pretty-printed XML string"""
        rough_string = tostring(elem, encoding='utf-8')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ", encoding='utf-8').decode('utf-8')
    
    def update_feed(self):
        """Main function to update the RSS feed"""
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Updating RSS feed...")
        
        # Read HTML file
        html_content = self.read_html_file()
        if not html_content:
            print("Failed to read HTML file")
            return False
        
        # Extract articles
        articles = self.extract_articles(html_content)
        if not articles:
            print("No articles found")
            return False
        
        print(f"Found {len(articles)} articles")
        
        # Generate RSS
        rss = self.generate_rss(articles)
        
        # Save to file
        xml_string = self.prettify_xml(rss)
        with open(self.output_file, 'w', encoding='utf-8') as f:
            f.write(xml_string)
        
        print(f"RSS feed saved to {self.output_file}")
        return True

if __name__ == "__main__":
    generator = RSSFeedGenerator()
    generator.update_feed()