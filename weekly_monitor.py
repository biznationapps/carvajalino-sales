"""
Carvajalino Sisters — Weekly Speaking Opportunity Monitor
Runs every Monday via GitHub Actions
Uses web search + Claude AI to find and validate new opportunities
"""

import json, re, os, sys, datetime, time
import urllib.request, urllib.parse

ANTHROPIC_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
TODAY = datetime.date.today()
LOG = []

def log(msg):
    print(msg)
    LOG.append({'time': str(datetime.datetime.now()), 'msg': msg})

def search_web(query):
    """Simple web search via DuckDuckGo HTML"""
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; CarvajalioMonitor/1.0)'
        })
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode('utf-8', errors='ignore')
        # Extract results
        results = re.findall(r'class="result__title".*?href="([^"]+)".*?class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
        clean = []
        for url, snippet in results[:5]:
            snippet = re.sub(r'<[^>]+>', '', snippet).strip()
            if len(snippet) > 20:
                clean.append({'url': url, 'snippet': snippet[:200]})
        return clean
    except Exception as e:
        log(f"  Search error: {e}")
        return []

def claude_extract(search_results_text, query):
    """Use Claude to extract structured event data from search results"""
    if not ANTHROPIC_KEY:
        return []
    
    prompt = f"""You are helping find speaking opportunities for the Carvajalino Sisters (Forbes 30U30, AI educators, bilingual EN/ES, Miami-based, trained 100K+ professionals).

Search query used: "{query}"

Search results found:
{search_results_text}

Extract any REAL, VERIFIED speaking opportunities from these results. Only include events that:
1. Actually exist (you can see a real URL or organization name)
2. Are in 2026 or 2027
3. Would be relevant for AI keynote speakers or professional trainers
4. Have not already happened

For each real opportunity found, respond with JSON array. If none found, return [].
Format:
[{{
  "name": "Event name",
  "org": "Organization name", 
  "city": "City, State/Country",
  "date": "Month Day, Year (or 'TBD 2026')",
  "contact": "email if found, or website",
  "why": "Why this fits Carvajalino Sisters profile (1 sentence)",
  "cat": "ai or host or corp",
  "priority": 1 or 2 or 3,
  "source_url": "url where found"
}}]

IMPORTANT: Only return events you are confident are real. Return [] if nothing verified found."""

    try:
        data = json.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1000,
            "messages": [{"role": "user", "content": prompt}]
        }).encode()
        
        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages',
            data=data,
            headers={
                'Content-Type': 'application/json',
                'x-api-key': ANTHROPIC_KEY,
                'anthropic-version': '2023-06-01'
            }
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read())
        
        text = resp.get('content', [{}])[0].get('text', '[]')
        text = re.sub(r'```json|```', '', text).strip()
        events = json.loads(text)
        return events if isinstance(events, list) else []
    except Exception as e:
        log(f"  Claude error: {e}")
        return []

def days_until(date_str):
    """Parse date string and return days until event"""
    try:
        months = {'January':1,'February':2,'March':3,'April':4,'May':5,'June':6,
                  'July':7,'August':8,'September':9,'October':10,'November':11,'December':12,
                  'Jan':1,'Feb':2,'Mar':3,'Apr':4,'Jun':6,'Jul':7,'Aug':8,
                  'Sep':9,'Oct':10,'Nov':11,'Dec':12}
        for month_name, month_num in months.items():
            if month_name in date_str:
                year_m = re.search(r'20(26|27)', date_str)
                year = int(year_m.group()) if year_m else 2026
                day_m = re.search(r'\b(\d{1,2})\b', date_str)
                day = int(day_m.group()) if day_m else 15
                event_date = datetime.date(year, month_num, min(day, 28))
                return (event_date - TODAY).days
    except:
        pass
    return None

def make_id(name, org):
    clean = re.sub(r'[^a-z0-9]', '_', (name[:20] + '_' + org[:10]).lower())
    return f"mon_{clean}_{TODAY.strftime('%Y%m%d')}"

