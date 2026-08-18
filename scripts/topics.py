"""Curated space-topic pool plus the selection logic.

Every topic carries:
  * id        -- stable slug, used for deduplication
  * category  -- helps spread videos across subject areas
  * title     -- base title (the script writer can polish it)
  * hook      -- strong first line for the narration
  * keywords  -- search terms for the NASA Image Library
  * facts     -- a handful of seed facts used when the LLM is unavailable

Selection is weighted-random across categories (so we don't run 10 videos in
a row about planets) and skips recently-used topics. When the whole pool has
been used, the oldest used topics become eligible again -- the state file
still records full history so nothing repeats back-to-back.
"""

from __future__ import annotations

import random
from typing import Any

from scripts import state

CATEGORY_WEIGHTS = {
    "Planets": 3,
    "Moons": 2,
    "The Sun": 2,
    "Deep Space": 3,
    "Stars": 2,
    "Black Holes": 2,
    "Small Bodies": 2,
    "Missions": 3,
    "Telescopes": 2,
    "Cosmology": 2,
    "Phenomena": 2,
    "Astronauts": 1,
}

TOPICS: list[dict[str, Any]] = [
    # --- Planets ----------------------------------------------------------
    {"id": "jupiter-great-red-spot", "category": "Planets", "title": "Jupiter's Great Red Spot Is Shrinking", "hook": "There is a storm on Jupiter bigger than planet Earth that has raged for centuries — and now it's shrinking.", "keywords": "jupiter great red spot", "facts": ["The Great Red Spot is an anticyclone at least 350 years old.", "It once held three Earths across; today it fits barely one.", "Winds inside reach 430 km/h, far faster than any Earth hurricane."]},
    {"id": "saturn-rings", "category": "Planets", "title": "Saturn's Rings Are Disappearing", "hook": "Saturn's magnificent rings are vanishing — and we can finally watch it happen.", "keywords": "saturn rings cassini", "facts": ["Rings are made of 99% water ice chunks from dust to house size.", "Ring rain pulls tons of material into the atmosphere every second.", "In 2025 the rings tilted edge-on to Earth, nearly invisible."]},
    {"id": "mars-rivers", "category": "Planets", "title": "Mars Once Had Rivers Wider Than Earth's", "hook": "Mars was once a planet of raging rivers wider than any on Earth today.", "keywords": "mars river valley", "facts": ["NASA's Perseverance found rounded pebbles moved by flowing water.", "Evidence suggests flowing water for at least 100,000 years.", "Much of Mars' early water escaped to space as the atmosphere thinned."]},
    {"id": "venus-extreme", "category": "Planets", "title": "Venus Is the Hottest Planet, Not Mercury", "hook": "The hottest planet is not the one closest to the Sun.", "keywords": "venus surface clouds", "facts": ["Venus has a runaway greenhouse atmosphere of 96% CO2.", "Surface temperature sits near 465°C — hot enough to melt lead.", "A day on Venus lasts longer than its entire year."]},
    {"id": "uranus-tilt", "category": "Planets", "title": "Uranus Rotates On Its Side", "hook": "Uranus rolls around the Sun like a barrel, knocked over by an ancient crash.", "keywords": "uranus planet", "facts": ["Uranus is tilted 98 degrees, so poles face the Sun directly.", "Each pole gets 42 years of daylight then 42 years of darkness.", "Its magnetic field is lopsided and offset from its center."]},
    {"id": "neptune-winds", "category": "Planets", "title": "Neptune Has the Fastest Winds", "hook": "The most distant planet also has the most violent winds in the solar system.", "keywords": "neptune", "facts": ["Neptune winds hit 2,100 km/h — faster than the speed of sound.", "It radiates 2.6x more heat than it receives from the Sun.", "Voyager 2 is the only spacecraft to ever visit it."]},
    {"id": "mercury-extremes", "category": "Planets", "title": "Mercury Is a Planet of Extreme Swings", "hook": "On Mercury, noon can be 430°C and midnight minus 180°C.", "keywords": "mercury planet monday", "facts": ["Mercury is the smallest planet and closest to the Sun.", "Temperatures swing by over 600°C between day and night.", "It has no atmosphere to hold the heat in."]},
    {"id": "exoplanets-earth", "category": "Planets", "title": "We Found Earth-Like Planets by the Thousands", "hook": "There are more Earth-like planets in our galaxy than stars you can see tonight.", "keywords": "exoplanet earth like kepler", "facts": ["Kepler found thousands of exoplanets around other stars.", "Some orbit in the habitable zone where liquid water can exist.", "The nearest potentially habitable world may be just 4 light-years away."]},
    # --- Moons ------------------------------------------------------------
    {"id": "titan-methane", "category": "Moons", "title": "Titan Has Rivers of Liquid Methane", "hook": "There is a moon where it rains methane and the lakes are made of ethane.", "keywords": "titan moon cassini huygens", "facts": ["Titan is the only moon with a thick atmosphere.", "Its surface has rivers, lakes and seas of liquid methane.", "NASA's Dragonfly rotorcraft is heading there in the 2030s."]},
    {"id": "europa-ocean", "category": "Moons", "title": "Europa's Hidden Ocean May Harbor Life", "hook": "Beneath Europa's icy shell hides a salty ocean with twice the water of Earth.", "keywords": "europa moon ocean jupiter", "facts": ["Europa's ocean may be 100 km deep under an ice crust.", "Tidal flexing heats the interior, keeping water liquid.", "NASA's Europa Clipper will map the moon's ice shell."]},
    {"id": "enceladus-geysers", "category": "Moons", "title": "Enceladus Blasts Water Into Space", "hook": "Saturn's moon Enceladus is spraying its ocean straight into space.", "keywords": "enceladus geysers saturn", "facts": ["Geysers erupt from the south pole through giant fissures.", "Samples show organic molecules and hydrogen — food for life.", "The plume feeds Saturn's vast E-ring."]},
    {"id": "io-volcanoes", "category": "Moons", "title": "Io Is the Most Volcanic World", "hook": "Io is the most volcanically active world in the solar system.", "keywords": "io moon volcanoes jupiter", "facts": ["Io hosts over 400 active volcanoes.", "Jupiter's gravity stretches and heats its interior.", "Volcanic plumes rise hundreds of kilometres above the surface."]},
    {"id": "moon-dark-side", "category": "Moons", "title": "What Hides on the Moon's Far Side", "hook": "For most of human history, half the Moon was completely invisible to us.", "keywords": "moon far side china chang e", "facts": ["The far side is never visible from Earth due to tidal locking.", "China's Chang'e 4 made the first landing there in 2019.", "Its crust is thicker and far more cratered."]},
    {"id": "phobos-doom", "category": "Moons", "title": "Phobos Will Crash Into Mars", "hook": "Mars' moon Phobos is doomed — it's spiralling toward the planet.", "keywords": "phobos deimos mars", "facts": ["Phobos drifts closer to Mars by 1.8 cm every year.", "In ~50 million years it will break apart into a ring.", "It may simply be a captured asteroid."]},
    {"id": "triton-retrograde", "category": "Moons", "title": "Triton Orbits Backwards", "hook": "Neptune's moon Triton is the only large moon that orbits backward.", "keywords": "triton neptune moon", "facts": ["Retrograde orbit means Triton was likely captured, not born there.", "It's colder than any other measured world, near -235°C.", "Geysers of nitrogen erupt through its frozen surface."]},
    # --- The Sun ----------------------------------------------------------
    {"id": "solar-flares", "category": "The Sun", "title": "Solar Storms Can Hit Earth", "hook": "The Sun throws tantrums — and when it does, Earth feels it.", "keywords": "solar flare sun corona", "facts": ["Coronal mass ejections hurl billions of tonnes of plasma.", "Strong storms can knock out power grids and satellites.", "Auroras are literally the sky glowing from charged particles."]},
    {"id": "sun-photosynthesis", "category": "The Sun", "title": "The Sun Is a Giant Nuclear Reactor", "hook": "Every second, the Sun fuses 600 million tonnes of hydrogen.", "keywords": "sun fusion solar", "facts": ["It converts 4 million tonnes of matter into pure energy per second.", "Light from the Sun takes 8 minutes 20 seconds to reach us.", "A single sunspot can swallow Earth whole."]},
    {"id": "parker-solar-probe", "category": "The Sun", "title": "We Touched the Sun", "hook": "A spacecraft flew closer to the Sun than any object we've ever built.", "keywords": "parker solar probe sun", "facts": ["Parker Solar Probe skimmed within 6 million km of the surface.", "It endured temperatures above 1,300°C behind its shield.", "It flies faster than any human-made object in history."]},
    # --- Deep Space -------------------------------------------------------
    {"id": "andromeda-collision", "category": "Deep Space", "title": "The Milky Way Will Collide With Andromeda", "hook": "Our galaxy is on a collision course — Andromeda is coming.", "keywords": "andromeda milky way galaxy", "facts": ["Andromeda approaches at about 110 km per second.", "The merger begins in roughly 4 billion years.", "Star collisions are unlikely, but the night sky will transform."]},
    {"id": "pulsars", "category": "Deep Space", "title": "Pulsars Are Cosmic Lighthouses", "hook": "Dead stars spin faster than a kitchen blender and beam energy like lighthouses.", "keywords": "pulsar neutron star", "facts": ["Pulsars are neutron stars spinning up to hundreds of times a second.", "Some keep time better than atomic clocks.", "Their beams sweep across Earth with every rotation."]},
    {"id": "neutron-stars", "category": "Deep Space", "title": "A Sugar Cube of Neutron Star Weighs a Mountain", "hook": "A neutron star is so dense a sugar cube of it would outweigh every human alive.", "keywords": "neutron star", "facts": ["A teaspoon weighs about a billion tonnes.", "They're the crushed cores of exploded massive stars.", "Just 20 km wide, they pack more mass than the Sun."]},
    {"id": "gamma-ray-bursts", "category": "Deep Space", "title": "Gamma-Ray Bursts Are the Universe's Brightest Flashes", "hook": "In a few seconds, a gamma-ray burst releases more energy than the Sun will in its lifetime.", "keywords": "gamma ray burst", "facts": ["These are the most energetic events in the universe.", "A nearby one could strip Earth's ozone layer.", "They mark the collapse of giant stars or merging neutron stars."]},
    {"id": "magnetars", "category": "Deep Space", "title": "Magnetars Are the Universe's Strongest Magnets", "hook": "A magnetar's magnetic field could wipe every credit card on Earth from half the Moon's distance.", "keywords": "magnetar neutron star", "facts": ["Their fields are a quadrillion times stronger than Earth's.", "They're neutron stars with twisted magnetic fields.", "Their starquakes can unleash giant flares seen across galaxies."]},
    {"id": "cosmic-web", "category": "Deep Space", "title": "The Universe Is a Web of Galaxies", "hook": "Galaxies aren't scattered randomly — they line up along a gigantic cosmic web.", "keywords": "cosmic web galaxies large scale structure", "facts": ["Galaxy clusters form filaments spanning hundreds of millions of light-years.", "These threads are connected by dark matter.", "The largest structures are called superclusters and walls."]},
    {"id": "voids", "category": "Deep Space", "title": "The Boötes Void Is Scarily Empty", "hook": "Somewhere in the sky, a bubble of nothing spans 330 million light-years.", "keywords": "bootes void cosmic void", "facts": ["The Boötes Void contains almost no galaxies at all.", "If the Milky Way were at its center, we wouldn't have seen other galaxies until the 1960s.", "Finding only 60 galaxies in a region that should hold thousands."]},
    # --- Stars ------------------------------------------------------------
    {"id": "betelgeuse", "category": "Stars", "title": "Betelgeuse Is Ready to Explode", "hook": "A giant star in Orion is one bad day away from going supernova.", "keywords": "betelgeuse orion star", "facts": ["Betelgeuse is 700 times the Sun's radius.", "It dimmed dramatically in 2019, thrilling astronomers.", "When it blows, it'll outshine the Moon for weeks."]},
    {"id": "sirius", "category": "Stars", "title": "Why Sirius Is the Brightest Star", "hook": "The brightest star in our night sky is actually part of a duo.", "keywords": "sirius dog star", "facts": ["Sirius is 25x more luminous than the Sun and twice as massive.", "Its faint companion, Sirius B, is a white dwarf.", "Ancient Egyptians timed the Nile flood by its rising."]},
    {"id": "red-giants", "category": "Stars", "title": "What Happens When a Star Swells Into a Red Giant", "hook": "In about 5 billion years, the Sun will swell to swallow Mercury and Venus.", "keywords": "red giant sun evolution", "facts": ["Red giants form when stars exhaust their hydrogen fuel.", "They can swell to hundreds of times their original size.", "The Sun's red giant phase will boil Earth's oceans."]},
    {"id": "black-dwarfs", "category": "Stars", "title": "The Universe Is Too Young for Black Dwarfs", "hook": "There's a kind of star that hasn't existed yet — because the universe isn't old enough.", "keywords": "white dwarf star cooling", "facts": ["White dwarfs slowly cool over trillions of years.", "A black dwarf is a fully cooled, invisible stellar corpse.", "The universe at 13.8 billion years is far too young to have one."]},
    {"id": "twin-stars", "category": "Stars", "title": "Most Stars Come in Pairs", "hook": "Our Sun is single — but most stars in the galaxy have a partner.", "keywords": "binary stars", "facts": ["Over half of Sun-like stars live in binary systems.", "Binary stars let us directly measure stellar masses.", "Some orbit so closely they share their outer layers."]},
    # --- Black holes ------------------------------------------------------
    {"id": "first-black-hole-image", "category": "Black Holes", "title": "The First Picture of a Black Hole", "hook": "In 2019, humanity photographed a black hole for the very first time.", "keywords": "black hole event horizon telescope M87", "facts": ["The image shows the shadow of a black hole in M87.", "It was captured by a planet-sized network of telescopes.", "The glowing ring is superheated gas falling inward."]},
    {"id": "sagittarius-a-star", "category": "Black Holes", "title": "A Black Hole Sits at the Center of Our Galaxy", "hook": "Every star in the Milky Way orbits a monster at its heart.", "keywords": "sagittarius a star black hole", "facts": ["Sagittarius A* weighs 4 million Suns.", "It's 26,000 light-years away, quiet for a supermassive black hole.", "We imaged its glowing ring in 2022."]},
    {"id": "spaghettification", "category": "Black Holes", "title": "Black Holes Spaghettify Everything", "hook": "Fall into a black hole and gravity will stretch you into a noodle.", "keywords": "black hole spaghettification tidal forces", "facts": ["Tidal forces stretch objects into thin strands — literally spaghettification.", "Gravity differs so much across your body it pulls you apart.", "The effect is named after the process of making spaghetti."]},
    {"id": "primordial-black-holes", "category": "Black Holes", "title": "Tiny Black Holes May Be Everywhere", "hook": "The universe may be full of microscopic black holes left over from the Big Bang.", "keywords": "primordial black hole dark matter", "facts": ["Primordial black holes could form from dense regions in the early universe.", "Some scientists propose they make up dark matter.", "A black hole the size of an atom could weigh like a mountain."]},
    # --- Small bodies -----------------------------------------------------
    {"id": "comet-life-origin", "category": "Small Bodies", "title": "Comets May Have Seeded Life on Earth", "hook": "Life's ingredients may have arrived on Earth inside frozen time capsules.", "keywords": "comet rosetta water organic", "facts": ["Comets are dirty snowballs of ice, rock and organic molecules.", "Rosetta's comet carried the building blocks of life.", "Impacts likely delivered water and organics to early Earth."]},
    {"id": "osiris-rex", "category": "Small Bodies", "title": "We Brought Home a Piece of an Asteroid", "hook": "NASA caught a piece of an asteroid and flew it back to Earth.", "keywords": "osiris rex bennu asteroid sample", "facts": ["OSIRIS-REx grabbed samples from asteroid Bennu in 2020.", "The sample landed in Utah in 2023.", "Bennu may hold clues to the origin of the solar system."]},
    {"id": "oumuamua", "category": "Small Bodies", "title": "Oumuamua Was an Alien Visitor", "hook": "The first object from another star system sailed through our solar system.", "keywords": "oumuamua interstellar object", "facts": ["'Oumuamua passed through in 2017, the first interstellar visitor.", "Its shape and motion stumped scientists.", "It was likely a pancake-shaped rock, not an alien probe."]},
    {"id": "kuiper-belt", "category": "Small Bodies", "title": "The Kuiper Belt Holds Trillions of Comets", "hook": "Beyond Neptune lurks a frozen ring of a trillion icy worlds.", "keywords": "kuiper belt pluto", "facts": ["The Kuiper Belt spans 30 to 55 AU from the Sun.", "Pluto is its most famous resident.", "Short-period comets come from this icy region."]},
    {"id": "oumuamua-2-borisov", "category": "Small Bodies", "title": "We Saw a Comet From Another Star", "hook": "Just two years after 'Oumuamua, a second interstellar traveler appeared.", "keywords": "borisov comet interstellar", "facts": ["Comet Borisov was the first confirmed interstellar comet.", "It showed the same dust features as solar-system comets.", "It came from the direction of the constellation Cassiopeia."]},
    {"id": "davida", "category": "Small Bodies", "title": "Some Asteroids Have Their Own Moons", "hook": "Some asteroids are so big they hold tiny moons in orbit.", "keywords": "asteroid moon binary", "facts": ["About 15% of near-Earth asteroids are binary systems.", "Dinkinesh was found to have a contact-binary moon in 2023.", "These systems help us measure asteroid masses directly."]},
    # --- Missions ---------------------------------------------------------
    {"id": "jwst-mission", "category": "Missions", "title": "James Webb Is Rewriting Astronomy", "hook": "A telescope 1.5 million km away is showing us the universe's first light.", "keywords": "james webb space telescope", "facts": ["JWST launched in December 2021 and unfolded in space.", "It sees infrared light, piercing cosmic dust clouds.", "It found galaxies that may be older than expected."]},
    {"id": "perseverance-mars", "category": "Missions", "title": "Perseverance Is Hunting for Martian Life", "hook": "A car-sized rover is drilling into Mars looking for ancient microbes.", "keywords": "perseverance rover mars jezero", "facts": ["Perseverance landed in Jezero Crater, an ancient lakebed, in 2021.", "It stashes rock cores for a future return to Earth.", "Its helicopter Ingenuity made the first flight on another world."]},
    {"id": "voyager-golden-record", "category": "Missions", "title": "Voyager Is Carrying Earth's Greatest Hits", "hook": "Two probes are carrying a golden record of Earth into deep space.", "keywords": "voyager golden record interstellar", "facts": ["Voyager 1 and 2 launched in 1977 and still phone home.", "The Golden Record carries sounds and images of Earth.", "Voyager 1 is the most distant human-made object ever."]},
    {"id": "artemis-moon", "category": "Missions", "title": "Humans Are Going Back to the Moon", "hook": "For the first time in half a century, boots are heading back to the Moon.", "keywords": "artemis moon landing NASA", "facts": ["Artemis aims to land humans near the lunar south pole.", "The first crewed lunar landing is targeted for the 2020s decade.", "It will build a permanent lunar presence."]},
    {"id": "juno-jupiter", "category": "Missions", "title": "Juno Is Diving Through Jupiter's Radiation", "hook": "A spacecraft is surviving the most hostile radiation in the solar system.", "keywords": "juno spacecraft jupiter", "facts": ["Juno orbits Jupiter pole-to-pole, skimming the cloud tops.", "It operates in radiation that would destroy most electronics.", "It revealed cyclones arranged in a hexagon at Jupiter's poles."]},
    {"id": "dart-asteroid", "category": "Missions", "title": "We Slammed a Spacecraft Into an Asteroid", "hook": "For the first time, humanity moved a celestial object on purpose.", "keywords": "DART asteroid deflection", "facts": ["DART crashed into Dimorphos in September 2022.", "It shortened the moon's orbit by 33 minutes.", "It proved planetary defense is possible."]},
    {"id": "chandra", "category": "Missions", "title": "Chandra Sees the X-Ray Universe", "hook": "There's a universe invisible to your eyes — and Chandra photographs it.", "keywords": "chandra x-ray observatory", "facts": ["Chandra captures X-rays from the most violent cosmic events.", "It studies black holes, supernovae and hot gas.", "Its images reveal the shadows of black holes directly."]},
    # --- Telescopes -------------------------------------------------------
    {"id": "hubble-observations", "category": "Telescopes", "title": "Hubble Changed Everything", "hook": "One telescope taught us the universe is 13.8 billion years old.", "keywords": "hubble space telescope deep field", "facts": ["Hubble launched in 1990 and gets a tune-up almost every decade.", "Its Deep Field revealed thousands of galaxies in a speck of sky.", "It helped measure the accelerating expansion of the universe."]},
    {"id": "webb-vs-hubble", "category": "Telescopes", "title": "How Webb Sees Deeper Than Hubble", "hook": "Hubble sees in visible light. Webb sees what Hubble can't.", "keywords": "webb telescope infrared hubble comparison", "facts": ["Webb looks in infrared, letting it see through dust.", "It can spot the first galaxies forming after the Big Bang.", "Its mirror is 6.5 meters wide — the largest ever flown."]},
    {"id": "radio-telescopes", "category": "Telescopes", "title": "Radio Telescopes Listen to the Universe", "hook": "The universe is screaming in radio waves — we just need the right ears.", "keywords": "radio telescope arecibo very large array", "facts": ["Radio telescopes can observe through clouds and daylight.", "They helped discover cosmic microwave background radiation.", "Pulsars were first found as ticking radio sources."]},
    {"id": "fermi-telescope", "category": "Telescopes", "title": "Fermi Sees the Gamma-Ray Sky", "hook": "Point a gamma-ray telescope anywhere and you find monsters.", "keywords": "fermi gamma ray telescope", "facts": ["Fermi maps the sky's most extreme high-energy events.", "It catches flashes from colliding neutron stars.", "It detected gamma-ray bursts from billions of light-years away."]},
    # --- Cosmology --------------------------------------------------------
    {"id": "big-bang-basics", "category": "Cosmology", "title": "The Big Bang Wasn't an Explosion", "hook": "The Big Bang wasn't an explosion in space — it was an explosion of space.", "keywords": "big bang universe origin", "facts": ["Space itself has been expanding for 13.8 billion years.", "The universe began from an unimaginably hot, dense point.", "We still see its afterglow as microwave radiation."]},
    {"id": "dark-matter", "category": "Cosmology", "title": "Dark Matter Is Everywhere", "hook": "85% of all matter in the universe is invisible to us.", "keywords": "dark matter galaxies", "facts": ["Dark matter doesn't emit or absorb light.", "Galaxies spin too fast to hold together without it.", "It's mapped through its gravity bending light."]},
    {"id": "dark-energy", "category": "Cosmology", "title": "Dark Energy Is Tearing the Universe Apart", "hook": "Something is pushing the universe apart faster and faster.", "keywords": "dark energy universe expansion", "facts": ["Dark energy makes up 68% of the universe.", "It drives the accelerating expansion of space.", "We discovered it in 1998 — and still don't understand it."]},
    {"id": "cosmic-microwave-background", "category": "Cosmology", "title": "We Can See the Echo of the Big Bang", "hook": "Point a telescope anywhere in space and you'll see the afterglow of creation.", "keywords": "cosmic microwave background", "facts": ["The CMB is light from 380,000 years after the Big Bang.", "It's cooled to just 2.7 degrees above absolute zero.", "Tiny temperature ripples seeded all galaxies."]},
    {"id": "multiverse", "category": "Cosmology", "title": "Could We Live in a Multiverse?", "hook": "Our universe might be just one bubble in an infinite froth of others.", "keywords": "multiverse universe theory", "facts": ["Eternal inflation could produce endless universes.", "Some theories suggest different physical laws per universe.", "It remains one of science's most debated ideas."]},
    {"id": "heat-death", "category": "Cosmology", "title": "The Universe Will Eventually Go Dark", "hook": "One day, the last star will flicker out and the universe will go quiet.", "keywords": "heat death universe end", "facts": ["Stars will exhaust their fuel over trillions of years.", "Black holes will slowly evaporate via Hawking radiation.", "Eventually only cold, dark emptiness may remain."]},
    # --- Phenomena --------------------------------------------------------
    {"id": "auroras", "category": "Phenomena", "title": "What Causes the Northern Lights", "hook": "The sky glows green because the Sun is screaming at Earth.", "keywords": "aurora northern lights", "facts": ["Solar wind particles slam into Earth's magnetic field.", "They collide with oxygen and nitrogen to paint the sky.", "Auroras also happen on Jupiter, Saturn and even Mars."]},
    {"id": "eclipses", "category": "Phenomena", "title": "Why Total Solar Eclipses Are a Cosmic Coincidence", "hook": "The Moon is exactly the right size and distance to perfectly cover the Sun.", "keywords": "solar eclipse total", "facts": ["The Moon is 400x smaller than the Sun but 400x closer.", "That balance makes total eclipses possible.", "The Moon drifts away 3.8 cm a year — one day, no more total eclipses."]},
    {"id": "supernova", "category": "Phenomena", "title": "A Supernova Can Outshine a Galaxy", "hook": "For a few weeks, a single dying star can outshine its entire galaxy.", "keywords": "supernova explosion", "facts": ["Supernovae forge heavy elements like gold and uranium.", "One type helped us discover dark energy.", "A star goes supernova somewhere in the observable universe every second."]},
    {"id": "meteor-shower", "category": "Phenomena", "title": "Meteor Showers Are Comet Graveyards", "hook": "Every shooting star is a tiny piece of a comet burning up.", "keywords": "meteor shower perseids", "facts": ["Meteor showers happen when Earth crosses cometary debris.", "The Perseids peak every August with up to 100 meteors an hour.", "Most meteors are smaller than a grain of sand."]},
    {"id": "planet-parade", "category": "Phenomena", "title": "When the Planets Line Up", "hook": "Every so often, the planets march across the sky in a line.", "keywords": "planet alignment planets", "facts": ["Planets line up along the ecliptic plane of the solar system.", "They're rarely exactly aligned but often appear close together.", "A full alignment of all eight planets is astronomically rare."]},
    {"id": "blue-moon", "category": "Phenomena", "title": "Why We Say Once in a Blue Moon", "hook": "A Blue Moon isn't blue — it's just rare.", "keywords": "blue moon lunar", "facts": ["A Blue Moon is the second full moon in one calendar month.", "It happens roughly every 2.7 years.", "Volcanic dust can genuinely turn the Moon blue."]},
    # --- Astronauts -------------------------------------------------------
    {"id": "starliner-space", "category": "Astronauts", "title": "What Happens to the Body in Space", "hook": "Astronauts grow taller in space and lose bone density every single day.", "keywords": "astronaut microgravity body effects", "facts": ["Bones lose up to 1-2% density per month in orbit.", "Hearts shrink slightly and muscles weaken without gravity.", "Astronauts grow a few centimeters taller from spine stretching."]},
    {"id": "iss-life", "category": "Astronauts", "title": "Life on the Space Station", "hook": "A football-field-sized lab orbits Earth every 90 minutes with people inside.", "keywords": "international space station astronauts", "facts": ["Astronauts see 16 sunrises and sunsets every day.", "They sleep in vertical pods strapped to the wall.", "The ISS has been continuously inhabited since 2000."]},
    {"id": "space-walk", "category": "Astronauts", "title": "Spacewalks Are the Most Dangerous Job in History", "hook": "Floating outside a spacecraft is one of the riskiest things a human can do.", "keywords": "spacewalk astronaut eva", "facts": ["Astronauts suit up for hours before a single spacewalk.", "A tear in the suit means near-instant decompression.", "Over 270 spacewalks built and maintain the ISS."]},
]

