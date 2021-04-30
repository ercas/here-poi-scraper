import configparser

import main

# load stored API keys
config = configparser.ConfigParser()
config.read("config.ini")
api_key = config["here"]["api_key"]

# set up the scraper and start scraping
scraper = main.HerePlacesScraper("harvard_longwood.db", api_key)
scraper.scrape(main.Rectangle(-71.1054416355, 42.3346006792, -71.1001952347, 42.3393749713))

# how many results did we get?
places = list(scraper.iter_places())
print("{} places".format(len(places)))

# write out data
scraper.write_ndjson("harvard_longwood.json")
scraper.write_csv("harvard_longwood.csv")