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
            
            # Look at the context around initialContents
            context_start = max(0, idx - 50)
            context_end = min(len(html_content), idx + 200)
            context = html_content[context_start:context_end]
            print(f"  Context: {repr(context)}")
            
            # Find where the actual JSON data starts
            # Look for common patterns: initialContents = [...] or initialContents: [...]
            start = html_content.find('[', idx)
            if start == -1:
                print("  ✗ No opening bracket found after initialContents")
                return []
            
            print(f"  Opening bracket at position {start} (offset +{start-idx} from initialContents)")
            print(f"  First 100 chars after bracket: {repr(html_content[start:start+100])}")
            
            # Check if this looks like valid JSON
            test_snippet = html_content[start:start+50].strip()
            if not test_snippet.startswith('['):
                print(f"  ✗ Unexpected content after bracket: {repr(test_snippet)}")
                return []
            
            # Try to find the end of the JSON array by looking for the pattern
            # We need to find either ];  or ]; or ]</script>
            
            # Method 1: Look for common termination patterns
            patterns = [
                (r'\];', 'semicolon'),
                (r'\]\s*<', 'tag'),
                (r'\]\s*var\s+', 'next var'),
            ]
            
            end = -1
            method_used = None
            
            for pattern, name in patterns:
                match = re.search(pattern, html_content[start:start+50000])
                if match:
                    end = start + match.end() - 1  # -1 to include the ]
                    method_used = name
                    print(f"  Found end using pattern '{name}' at position {end}")
                    break
            
            if end == -1:
                print("  ✗ Could not find JSON array end using patterns")
                print("  Trying bracket counting method...")
                
                # Fallback: bracket counting
                bracket_count = 0
                in_string = False
                escape_next = False
                
                for i in range(start, min(start + 50000, len(html_content))):
                    char = html_content[i]
                    
                    if escape_next:
                        escape_next = False
                        continue
                    
                    if char == '\\':
                        escape_next = True
                        continue
                    
                    if char == '"' and not escape_next:
                        in_string = not in_string
                        continue
                    
                    if not in_string:
                        if char == '[' or char == '{':
                            bracket_count += 1
                        elif char == ']' or char == '}':
                            bracket_count -= 1
                            if bracket_count == 0:
                                end = i + 1
                                method_used = 'bracket counting'
                                break
                
                if end > start:
                    print(f"  Found end using bracket counting at position {end}")
                else:
                    print("  ✗ Bracket counting failed")
                    return []
            
            json_str = html_content[start:end]
            print(f"  Extracted JSON string ({len(json_str)} characters)")
            print(f"  First 200 chars: {repr(json_str[:200])}")
            print(f"  Last 100 chars: {repr(json_str[-100:])}")
            
            # Parse the JSON
            try:
                articles = json.loads(json_str)
                print(f"✓ Successfully parsed {len(articles)} articles")
            except json.JSONDecodeError as e:
                print(f"  ✗ JSON decode error: {e}")
                
                # Save full JSON for debugging
                with open('debug_json_full.txt', 'w', encoding='utf-8') as f:
                    f.write(json_str)
                print(f"  Saved full JSON to debug_json_full.txt ({len(json_str)} bytes)")
                
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