from typing import Any, Callable, Dict, List, Optional
import jax
from JaxSeq.models.base_interface import Inference
import numpy as np
from rouge_score import rouge_scorer
from nltk.translate.bleu_score import sentence_bleu
import string
from tqdm.auto import tqdm
from JaxSeq.utils import BlockingStrategy, Padding, Truncation
from transformers.generation import GenerationConfig

def generate_language(
    inference: Inference, 
    prompts: List[str], 
    references: List[List[str]], 
    prng_key: Optional[jax.random.PRNGKeyArray], 
    bsize: int, 
    generation_batches: Optional[int], 
    blocking_strategy: BlockingStrategy=BlockingStrategy(padding=Padding.LEFT, truncation=Truncation.LEFT, max_length=None), 
    generation_config: Optional[GenerationConfig]=None, 
    input_token_process: Optional[Callable[[List[int]], List[int]]]=None, 
    target_token_process: Optional[Callable[[List[int]], List[int]]]=None, 
    trace: bool=True, 
    verbose: bool=True, 
) -> List[Dict[str, Any]]:
    assert len(prompts) == len(references)

    batches = []
    for i in range(0, len(prompts), bsize):
        batches.append((prompts[i:(i+bsize)], references[i:(i+bsize)],))

    all_generations = []

    for i, (prompts, references) in tqdm(enumerate(batches), disable=not verbose):
        
        # conditionally terminate early
        if generation_batches is not None and i >= generation_batches:
            break

        # get eval logs
        generations = inference.generate_from_str(
            input_strs=prompts, 
            prng_key=prng_key, 
            blocking_strategy=blocking_strategy, 
            generation_config=generation_config, 
            input_token_process=input_token_process, 
            target_token_process=target_token_process, 
            trace=trace, 
        ).output_strs
        
        for prompt, reference, generation in zip(prompts, references, generations):
            all_generations.append({'prompt': prompt, 'reference': reference, 'generation': generation})
    
    return all_generations

# some simple generation metrics

def metric_max_over_references(metric_fn: Callable[[str, str], float], prediction: str, references: List[str]) -> float:
    scores_for_references = []
    for ground_truth in references:
        score = metric_fn(prediction, ground_truth)
        scores_for_references.append(score)
    return max(scores_for_references)

# adapted the flowing from Squad v1.1 evaluation, without removing the articles.
def normalize_answer(s):
    """Lower text and remove punctuation, and extra whitespace."""

    def white_space_fix(text):
        return ' '.join(text.split())

    def remove_punc(text):
        exclude = set(string.punctuation)
        return ''.join(ch for ch in text if ch not in exclude)

    def lower(text):
        return text.lower()

    return white_space_fix(remove_punc(lower(s)))

def rouge1_score(prediction: str, reference: str) -> float:
    scorer = rouge_scorer.RougeScorer(['rouge1'], use_stemmer=True)
    scores = scorer.score(prediction=prediction, target=reference)
    return scores["rouge1"].fmeasure

def rougeL_score(prediction: str, reference: str) -> float:
    scorer = rouge_scorer.RougeScorer(['rougeL'], use_stemmer=True)
    scores = scorer.score(prediction=prediction, target=reference)
    return scores["rougeL"].fmeasure

def exact_match(prediction: str, reference: str) -> float:
    return float(normalize_answer(prediction) == normalize_answer(reference))

def bleu_score(prediction: str, references: List[str]) -> float:
    return sentence_bleu(list(map(lambda x: x.strip().split(), references)), prediction.strip().split())

def diversity(predictions: List[str], n: int) -> float:
    all_n_grams = []
    for prediction in predictions:
        tokens = prediction.lower().strip().split()
        n_grams = list(zip(*[tokens[i:] for i in range(n)]))
        all_n_grams.extend(n_grams)
    if len(all_n_grams) == 0:
        return 1.0
    score = len(set(all_n_grams)) / len(all_n_grams)
    return score

def gram_length(prediction: str) -> float:
    return float(len(prediction.strip().split()))

def compute_metrics(generation_data: List[Dict[str, Any]]):
    prompts, predictions, references = list(zip(*map(lambda x: (x['prompt'], x['generation'], x['reference']), generation_data)))

    rouge1 = np.asarray([metric_max_over_references(rouge1_score, pred, ref) for pred, ref in zip(predictions, references)])
    rougel = np.asarray([metric_max_over_references(rougeL_score, pred, ref) for pred, ref in zip(predictions, references)])
    exact_match_scores = np.asarray([metric_max_over_references(exact_match, pred, ref) for pred, ref in zip(predictions, references)])

    diversity2 = diversity(predictions, 2)
    diversity3 = diversity(predictions, 3)
    
    avg_length_scores = np.asarray(list(map(gram_length, predictions)))

    return {
        "rouge1": rouge1.mean(),
        "rouge1_err": rouge1.std() / np.sqrt(len(rouge1)),
        "rougeL": rougel.mean(),
        "rougeL_err": rougel.std() / np.sqrt(len(rougel)),
        "exact_match": exact_match_scores.mean(), 
        "exact_match_err": exact_match_scores.std() / np.sqrt(len(exact_match_scores)), 
        "diversity2": diversity2, 
        "diversity3": diversity3, 
        "avg_length": avg_length_scores.mean(), 
        "avg_length_err": avg_length_scores.std() / np.sqrt(len(avg_length_scores)), 
    }
