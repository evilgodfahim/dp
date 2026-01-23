#!/usr/bin/env python3
import json
from datetime import datetime
import html
import sys
import os
import re

class RSSFeedGenerator:
    def __init__(self, html_file='opinion.html', output_file='feed.xml'):
        self.html_file = html_file
        self.output_file = output_file
        self.max_articles = 500

    def read_html_file(self):
        """Read the opinion.html file from local directory"""
        try:
            print(f"Reading file: {self.html_file}")
            with open(self.html_file, 'r', encoding='utf-8') as f:
                content = f.read()
            print(f"✓ File read successfully ({len(content)} characters)")
            return content
        except FileNotFoundError:
            print(f"✗ ERROR: File '{self.html_file}' not found!")
            for f in os.listdir('.'):
                print(f"   - {f}")
            return None
        except Exception as e:
            print(f"✗ ERROR reading file: {e}")
            return None

    def extract_articles(self, html_content):
        """Extract article data from the HTML content"""
        try:
            print("Extracting articles from HTML...")

            # Find the initialContents variable
            idx = html_content.find('initialContents')
            if idx == -1:
                print("✗ ERROR: 'initialContents' not found")
                return []
            
            print(f"  Found 'initialContents' at position {idx}")
            
            # The JSON is escaped with backslashes, so we need to find the pattern
            # "initialContents":[{...}]
            # The actual JSON starts after the colon and opening bracket
            
            # Find the opening bracket after initialContents
            start = html_content.find('[', idx)
            if start == -1:
                print("  ✗ No opening bracket found")
                return []
            
            print(f"  Opening bracket at position {start}")
            
            # Now we need to find the matching closing bracket
            # The string has escaped quotes, so we need to handle \\" properly
            bracket_count = 0
            in_string = False
            i = start
            escape_next = False
            
            while i < len(html_content):
                char = html_content[i]
                
                # Handle escaped characters
                if escape_next:
                    escape_next = False
                    i += 1
                    continue
                
                if char == '\\':
                    escape_next = True
                    i += 1
                    continue
                
                # Track if we're inside a string (checking for \")
                if char == '"':
                    in_string = not in_string
                    i += 1
                    continue
                
                # Only count brackets when not in a string
                if not in_string:
                    if char == '[' or char == '{':
                        bracket_count += 1
                    elif char == ']' or char == '}':
                        bracket_count -= 1
                        if bracket_count == 0:
                            end = i + 1
                            break
                
                i += 1
            
            if bracket_count != 0:
                print(f"  ✗ Could not find matching closing bracket (count={bracket_count})")
                return []
            
            # Extract the JSON string (with escaped quotes)
            json_str_escaped = html_content[start:end]
            print(f"  Extracted escaped JSON ({len(json_str_escaped)} characters)")
            
            # Now unescape the JSON string
            # Replace \" with " and \\ with \
            json_str = json_str_escaped.replace('\\"', '"').replace('\\\\', '\\')
            
            print(f"  Unescaped to {len(json_str)} characters")
            print(f"  First 150 chars: {json_str[:150]}")
            print(f"  Last 150 chars: {json_str[-150:]}")
            
            # Parse the JSON
            try:
                articles = json.loads(json_str)
                print(f"✓ Successfully parsed {len(articles)} articles")
                
                # Show a sample article
                if articles and len(articles) > 0:
                    sample = articles[0]
                    print(f"  Sample article: {sample.get('Heading', 'N/A')[:50]}...")
                    
            except json.JSONDecodeError as e:
                print(f"  ✗ JSON decode error: {e}")
                
                # Save for debugging
                with open('debug_json_unescaped.txt', 'w', encoding='utf-8') as f:
                    f.write(json_str[:5000])  # First 5000 chars
                print(f"  Saved first 5000 chars to debug_json_unescaped.txt")
                
                return []
            
            if len(articles) > self.max_articles:
                articles = articles[:self.max_articles]
                print(f"  Limited to {self.max_articles} articles")

            return articles
            
        except Exception as e:
            print(f"✗ ERROR extracting articles: {e}")
            import traceback
            traceback.print_exc()
            return []

    def parse_bangla_date(self, bangla_date):
        """Convert Bangla date to RFC 822 format"""
        bangla_months = {
            'জানুয়ারি': 1, 'ফেব্রুয়ারি': 2, 'মার্চ': 3, 'এপ্রিল': 4,
            'মে': 5, 'জুন': 6, 'জুলাই': 7, 'আগস্ট': 8,
            'সেপ্টেম্বর': 9, 'অক্টোবর': 10, 'নভেম্বর': 11, 'ডিসেম্বর': 12
        }

        bangla_digits = {'০': '0', '১': '1', '২': '2', '৩': '3', '৪': '4',
                         '৫': '5', '৬': '6', '৭': '7', '৮': '8', '৯': '9'}

        try:
            english_date = bangla_date
            for bn, en in bangla_digits.items():
                english_date = english_date.replace(bn, en)

            parts = english_date.split(',')
            date_part = parts[0].strip()
            time_part = parts[1].strip() if len(parts) > 1 else "00:00"

            date_components = date_part.split()
            day = int(date_components[0])
            month_name = date_components[1]
            year = int(date_components[2])

            month = bangla_months.get(month_name, 1)

            time_components = time_part.split(':')
            hour = int(time_components[0])
            minute = int(time_components[1]) if len(time_components) > 1 else 0

            dt = datetime(year, month, day, hour, minute)
            return dt.strftime('%a, %d %b %Y %H:%M:%S +0600')
        except:
            return datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0600')

    def escape_xml(self, text):
        """Escape special XML characters"""
        if not text:
            return ''
        return html.escape(str(text))

    def generate_rss(self, articles):
        """Generate RSS 2.0 XML from articles"""
        print(f"Generating RSS feed with {len(articles)} articles...")

        rss_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<rss version="2.0" '
            'xmlns:atom="http://www.w3.org/2005/Atom" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:content="http://purl.org/rss/1.0/modules/content/">',
            '  <channel>',
            '    <title>Dhaka Post - Opinion</title>',
            '    <link>https://www.dhakapost.com/opinion</link>',
            '    <description>Latest opinion articles from Dhaka Post</description>',
            '    <language>bn</language>',
            f'    <lastBuildDate>{datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0600")}</lastBuildDate>',
            '    <generator>Dhaka Post RSS Generator</generator>',
            ''
        ]

        for idx, article in enumerate(articles):
            try:
                title = article.get('Heading', 'No Title')
                if article.get('Subheading'):
                    title += f" | {article['Subheading']}"

                link = article.get('URL', '')
                description = article.get('Brief', '')
                pub_date = self.parse_bangla_date(article.get('CreatedAtBangla', ''))
                image_url = article.get('ImagePathMd', '')

                content_html = ''
                if image_url:
                    content_html += f'<img src="{image_url}" alt="{self.escape_xml(title)}" /><br/><br/>'
                content_html += self.escape_xml(description)

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

                if image_url:
                    rss_lines.append(f'      <enclosure url="{self.escape_xml(image_url)}" type="image/jpeg" length="0"/>')

                rss_lines.extend([
                    f'      <content:encoded><![CDATA[{content_html}]]></content:encoded>',
                    '    </item>',
                    ''
                ])

            except Exception as e:
                print(f"  Warning: Error processing article {idx}: {e}")
                continue

        rss_lines.extend([
            '  </channel>',
            '</rss>'
        ])

        print(f"✓ RSS XML generated ({len(rss_lines)} lines)")
        return '\n'.join(rss_lines)

    def update_feed(self):
        """Main function to update the RSS feed"""
        print("=" * 60)
        print(f"RSS Feed Generator - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        html_content = self.read_html_file()
        if not html_content:
            print("\n✗ FAILED: Could not read HTML file")
            return False

        articles = self.extract_articles(html_content)
        if not articles:
            print("\n✗ FAILED: No articles extracted")
            return False

        rss_content = self.generate_rss(articles)

        try:
            print(f"Writing RSS feed to: {self.output_file}")
            with open(self.output_file, 'w', encoding='utf-8') as f:
                f.write(rss_content)

            if os.path.exists(self.output_file):
                file_size = os.path.getsize(self.output_file)
                print(f"✓ SUCCESS: {self.output_file} created ({file_size:,} bytes)")
                print("=" * 60)
                return True
            else:
                print(f"✗ FAILED: File was not created!")
                return False

        except Exception as e:
            print(f"✗ FAILED: Error writing file: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    generator = RSSFeedGenerator()
    success = generator.update_feed()
    sys.exit(0 if success else 1)