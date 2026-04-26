import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from caine.core.conversation_state import normalize_human_input, validate_caine_output

inputs = [
    'LIN >> subele el volumen',
    'LIN: subele el volumen',
    'LIN: LIN >> subele el volumen',
    'Usuario: hola',
    'hola'
]
for t in inputs:
    print(f"INPUT [{t}] -> [{normalize_human_input(t)}]")

outputs = [
    'LIN: subiendo el volumen',
    'LIN >> subiendo el volumen',
    'caine: subiendo el volumen',
    'Subiendo el volumen.'
]
for o in outputs:
    print(f"OUTPUT [{o}] -> {validate_caine_output(o)}")