# A few topical evergreen entries appended so recent events stay fresh.
EXTRA_TOPICS: list[dict[str, Any]] = []


def all_topics() -> list[dict[str, Any]]:
    return TOPICS + EXTRA_TOPICS


def _weighted_category_priority(used_this_cycle: dict[str, int]) -> list[str]:
    """Order categories so less-used categories are preferred."""
    cats = list(CATEGORY_WEIGHTS.keys())
    random.shuffle(cats)
    cats.sort(key=lambda c: (used_this_cycle.get(c, 0), -CATEGORY_WEIGHTS[c]))
    return cats


def pick_topic(state_path: str, exclude_ids: set[str] | None = None) -> dict[str, Any] | None:
    """Pick a topic, preferring unused ones and spreading across categories."""
    exclude_ids = exclude_ids or set()
    data = state.load_state(state_path)
    used = set(data["used_topic_ids"])
    recent = set(data["recent_ids"])
    topics = all_topics()

    def _pick(candidates: list[dict[str, Any]], block_recent: bool) -> dict[str, Any] | None:
        if not candidates:
            return None
        counts: dict[str, int] = {}
        for t in candidates:
            counts[t["category"]] = counts.get(t["category"], 0) + 1
        for cat in _weighted_category_priority(counts):
            pool = [t for t in candidates if t["category"] == cat]
            if not pool:
                continue
            pool = [t for t in pool if t["id"] not in recent] if block_recent else pool
            if not pool:
                pool = [t for t in candidates if t["category"] == cat]
            if not pool:
                continue
            return random.choice(pool)
        return None

    fresh = [t for t in topics if t["id"] not in used and t["id"] not in exclude_ids]
    candidate = _pick(fresh, block_recent=True)
    if candidate:
        return candidate

    # Pool exhausted (or nearly): fall back to the full pool, still avoiding recent.
    all_but_excluded = [t for t in topics if t["id"] not in exclude_ids]
    candidate = _pick(all_but_excluded, block_recent=True)
    if candidate:
        return candidate

    # Last resort: allow recent repeats but never the exact last topic.
    last_used = list(recent)[-1:] if recent else []
    candidate = _pick([t for t in topics if t["id"] not in exclude_ids and t["id"] not in last_used], block_recent=False)
    return candidate
