"""High-entropy procedural pools for names, aliases, places, vehicles, shells, and commodities."""

from __future__ import annotations

import random
from typing import Sequence

FIRST_NAMES = (
    "Marcus", "Elena", "Darnell", "Logan", "Valerie", "Hector", "Tessa", "Raymond",
    "Nadia", "Curtis", "Brenda", "Julian", "Keisha", "Arthur", "Monique", "Trevor",
    "Carmen", "Devin", "Patricia", "Kenneth", "Sylvia", "Omar", "Lindsey", "Gregory",
    "Miriam", "Lonnie", "Irene", "Mateo", "Rhonda", "Caleb", "Denise", "Russell",
    "Farah", "Dwight", "Alicia", "Shane", "Veronica", "Terrence", "Hanna", "Gordon",
    "Yolanda", "Clint", "Bianca", "Wesley", "Naomi", "Cedric", "Tamara", "Preston",
    "Rosa", "Mitchell", "Kendra", "Duane", "Selena", "Garrett", "Priya", "Vernon",
    "Lydia", "Malik", "Colleen", "Ruben", "Audrey", "Derrick", "Janet", "Sterling",
    "Tomas", "corinne", "Victor", "Estelle", "Damon", "Simone", "warren", "Noelle",
    "desmond", "Camille", "Leland", "Marisol", "Gavin", "Anita", "Bryce", "celeste",
    "roman", "Joanne", "Tariq", "Meredith", "alton", "Sabrina", "harlan", "Clarissa",
    "nelson", "Phoebe", "kirk", "beatrice", "elliot", "Regina", "vance", "diana",
    "leon", "pauline", "grant", "lucia", "spencer", "claudia", "noah", "sonia",
    "reid", "helena", "miles", "yvonne", "clark", "karina", "ross", "gloria",
    "keith", "maya", "bruce", "elise", "lloyd", "nina", "floyd", "vera",
)
FIRST_NAMES = tuple(dict.fromkeys(n.strip().capitalize() for n in FIRST_NAMES))

LAST_NAMES = (
    "Kowalski", "Delgado", "Mercer", "Hargrove", "Okafor", "Callahan", "Vasquez",
    "Pruitt", "Bauer", "Whitaker", "Salazar", "McAllister", "Tran", "Boudreaux",
    "Stanton", "Khoury", "Alvarez", "Gillespie", "Sato", "Hendricks", "Molina",
    "Faulkner", "Choi", "Holloway", "Carver", "Benitez", "Langley", "Novak",
    "Wilkins", "Osorio", "Rutledge", "Pacheco", "Keane", "Sorensen", "Guzman",
    "Maddox", "Lindqvist", "Burnett", "Cabrera", "Vance", "Ashford", "Caffrey",
    "Padilla", "Hensley", "Roche", "Kaufman", "Estrada", "Pelletier", "Tucker",
    "Zamora", "Donnelly", "Briggs", "Navarro", "Steele", "Ibarra", "Corbin",
    "Herrera", "Delaney", "Whitfield", "Reyes", "Hahn", "Luna", "Bell", "Marsh",
    "tierney", "moreau", "kaczmarek", "haddad", "halvorsen", "devera", "quinn", "lockwood",
    "gallagher", "medina", "solis", "carmichael", "beauchamp", "vogel", "santoro", "kline",
    "broussard", "espinoza", "macdonald", "lund", "mercado", "thorne", "doyle", "pritchard",
    "almeida", "berglund", "castellano", "driscoll", "fischer", "grimes", "holcomb", "ingram",
    "jarvis", "kerrigan", "lomax", "mueller", "nolan", "orsini", "prescott", "quintana",
    "ramsey", "sinclair", "talbot", "ullman", "villarreal", "winslow", "yates", "zimmerman",
)
LAST_NAMES = tuple(dict.fromkeys(n.strip().capitalize() if not n.startswith("Mc") else n for n in LAST_NAMES))

ALIAS_NICKNAMES: dict[str, tuple[str, ...]] = {
    "Raymond": ("Ray", "R.J."),
    "Marcus": ("Marc", "M."),
    "Kenneth": ("Kenny", "Ken"),
    "Patricia": ("Patty", "Trish"),
    "Gregory": ("Greg", "G."),
    "Tomas": ("Tommy", "Tom"),
    "Veronica": ("Ronnie", "V."),
    "Mitchell": ("Mitch",),
    "Terrence": ("Terry", "T-Bone"),
    "nicholas": ("Nick",),
    "Benjamin": ("Benny",),
    "salvador": ("Sal",),
    "Victoria": ("Vicki",),
    "Derrick": ("Rick", "D."),
    "Russell": ("Russ",),
    "Camille": ("Cami",),
}

