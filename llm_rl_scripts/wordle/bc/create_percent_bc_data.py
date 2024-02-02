import json
from JaxSeq.bucket_manager import open_with_bucket as open
from tqdm.auto import tqdm

if __name__ == "__main__":
    percentage = 0.1

    all_data = []
    with open('', 'r') as f:
        for item in tqdm(f):
            item = json.loads(item)
            all_data.append(item)
    
    all_data_filtered = sorted(all_data, key=lambda x: sum(x['reward']), reverse=True)[:int(len(all_data) * percentage)]

    with open(f'', 'w') as f:
        for item in all_data_filtered:
            f.write(json.dumps(item)+'\n')
