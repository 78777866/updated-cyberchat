import requests
import logging
from typing import Dict, Any, List
from urllib.parse import quote_plus

class SearchService:
    def __init__(self):
        self.duckduckgo_api = "https://api.duckduckgo.com/"
    
    def search(self, query: str) -> str:
        """Search using DuckDuckGo and return formatted results"""
        try:
            # Use DuckDuckGo Instant Answer API
            params = {
                'q': query,
                'format': 'json',
                'no_redirect': '1',
                'no_html': '1',
                'skip_disambig': '1'
            }
            
            response = requests.get(self.duckduckgo_api, params=params, timeout=10)
            
            if response.status_code != 200:
                return f"❌ Search service unavailable (Status: {response.status_code})"
            
            data = response.json()
            
            # Format search results
            results = []
            
            # Abstract (main answer)
            if data.get('Abstract'):
                results.append(f"## 🔍 Search Results for: {query}\n")
                results.append(f"**{data.get('AbstractText', '')}**\n")
                if data.get('AbstractURL'):
                    results.append(f"[Read more]({data.get('AbstractURL')})\n")
            
            # Related topics
            if data.get('RelatedTopics'):
                results.append("### Related Topics:\n")
                for i, topic in enumerate(data['RelatedTopics'][:5]):  # Limit to 5
                    if isinstance(topic, dict) and topic.get('Text'):
                        results.append(f"{i+1}. {topic['Text']}")
                        if topic.get('FirstURL'):
                            results.append(f"   [Link]({topic['FirstURL']})")
                        results.append("")
            
            # Answer (direct answer)
            if data.get('Answer'):
                results.append(f"### Quick Answer:\n{data['Answer']}\n")
            
            # Definition
            if data.get('Definition'):
                results.append(f"### Definition:\n{data['Definition']}")
                if data.get('DefinitionURL'):
                    results.append(f"[Source]({data['DefinitionURL']})")
                results.append("")
            
            if not results:
                # Fallback: try web search with limited results
                return self._fallback_search(query)
            
            return "\n".join(results)
            
        except requests.exceptions.Timeout:
            return "⏳ Search request timed out. Please try again."
        except requests.exceptions.RequestException as e:
            logging.error(f"Search API error: {e}")
            return f"❌ Search service error: {str(e)}"
        except Exception as e:
            logging.error(f"Search error: {e}")
            return f"❌ An error occurred during search: {str(e)}"
    
    def _fallback_search(self, query: str) -> str:
        """Fallback search method when main search returns no results"""
        return f"""## 🔍 Search Results for: {query}

I apologize, but I couldn't find specific results for your query using the search service. This could be due to:

- The query being too specific or uncommon
- Temporary search service limitations
- Network connectivity issues

**Suggestions:**
- Try rephrasing your search with different keywords
- Use more general terms
- Check your spelling

You can also try searching directly on:
- [DuckDuckGo](https://duckduckgo.com/?q={quote_plus(query)})
- [Google](https://www.google.com/search?q={quote_plus(query)})

Feel free to ask me directly about the topic - I might be able to help based on my training data!"""