# ── SEARCH QUERIES (methodology: location + industry + conference) ────────
QUERIES = [
    # Location + Industry + Conference
    "Miami AI conference 2026 call for speakers",
    "New York technology conference 2026 keynote speakers",
    "California entrepreneurship conference 2026 speakers",
    "Florida leadership summit 2026 speakers",
    "Texas business conference 2026 call for speakers",
    "Washington DC AI summit 2026 speakers",
    "Chicago innovation conference 2026 keynote",
    # Hispanic/Latina
    "Hispanic business conference 2026 speakers",
    "Latina leadership summit 2026 keynote",
    "LATAM conference 2026 call for speakers",
    "Latino entrepreneurship conference 2026 speakers",
    # AI specific
    "artificial intelligence conference 2026 call for speakers",
    "AI for business summit 2026 keynote",
    "AI women leaders conference 2026",
    "AI workforce development conference 2026",
    # Industry
    "HR conference 2026 call for speakers",
    "fintech conference 2026 keynote speakers",
    "healthcare AI conference 2026 speakers",
    "diversity inclusion conference 2026 keynote",
    # Hashtag equivalent
    '"call for speakers" conference 2026 AI bilingual',
    '"keynote speaker" wanted conference 2026 latina',
    '"speaker submission" summit 2026 artificial intelligence',
]

def main():
    log(f"=== Carvajalino Weekly Monitor — {TODAY} ===")
    
    # Load current app
    with open('index.html', encoding='utf-8') as f:
        html = f.read()
    
    m = re.search(r'const BASE=(\[.*?\]);', html, re.DOTALL)
    current_opps = json.loads(m.group(1))
    existing_names = {o['name'].lower().strip() for o in current_opps}
    existing_orgs = {o['org'].lower().strip() for o in current_opps}
    
    log(f"Current opps: {len(current_opps)}")
    
    new_events = []
    
    for i, query in enumerate(QUERIES):
        log(f"\n[{i+1}/{len(QUERIES)}] Searching: {query}")
        results = search_web(query)
        
        if not results:
            log("  No results")
            continue
        
        results_text = '\n'.join([f"URL: {r['url']}\nSnippet: {r['snippet']}" for r in results])
        events = claude_extract(results_text, query)
        
        for event in events:
            name = event.get('name', '').strip()
            org = event.get('org', '').strip()
            
            # Skip if already exists
            if name.lower() in existing_names:
                log(f"  SKIP (exists): {name}")
                continue
            if org.lower() in existing_orgs and len(org) > 5:
                log(f"  SKIP (org exists): {org}")
                continue
            
            # Build opp object
            days = days_until(event.get('date', ''))
            opp = {
                'id': make_id(name, org),
                'cat': event.get('cat', 'ai'),
                'name': name,
                'org': org,
                'city': event.get('city', 'TBD'),
                'date': event.get('date', 'TBD 2026'),
                'days': days,
                'days_label': f'{days}d' if days is not None else 'TBD',
                'days_urgency': 'now' if (days and days<=30) else 'soon' if (days and days<=90) else 'upcoming' if (days and days<=180) else 'later' if days else 'rolling',
                'days_sort': days if days is not None else 9999,
                'priority': event.get('priority', 2),
                'score': 70,
                'warm': False,
                'existing': False,
                'why': event.get('why', ''),
                'contact': event.get('contact', event.get('source_url', '')),
                'dm': '',
                'sq': event.get('source_url', ''),
                'contact_level': 'portal',
                'contact_label': '🔍 Monitor — verificar',
                'verified': False,
                'opp_type': 'conference',
                'monitor_added': str(TODAY),
            }
            
            new_events.append(opp)
            existing_names.add(name.lower())
            log(f"  ✅ NEW: {name} | {org} | {event.get('date', '?')}")
        
        time.sleep(2)  # Be polite
    
    log(f"\n=== RESULTS: {len(new_events)} new opportunities found ===")
    
    if new_events:
        # Inject into HTML
        updated_opps = current_opps + new_events
        new_base = json.dumps(updated_opps, ensure_ascii=True, separators=(',',':'))
        
        # Replace BASE
        old_m = re.search(r'const BASE=\[.*?\];', html, re.DOTALL)
        html = html[:old_m.start()] + 'const BASE=' + new_base + ';' + html[old_m.end():]
        
        with open('index.html', 'w', encoding='utf-8') as f:
            f.write(html)
        
        log(f"✅ index.html updated with {len(new_events)} new events")
    else:
        log("No new events to add this week")
    
    # Save log
    with open('monitor_log.json', 'w') as f:
        json.dump({
            'last_run': str(TODAY),
            'new_events': len(new_events),
            'total_opps': len(current_opps) + len(new_events),
            'log': LOG,
            'new_event_names': [e['name'] for e in new_events]
        }, f, indent=2, ensure_ascii=False)
    
    log("Done!")
    return len(new_events)

if __name__ == '__main__':
    main()
