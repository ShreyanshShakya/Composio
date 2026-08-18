with open(r'D:\Composio Assignment\composio-app-research\agent\researcher.py', 'r') as f:
    content = f.read()

# Remove the finally block from HTTPScraper.scrape and keep only except clauses
old = '''            except ImportError:
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
            finally:
                pass
            
            return FirecrawlResult('''

new = '''            except ImportError:
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
            
            return FirecrawlResult('''

content = content.replace(old, new)

with open(r'D:\Composio Assignment\composio-app-research\agent\researcher.py', 'w') as f:
    f.write(content)

print('Removed finally block from scrape method')