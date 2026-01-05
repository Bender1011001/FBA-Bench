from schema import validate_genome_yaml

with open('genomes/student_agent_gen_0.yaml') as f:
    content = f.read()

try:
    genome = validate_genome_yaml(content)
    print('Validation successful')
    print(genome.model_dump_json(indent=2))
except Exception as e:
    print(f'Validation failed: {e}')
