# here-poi-scraper

`here-poi-scraper` is a small scraper for HERE places. For example usage see [demo.py](demo.py).

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