COUNTIES = (
    ("Calhoun County", "Mercer County", "State Route 41"),
    ("Garrick County", "Redwood County", "US-19 Corridor"),
    ("Huron County", "Wexford County", "County Line Rd"),
    ("Blackwater County", "Polk County", "Interstate 74"),
    ("Cumberland County", "Pike County", "Old Mill Turnpike"),
    ("Kestrel County", "Washburn County", "Riverbend Pkwy"),
    ("Cortland County", "Seneca County", "Route 9 Bridge"),
    ("Pembroke County", "Halifax County", "Highway 62"),
    ("Alder County", "Navarro County", "Spur 308"),
    ("Shawnee County", "Osage County", "Bypass 50"),
    ("Rockland County", "Bergen County", "Palisades Connector"),
    ("genesee County", "Monroe County", "Canal Expressway"),
)
COUNTIES = tuple((a[0].upper() + a[1:], b[0].upper() + b[1:], c) for a, b, c in COUNTIES)

STREET_ROOTS = (
    "Oak", "Sycamore", "Foundry", "Railroad", "Cedar", "Millbrook", "Hawthorne",
    "Quarry", "Canal", "Timberline", "Cypress", "Division", "Commerce", "Industrial",
    "Juniper", "Bayside", "Ridgeview", "Harbor", "Orchard", "Blacksmith", "Chestnut",
    "Fairview", "Ironworks", "Copper", "Meadow", "Frontage", "Telegraph", "Granite",
    "Pier", "Shipyard", "Warehouse", "Terminal", "Linden", "Broad", "Mercantile", "Spruce",
    "Waterworks", "Tannery", "Brickyard", " viaduct",
)
STREET_ROOTS = tuple(s.strip().capitalize() for s in STREET_ROOTS)

STREET_SUFFIXES = ("St", "Ave", "Rd", "Blvd", "Ln", "Pkwy", "Dr", "Way", "Ct", "Hwy")

VEHICLES = (
    ("1998 Ford Ranger XLT", "primer-gray", "pickup"),
    ("2014 Ford Taurus", "dark blue", "sedan"),
    ("2009 Dodge Grand Caravan", "burgundy", "minivan"),
    ("2004 Jeep Grand Cherokee", "tan", "suv"),
    ("2012 Honda Accord", "silver", "sedan"),
    ("2006 GMC Savana 2500", "faded white", "cargo van"),
    ("2011 Chevrolet Impala", "navy blue", "sedan"),
    ("2008 Toyota Tacoma", "maroon", "pickup"),
    ("2015 Nissan Altima", "charcoal", "sedan"),
    ("2003 Buick LeSabre", "champagne", "sedan"),
    ("2016 Chevrolet Silverado 1500", "black", "pickup"),
    ("2007 Subaru Outback", "forest green", "wagon"),
    ("2013 Chrysler 300", "pearl white", "sedan"),
    ("2010 Ford Econoline E-150", "utility gray", "van"),
    ("2005 Mazda Tribute", "slate blue", "suv"),
    ("2017 Hyundai Sonata", "pewter", "sedan"),
    ("2001 Pontiac Grand Prix", "red", "coupe"),
    ("2015 Ram 1500 Tradesman", "white", "pickup"),
    ("2008 Kia Sedona", "gold", "minivan"),
    ("2012 Volkswagen Jetta", "graphite", "sedan"),
)

LEGIT_BUSINESS_PROFILES = (
    ("Redwood Grading & Excavation Inc.", "civil construction", "Caterpillar 320 hydraulic excavator purchase backed by UCC-1 equipment lien & municipal paving contract"),
    ("Harborview Family Dental PLLC", "dental clinic", "CBCT 3D dental imaging scanner wire to verified medical manufacturer + steady insurance/card inflows"),
    ("Bayside Artisan Bakery & Cafe LLC", "bakery & cafe", "weekend cash spike matching documented 3-day waterfront festival & parallel 4.2x Square POS card surge"),
    ("Kestrel Precision Machining Corp.", "CNC manufacturing", "quarterly raw 6061 billet aluminum order matching 36-employee ADP payroll & 3-phase industrial kWh meter"),
    ("Alder Creek Cold Logistics LLC", "refrigerated freight", "fleet diesel cardlock settlements & DOT weigh-station logs matching 18-tractor commercial insurance policy"),
    ("Seneca Valley Vet Hospital PC", "veterinary clinic", "digital X-ray suite escrow wire + corroborated distributor pharmaceutical invoices & W-2 veterinary staff"),
    ("Foundry Street Sheet Metal Inc.", "HVAC fabrication", "galvanized coil steel mill invoice matching union benefit remittance & municipal building permit jobs"),
    ("Cortland Grain & Feed Co-op", "agricultural supply", "autumn harvest bulk cash & check spike matching county grain-elevator scale tickets & seasonal 6-year history"),
)

