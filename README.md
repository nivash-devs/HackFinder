# HackFinder

Type your city, see every hackathon and game jam near you. Online ones too.

Events are pulled automatically from:

| Source | What it has | How it's read |
|---|---|---|
| Hack Club | High school hackathons, with map coordinates | Public JSON API |
| Devpost | College and company hackathons, online and in person | Devpost's public listing JSON, plus each event page for the street address |
| MLH | Official MLH member hackathons | Event cards on mlh.com (schema.org tags) |
| itch.io | Game jams (almost all online) | The /jams/upcoming and /jams/in-progress pages |

Organizers don't sign up or paste anything. If an event is public on one of these sites, it shows up on the next run (every 6 hours).

## How it works

1. `scraper/fetch_events.py` downloads the listings, converts them to one format, merges duplicates (the same event is often on MLH and Devpost), and turns addresses into map coordinates with OpenStreetMap's free geocoder.
2. It writes `site/events.json`.
3. `site/index.html` loads that file. When you type a city, it finds the city's coordinates (Photon, a free OpenStreetMap geocoder) and shows events within your radius using the haversine formula for distance on a sphere.
4. A GitHub Action does steps 1 and 2 every 6 hours and republishes the site. Free.

## Put it online (about 10 minutes)

1. Make a GitHub account if you don't have one, then create a new **public** repository called `hackfinder`.
2. Upload everything in this folder (keep the folder structure, including `.github`).
3. In `scraper/fetch_events.py`, change `YOUR_USERNAME` in `USER_AGENT` to your GitHub username.
4. Repo **Settings → Pages → Build and deployment → Source: GitHub Actions**.
5. Go to the **Actions** tab, pick **Update events**, press **Run workflow**.
6. After a couple of minutes your site is at `https://nivash-devs.github.io/HackFinder/`.

## Run it on your own computer

```
pip install -r requirements.txt
python scraper/fetch_events.py
cd site && python -m http.server 8000
```
Then open http://localhost:8000.

## When something breaks

Websites change their layout. If one source stops working, the others keep going and the footer of the site shows which one failed. `python tests/test_scraper.py` has a fake copy of each site's layout, so you can compare it to the real page and fix the parser.

## Not included yet

- **Luma.** It has lots of tech events but no public search API. Its official API only covers calendars you own.
- **Devfolio** (big in India), **Unstop**, **Eventbrite**. Good next sources to add.

Be polite to these sites: keep the 6 hour schedule and the delays in the code. Devpost's listing JSON is not an official API, so it could change without warning.
