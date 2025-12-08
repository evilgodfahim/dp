import json
import re
from datetime import datetime
import html

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
    
    def escape_xml(self, text):
        """Escape special XML characters"""
        if not text:
            return ''
        return html.escape(text)
    
    def generate_rss(self, articles):
        """Generate RSS 2.0 XML from articles using string building"""
        
        # Start RSS feed
        rss_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:content="http://purl.org/rss/1.0/modules/content/">',
            '  <channel>',
            '    <title>Dhaka Post - Opinion</title>',
            '    <link>https://www.dhakapost.com/opinion</link>',
            '    <description>Latest opinion articles from Dhaka Post</description>',
            '    <language>bn</language>',
            f'    <lastBuildDate>{datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0600")}</lastBuildDate>',
            '    <generator>Dhaka Post RSS Generator</generator>',
            '    <atom:link href="https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/feed.xml" rel="self" type="application/rss+xml"/>',
            ''
        ]
        
        # Add articles as items
        for article in articles:
            # Title
            title = article.get('Heading', 'No Title')
            if article.get('Subheading'):
                title += f" | {article['Subheading']}"
            
            # Other fields
            link = article.get('URL', '')
            description = article.get('Brief', '')
            pub_date = self.parse_bangla_date(article.get('CreatedAtBangla', ''))
            image_url = article.get('ImagePathMd', '')
            
            # Build content HTML
            content_html = ''
            if image_url:
                content_html += f'<img src="{image_url}" alt="{self.escape_xml(title)}" /><br/><br/>'
            content_html += self.escape_xml(description)
            
            # Add item
            rss_lines.extend([
                '    <item>',
                f'      <title>{self.escape_xml(title)}</title>',
                f'      <link>{self.escape_xml(link)}</link>',
                f'      <description>{self.escape_xml(description)}</description>',
                f'      <guid isPermaLink="true">{self.escape_xml(link)}</guid>',
                f'      <pubDate>{pub_date}</pubDate>',
                '      <category>Opinion</category>',
                '      <dc:creator>Dhaka Post</dc:creator>',
            ])
            
            # Add enclosure if image exists
            if image_url:
                rss_lines.append(f'      <enclosure url="{self.escape_xml(image_url)}" type="image/jpeg" length="0"/>')
            
            # Add content:encoded
            rss_lines.extend([
                f'      <content:encoded><![CDATA[{content_html}]]></content:encoded>',
                '    </item>',
                ''
            ])
        
        # Close RSS feed
        rss_lines.extend([
            '  </channel>',
            '</rss>'
        ])
        
        return '\n'.join(rss_lines)
    
    def update_feed(self):
        """Main function to update the RSS feed"""
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Updating RSS feed...")
        
        # Read HTML file
        html_content = self.read_html_file()
        if not html_content:
            print("ERROR: Failed to read HTML file")
            return False
        
        print(f"Successfully read HTML file: {self.html_file}")
        
        # Extract articles
        articles = self.extract_articles(html_content)
        if not articles:
            print("ERROR: No articles found in HTML")
            return False
        
        print(f"Successfully extracted {len(articles)} articles")
        
        # Generate RSS
        rss_content = self.generate_rss(articles)
        print(f"Generated RSS content ({len(rss_content)} characters)")
        
        # Save to file
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                f.write(rss_content)
            print(f"✓ SUCCESS: RSS feed saved to {self.output_file}")
            
            # Verify file was created
            import os
            if os.path.exists(self.output_file):
                file_size = os.path.getsize(self.output_file)
                print(f"✓ File verified: {self.output_file} ({file_size} bytes)")
            else:
                print(f"✗ ERROR: File was not created!")
                return False
                
            return True
        except Exception as e:
            print(f"✗ ERROR writing file: {e}")
            return False

if __name__ == "__main__":
    generator = RSSFeedGenerator()
    generator.update_feed()