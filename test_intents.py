import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from caine.intent_parser import IntentParser
parser = IntentParser()

tests = [
    'caine, sube el volumen',
    'mutea el sistema',
    'reproduce la música',
    'busca un video de the digital circus en youtube',
    'pon the amazing digital circus en youtube'
]
for t in tests:
    print(f"[{t}] -> {parser.parse_intent(t)}")
