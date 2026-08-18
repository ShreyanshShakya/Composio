with open(r'D:\Composio Assignment\composio-app-research\agent\researcher.py', 'r') as f:
    content = f.read()

# Fix HTTPScraper.scrape method - restructure the try/except
old = '''            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(content, 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style", "nav", "footer", "header", "aside"]):
                    script.decompose()
                
                # Get text content
                text = soup.get_text(separator='\n', strip=True)
                
                # Clean problematic Unicode characters
                text = text.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '').replace('\ufeff', '')
                
                # Limit length
                if len(text) > 10000:
                    text = text[:10000] + "... [truncated]"
                
                content = text
            except ImportError:
                # BeautifulSoup not available, use raw HTML (truncated)
                if len(content) > 10000:
                    content = content[:10000] + "... [truncated]"
            
            return FirecrawlResult(
                url=url,
                content=content,
                metadata={"status_code": resp.status_code},
                success=True,
                error=None
            )
            except Exception as e:
                        return FirecrawlResult(
                        url=url,
                        content="",
                        metadata={},
                        success=False,
                        error=str(e)
                    )'''

new = '''            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(content, 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style", "nav", "footer", "header", "aside"]):
                    script.decompose()
                
                # Get text content
                text = soup.get_text(separator='\n', strip=True)
                
                # Clean problematic Unicode characters
                text = text.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '').replace('\ufeff', '')
                
                # Limit length
                if len(text) > 10000:
                    text = text[:10000] + "... [truncated]"
                
                content = text
            except ImportError:
                # BeautifulSoup not available, use raw HTML (truncated)
                if len(content) > 10000:
                    content = content[:10000] + "... [truncated]"
            except Exception as e:
                return FirecrawlResult(
                    url=url,
                    content="",
                    metadata={},
                    success=False,
                    error=str(e)
                )
            
            return FirecrawlResult(
                url=url,
                content=content,
                metadata={"status_code": resp.status_code},
                success=True,
                error=None
            )'''

content = content.replace(old, new)

with open(r'D:\Composio Assignment\composio-app-research\agent\researcher.py', 'w') as f:
    f.write(content)

print('Fixed HTTPScraper.scrape method')