SHELL_PREFIXES = (
    "Apex Meridian", "Vanguard Pacific", "Solstice Global", "Caspian Trade",
    "Veridian", "Monarch Corridor", "Orchid Logistics", "Boreal Advisory",
    "Silverline", "Aegis Horizon", "Pinnacle Charter", "Kestrel Offshore",
    "Obsidian Peak", "Lumina Bridge", "Atlas Crossings", "Mariner Crest",
    "Cobalt Nexus", "Halcyon Gate", "Valiant Spire", "Equinox Maritime",
)

SHELL_SUFFIXES = (
    "Holdings LLC", "Trading Ltd.", "Advisory Group LLC", "Ventures Corp.",
    "Import-Export LLC", "Capital Partners LLC", "International IBC", "Logistics S.A.",
)

OFFSHORE_JURISDICTIONS = (
    ("Wilmington, DE", "Delaware domestic LLC"),
    ("Cheyenne, WY", "Wyoming series LLC"),
    ("Road Town, Tortola, BVI", "BVI International Business Company"),
    ("Panama City, Panama", "Panamanian S.A."),
    ("George Town, Cayman Islands", "Cayman exempted company"),
    ("Dubai Multi Commodities Centre, UAE", "DMCC free-zone entity"),
)

COMMODITY_BENCHMARKS = (
    ("virgin polypropylene injection pellets", 1.45, "kg", 26500),
    ("grade-A Cavendish green bananas", 0.95, "kg", 22000),
    ("galvanized steel drywall screws", 2.80, "kg", 27000),
    ("baled OCC corrugated cardboard scrap", 0.22, "kg", 24000),
    ("schedule-40 PVC 4-inch drainage pipe", 3.40, "kg", 19000),
    ("unbleached cotton twill fabric rolls", 5.60, "kg", 21000),
    ("secondary aluminum tense scrap", 1.90, "kg", 26000),
    ("bulk yellow dent #2 feed corn", 0.26, "kg", 27500),
    ("ceramic glazed floor tile", 0.88, "kg", 27000),
    ("automotive cast-iron brake rotors", 3.15, "kg", 26500),
)

CASH_FRONT_ARCHETYPES = (
    ("SparkleWave Tunnel Car Wash LLC", "automated car wash", 4140, "municipal water meter billed 9,200 gal total (~230 washes @ 40 gal/wash -> max ~$4,140 gross)"),
    ("Lotus Blossom Nail & Spa LLC", "4-chair nail salon", 11500, "linen & acetone supplier deliveries + 2 part-time W-2 techs cap physical capacity at ~$11,500/mo"),
    ("SpinCycle 24hr Coin Laundry LLC", "self-serve laundromat", 3720, "natural-gas dryer & water meter draw supports ~620 machine loads/mo -> max ~$3,720 gross"),
    ("MetroPark Surface Lot #4 LLC", "40-stall surface parking lot", 9600, "40 stalls x $8 daily max x 30 days physical ceiling = $9,600/mo at 100% 24/7 occupancy"),
    ("QuickVend Beverage Route LLC", "12-machine snack vending route", 5400, "wholesale beverage distributor invoices total $1,950 COGS/mo -> max retail vending gross ~$5,400/mo"),
)


def sample_unique_names(rng: random.Random, count: int) -> list[str]:
    used: set[str] = set()
    out: list[str] = []
    while len(out) < count:
        full = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
        if full not in used:
            used.add(full)
            out.append(full)
    return out


def random_address(rng: random.Random) -> str:
    return f"{rng.randint(104, 9840)} {rng.choice(STREET_ROOTS)} {rng.choice(STREET_SUFFIXES)}"


def random_plate(rng: random.Random) -> str:
    return f"{rng.choice('KLMNPRTVW')}{rng.choice('ABCDEFGHJ')}{rng.choice('XYZKLM')}-{rng.randint(1020, 9989)}"


def pick_distinct(rng: random.Random, seq: Sequence, k: int) -> list:
    return rng.sample(list(seq), k)
