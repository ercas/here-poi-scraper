# here-poi-scraper

For example usage see [demo.py](demo.py).

`here-poi-scraper` is a small scraper for HERE places.  This scraper supports the Browse endpoint in both the [Places v1](https://developer.here.com/documentation/places/dev_guide/topics_api/resource-browse.html) and [Geocoding & Search v7](https://developer.here.com/documentation/geocoding-search-api/dev_guide/topics/endpoint-browse-brief.html) APIs.

The v1 API is much faster but has been deprecated; new accounts cannot obtain keys for it; as such, the default functionality is to use the v7 API. However, each function has been implemented in both the v7 and v1 APIs; see [main.py](main.py) for more information.

[main.py](main.py) also has a CLI interface - see `main.py --help` for usage information. To do the same as in the example script:

```bash
# scrape
python3 main.py --db harvard_longwood.db scrape \
    --app-id APP_ID_HERE --app-code APP_CODE_HERE \
    --rectangle "(-71.1054416355,42.3346006792,-71.1001952347,42.3393749713)"

# export
python3 main.py --db harvard_longwood.db export\
    --format json --output harvard_longwood.json
python3 main.py --db harvard_longwood.db export\
    --format csv --output harvard_longwood.csv
```

More to follow.