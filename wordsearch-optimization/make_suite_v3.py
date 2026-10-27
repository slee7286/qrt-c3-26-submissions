"""Reproducible synthetic and curated stress cases; seed fixed at 710677."""
import json
import random
from pathlib import Path

SEED = 710677
rng = random.Random(SEED)
CATEGORIES = {
'dinosaurs': '''ALBERTOSAURUS ARCHAEOPTERYX TYRANNOSAURUS TRICERATOPS STEGOSAURUS BRACHIOSAURUS APATOSAURUS ALLOSAURUS DIPLODOCUS VELOCIRAPTOR ANKYLOSAURUS IGUANODON SPINOSAURUS PARASAUROLOPHUS GALLIMIMUS COMPSOGNATHUS PACHYCEPHALOSAURUS DEINONYCHUS CARNOTAURUS DILOPHOSAURUS'''.split(),
'elements': '''HYDROGEN HELIUM LITHIUM BERYLLIUM BORON CARBON NITROGEN OXYGEN FLUORINE NEON SODIUM MAGNESIUM ALUMINUM SILICON PHOSPHORUS SULFUR CHLORINE ARGON POTASSIUM CALCIUM TITANIUM CHROMIUM MANGANESE IRON COBALT NICKEL COPPER ZINC BROMINE SILVER GOLD MERCURY LEAD URANIUM'''.split(),
'cities': '''LONDON PARIS BERLIN MADRID LISBON ROME ATHENS VIENNA PRAGUE WARSAW HELSINKI OSLO STOCKHOLM TOKYO SEOUL BEIJING SHANGHAI MUMBAI DELHI CAIRO NAIROBI SYDNEY MELBOURNE TORONTO CHICAGO BOSTON SEATTLE MIAMI DALLAS'''.split(),
'countries': '''CANADA BRAZIL ARGENTINA CHILE PERU MEXICO FRANCE GERMANY ITALY SPAIN PORTUGAL POLAND SWEDEN NORWAY FINLAND JAPAN CHINA INDIA NEPAL EGYPT KENYA MOROCCO AUSTRALIA INDONESIA MALAYSIA VIETNAM THAILAND GREECE IRELAND'''.split(),
'figures': '''NEWTON EINSTEIN DARWIN GALILEO CURIE TESLA FARADAY EULER GAUSS TURING LOVELACE PASTEUR MENDELEEV KEPLER COPERNICUS ARISTOTLE PLATO SOCRATES HIPPOCRATES PYTHAGORAS'''.split(),
'animals': '''ELEPHANT GIRAFFE ZEBRA LION TIGER PANTHER CHEETAH LEOPARD RHINOCEROS HIPPOPOTAMUS KANGAROO KOALA PLATYPUS DOLPHIN WHALE SHARK OCTOPUS PENGUIN FALCON EAGLE'''.split(),
'science': '''PHOTOSYNTHESIS MITOCHONDRIA CHROMOSOME QUANTUM GRAVITY ELECTRON PROTON NEUTRON MOLECULE GENOME PHOTON ISOTOPE POLYMER CATALYST GALAXY NEBULA ORBITAL PROTEIN ENZYME GEOLOGY'''.split(),
}


def synthetic(base, count, alphabet='ACDEGHILMNOPRSTUY'):
    """Preserve curated examples; extend with explicitly synthetic words."""
    out = list(dict.fromkeys(base))
    while len(out) < count:
        candidate = ''.join(rng.choice(alphabet) for _ in range(rng.randint(5, 10)))
        if candidate not in out:
            out.append(candidate)
    return out[:count]


def make():
    cases = []
    for category, count in [('dinosaurs',70), ('elements',100), ('cities',80), ('countries',125), ('figures',70), ('animals',100), ('science',150)]:
        base = CATEGORIES[category]
        req = synthetic(base,count)
        # 'ZZ' cannot occur in these requirements and Z is absent from it.
        forbidden = ['ZZ'] if category in ('dinosaurs','countries','animals','science') else []
        cases.append(dict(name=category+'-curated-plus-synthetic-'+str(count), required=req, forbidden=forbidden, curated_count=len(base), synthetic_count=count-len(base), seed=SEED))
    for count in (50, 70, 100, 125, 150):
        for style, alphabet in [('random26','ABCDEFGHIJKLMNOPQRSTUVWXYZ'), ('dense5','ACEST')]:
            req = synthetic([],count,alphabet)
            forb = ['ZZ'] if style == 'dense5' else []
            cases.append(dict(name=style+'-'+str(count),required=req,forbidden=forb,curated_count=0,synthetic_count=count,seed=SEED))
    for count in (70, 125):
        req = list(dict.fromkeys(rng.choice(['BIO','THERMO','GEO','MICRO','NEURO'])+rng.choice(['LOGICAL','DYNAMIC','SCOPE','GRAPHIC','METER','PHOBIA'])+''.join(rng.choice('ACEST') for _ in range(2)) for _ in range(count*3)))[:count]
        cases.append(dict(name='shared-morphology-'+str(count),required=req,forbidden=['ZZ'],curated_count=0,synthetic_count=len(req),seed=SEED))
    # Exact 677-letter stress fixture used in the 140x140 regression test.
    from test_iteration_v3 import fallback_case
    req, forb = fallback_case()
    cases.append(dict(name='forced-fallback-677-synthetic',required=req,forbidden=forb,curated_count=0,synthetic_count=len(req),seed=SEED))
    Path('suite_v3.json').write_text(json.dumps(cases,indent=2))
    return cases

if __name__ == '__main__':
    for c in make():
        print(c['name'],len(c['required']),sum(map(len,c['required'])),len(c['forbidden']))
